import json
from pathlib import Path
import subprocess

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from research.market_data.validate_archive import compile_scanner, decoded, inventory, reconcile

HOUR = 1793448000000000000
BOOK_SCHEMA = pa.schema([(name, kind) for name, kind in [
    ('received_time', pa.int64()), ('event_time', pa.int64()), ('transaction_time', pa.int64()),
    ('symbol', pa.string()), ('event_type', pa.string()), ('first_update_id', pa.int64()),
    ('final_update_id', pa.int64()), ('prev_final_update_id', pa.int64()), ('last_update_id', pa.int64()),
    ('side', pa.string()), ('price', pa.string()), ('quantity', pa.string()), ('order_count', pa.int64())]])
TRADE_SCHEMA = pa.schema([(name, kind) for name, kind in [
    ('received_time', pa.int64()), ('event_time', pa.int64()), ('symbol', pa.string()),
    ('trade_id', pa.int64()), ('price', pa.string()), ('quantity', pa.string()),
    ('trade_time', pa.int64()), ('is_buyer_maker', pa.bool_()), ('order_type', pa.string())]])


@pytest.fixture(scope='session')
def scanner(tmp_path_factory):
    return compile_scanner(tmp_path_factory.mktemp('native-validator'))


def level(receipt, seq=100, snapshot=False, pu=99, price='100', qty='1', side='bid'):
    return dict(received_time=receipt, event_time=receipt // 1000000, transaction_time=None,
                symbol='BTCUSDT', event_type='snapshot' if snapshot else 'update',
                first_update_id=None if snapshot else seq, final_update_id=seq,
                prev_final_update_id=None if snapshot else pu,
                last_update_id=seq if snapshot else None, side=side, price=price,
                quantity=qty, order_count=None)


def snapshot(receipt=HOUR, seq=100):
    return [level(receipt, seq, True, price=str(100 - i), side='bid') for i in range(20)] + [
            level(receipt, seq, True, price=str(101 + i), side='ask') for i in range(20)]


def scan(scanner, tmp_path, rows, kind='book', more=None):
    jobs = [(HOUR, rows)] + (more or [])
    commands = []
    for i, (hour, values) in enumerate(jobs):
        path = tmp_path / f'{kind}-{i}.parquet'
        pq.write_table(pa.Table.from_pylist(values, schema=BOOK_SCHEMA if kind == 'book' else TRADE_SCHEMA),
                       path, row_group_size=7)
        commands.append(f'{hour}\t{path}\n')
    result = subprocess.run([str(scanner), kind], input=''.join(commands), capture_output=True, text=True, check=True)
    return [json.loads(line) for line in result.stdout.splitlines()]


def test_full_event_atomicity_absolute_updates_and_freshness(scanner, tmp_path):
    rows = snapshot()
    for i in range(120):
        rows.append(level(HOUR + i * 1000000000 + 100000000, 101 + i, pu=100 + i, qty='2'))
    # Intra-message transient crossing must not be confused with a crossed completed book.
    rows += [level(HOUR + 120100000000, 221, pu=220, price='105'),
             level(HOUR + 120100000000, 221, pu=220, price='105', qty='0')]
    q = scan(scanner, tmp_path, rows)[0]
    assert q['ok'] and q['valid_end']
    assert q['counts']['accepted_updates'] == 121
    assert not q['counts'].get('empty_or_crossed_events')
    assert q['good_seconds_per_minute'][0] == 59
    assert q['good_seconds_per_minute'][1] == 60
    assert q['good_seconds_per_minute'][3] == 0  # Stale book is not carried forever.


def test_gap_requires_new_snapshot_and_duplicate_is_safe(scanner, tmp_path):
    rows = snapshot() + [level(HOUR + 100000000, 101, pu=100),
                         level(HOUR + 200000000, 101, pu=100),
                         level(HOUR + 300000000, 103, pu=999),
                         level(HOUR + 400000000, 104, pu=103)]
    rows += snapshot(HOUR + 500000000, 200) + [level(HOUR + 600000000, 201, pu=200)]
    q = scan(scanner, tmp_path, rows)[0]
    assert q['counts']['sequence_gaps'] == 1
    assert q['counts']['stale_or_duplicate_updates'] == 1
    assert q['counts']['orphan_updates'] == 1
    assert q['counts']['accepted_updates'] == 2 and q['valid_end']


def test_duplicate_snapshot_and_invalid_decimal(scanner, tmp_path):
    rows = snapshot() + snapshot(HOUR + 100000000)
    rows += [level(HOUR + 200000000, 101, pu=100, price='nan')]
    q = scan(scanner, tmp_path, rows)[0]
    assert q['counts']['duplicate_identical_snapshots'] == 1
    assert q['counts']['invalid_level_rows'] == 1 and not q['valid_end']


def test_interleaved_provider_snapshot_copies_form_one_complete_snapshot(scanner, tmp_path):
    rows = []
    for row in snapshot(HOUR + 200000000):
        rows.append(row)
        rows.append({**row, 'received_time': HOUR})
    rows.append(level(HOUR + 300000000, 101, pu=100))
    q = scan(scanner, tmp_path, rows)[0]
    assert q['counts']['snapshots'] == 1
    assert not q['counts'].get('invalid_snapshots')
    assert q['counts']['accepted_updates'] == 1 and q['valid_end']
    assert q['counts']['duplicate_snapshot_level_rows'] == 40
    # Keep the raw receipt anomaly visible; reconstruction doesn't certify timing.
    assert q['counts']['backward_receipt_rows'] > 0


def test_conflicting_snapshot_level_cannot_be_silently_overwritten(scanner, tmp_path):
    rows = snapshot()
    rows.append({**rows[0], 'quantity': '999'})
    rows.append(level(HOUR + 300000000, 101, pu=100))
    q = scan(scanner, tmp_path, rows)[0]
    assert q['counts']['conflicting_snapshot_level_rows'] == 1
    assert not q['valid_end']


def test_completed_crossed_book_is_invalid(scanner, tmp_path):
    q = scan(scanner, tmp_path, snapshot() + [level(HOUR + 100000000, 101, pu=100, price='105')])[0]
    assert q['counts']['empty_or_crossed_events'] == 1 and not q['valid_end']


def test_corrupt_parquet_is_reported_and_scanner_can_continue(scanner, tmp_path):
    bad = tmp_path / 'corrupt.parquet'
    bad.write_bytes(b'PAR1invalid-footer')
    good = tmp_path / 'good.parquet'
    pq.write_table(pa.Table.from_pylist(snapshot() + [level(HOUR + 100000000, 101, pu=100)],
                                      schema=BOOK_SCHEMA), good)
    r = subprocess.run([str(scanner), 'book'], input=f'{HOUR}\t{bad}\n{HOUR}\t{good}\n',
                       capture_output=True, text=True, check=True)
    results = [json.loads(line) for line in r.stdout.splitlines()]
    assert not results[0]['ok']
    assert results[1]['ok'] and results[1]['valid_end']


def test_contiguous_hour_carry_and_missing_hour_invalidation(scanner, tmp_path):
    rows = snapshot() + [level(HOUR + 100000000, 101, pu=100)]
    q = scan(scanner, tmp_path, rows, more=[(HOUR + 3600 * 10**9,
        [level(HOUR + 3600 * 10**9 + 100000000, 102, pu=101)]),
        (HOUR + 10800 * 10**9, [level(HOUR + 10800 * 10**9 + 100000000, 103, pu=102)])])
    assert q[1]['counts']['accepted_updates'] == 1
    assert q[2]['counts']['orphan_updates'] == 1 and not q[2]['valid_end']


def trades(ids):
    return [dict(received_time=HOUR + 100000000 + i * 1000000, event_time=HOUR // 1000000 + 100 + i,
                 trade_time=HOUR // 1000000 + 100 + i, trade_id=tid, symbol='BTCUSDT',
                 price='100.10', quantity='0.003', is_buyer_maker=False, order_type='MARKET')
            for i, tid in enumerate(ids)]


def test_trade_precision_and_id_gaps(scanner, tmp_path):
    q = scan(scanner, tmp_path, trades([1, 2, 5, 5]), 'trades')[0]
    assert q['counts']['missing_trade_ids'] == 2
    assert q['counts']['adjacent_duplicate_trade_ids'] == 1
    c = q['candles'][0]
    assert c['volume'] == '0.01200000' and c['quote_volume'] == '1.2012000000000000'
    assert c['bad']


def test_exchange_non_market_zero_events_preserve_ids_but_not_candles(scanner, tmp_path):
    rows = trades([1, 2, 3])
    rows[1].update(price='0', quantity='0', order_type='NA')
    q = scan(scanner, tmp_path, rows, 'trades')[0]
    assert q['counts']['non_market_zero_events'] == 1
    assert not q['counts'].get('invalid_trade_rows')
    assert not q['counts'].get('trade_id_gap_events')
    assert q['candles'][0]['count'] == 2
    assert q['candles'][0]['low'] == '100.10000000'
    assert q['candles'][0]['volume'] == '0.00600000'


def test_zstd_wrapper_preserves_raw_bytes(tmp_path):
    path = tmp_path / 'wrapped.parquet.zst'
    raw = tmp_path / 'raw.parquet'
    pq.write_table(pa.table({'a': [1, 2, 3]}), raw)
    with pa.output_stream(str(path), compression='zstd') as target:
        target.write(raw.read_bytes())
    before = path.read_bytes()
    with decoded(path, tmp_path) as plain:
        assert pq.read_table(plain).num_rows == 3
    assert path.read_bytes() == before


def test_inventory_reports_missing_and_duplicates(tmp_path):
    r = {'remote_file': 'binance_futures/2025-11-01/00/BTCUSDT_trades.parquet', 'rows': 3, 'bytes': 7}
    inv = inventory(tmp_path, [r, r])
    assert inv['expected_files'] == 17520
    assert inv['duplicate_remote_files'] == [r['remote_file']]
    assert len(inv['missing_remote_files']) == 17519


def test_independent_reference_rejects_wrong_volume_and_keeps_training_gate_closed(tmp_path):
    import zipfile
    refs = tmp_path / 'reference'
    refs.mkdir()
    minute = HOUR // 1000000
    rows = [f'{minute+i*60000},100.10,100.10,100.10,100.10,0.003,{minute+(i+1)*60000-1},0.3003,1,0,0,0\n'
            for i in range(2)]
    with zipfile.ZipFile(refs / 'BTCUSDT-1m-2026-10.zip', 'w') as archive:
        archive.writestr('candles.csv', ''.join(rows))
    folder = tmp_path / 'hours' / '2026-10-31' / '12'
    folder.mkdir(parents=True)
    candles = [dict(minute_ms=minute+i*60000, count=1, open='100.10', high='100.10',
                    low='100.10', close='100.10', volume='0.003' if i == 0 else '0.004',
                    quote_volume='0.3003', first_id=i+1, last_id=i+1, bad=False) for i in range(2)]
    (folder / 'BTCUSDT_trades.parquet.quality.json').write_text(json.dumps(dict(
        ok=True, remote_file='binance_futures/2026-10-31/12/BTCUSDT_trades.parquet',
        hour_ns=HOUR, counts={'rows': 2}, first_trade_id=1, last_trade_id=2, candles=candles)))
    reconcile(tmp_path, {}, [{'month': '2026-10', 'available': True}])
    report = json.loads((tmp_path / 'report.json').read_text())
    assert report['trade_candle_mismatches']['volume'] == 1
    assert report['trade_minutes_passing'] == 1
    assert report['candidate_1440_context_origins'] == 0
    assert not report['training_ready']


def test_rest_reference_day_recovery_requires_hash_and_complete_day(tmp_path):
    import hashlib
    from datetime import datetime, timezone
    refs = tmp_path / 'reference'
    refs.mkdir()
    (tmp_path / 'hours').mkdir()
    start = int(datetime(2026, 10, 28, tzinfo=timezone.utc).timestamp()) * 1000
    rows = [[start + i * 60000, '100', '101', '99', '100', '1', start + (i+1)*60000-1,
             '100', 1, '0', '0', '0'] for i in range(1440)]
    source = refs / 'REST-BTCUSDT-1m-2026-10-28.json'
    source.write_text(json.dumps(rows))
    source.with_suffix('.metadata.json').write_text(json.dumps({
        'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'url': 'https://fapi.binance.com/fapi/v1/klines'}))
    reconcile(tmp_path, {}, [])
    result = json.loads((tmp_path / 'report.json').read_text())
    assert result['official_minutes'] == 1440
    assert result['independent_reference_supplements'][0]['minutes_added'] == 1440
    source.write_text(json.dumps(rows[:-1]))
    with pytest.raises(ValueError, match='hash mismatch'):
        reconcile(tmp_path, {}, [])


def test_pilot_boundaries_cover_one_month_without_overlapping_targets():
    from research.market_data.freeze_pilot import SPLITS, timestamp
    ranges = [(timestamp(a), timestamp(b)) for a, b in SPLITS.values()]
    assert ranges[0][0] == timestamp('2026-10-01')
    assert ranges[-1][1] == timestamp('2026-11-01')
    assert all(a[1] == b[0] for a, b in zip(ranges, ranges[1:]))
    assert sum((b-a)//60000 for a, b in ranges) == 31 * 1440
