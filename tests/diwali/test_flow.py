import torch
from research.diwali.flow import FlowResidual
from research.diwali.model import CANDLE_SIZE,BOOK_SIZE


def test_flow_input_layout_and_candle_exclusion():
    x=torch.zeros(2,17041);x[:,CANDLE_SIZE:CANDLE_SIZE+BOOK_SIZE]=1;x[:,CANDLE_SIZE+BOOK_SIZE:-1]=2
    model=FlowResidual('flow_sequence');v=model.inputs(x);assert v.shape==(2,60,92);assert (v[:,:,:87]==1).all() and (v[:,:,87:]==2).all()
    x[:,:CANDLE_SIZE]=999;x[:,-1]=777;torch.testing.assert_close(model.inputs(x),v)


def test_control_removes_order_but_keeps_channel_means_with_identical_capacity():
    x=torch.randn(2,17041);a=FlowResidual('mean_control');b=FlowResidual('flow_sequence');va=a.inputs(x);vb=b.inputs(x)
    torch.testing.assert_close(va[:,0],vb.mean(1));torch.testing.assert_close(va[:,0],va[:,-1]);assert not torch.allclose(vb[:,0],vb[:,-1])
    assert sum(p.numel() for p in a.parameters())==sum(p.numel() for p in b.parameters())
    for m in [a,b]:
        z,c=m(x);assert not z.any() and not c.any();loss=z[:,0].sum()+c.sum();loss.backward();assert torch.isfinite(m.head.weight.grad).all()
