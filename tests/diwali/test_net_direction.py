import numpy as np
import pytest
from research.diwali.net_direction import net_probabilities,direction_summary,net_metrics


def test_net_direction_uses_zero_not_two_basis_point_threshold():
    p=np.zeros((15,26));p[:,12]=.2;p[:,13]=.8
    np.testing.assert_allclose(net_probabilities(p),np.tile([.2,.8],(15,1)))
    s=direction_summary(p);assert s['up']==.8 and s['favoured_side']=='up' and s['horizon']==15


def test_net_endpoint_is_not_first_candle_and_equality_is_not_silently_down():
    p=np.zeros((15,26));p[:14,0]=1;p[14,25]=1
    assert direction_summary(p)['up']==1
    m=net_metrics(np.array([12,13]),np.eye(26)[[12,13]]);assert m['accuracy']==1 and m['binary_log_loss']==0
    assert m['labels']==['down_or_unchanged','up']


def test_invalid_clouds_cannot_generate_direction_claims():
    with pytest.raises(ValueError):direction_summary(np.zeros((15,26)))
    with pytest.raises(ValueError):net_probabilities(np.ones((15,25)))
