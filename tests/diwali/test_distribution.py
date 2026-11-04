import numpy as np
import pytest
import torch
from research.diwali.distribution import EDGES,range_labels,direction,rps_torch,range_metrics,DistributionModel
from research.diwali.multiscale import SHORT_WIDTH


def test_threshold_boundaries_and_unbounded_tails_are_coherent():
    r=np.array([-1e6,-20,-2,-2+1e-8,0,2-1e-8,2,20,1e6])
    b=range_labels(r)
    np.testing.assert_array_equal(np.where(b<6,0,np.where(b>=12,2,1)),[0,0,0,1,1,1,2,2,2])
    assert b[0]==0 and b[-1]==17
    with pytest.raises(ValueError):range_labels([np.nan])


def test_histogram_and_aggregated_direction_conserve_probability():
    torch.manual_seed(17);model=DistributionModel().eval()
    with torch.no_grad():z=model(torch.zeros(2,SHORT_WIDTH));p=z[:,:18].softmax(-1).numpy()
    assert z.shape==(2,21)
    np.testing.assert_allclose(p.sum(1),1,atol=1e-6)
    np.testing.assert_allclose(direction(p).sum(1),1,atol=1e-6)
    assert (np.diff(np.cumsum(p,axis=1))>=0).all()


def test_ranked_score_rewards_correct_distribution_and_penalizes_farther_error():
    y=torch.tensor([5]);good=torch.full((1,18),-30.);near=good.clone();far=good.clone()
    good[0,5]=30;near[0,6]=30;far[0,17]=30
    assert rps_torch(good,y)<rps_torch(near,y)<rps_torch(far,y)
    p=good.softmax(-1).numpy();v=range_metrics(y.numpy(),p)
    assert v['bin_accuracy']==1 and v['intervals']['0.8']['actual_coverage']==1


def test_distribution_checkpoint_roundtrip_preserves_probabilities(tmp_path):
    model=DistributionModel().eval();x=torch.randn(1,SHORT_WIDTH)
    path=tmp_path/'model.pt';torch.save(model.state_dict(),path)
    restored=DistributionModel().eval();restored.load_state_dict(torch.load(path,weights_only=True))
    with torch.no_grad():
        torch.testing.assert_close(model(x).softmax(-1),restored(x).softmax(-1))
