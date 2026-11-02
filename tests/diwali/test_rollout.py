import numpy as np
import torch
from research.diwali.rollout import rollout
from research.market_data.build_pilot import WARMUP,feature_dtype
from research.diwali.train import Data


class Spy(torch.nn.Module):
    def __init__(self):super().__init__();self.inputs=[]
    def forward(self,x):
        self.inputs.append(x.detach().numpy().copy())
        return torch.tensor([[0.,3.,-1.,2.]])


def fixture():
    d=Data.__new__(Data)
    d.candles=np.zeros((1500,8),dtype=np.float32)
    d.raw=np.tile([100.,101.,99.,100.,1.,100.,2.],(1500,1))
    d.book=np.zeros(120,dtype=feature_dtype('book'));d.trades=np.zeros(120,dtype=feature_dtype('trades'))
    d.scalers={k:{'mean':[0]*n,'std':[1]*n} for k,n in [('candles',8),('book',87),('trades',5)]}
    row=np.array([WARMUP+1440*60000+15000,WARMUP+1441*60000,1440,0,60])
    return d,row


def test_rollout_uses_its_own_forecast_and_keeps_consecutive_history():
    d,row=fixture();m=Spy();r=rollout(d,m,row)
    assert len(r['candles'])==len(r['feedback'])==len(m.inputs)==15
    assert len(r['bridges'])==1 and r['bridges'][0]['time']==WARMUP+1440*60000
    assert r['candles'][1]['ohlc'][3]==100*(1.0002**2)
    np.testing.assert_allclose(m.inputs[1][0,:1440*8].reshape(1440,8)[-1,0],np.log(1.0002),rtol=1e-5)
    assert all(x['context_length']==1440 for x in r['feedback'])
    assert np.diff([c['time'] for c in r['candles']]).tolist()==[60000]*14
    assert r['future_actuals_used'] is False and r['uncertainty_calibrated_for_15_steps'] is False


def test_future_observations_cannot_change_any_rollout_step_and_sources_unchanged():
    d,row=fixture();before=d.candles.copy();a=rollout(d,Spy(),row)
    np.testing.assert_equal(d.candles,before)
    d.raw[1440:]=1e9;d.candles[1440:]=1e9;d.book['x'][60:]=1e9;d.trades['x'][60:]=1e9
    b=rollout(d,Spy(),row)
    assert a==b
