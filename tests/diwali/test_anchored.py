import numpy as np
import pytest
import torch
from research.diwali.anchored import AnchoredResidual,JoinedFeatures,OLD_WIDTH,augment_live
from research.market_data.midpoint import window_features
from research.market_data.midpoint_windows import summaries


def test_join_preserves_original_delta_and_handles_slices_and_indices():
    old=np.arange(3*OLD_WIDTH,dtype=np.float32).reshape(3,OLD_WIDTH);extra=np.array([[1,2],[3,4],[5,6]],np.float32);data=JoinedFeatures(old,extra)
    np.testing.assert_array_equal(data[:2][:,:OLD_WIDTH],old[:2]);np.testing.assert_array_equal(data[[2,0]][:,-2:],extra[[2,0]])
    assert data[1][OLD_WIDTH-1]==old[1,-1] and len(data)==3


def test_midpoint_control_has_matching_capacity_but_no_midpoint_information():
    x=torch.randn(2,OLD_WIDTH+2);other=x.clone();other[:,-2:]+=100
    a=AnchoredResidual('no_midpoint');b=AnchoredResidual('with_midpoint');assert sum(p.numel() for p in a.parameters())==sum(p.numel() for p in b.parameters())==18465
    torch.testing.assert_close(a.inputs(x),a.inputs(other));assert not torch.equal(b.inputs(x),b.inputs(other))
    for model in [a,b]:
        z,c=model(x);assert not z.any() and not c.any()
    with pytest.raises(ValueError):a(x[:,:OLD_WIDTH])


def request():
    at=100_000_000_000;start=at-60*10**9;rows=[]
    for i in range(60):
        mid=100+i*.01;levels={'bids':[[mid-.5-j,1] for j in range(20)],'asks':[[mid+.5+j,1] for j in range(20)],'top20_within_snapshot_bounds':True};grid=start+i*10**9
        rows.append({'grid_utc_ns':grid,'book':{'available_ns':grid,'source_receipt_ns':grid,'exchange_event_ms':grid//10**6,'levels':levels}})
    return {'snapshot_utc_ns':at,'book_trade_window_ns':[start,at],'book_seconds':rows,'candles':[{'values':[100,101,99,100,0,0,0],'available_ns':1,'close_ms':59999}]}


def test_live_midpoint_transform_matches_historical_definition_and_rejects_future():
    r=request();scaler={'mean':[1,2],'std':[3,4]};x=augment_live(r,np.zeros(OLD_WIDTH),scaler);expected=summaries(window_features(100+np.arange(60)*.01,100)[None])[0]
    np.testing.assert_allclose(x[-2:],(expected-[1,2])/[3,4],rtol=1e-6)
    r['book_seconds'][-1]['book']['available_ns']=r['snapshot_utc_ns']
    with pytest.raises(ValueError,match='Future/stale'):augment_live(r,np.zeros(OLD_WIDTH),scaler)
