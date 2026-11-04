import numpy as np
from research.market_data.event_join_cohort import source_release, join_selection
from research.market_data.event_replay import DTYPE as BOOK
from research.market_data.trade_events import DTYPE as TRADE


def test_excluded_clock_hour_cannot_reset_release_barrier():
    rows = np.zeros(3, dtype=TRADE)
    rows['receipt_ns'] = [10, 20, 30]
    rows['event_ns'] = [10, 200, 30]
    rows['trade_ns'] = [10, 20, 30]
    times = source_release(rows, 'trades', -1, clock_bad=True)
    np.testing.assert_array_equal(times, [10, 200, 200])
    next_hour = rows[:1].copy()
    next_hour['receipt_ns'] = next_hour['event_ns'] = next_hour['trade_ns'] = 40
    assert source_release(next_hour, 'trades', int(times[-1]))[0] == 200


def test_window_crosses_hour_and_keeps_strict_freeze():
    second = 10**9
    # Last update of the preceding hour plus updates every 0.5 seconds.
    b = np.zeros(125, dtype=BOOK)
    b['receipt_ns'] = (np.arange(125)*second//2 + 3554*second)
    b['event_ns'] = b['receipt_ns']
    b['valid'] = b['accepted_update'] = 1
    t = np.zeros(3, dtype=TRADE)
    t['receipt_ns'] = [3599*second, 3600*second, 3615*second]
    t['event_ns'] = t['trade_ns'] = t['receipt_ns']
    chosen = join_selection(b, t, 3615*second)
    assert chosen['book_seed_row'] == 1
    assert chosen['trade_rows'] == 2
    assert chosen['events']['available_ns'].min() < 3600*second
    assert chosen['events']['available_ns'].max() < 3615*second
