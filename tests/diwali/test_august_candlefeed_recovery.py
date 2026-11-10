from decimal import Decimal

import pyarrow as pa
import pytest

from research.diwali.august_candlefeed_recovery import exact_text, select_anchor
from research.diwali.august_candlefeed_day import seeded_interval


def anchor(at, seq):
    return [{'recv_time': at, 'event_time': 1, 'final_update_id': seq, 'node': 'test',
             'symbol': 'BTCUSDT', 'is_snapshot': True, 'anchor_class': 'straddle', 'side': side}
            for side in ['bid', 'ask'] for _ in range(20)]


def test_anchor_excludes_snapshot_at_or_after_window_start():
    table = pa.Table.from_pylist(anchor(2_000_000, 1)+anchor(3_000_000, 2))
    assert select_anchor(table, 3_000_000)['final_update_id'][0].as_py() == 1
    with pytest.raises(ValueError, match='before input window'):
        select_anchor(table, 2_000_000)


def test_decimal_adapter_preserves_exact_levels_and_rejects_precision_loss():
    assert exact_text(Decimal('62863.800000000000')) == '62863.8'
    assert exact_text(Decimal('0.000000010000')) == '0.00000001'
    with pytest.raises(ValueError, match='exactly'):
        exact_text(Decimal('0.000000001'))


def test_snapshot_bridge_buffers_earlier_received_updates_without_changing_raw_clocks():
    schema = pa.schema([(n, pa.int64()) for n in ['received_time', 'event_time', 'transaction_time',
        'first_update_id', 'final_update_id', 'prev_final_update_id', 'last_update_id']]+
        [(n, pa.string()) for n in ['symbol', 'event_type', 'side', 'price', 'quantity']])
    raw = pa.Table.from_pylist([{'received_time': r, 'final_update_id': seq, 'event_type': 'update'}
                               for r, seq in [(3_000_000, 90), (4_000_000, 110), (10_000_000, 120)]], schema=schema)
    snapshot = pa.Table.from_pylist([{'recv_time': 5_000_000, 'final_update_id': 100, 'node': 'test',
        'is_snapshot': True, 'symbol': 'BTCUSDT', 'event_time': 1, 'tx_time': 1,
        'side': side, 'price': Decimal(p), 'qty': Decimal('1')} for side, p in [('bid','99'), ('ask','101')]])
    initial, kept = seeded_interval(snapshot, raw, 9_000_000, schema)
    assert initial['last_update_id'].to_pylist() == [100, 100]
    assert kept['final_update_id'].to_pylist() == [110]
    assert kept['received_time'].to_pylist() == [5_000_000]
    assert raw['received_time'].to_pylist() == [3_000_000, 4_000_000, 10_000_000]
