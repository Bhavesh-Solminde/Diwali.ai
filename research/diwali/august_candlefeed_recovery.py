"""Recover the fixed August 1 sample with independent native-ID snapshots.

No model fitting or changes to frozen replay sources. Raw sources stay private.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import subprocess

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from ..market_data.candle_tape import CandleTape, MINUTE, SECOND, SCALE, released
from ..market_data.event_join_cohort import hour_ns, join_selection, source_release, HOUR
from ..market_data.event_month_cohort import clock_exclusions, intersects
from ..market_data.event_replay import DTYPE as BOOK, compile_events, validate_events
from ..market_data.event_shards import read_events, store_events
from ..market_data.trade_events import DTYPE as TRADE
from ..market_data.validate_archive import decoded, file_hash, raw_path, save


def exact_text(value):
    value = Decimal(value)
    if not value.is_finite() or value < 0 or value*SCALE != (value*SCALE).to_integral_value():
        raise ValueError('Snapshot level cannot be represented exactly by the existing replay')
    return format(value.normalize(), 'f')


def select_anchor(table, window_start):
    # Never choose an anchor using target prices, nor a snapshot arriving during the input window.
    eligible = table.filter(pc.and_(pc.less(table['recv_time'], window_start),
                                    pc.is_in(table['anchor_class'], value_set=pa.array(['clean', 'straddle']))))
    if not len(eligible):
        raise ValueError('No independently received snapshot before input window')
    at = pc.max(eligible['recv_time']).as_py()
    anchor = eligible.filter(pc.equal(eligible['recv_time'], at))
    if len(pc.unique(anchor['final_update_id'])) != 1 or len(pc.unique(anchor['node'])) != 1:
        raise ValueError('Ambiguous snapshot identity')
    if not pc.all(pc.equal(anchor['symbol'], 'BTCUSDT')).as_py() or not pc.all(anchor['is_snapshot']).as_py():
        raise ValueError('Wrong contract or event type')
    if at < pc.max(anchor['event_time']).as_py()*10**6:
        raise ValueError('Snapshot receipt precedes exchange time')
    sides = anchor['side'].to_pylist()
    if sides.count('bid') < 20 or sides.count('ask') < 20 or len(sides) != sides.count('bid')+sides.count('ask'):
        raise ValueError('Snapshot lacks required sides/depth')
    return anchor


def replay_origin(anchor, cutoff, original, records, output, binary):
    output.mkdir()
    at = pc.max(anchor['recv_time']).as_py()
    seq = anchor['final_update_id'][0].as_py()
    first = at//HOUR*HOUR
    last = cutoff//HOUR*HOUR
    all_events = []
    audits = []
    sources = {}
    process = subprocess.Popen([str(binary)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True)
    try:
        for current in range(first, last+1, HOUR):
            stamp = datetime.fromtimestamp(current/SECOND, timezone.utc)
            remote = f'binance_futures/{stamp:%Y-%m-%d}/{stamp:%H}/BTCUSDT_orderbook.parquet'
            record = records[remote]
            path = raw_path(original, record)
            if file_hash(path) != record['sha256']:
                raise ValueError('Changed original book file')
            sources[remote] = record['sha256']
            prepared = output/f'{stamp:%H}-seeded.parquet'
            with decoded(path, output) as raw:
                reader = pq.ParquetFile(raw)
                schema = reader.schema_arrow
                with pq.ParquetWriter(prepared, schema, compression='zstd') as writer:
                    if current == first:
                        snapshot = []
                        for row in anchor.to_pylist():
                            snapshot.append({**{name: None for name in schema.names},
                                'received_time': at, 'event_time': row['event_time'],
                                'transaction_time': row['tx_time'], 'symbol': 'BTCUSDT',
                                'event_type': 'snapshot', 'last_update_id': seq, 'side': row['side'],
                                'price': exact_text(row['price']), 'quantity': exact_text(row['qty'])})
                        writer.write_table(pa.Table.from_pylist(snapshot, schema=schema))
                    for batch in reader.iter_batches(batch_size=65536):
                        x = pa.Table.from_batches([batch])
                        mask = pc.and_kleene(pc.equal(x['event_type'], 'update'),
                                            pc.greater_equal(x['final_update_id'], seq))
                        mask = pc.and_kleene(mask, pc.less(x['received_time'], cutoff))
                        kept = x.filter(mask)
                        if not len(kept):
                            continue
                        # Buffer updates overlapping the independently received REST snapshot.
                        # The raw archive keeps original clocks; this is a derived availability.
                        ix = schema.get_field_index('received_time')
                        kept = kept.set_column(ix, schema.field(ix),
                                               pc.max_element_wise(kept['received_time'], at))
                        writer.write_table(kept)
            seconds = output/f'{stamp:%H}-seconds.bin'
            events = output/f'{stamp:%H}-events.bin'
            process.stdin.write(f'{current}\t{prepared.resolve()}\t{seconds.resolve()}\t{events.resolve()}\n')
            process.stdin.flush()
            line = process.stdout.readline()
            if not line:
                raise ValueError('Independent snapshot replay failed')
            audit = json.loads(line)
            values = np.fromfile(events, dtype=BOOK)
            validate_events(values, audit['counts'])
            all_events.append(values)
            audits.append(audit)
            prepared.unlink()
            events.unlink()
            seconds.unlink()
    finally:
        process.stdin.close()
        process.wait(timeout=30)
    if process.returncode:
        raise ValueError('Replay did not finish normally')
    book = np.concatenate(all_events)
    book = book[book['receipt_ns'] >= cutoff-120*SECOND]
    store_events(output/'book-events.parquet', book)
    save(output/'audit.json', {'snapshot_receipt_ns': at, 'snapshot_native_id': seq,
                              'source_hashes': sources, 'hour_audits': audits})
    return book


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    fixed = Path('data/btc-perp/august-book-recovery-v1/fixed-sample.json')
    vendor = Path('data/btc-perp/august-book-recovery-v1/candlefeed-v1')
    listing = json.loads((vendor/'aug01-listing.json').read_text())
    expected = next(f for f in listing['days'][0]['files'] if f['name'] == 'snapshot.parquet')
    snapshot_path = vendor/'snapshot.parquet'
    if file_hash(snapshot_path) != expected['sha256'] or snapshot_path.stat().st_size != expected['size']:
        raise ValueError('Changed or incomplete independent snapshot file')
    snapshots = pq.read_table(snapshot_path)
    sample = [r for r in json.loads(fixed.read_text())['strata']
              if r['cutoff_ns'] is not None and r['stratum'].startswith('2026-08-01')]
    source = Path('data/btc-perp/event-shards-snapshot-seeded-august-v2')
    sr = json.loads((source/'report.json').read_text())
    original = Path('data/btc-perp/cryptohftdata-monthly')
    records = {r['remote_file']: r for r in json.loads((original/'manifest.json').read_text())}
    save(out/'protocol.json', {
        'fixed_sample_sha256': file_hash(fixed), 'snapshot_sha256': expected['sha256'],
        'source_report_sha256': file_hash(source/'report.json'),
        'book_policy': 'Latest clean/straddle independent snapshot strictly before window start. Original native deltas with u>=snapshot ID, buffered availability max(original receipt, snapshot receipt). Existing exact-decimal replay, native bridge, verified bounds and window gates unchanged. Original smaller snapshots are not needed to reset a continuous derived chain; sequence failures still reject.',
        'clock_policy': 'CandleFeed receipt clock (millisecond precision in August) combined with original provider clocks. Max availability preserves causality under these historical clocks, not proof of synchronized original receipt timing.',
        'inputs_frozen_before_labels': True, 'original_sources_modified': False,
        'current_forward_models_modified': False})
    build = out/'compiler'
    build.mkdir()
    binary = compile_events(build)
    results = []
    books = {}
    for row in sample:
        cutoff = row['cutoff_ns']
        result = {'input_cutoff_ns': cutoff, 'stratum': row['stratum'], 'accepted': False}
        try:
            anchor = select_anchor(snapshots, cutoff-60*SECOND)
            books[cutoff] = replay_origin(anchor, cutoff, original, records,
                                          out/row['stratum'], binary)
        except ValueError as exc:
            result['first_failed_gate'] = str(exc)
        results.append(result)
        save(out/'status.json', {'state': 'replaying_fixed_sample', 'origins_processed': len(results)})
        print(row['stratum'], 'book replay complete' if cutoff in books else result['first_failed_gate'], flush=True)
    # Reconstruct the original trade tape once. Save every input before inspecting any labels.
    exclusions = clock_exclusions(source, sr['hours'])
    tape = CandleTape()
    pending = np.empty(0, TRADE)
    pending_at = np.empty(0, np.int64)
    watermark = -1
    previous = None
    frozen = {}
    trade_hashes = {}
    end = max(r['input_cutoff_ns'] for r in results)+17*MINUTE
    for entry in sr['hours']:
        at = hour_ns(entry['UTC_hour'])
        if at > end:
            break
        part = entry['files']['trades']
        path = source/entry['UTC_hour']/part['file']
        if file_hash(path) != part['sha256']:
            raise ValueError('Changed original trade shard')
        trade_hashes[entry['UTC_hour']] = part['sha256']
        rows = read_events(path, TRADE)
        before = watermark
        times = released(rows, watermark)
        if len(times): watermark = int(times[-1])
        current = {'rows': rows, 'before': before, 'part': part, 'entry': entry}
        combined = np.concatenate([pending, rows])
        available = np.r_[pending_at, times]
        cursor = 0
        for result in [r for r in results if at <= r['input_cutoff_ns'] < at+HOUR]:
            cutoff = result['input_cutoff_ns']
            stop = int(np.searchsorted(available, cutoff, side='left'))
            for trade, release in zip(combined[cursor:stop], available[cursor:stop]):
                tape.ingest(trade, int(release))
            cursor = stop
            if cutoff not in books:
                continue
            try:
                if intersects(cutoff//MINUTE*MINUTE-1440*MINUTE, cutoff, exclusions):
                    raise ValueError('clock_trade_hour_intersects_input_history')
                if previous is None or previous['part']['clock_bad'] or part['clock_bad']:
                    raise ValueError('clock_flagged_recent_trade_source_hour')
                # Original book-clock flags remain eligibility exclusions even after reseeding.
                if previous['entry']['files']['orderbook']['clock_bad'] or entry['files']['orderbook']['clock_bad']:
                    raise ValueError('clock_flagged_recent_book_source_hour')
                trades = np.concatenate([previous['rows'], rows])
                trades = trades[released(trades, previous['before']) < cutoff]
                books[cutoff] = books[cutoff][source_release(books[cutoff], 'orderbook', -1) < cutoff]
                chosen = join_selection(books[cutoff], trades, cutoff, -1, previous['before'])
                snapshot = tape.snapshot(cutoff, mask_context=True)
            except ValueError as exc:
                result['first_failed_gate'] = str(exc)
                continue
            folder = out/result['stratum']
            b = books[cutoff]
            store_events(folder/'frozen-book.parquet', b)
            store_events(folder/'frozen-trades.parquet', trades)
            np.savez_compressed(folder/'frozen-input.npz', candles=snapshot.pop('candles'),
                                candle_mask=snapshot.pop('candle_mask'), events=chosen['events'])
            save(folder/'frozen-input.json', {**snapshot, 'book_seed_row': chosen['book_seed_row'],
                 'input_file_sha256': file_hash(folder/'frozen-input.npz'),
                 'book_sha256': file_hash(folder/'frozen-book.parquet'),
                 'trades_sha256': file_hash(folder/'frozen-trades.parquet'),
                 'tie_policy': chosen['tie_policy']})
            result['input_passed'] = True
            frozen[cutoff] = snapshot
        stop = int(np.searchsorted(available, at+HOUR, side='left'))
        for trade, release in zip(combined[cursor:stop], available[cursor:stop]):
            tape.ingest(trade, int(release))
        pending, pending_at = combined[stop:].copy(), available[stop:].copy()
        previous = current
    save(out/'input-ledger.json', results)
    save(out/'input-source-hashes.json', trade_hashes)
    for result in results:
        cutoff = result['input_cutoff_ns']
        if cutoff not in frozen:
            continue
        metadata = frozen[cutoff]
        start = metadata['target_start_ns']
        bars = [tape.minutes.get(start+i*MINUTE) for i in range(15)]
        if intersects(start, start+15*MINUTE, exclusions):
            result['first_failed_gate'] = 'clock_trade_hour_intersects_target'
        elif any(b is None or not b['n'] or b['bad'] for b in bars):
            result['first_failed_gate'] = 'missing_or_bad_target'
        else:
            save(out/result['stratum']/'targets.json', {
                'target_start_ns': start, 'closes': [b['c']/SCALE for b in bars],
                'returns_bp': [(b['c']/SCALE/metadata['reference']-1)*10000 for b in bars]})
            result['accepted'] = True
    report = {'state': 'complete', 'fixed_origins_tested': len(results),
              'inputs_passed': len(frozen), 'accepted_examples': sum(r['accepted'] for r in results),
              'origins': results, 'training_started': False,
              'clock_limitations': 'Historical cross-provider receipts, including millisecond snapshot precision; not proven original live availability.'}
    save(out/'report.json', report)
    save(out/'status.json', {k: v for k, v in report.items() if k != 'origins'})
    print({k: v for k, v in report.items() if k != 'origins'}, flush=True)


if __name__ == '__main__':
    main()
