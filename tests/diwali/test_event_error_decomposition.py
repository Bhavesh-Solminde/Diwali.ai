import numpy as np

from research.diwali.event_error_decomposition import decompose


def test_direction_and_conditional_errors_reconstruct_joint_error():
    p = np.full((2, 15, 26), .2/13)
    p[..., 13:] = .8/13
    y = np.full((2, 15), 13)
    r = decompose(y, p)
    assert abs(r['mean15_direction_log_loss'] + np.log(.8)) < 1e-12
    assert abs(r['mean15_within_side_log_loss'] - np.log(13)) < 1e-12
    assert abs(r['mean15_total_bin_log_loss'] - np.log(13/.8)) < 1e-12
    assert r['maximum_decomposition_difference'] < 1e-12
