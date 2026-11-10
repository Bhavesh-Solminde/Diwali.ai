import numpy as np
import pytest

from research.diwali.event_direction_diagnostic import binary_metrics, probability_groups, uncalibrated_bins
from research.diwali.event_train import probabilities
from research.diwali.event_data import labels


def test_temperature_inversion_recovers_raw_distribution():
    rng = np.random.default_rng(17); logits = rng.normal(size=(21, 15, 26))
    temperatures = np.geomspace(.5, 4, 15)
    calibrated = probabilities(logits, temperatures)
    np.testing.assert_allclose(uncalibrated_bins(calibrated, temperatures), probabilities(logits), atol=1e-14)


def test_down_biased_forecasts_can_still_rank_perfectly():
    r = binary_metrics([0, 0, 1, 1], [.46, .47, .48, .49])
    assert r['forecasts_favouring_up'] == 0
    assert r['roc_auc'] == 1 and r['accuracy'] == .5


def test_multiclass_temperature_can_reorder_summed_binary_probabilities():
    p = np.full((2, 15, 26), 1e-12)
    p[0, :, :13] = .51/13; p[0, :, 13] = .49-12e-12
    p[1, :, 13:] = .48/13; p[1, :, 0] = .52-12e-12
    assert p[0, 0, 13:].sum() > p[1, 0, 13:].sum()
    calibrated = probabilities(np.log(p), [2.]*15)
    assert calibrated[0, 0, 13:].sum() < calibrated[1, 0, 13:].sum()


def test_tied_and_single_class_auc_are_not_fabricated():
    assert binary_metrics([0, 1, 0, 1], [.47]*4)['roc_auc'] == .5
    assert binary_metrics([1, 1], [.47, .48])['roc_auc'] is None
    groups = probability_groups([0, 1, 0, 1], [.47]*4, rank=True)
    assert len(groups) == 1 and groups[0]['origins'] == 4


def test_probability_groups_cover_every_row_without_using_truth_for_boundaries():
    p = np.array([.4, .45, .475, .49, .5, .51, .525, .55, .6])
    for rank in [False, True]:
        a = probability_groups(np.arange(len(p)) % 2, p, rank)
        b = probability_groups(1-np.arange(len(p)) % 2, p, rank)
        assert sum(r['origins'] for r in a) == len(p)
        assert [(r['lower_inclusive'], r['upper_exclusive']) for r in a] == [(r['lower_inclusive'], r['upper_exclusive']) for r in b]


def test_zero_and_adjacent_returns_agree_with_binary_label():
    values = np.array([np.nextafter(0., -np.inf), 0., np.nextafter(0., np.inf), -2., 2.])
    y = labels(np.repeat(values[:, None], 15, axis=1))
    np.testing.assert_array_equal(y[:, 0] >= 13, values > 0)


def test_reject_invalid_saved_probabilities_and_binary_values():
    p = np.full((1, 15, 26), 1/26); p[0, 0, 0] = 0
    with pytest.raises(ValueError):
        uncalibrated_bins(p, [1.]*15)
    with pytest.raises(ValueError):
        binary_metrics([0, 2], [.3, .4])
