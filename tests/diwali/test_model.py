import numpy as np
import pytest
import torch
from research.diwali.model import Diwali,WIDTH
from research.diwali.train import Data
from research.market_data.build_pilot import feature_dtype


@pytest.mark.parametrize('architecture',['mlp','sequence'])
def test_checkpoint_roundtrip_preserves_real_inference_and_valid_candles(architecture,tmp_path):
    torch.manual_seed(17);model=Diwali(architecture,[2.,3.,3.,4.]).eval();x=torch.randn(2,WIDTH)
    with torch.no_grad():before=model(x)
    assert torch.isfinite(before).all()
    assert (before[:,1]>=torch.maximum(before[:,0],before[:,3])).all()
    assert (before[:,2]<=torch.minimum(before[:,0],before[:,3])).all()
    path=tmp_path/'weights.pt';torch.save(model.state_dict(),path)
    restored=Diwali(architecture,[2.,3.,3.,4.]);restored.load_state_dict(torch.load(path,weights_only=True));restored.eval()
    with torch.no_grad():torch.testing.assert_close(restored(x),before)


def test_model_feature_window_cannot_read_future_candle_or_trade_rows():
    d=Data.__new__(Data);d.raw=np.ones((1443,7))*100;d.candles=np.ones((1443,8))
    d.book=np.zeros(120,dtype=feature_dtype('book'));d.trades=np.zeros(120,dtype=feature_dtype('trades'))
    d.scalers={k:{'mean':[0]*w,'std':[1]*w} for k,w in [('candles',8),('book',87),('trades',5)]}
    row=np.array([0,0,1440,0,60]);before=d.feature(row)
    d.raw[1440:]=1e10;d.candles[1440:]=1e10;d.book['x'][60:]=1e10;d.trades['x'][60:]=1e10
    np.testing.assert_equal(d.feature(row),before)
    d.candles[1439,0]+=1
    assert not np.array_equal(d.feature(row),before)
