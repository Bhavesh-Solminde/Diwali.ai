import numpy as np
import torch
from research.diwali.fan import range_labels,collapse18,direction,target_rows,FanModel
from research.diwali.distribution import range_labels as labels18,direction as direction18
from research.diwali.multiscale import SHORT_WIDTH
from research.market_data.build_pilot import WARMUP


def test_expanded_bins_collapse_to_original18_and_directions():
    r=np.r_[np.linspace(-200,200,10001),-2,-2+1e-8,2-1e-8,2]
    bins=range_labels(r);onehot=np.eye(26)[bins]
    np.testing.assert_array_equal(collapse18(onehot).argmax(1),labels18(r))
    np.testing.assert_array_equal(direction(onehot),direction18(collapse18(onehot)))


def test_target_windows_exclude_split_crossings_and_missing_contents():
    raw=np.ones((60,7));valid=np.ones(60,bool);idx=np.zeros((3,5),np.int64);idx[:,1]=WARMUP+np.array([0,14,15])*60000
    keep,rows,ledger=target_rows(idx,raw,valid,WARMUP+29*60000)
    np.testing.assert_array_equal(keep,[True,True,False]);assert rows[1,-1]==28
    valid[20]=False;keep,_,ledger=target_rows(idx,raw,valid,WARMUP+29*60000)
    np.testing.assert_array_equal(keep,[True,False,False]);assert ledger['bad_future_label_content']==1


def test_fifteen_direct_outputs_are_normalized_and_checkpoint_reproducible(tmp_path):
    torch.manual_seed(17);model=FanModel().eval();x=torch.randn(2,SHORT_WIDTH)
    with torch.no_grad():z,c=model(x);p=z.softmax(-1).numpy()
    assert p.shape==(2,15,26) and c.shape==(2,3)
    np.testing.assert_allclose(p.sum(-1),1,atol=1e-6)
    path=tmp_path/'fan.pt';torch.save(model.state_dict(),path);other=FanModel().eval();other.load_state_dict(torch.load(path,weights_only=True))
    with torch.no_grad():torch.testing.assert_close(other(x)[0],z)
