import numpy as np

from research.market_data.build_pilot import (START, WARMUP, feature_dtype,
                                             eligible_indices, fit_scaler, trade_values)


def example():
    origin = START + 60000
    ci = (origin-WARMUP)//60000
    valid = np.ones(ci+1, bool)
    receipt = (np.arange(ci+1)*60000+WARMUP+59900)*10**6
    book = np.zeros(60, dtype=feature_dtype('book'))
    trades = np.zeros(60, dtype=feature_dtype('trades'))
    for rows in (book, trades):
        rows['time_ns'] = START*10**6+np.arange(60)*10**9
        rows['receipt_ns'] = rows['time_ns']+1000
        rows['event_ns'] = rows['time_ns']
        rows['valid'] = 1
    return origin, valid, receipt, book, trades


def test_receipt_cutoff_excludes_late_candles_and_future_trades():
    origin, valid, receipt, book, trades = example()
    assert len(eligible_indices([origin], 0, valid, receipt, book, trades)[0]) == 1
    receipt[-2] = origin*10**6
    assert eligible_indices([origin], 0, valid, receipt, book, trades)[1] == {
        'candle_not_fully_received_by_cutoff': 1}
    receipt[-2] -= 1000000
    trades['event_ns'][-1] = origin*10**6+1
    assert eligible_indices([origin], 0, valid, receipt, book, trades)[1] == {
        'late_or_future_book_trade_input': 1}


def test_incomplete_candle_context_and_invalid_second_are_rejected():
    origin, valid, receipt, book, trades = example()
    valid[10] = False
    assert not len(eligible_indices([origin], 0, valid, receipt, book, trades)[0])
    valid[:] = True
    book['valid'][20] = 0
    assert eligible_indices([origin], 0, valid, receipt, book, trades)[1] == {
        'invalid_book_or_trade_seconds': 1}


def test_scaler_uses_only_supplied_fitting_values():
    values = np.array([[1, 2], [3, 4]])
    scaler = fit_scaler(iter([values]), 2)
    assert scaler['mean'] == [2, 3]
    assert scaler['std'] == [1, 1]


def test_empty_trade_bucket_has_no_fake_negative_price_move():
    rows = np.zeros(2, dtype=feature_dtype('trades'))
    rows['x'][1] = [1, 0, 100, 0, 1, 1, 0, 100]
    result = trade_values(rows, 100)
    assert result[0, 7] == 0 and result[1, 7] == 0
    assert np.isfinite(result).all()
