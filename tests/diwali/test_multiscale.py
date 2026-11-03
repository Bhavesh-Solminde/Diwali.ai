import numpy as np
import torch
from research.diwali.multiscale import prefix_sources,context,MultiModel,SHORT_WIDTH,LONG_WIDTH
from research.market_data.build_pilot import feature_dtype


def test_context_causality_missing_prefix_and_invalid_seconds(tmp_path):
    b=np.zeros(180,dtype=feature_dtype('book'));t=np.zeros(180,dtype=feature_dtype('trades'))
    for a in [b,t]:a['time_ns']=np.arange(180)*10**9;a['valid']=1
    b['x'][:,80:]=2;t['x'][:,:4]=[2,1,200,100]
    p=prefix_sources(b,t,tmp_path);before=context(p,120,100)
    assert before.shape==(84,24)
    np.testing.assert_allclose(before[59,:7],2)
    np.testing.assert_allclose(before[59,14:18],np.log1p([120,60,12000,6000]),rtol=1e-6)
    assert before[0,23]==0 and before[59,23]==1
    b['x'][120:]=1e8;t['x'][120:]=1e8
    p=prefix_sources(b,t,tmp_path);np.testing.assert_array_equal(before,context(p,120,100))
    b['valid'][60:120]=0;t['event_ns'][60:120]=10**15
    p=prefix_sources(b,t,tmp_path);bad=context(p,120,100)
    assert (bad[59,:20]==0).all() and bad[59,20]==0 and bad[59,21]==0


def test_long_history_can_affect_multiscale_but_not_matched_short_control():
    torch.manual_seed(17);a=MultiModel('multiscale').eval();b=MultiModel('short_control').eval();b.load_state_dict(a.state_dict())
    x=torch.randn(2,SHORT_WIDTH+LONG_WIDTH);other=x.clone();other[:,SHORT_WIDTH:]+=2
    with torch.no_grad():
        torch.testing.assert_close(b(x),b(other))
        assert not torch.allclose(a(x),a(other))
        assert a(x).shape==(2,2,3)


def test_checkpoint_roundtrip_and_comparison_capacity(tmp_path):
    torch.manual_seed(29);model=MultiModel('multiscale').eval()
    x=torch.randn(1,SHORT_WIDTH+LONG_WIDTH)
    path=tmp_path/'checkpoint.pt'
    torch.save({'mode':'multiscale','state_dict':model.state_dict()},path)
    saved=torch.load(path,map_location='cpu',weights_only=True)
    restored=MultiModel(saved['mode']).eval();restored.load_state_dict(saved['state_dict'])
    with torch.no_grad():torch.testing.assert_close(model(x),restored(x))
    control=MultiModel('short_control')
    assert sum(p.numel() for p in control.parameters())==sum(p.numel() for p in model.parameters())==19532
