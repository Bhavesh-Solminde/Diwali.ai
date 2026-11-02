import numpy as np
import pytest
import torch
from research.diwali.probability import labels, observed_reference, probabilities, calibrate, metrics, ProbabilityModel
from research.diwali.model import WIDTH
from research.market_data.build_pilot import feature_dtype


def test_label_boundaries_and_reference():
    np.testing.assert_array_equal(labels(np.array([99.97,100,100.03]),100), [0,1,2])
    np.testing.assert_array_equal(labels(np.array([200,200]),np.array([199.,201.])), [2,0])


def test_reference_ignores_future_and_uses_received_window():
    rows = np.zeros(62, dtype=feature_dtype('trades'))
    rows['x'][58,:4] = [2,1,200,100]
    rows['receipt_ns'][58] = 59_000_000_000
    row = np.array([60_000,120_000,1440,0,60])
    assert observed_reference(rows,row) == (100.,1.)
    rows['x'][60:,:4] = 1e9
    assert observed_reference(rows,row) == (100.,1.)
    rows['event_ns'][58] = 60_000_000_000
    with pytest.raises(ValueError):observed_reference(rows,row)


@pytest.mark.parametrize('architecture,width',[('logistic',57),('mlp',WIDTH+1),('sequence',WIDTH+1)])
def test_models_emit_two_normalized_three_class_distributions(architecture,width):
    model = ProbabilityModel(architecture,width).eval()
    with torch.no_grad():logits = model(torch.zeros(2,width)).numpy()
    p = probabilities(logits)
    assert p.shape == (2,2,3)
    np.testing.assert_allclose(p.sum(-1),1)
    assert (p>=0).all() and np.isfinite(p).all()


def test_calibration_improves_overconfident_wrong_predictions():
    logits = np.tile([0.,0.,8.], (100,1))
    y = np.arange(100)%3
    before = metrics(y,probabilities(logits))['log_loss']
    t = calibrate(logits,y)
    assert metrics(y,probabilities(logits,t))['log_loss'] < before
    assert metrics(y,probabilities(logits))['high_confidence']['0.9']['n'] == 100
