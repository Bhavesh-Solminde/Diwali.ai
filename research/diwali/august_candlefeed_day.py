"""Build a separately versioned August source with fresh August 1 book anchors."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from .august_candlefeed_recovery import exact_text
from ..market_data.event_replay import DTYPE, compile_events, validate_events
from ..market_data.event_shards import store_events
from ..market_data.event_join_cohort import hour_ns, HOUR
from ..market_data.validate_archive import HARD_CLOCK, decoded, file_hash, raw_path, save


def finalize_metadata(report, out):
    """Bind new replay quality to its own audit, retaining the parent raw audit separately."""
    for entry in report['hours']:
        if not entry['UTC_hour'].startswith('2026-08-01T'):
            continue
        part = entry['files']['orderbook']
        if 'parent_raw_quality_sha256' not in part:
            part['parent_raw_quality_sha256'] = part['quality_sha256']
        part['quality_sha256'] = file_hash(out/entry['UTC_hour']/'orderbook-audit.json')
        part['quality_file'] = 'orderbook-audit.json'
        part['quality_kind'] = 'Derived independent-snapshot/native-update replay audit'
        save(out/entry['UTC_hour']/'manifest.json', entry)
    report['compressed_bytes'] = sum(p['stored_bytes'] for h in report['hours'] for p in h['files'].values())
    report['uncompressed_bytes'] = sum(p['uncompressed_bytes'] for h in report['hours'] for p in h['files'].values())
    report['limitations'] = [*report['limitations'],
        report['protocol']['clock_limitations'],
        'Only August 1 book inputs reseeded; other days retain original source coverage.',
        'Fresh snapshot bootstrap markers and any failed native bridge remain excluded by the unchanged window gates.']
    return report


def updates(table, sequence=None, stop=None):
    mask = pc.equal(table['event_type'], 'update')
    if sequence is not None:
        mask = pc.and_kleene(mask, pc.greater_equal(table['final_update_id'], sequence))
    if stop is not None:
        mask = pc.and_kleene(mask, pc.less(table['received_time'], stop))
    return table.filter(mask)


def seeded_interval(anchor, raw, stop, schema):
    at = pc.max(anchor['recv_time']).as_py()
    seq = anchor['final_update_id'][0].as_py()
    if len(pc.unique(anchor['final_update_id'])) != 1 or len(pc.unique(anchor['node'])) != 1:
        raise ValueError('Mixed snapshot identity')
    if not pc.all(anchor['is_snapshot']).as_py() or not pc.all(pc.equal(anchor['symbol'], 'BTCUSDT')).as_py():
        raise ValueError('Wrong independent snapshot contract/type')
    if at < pc.max(anchor['event_time']).as_py()*10**6:
        raise ValueError('Independent snapshot clock conflict')
    rows = [{**{name: None for name in schema.names}, 'received_time': at,
             'event_time': r['event_time'], 'transaction_time': r['tx_time'],
             'symbol': 'BTCUSDT', 'event_type': 'snapshot', 'last_update_id': seq,
             'side': r['side'], 'price': exact_text(r['price']), 'quantity': exact_text(r['qty'])}
            for r in anchor.to_pylist()]
    initial = pa.Table.from_pylist(rows, schema=schema)
    kept = updates(raw, seq, stop)
    ix = schema.get_field_index('received_time')
    kept = kept.set_column(ix, schema.field(ix), pc.max_element_wise(kept['received_time'], at))
    return initial, kept


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    parent = Path('data/btc-perp/event-shards-snapshot-seeded-august-v2').resolve()
    original = Path('data/btc-perp/cryptohftdata-monthly')
    vendor = Path('data/btc-perp/august-book-recovery-v1/candlefeed-v1')
    expected = next(f for f in json.loads((vendor/'aug01-listing.json').read_text())['days'][0]['files']
                    if f['name'] == 'snapshot.parquet')
    if file_hash(vendor/'snapshot.parquet') != expected['sha256']:
        raise ValueError('Changed independent snapshot file')
    snapshots = pq.read_table(vendor/'snapshot.parquet')
    snapshots = snapshots.filter(pc.is_in(snapshots['anchor_class'], value_set=pa.array(['clean', 'straddle'])))
    times = sorted(set(snapshots['recv_time'].to_pylist()))
    originals = {r['remote_file']: r for r in json.loads((original/'manifest.json').read_text())}
    report = json.loads((parent/'report.json').read_text())
    report['protocol'].update(recovery='CandleFeed August 1 only; independent snapshots plus original native deltas',
        parent_report_sha256=file_hash(parent/'report.json'), independent_snapshot_sha256=expected['sha256'],
        recovery_code_sha256=file_hash(Path(__file__)),
        policy='Existing exact replay and all quality gates. Native-ID buffering released at max original/snapshot receipt. Fresh snapshots may invalidate a window until their update bridge completes. No future snapshot repairs an earlier input.',
        clock_limitations='Cross-provider historical clocks with millisecond precision on August snapshots; no independent clock-offset calibration.')
    save(out/'protocol.json', report['protocol'])
    build = out/'compiler';build.mkdir()
    binary = compile_events(build)
    process = subprocess.Popen([str(binary)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True)
    previous_raw = None
    provenance = []
    rebuilt = 0
    try:
        for entry in report['hours']:
            name = entry['UTC_hour']
            if not name.startswith('2026-08-01T'):
                (out/name).symlink_to(parent/name, target_is_directory=True)
                continue
            folder = out/name;folder.mkdir()
            at = hour_ns(name)
            remote = f'binance_futures/2026-08-01/{name[-2:]}/BTCUSDT_orderbook.parquet'
            record = originals[remote]
            path = raw_path(original, record)
            if file_hash(path) != record['sha256']:
                raise ValueError('Changed original book file')
            with decoded(path, out) as plain:
                current = pq.read_table(plain)
            schema = current.schema
            raw = current if previous_raw is None else pa.concat_tables([previous_raw, current])
            hour_times = [t for t in times if at <= t < at+HOUR]
            prepared = folder/'derived-native.parquet'
            with pq.ParquetWriter(prepared, schema, compression='zstd') as writer:
                # Before the first new anchor, continue the preceding derived chain.
                first = hour_times[0] if hour_times else at+HOUR
                writer.write_table(updates(current, stop=first))
                for i, received in enumerate(hour_times):
                    stop = hour_times[i+1] if i+1 < len(hour_times) else at+HOUR
                    anchor = snapshots.filter(pc.equal(snapshots['recv_time'], received))
                    initial, kept = seeded_interval(anchor, raw, stop, schema)
                    writer.write_table(initial)
                    writer.write_table(kept)
            seconds = folder/'seconds.bin'
            events = folder/'events.bin'
            process.stdin.write(f'{at}\t{prepared.resolve()}\t{seconds.resolve()}\t{events.resolve()}\n')
            process.stdin.flush()
            line = process.stdout.readline()
            if not line:
                raise ValueError('Reseeded day replay failed')
            audit = json.loads(line)
            save(folder/'orderbook-audit.json', audit)
            rows = np.fromfile(events, dtype=DTYPE)
            validate_events(rows, audit['counts'])
            book_path = folder/'orderbook-events.parquet'
            store_events(book_path, rows)
            old_part = entry['files']['orderbook']
            entry['files']['orderbook'] = {**old_part, 'sha256': file_hash(book_path),
                'decoded_binary_sha256': file_hash(events), 'source_sha256': file_hash(prepared),
                'rows': len(rows), 'uncompressed_bytes': rows.nbytes, 'stored_bytes': book_path.stat().st_size,
                'clock_bad': old_part['clock_bad'] or any(audit['counts'].get(k, 0) for k in HARD_CLOCK+('backward_receipt_rows',))}
            for child in (parent/name).iterdir():
                if child.name.startswith('trades'):
                    (folder/child.name).symlink_to(child)
            save(folder/'manifest.json', entry)
            provenance.append({'hour': name, 'original_book_sha256': record['sha256'],
                               'independent_anchors': len(hour_times), 'derived_parquet_sha256': file_hash(prepared),
                               'book_events_sha256': entry['files']['orderbook']['sha256'], 'counts': audit['counts']})
            # The original native records and snapshot file remain available for exact reconstruction.
            prepared.unlink();events.unlink();seconds.unlink()
            previous_raw = current
            rebuilt += 1
            save(out/'status.json', {'state': 'replaying', 'hours_completed': rebuilt, 'hours_total': 24})
            print(name, 'anchors', len(hour_times), 'good seconds', sum(audit['good_seconds_per_minute']), flush=True)
    finally:
        process.stdin.close()
        process.wait(timeout=30)
    if process.returncode:
        raise ValueError('Replay did not finish normally')
    report['state'] = 'complete'
    save(out/'recovery-provenance.json', provenance)
    save(out/'report.json', finalize_metadata(report, out))
    save(out/'status.json', {'state': 'complete', 'hours_completed': rebuilt,
        'native_sequence_gaps': sum(p['counts'].get('sequence_gaps', 0) for p in provenance),
        'training_started': False})


if __name__ == '__main__':
    main()
