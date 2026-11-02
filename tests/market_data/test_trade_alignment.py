from decimal import Decimal
import numpy as np
import pytest
from research.market_data.trade_alignment import additive,transform,live_features
from research.market_data.button_baselines import predict
from research.market_data.build_pilot import feature_dtype


def test_same_price_side_fill_splitting_cannot_change_common_features():
    individual=[('100','1',False),('100','2',False),('101','4',True)]
    grouped=[('100','3',False),('101','4',True)]
    assert additive(individual)==additive(grouped)
    np.testing.assert_equal(transform([additive(individual)],100),transform([additive(grouped)],100))
    assert len(transform([additive(individual)],100)[0])==5


def test_live_adapter_uses_total_q_not_non_rpi_nq_and_no_message_counts():
    request={'snapshot_utc_ns':61*10**9,'book_trade_window_ns':[0,60*10**9],
        'trades':[{'available_ns':1_100_000_000,'payload':{'p':'100','q':'3','nq':'1','m':False,'E':1000,'T':999}}]}
    actual=live_features(request,100)
    expected=np.zeros((60,4));expected[1]=[3,0,300,0]
    np.testing.assert_allclose(actual,transform(expected,100))
    assert actual.shape==(60,5) and np.isfinite(actual).all()
    request['trades'][0]['available_ns']=60*10**9
    with pytest.raises(ValueError):live_features(request,100)


def test_empty_seconds_have_zero_vwap_offset_and_bad_values_rejected():
    assert np.all(transform(np.zeros((60,4)),100)==0)
    with pytest.raises(ValueError):transform([[1,-1,100,0]],100)
    with pytest.raises(ValueError):additive([('NaN','1',False)])


def test_new_baselines_do_not_read_future_target_rows():
    raw=np.array([[100,102,99,101,1,1,1],[101,104,100,103,1,1,1],[103,200,1,150,1,1,1.]])
    idx=np.array([[0,0,2,0,60]])
    b=np.zeros(60,dtype=feature_dtype('book'));t=np.zeros(60,dtype=feature_dtype('trades'))
    t['x'][59,:4]=[2,0,210,0]
    before=predict(raw,idx,b,t,1);raw[2]=999
    after=predict(raw,idx,b,t,1)
    for name in before:np.testing.assert_equal(before[name],after[name])
    assert before['recent_vwap_persistence'][0,0]==pytest.approx((105/103-1)*10000)


def test_alignment_gate_requires_meaningful_overlap_and_zero_conflicts():
    from research.market_data.trade_alignment import probe_gate
    assert probe_gate(1000,100,1020,[],[])
    assert not probe_gate(1,0,1,[],[])
    assert not probe_gate(100,20,200,[],[])
    assert not probe_gate(1000,100,1020,[123],[])
    assert not probe_gate(1000,100,1020,[],['network error'])
