"""Inference/reveal separation for the new historical event-model demo."""
import copy
import threading

import numpy as np
import pytest
import torch

from research.diwali.event_serve import Engine, forecast_payload, inference_input


class InputOnly:
    @property
    def y(self):
        raise AssertionError('Inference must not read future labels')

    def raw(self, index):
        return (np.zeros((60, 103), np.float32), np.arange(60),
                np.zeros((1440, 8), np.float32), np.ones(1440, bool),
                np.zeros(80, np.float32), np.zeros(1, np.float32))

    def exact_elapsed(self, index):
        return np.arange(60, dtype=np.int64)*10**9


def transforms():
    return {'representation': 'one_second', 'moments': {
        n: {'mean': [0.]*w, 'std': [1.]*w}
        for n, w in [('event', 103), ('candle', 8), ('seed', 80), ('reference', 1)]}}


def test_inference_does_not_access_future_labels():
    args = inference_input(InputOnly(), 0, transforms())
    assert args[0].shape == (1, 60, 103)
    assert args[2].shape == (1, 1440, 8)
    assert all(torch.isfinite(a).all() for a in args)


def test_forecast_direction_is_mass_from_same_bins():
    p = np.zeros((15, 26)); p[:, 12] = .3; p[:, 13] = .7
    fan = forecast_payload(p, 100., 60000)
    assert len(fan) == 15
    assert fan[-1]['up'] == .7 and fan[-1]['down_or_unchanged'] == .3
    assert fan[0]['close_ms'] == 120000
    assert fan[-1]['close_ms'] == 960000
    assert fan[0]['ranges'][0]['lower_price'] is None
    assert fan[0]['ranges'][-1]['upper_price'] is None
    # +2bp belongs to the bullish band, matching the frozen target convention.
    assert fan[0]['ranges'][16]['lower_inclusive']
    assert not fan[0]['ranges'][15]['upper_inclusive']
    with pytest.raises(AssertionError):
        forecast_payload(p*.5, 100., 60000)


def engine_stub():
    e = object.__new__(Engine)
    e.lock = threading.RLock(); e.requests = {}; e.data = InputOnly()
    e.transforms = transforms(); e.calibration = {'temperatures': [1.]*15}
    e.weights_sha256 = 'test-fixed-weights'
    e.model = lambda *args: torch.zeros((1, 15, 26))
    e.cases = [{'data_index': 0, 'snapshot_ms': 15000, 'target_ms': 60000,
                'reference': 100., 'past': [{'time': -60000, 'ohlc': [100.]*4}],
                'actual_closes': list(range(100, 115))}]
    return e


def test_answers_are_absent_until_token_reveal_and_cannot_change_prediction():
    e = engine_stub()
    assert set(e.case(0)) == {'snapshot_ms', 'target_ms', 'reference', 'past'}
    p = e.predict(0); before = copy.deepcopy(p)
    assert 'actual_closes' not in p and p['future_actuals_used'] is False
    revealed = e.reveal(p['token'])
    assert len(revealed['actual_closes']) == 15
    assert revealed['actual_closes'][0] == {'close_ms': 120000, 'close': 100}
    assert p == before
    revealed['actual_closes'][0]['close'] = -1
    assert e.reveal(p['token'])['actual_closes'][0]['close'] == 100
    e.cases[0]['actual_closes'] = [999.]*15
    assert e.requests[p['token']][1] == before
    assert e.predict(0)['fan'] == before['fan']


def test_invalid_case_or_unissued_token_is_rejected():
    e = engine_stub()
    for invalid in [-1, 1, True, '0']:
        with pytest.raises(ValueError):
            e.predict(invalid)
    with pytest.raises(ValueError):
        e.reveal('unissued-token')
