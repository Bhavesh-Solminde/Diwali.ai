import torch
from research.diwali.event_model import EventModel


def test_all_inputs_trainable_no_parent_and_tail_reaches_forecast():
    torch.manual_seed(17)
    for mode in ['temporal_conv','attention']:
        model=EventModel(mode,width=16,block=8);events=torch.randn(1,19,103,requires_grad=True);mask=torch.ones(1,19,dtype=torch.bool);candles=torch.randn(1,1440,8,requires_grad=True);seed=torch.randn(1,80,requires_grad=True)
        reference=torch.zeros(1,1,requires_grad=True)
        groups=torch.arange(19)[None];logits=model(events,mask,candles,seed,groups,torch.ones(1,1440,dtype=torch.bool),reference);assert logits.shape==(1,15,26)
        logits.square().mean().backward()
        assert events.grad[0,-1].abs().sum()>0 and candles.grad.abs().sum()>0 and seed.grad.abs().sum()>0
        assert reference.grad.abs().sum()>0
        assert all(p.requires_grad for p in model.parameters()) and not hasattr(model,'parent')
        assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())
        torch.testing.assert_close(logits.softmax(-1).sum(-1),torch.ones(1,15))


def test_padded_values_cannot_change_probabilities():
    torch.manual_seed(29);model=EventModel(width=16,block=8).eval();a=torch.randn(2,19,103);mask=torch.arange(19)[None,:]<torch.tensor([19,9])[:,None];c=torch.randn(2,1440,8);s=torch.randn(2,80)
    b=a.clone();b[~mask]=100000
    groups=torch.arange(19)[None].expand(2,-1).clone();groups[~mask]=0
    cm=torch.ones(2,1440,dtype=torch.bool)
    torch.testing.assert_close(model(a,mask,c,s,groups,cm,torch.zeros(2,1)),model(b,mask,c,s,groups,cm,torch.zeros(2,1)))


def test_equal_time_permutation_cannot_invent_causal_order():
    torch.manual_seed(43);model=EventModel(width=16,block=8).eval();a=torch.randn(1,19,103);m=torch.ones(1,19,dtype=torch.bool);g=(torch.arange(19)//3)[None];c=torch.randn(1,1440,8);s=torch.randn(1,80)
    permutation=torch.arange(19);permutation[:3]=torch.tensor([2,0,1]);b=a[:,permutation]
    cm=torch.ones(1,1440,dtype=torch.bool)
    torch.testing.assert_close(model(a,m,c,s,g,cm,torch.zeros(1,1)),model(b,m,c,s,g,cm,torch.zeros(1,1)),atol=1e-6,rtol=1e-5)


def test_unavailable_candle_values_cannot_affect_forecast():
    torch.manual_seed(17);model=EventModel(width=16,block=8).eval();a=torch.randn(1,19,103);m=torch.ones(1,19,dtype=torch.bool);g=torch.arange(19)[None];c=torch.randn(1,1440,8);s=torch.randn(1,80);cm=torch.ones(1,1440,dtype=torch.bool);cm[:,20:25]=False
    other=c.clone();other[:,20:25]=float('nan')
    torch.testing.assert_close(model(a,m,c,s,g,cm,torch.zeros(1,1)),model(a,m,other,s,g,cm,torch.zeros(1,1)))
