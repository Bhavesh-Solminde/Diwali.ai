import numpy as np
from research.diwali.event_train import probabilities,calibrate,metrics


def test_probability_scoring_and_calibration_keep_direction_coherent_with_bins():
    rng=np.random.default_rng(17);z=rng.normal(size=(130,15,26));y=rng.integers(0,26,size=(130,15))
    p=probabilities(z);np.testing.assert_allclose(p.sum(-1),1.)
    t=calibrate(y,z);q=probabilities(z,t);r=metrics(y,q)
    assert len(t)==15 and all(.5<=x<=4 for x in t)
    assert np.isfinite(r['mean15_bin_log_loss']) and len(r['per_horizon_bin_log_loss'])==15
    up=q[:,-1,13:].sum(-1);expected=-np.log(np.where(y[:,-1]>=13,up,1-up)).mean()
    np.testing.assert_allclose(r['final_direction_log_loss'],expected)


def test_sparse_calibration_retains_unmodified_probabilities():
    rng=np.random.default_rng(29);z=rng.normal(size=(25,15,26));y=rng.integers(0,26,size=(25,15))
    assert calibrate(y,z)==[1.]*15
