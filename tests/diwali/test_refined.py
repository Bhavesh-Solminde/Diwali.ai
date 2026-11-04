import numpy as np
import torch
from research.diwali.refined import RecentResidual
from research.diwali.model import CANDLE_SIZE


def test_zero_heads_preserve_parent_and_both_arms_have_same_capacity():
    x=torch.randn(2,17041);a=RecentResidual('grouped');b=RecentResidual('minute_detail')
    assert sum(p.numel() for p in a.parameters())==sum(p.numel() for p in b.parameters())
    for model in [a,b]:
        z,c=model(x);assert z.shape==(2,15,26) and c.shape==(2,3);assert not z.any() and not c.any()


def test_grouped_control_removes_within_group_order_but_detail_retains_it():
    x=torch.zeros(1,17041);candles=x[:,:CANDLE_SIZE].reshape(1,1440,8);candles[:,-60:,0]=torch.arange(60)
    grouped=RecentResidual('grouped').inputs(x);detail=RecentResidual('minute_detail').inputs(x)
    torch.testing.assert_close(grouped[0,:15,0],torch.full((15,),7.));torch.testing.assert_close(detail[0,:,0],torch.arange(60,dtype=torch.float32))
    altered=x.clone();altered[:,CANDLE_SIZE:]=999;altered[:,:CANDLE_SIZE-60*8]=777
    torch.testing.assert_close(RecentResidual('minute_detail').inputs(altered),detail)


def test_finite_gradient_can_learn_without_training_the_parent():
    model=RecentResidual('minute_detail');x=torch.randn(3,17041);z,c=model(x);loss=torch.nn.functional.cross_entropy(z[:,0],torch.tensor([0,10,25]));loss.backward()
    assert torch.isfinite(model.head.weight.grad).all() and model.head.weight.grad.abs().sum()>0
