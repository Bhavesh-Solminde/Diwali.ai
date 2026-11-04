import json

import numpy as np
import torch

from research.diwali.balanced import losses,calibrate_composite
from research.diwali.path import PathModel,propagate,chain_losses
from research.diwali.probability import probabilities
from research.diwali.multiscale import SHORT_WIDTH
from research.diwali.forward_follower import complete_lines


def test_differentiable_joint_and_marginal_scores_match_numpy_exact_recursion():
    torch.manual_seed(17);a=torch.randn(3,26,dtype=torch.float64,requires_grad=True);t=torch.randn(3,14,26,26,dtype=torch.float64,requires_grad=True);y=torch.randint(26,(3,15))
    j,m=losses(a,t,y);aa=probabilities(a.detach().numpy());tt=probabilities(t.detach().numpy());p=propagate(aa,tt)
    np.testing.assert_allclose(j.detach(),chain_losses(aa,tt,y.numpy()).mean()/15,atol=1e-10)
    expected=-np.log(np.take_along_axis(p,y.numpy()[:,:,None],2)).mean();np.testing.assert_allclose(m.detach(),expected,atol=1e-10)
    m.backward();assert torch.isfinite(a.grad).all() and torch.isfinite(t.grad).all();assert a.grad.abs().sum()>0 and t.grad.abs().sum()>0


def test_enumerated_joint_training_equals_shifted_conditional_likelihood():
    torch.manual_seed(29);model=PathModel('markov').eval();x=torch.randn(2,SHORT_WIDTH);y=torch.randint(26,(2,15))
    with torch.no_grad():a,t,_=model.all_transitions(x);z,_=model(x,y[:,:-1]);j,m=losses(a,t,y)
    torch.testing.assert_close(j,torch.nn.functional.cross_entropy(z.reshape(-1,26),y.reshape(-1)),atol=1e-6,rtol=1e-6)


def test_joint_control_optimization_has_same_parameter_gradients():
    torch.manual_seed(43);model=PathModel('markov');other=PathModel('markov');other.load_state_dict(model.state_dict());x=torch.randn(2,SHORT_WIDTH);y=torch.randint(26,(2,15))
    a,t,_=model.all_transitions(x);j,_=losses(a,t,y);j.backward()
    z,_=other(x,y[:,:-1]);torch.nn.functional.cross_entropy(z.reshape(-1,26),y.reshape(-1)).backward()
    for p,q in zip(model.parameters(),other.parameters()):
        if p.grad is not None:torch.testing.assert_close(p.grad,q.grad,atol=1e-6,rtol=1e-5)


def test_calibration_bound_hit_is_exposed_instead_of_silently_expanding_search():
    a=np.zeros((2,26));a[:,1]=8;t=np.zeros((2,14,26,26));t[:,:,:,1]=8;y=np.zeros((2,15),int)
    temp,ledger=calibrate_composite(a,t,y)
    assert temp==2. and ledger['bound_hit'] and ledger['selected_index']==40


def test_follower_does_not_consume_partial_source_record(tmp_path):
    p=tmp_path/'events.jsonl';first=json.dumps({'kind':'first'}).encode()+b'\n';second=json.dumps({'kind':'second'}).encode()
    p.write_bytes(first+second[:5]);rows,offset=complete_lines(p,0);assert rows==[{'kind':'first'}] and offset==len(first)
    with p.open('ab') as f:f.write(second[5:]+b'\n')
    rows,end=complete_lines(p,offset);assert rows==[{'kind':'second'}] and end==len(first)+len(second)+1
    assert complete_lines(p,end)==([],end)
