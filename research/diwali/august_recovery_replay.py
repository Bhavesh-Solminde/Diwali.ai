"""Bounded first-day recovery replay with independently received snapshot provenance."""
import argparse
import json
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from ..market_data.event_replay import DTYPE as BOOK, compile_events
from ..market_data.event_shards import store_events
from ..market_data.validate_archive import decoded, file_hash, raw_path, save

HOUR = 3600*10**9


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--attempt', default='independent-snapshot-buffered-replay')
    args = parser.parse_args()
    root = args.root
    sample = json.loads((root/'fixed-sample.json').read_text())
    first = [r for r in sample['strata'] if r['stratum'].startswith('2026-08-01') and r['cutoff_ns']]
    if not first:
        raise ValueError('No first-day sample')
    feed = root/'tardis-aug01-minute0.txt'
    snapshots = []
    for line in feed.open():
        stamp, value = line.split(' ',1)
        event = json.loads(value)
        if event['stream']=='btcusdt@depthSnapshot':
            snapshots.append((int(pd.Timestamp(stamp).value),event['data']))
    if len(snapshots)!=1:
        raise ValueError('Expected exactly the downloaded first-minute snapshot')
    at, snapshot = snapshots[0]
    if at < max(snapshot['E'], snapshot['T'])*10**6:
        raise ValueError('Independent snapshot has impossible receipt timing')
    archive = Path('data/btc-perp/cryptohftdata-monthly')
    records = {r['remote_file']:r for r in json.loads((archive/'manifest.json').read_text())}
    out = root/args.attempt
    out.mkdir(exist_ok=False)
    build = out/'compiler'
    build.mkdir()
    binary = compile_events(build)
    save(out/'protocol.json', {'snapshot_receipt_ns':at,'snapshot_sequence':snapshot['lastUpdateId'],
                              'snapshot_sha256':file_hash(feed),'sample_sha256':file_hash(root/'fixed-sample.json'),
                              'policy':'Inject the independently received snapshot. Apply original buffered deltas with final update ID >= snapshot ID, releasing buffered transitions at max(original receipt, independent snapshot receipt). Original clocks remain in the source archive. Existing snapshot-bound, sequence and quality rules apply.'})
    process = subprocess.Popen([str(binary)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,text=True)
    hour0 = at//HOUR*HOUR
    stop = max(r['cutoff_ns'] for r in first)//HOUR*HOUR
    reports=[]
    try:
        for hour in range(int((stop-hour0)//HOUR)+1):
            remote=f'binance_futures/2026-08-01/{hour:02d}/BTCUSDT_orderbook.parquet'
            record=records[remote]
            path=raw_path(archive,record)
            if file_hash(path)!=record['sha256']:
                raise ValueError('Original raw bytes changed')
            with decoded(path,out) as raw:
                prepared=raw
                if hour==0:
                    prepared=out/'seeded-hour00.parquet'
                    reader=pq.ParquetFile(raw)
                    names=reader.schema_arrow.names
                    rows=[]
                    for side,key in [('bid','bids'),('ask','asks')]:
                        for price,quantity in snapshot[key]:
                            rows.append({**{n:None for n in names},'received_time':at,
                                'event_time':snapshot['E'],'transaction_time':snapshot['T'],
                                'symbol':'BTCUSDT','event_type':'snapshot','last_update_id':snapshot['lastUpdateId'],
                                'side':side,'price':price,'quantity':quantity})
                    with pq.ParquetWriter(prepared,reader.schema_arrow,compression='zstd') as writer:
                        writer.write_table(pa.Table.from_pylist(rows,schema=reader.schema_arrow))
                        for batch in reader.iter_batches(batch_size=65536):
                            is_update=pc.equal(batch.column(names.index('event_type')),'update')
                            native_after=pc.greater_equal(batch.column(names.index('final_update_id')),snapshot['lastUpdateId'])
                            other_after=pc.greater_equal(batch.column(names.index('received_time')),at)
                            kept=pc.filter(batch,pc.or_kleene(pc.and_kleene(is_update,native_after),
                                                            pc.and_kleene(pc.invert(is_update),other_after)))
                            if len(kept):
                                ix=names.index('received_time')
                                released=pc.max_element_wise(kept.column(ix),pa.scalar(at,pa.int64()))
                                kept=kept.set_column(ix,reader.schema_arrow.field(ix),released)
                            if len(kept):writer.write_batch(kept)
                seconds=out/f'{hour:02d}-seconds.bin'
                events=out/f'{hour:02d}-events.bin'
                process.stdin.write(f'{hour0+hour*HOUR}\t{prepared.resolve()}\t{seconds.resolve()}\t{events.resolve()}\n')
                process.stdin.flush()
                line=process.stdout.readline()
                if not line:
                    raise ValueError('Independent seeded replay failed')
                audit=json.loads(line)
                save(out/f'{hour:02d}-audit.json',audit)
                values=np.fromfile(events,dtype=BOOK)
                keep=(values['receipt_ns']>=hour0+hour*HOUR-120*10**9)
                # Retain only fixed-sample windows and their preceding-hour tail.
                sample_at=[r['cutoff_ns'] for r in first]
                keep=np.zeros(len(values),bool)
                for cutoff in sample_at:
                    keep|=(values['receipt_ns']>=cutoff-120*10**9)&(values['receipt_ns']<cutoff)
                store_events(out/f'{hour:02d}-sample-events.parquet',values[keep])
                reports.append({'hour':hour,'counts':audit['counts'],'retained_window_rows':int(keep.sum()),
                                'source_sha256':record['sha256']})
                del values
                events.unlink()
                seconds.unlink()
                if prepared!=raw:prepared.unlink()
                save(out/'progress.json',{'hours_done':hour+1,'hours_total':int((stop-hour0)//HOUR)+1})
                print('Independent seed replay hour',hour,'complete',flush=True)
    finally:
        process.stdin.close()
        process.wait(timeout=30)
    save(out/'report.json', {'state':'complete','hours':reports,'snapshot_receipt_ns':at,
                            'snapshot_sequence':snapshot['lastUpdateId']})
    print('Bounded replay complete',flush=True)


if __name__=='__main__':
    main()
