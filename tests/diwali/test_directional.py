import numpy as np
import torch
from research.diwali.directional import net_loss,calibrate_endpoint


def test_binary_objective_is_exactly_summed_price_probability_loss():
    torch.manual_seed(17);z=torch.randn(5,15,26,requires_grad=True);y=torch.zeros(5,15,dtype=torch.long);y[:,-1]=torch.tensor([0,12,13,19,25]);p=z[:,-1].softmax(-1);q=torch.stack([p[:,:13].sum(1),p[:,13:].sum(1)],1)
    expected=-q[torch.arange(5),(y[:,-1]>12).long()].log().mean();actual=net_loss(z,y);torch.testing.assert_close(actual,expected);actual.backward();assert torch.isfinite(z.grad).all();assert z.grad[:,:-1].abs().sum()==0;assert z.grad[:,-1].abs().sum()>0


def test_endpoint_calibration_selects_full_histogram_temperature():
    rng=np.random.default_rng(17);z=rng.normal(size=(100,26));y=rng.integers(0,26,100);t,ledger=calibrate_endpoint(z,y);assert .5<=t<=2;assert ledger['binary_losses'][ledger['index']]==min(ledger['binary_losses'])
