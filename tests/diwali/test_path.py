import itertools

import numpy as np
import pytest
import torch

from research.diwali.path import PathModel,propagate,path_events,chain_losses,fit_chain,forecast
from research.diwali.multiscale import SHORT_WIDTH


def toy_chain():
    a=np.zeros((1,26));a[0,:2]=[.3,.7]
    t=np.tile(np.eye(26),(1,14,1,1));t[0,0,:2,:2]=[[.8,.2],[.1,.9]];t[0,1,:2,:2]=[[.6,.4],[.3,.7]]
    return a,t


def test_exact_marginals_and_path_events_match_exhaustive_enumeration():
    a,t=toy_chain();m=propagate(a,t);expected=np.zeros((15,26));stay=visit=0
    for prefix in itertools.product(range(2),repeat=3):
        path=list(prefix)+[prefix[-1]]*12;p=a[0,path[0]]*t[0,0,path[0],path[1]]*t[0,1,path[1],path[2]]
        for h,state in enumerate(path):expected[h,state]+=p
        stay+=p*all(i==0 for i in path);visit+=p*any(i==0 for i in path)
        np.testing.assert_allclose(chain_losses(a,t,np.array([path])),[-np.log(p)],atol=1e-12)
    np.testing.assert_allclose(m[0],expected,atol=1e-12)
    s,v=path_events(a,t,0,0);np.testing.assert_allclose(s,[stay]);np.testing.assert_allclose(v,[visit])
    s,v=path_events(a,t,0,25);np.testing.assert_allclose(s,1);np.testing.assert_allclose(v,1)
    np.testing.assert_allclose(m.sum(-1),1)


def test_teacher_labels_only_affect_the_immediately_following_conditional():
    torch.manual_seed(17);model=PathModel().eval();x=torch.randn(2,SHORT_WIDTH);previous=torch.zeros(2,14,dtype=torch.long)
    with torch.no_grad():before,_=model(x,previous);previous[:,7]=20;after,_=model(x,previous)
    unchanged=[i for i in range(15) if i!=8]
    torch.testing.assert_close(before[:,unchanged],after[:,unchanged]);assert not torch.equal(before[:,8],after[:,8])


def test_independent_control_ignores_previous_bins_and_forecast_never_needs_labels():
    torch.manual_seed(17);model=PathModel('independent_control').eval();x=torch.randn(2,SHORT_WIDTH)
    with torch.no_grad():a,_=model(x,torch.zeros(2,14,dtype=torch.long));b,_=model(x,torch.full((2,14),25,dtype=torch.long))
    torch.testing.assert_close(a,b)
    initial,t,m,_=forecast(model,x.numpy(),np.ones(15),'cpu')
    np.testing.assert_allclose(m,a.softmax(-1).numpy(),atol=1e-6)
    np.testing.assert_allclose(t.sum(-1),1,atol=1e-6)


def test_checkpoint_forecasts_and_gradients_are_reproducible(tmp_path):
    torch.manual_seed(43);model=PathModel();x=torch.randn(2,SHORT_WIDTH);y=torch.randint(26,(2,15));z,c=model(x,y[:,:-1])
    loss=torch.nn.functional.cross_entropy(z.reshape(-1,26),y.reshape(-1));loss.backward()
    assert torch.isfinite(loss) and model.previous.weight.grad.abs().sum()>0
    model.eval();expected=forecast(model,x.numpy(),np.ones(15),'cpu')[2]
    path=tmp_path/'weights.pt';torch.save(model.state_dict(),path);other=PathModel().eval();other.load_state_dict(torch.load(path,weights_only=True))
    np.testing.assert_allclose(forecast(other,x.numpy(),np.ones(15),'cpu')[2],expected,atol=1e-7)


def test_count_baseline_smoothing_and_event_bounds():
    y=np.tile(np.arange(15),(20,1));a,t=fit_chain(y)
    np.testing.assert_allclose(a.sum(),1);np.testing.assert_allclose(t.sum(-1),1)
    assert (t>0).all() and t[0,0,1]>t[0,0,0]
    with pytest.raises(ValueError):path_events(a[None],t[None],10,9)
