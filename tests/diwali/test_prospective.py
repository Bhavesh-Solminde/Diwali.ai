import copy
import json

import numpy as np
import pytest

from research.diwali.prospective import book_features,live_input,exclusive_json,ForwardStore


def request_fixture():
    minute=1_800_000_000_000_000_000
    minute=minute//60_000_000_000*60_000_000_000
    at=minute+15_000_000_000;start=at-60_000_000_000
    levels={'bids':[[100-i*.01,2] for i in range(20)],
            'asks':[[100.1+i*.01,1] for i in range(20)],'top20_within_snapshot_bounds':True}
    candles=[]
    for i in range(1440):
        open_ms=minute//10**6-(1440-i)*60000
        candles.append({'open_ms':open_ms,'close_ms':open_ms+59999,'values':[100,101,99,100,2,200,2],
                        'available_ns':minute-1,'source':'test'})
    books=[];trades=[]
    for i in range(60):
        grid=start+i*10**9
        books.append({'grid_utc_ns':grid,'book':{'available_ns':grid-100_000_000,
            'source_receipt_ns':grid-100_000_000,'exchange_event_ms':grid//10**6-100,'levels':copy.deepcopy(levels)}})
        trade_ns=grid+500_000_000
        trades.append({'available_ns':trade_ns,'payload':{'p':'100.05','q':'1','m':False,'E':trade_ns//10**6,'T':trade_ns//10**6}})
    return {'snapshot_utc_ns':at,'candles':candles,'book_seconds':books,'trades':trades,'book_trade_window_ns':[start,at]}


def convert(request):
    scalers={name:{'mean':[0]*n,'std':[1]*n} for name,n in [('candles',8),('book',87),('trades',5)]}
    return live_input(request,scalers,{'delta_mean':0,'delta_std':1})


def test_live_converter_preserves_causal_shapes_reference_and_side():
    r=request_fixture();x,m=convert(r)
    assert x.shape==(17041,) and np.isfinite(x).all()
    assert m['reference']==pytest.approx(100.05,abs=1e-5)
    assert m['reference_age_seconds']==.5
    trades=x[1440*8+60*87:-1].reshape(60,5)
    assert np.all(trades[:,0]>0) and np.all(trades[:,1]==0)
    assert trades[-1,4]==pytest.approx(5,abs=.001)
    assert x[-1]==pytest.approx(5,abs=.001)


@pytest.mark.parametrize('kind',['candle','book','trade','stale_reference','candle_gap'])
def test_future_or_missing_input_is_rejected(kind):
    r=request_fixture()
    if kind=='candle':r['candles'][-1]['available_ns']=r['snapshot_utc_ns']
    elif kind=='book':r['book_seconds'][-1]['book']['source_receipt_ns']=r['snapshot_utc_ns']
    elif kind=='trade':r['trades'][-1]['payload']['E']=r['snapshot_utc_ns']//10**6
    elif kind=='stale_reference':r['trades']=r['trades'][:-3]
    else:r['candles'][50]['open_ms']+=1
    with pytest.raises(ValueError):convert(r)


def test_book_features_are_relative_and_depth_matches_quantity():
    levels=request_fixture()['book_seconds'][0]['book']['levels'];a=book_features(levels)
    for side in ['bids','asks']:
        for row in levels[side]:row[0]*=100
    np.testing.assert_allclose(book_features(levels),a,atol=1e-5)
    np.testing.assert_allclose(a[81:84],1/3,atol=1e-6)
    assert a.shape==(87,)


def test_committed_forecast_cannot_be_replaced(tmp_path):
    path=tmp_path/'forecast.json';digest=exclusive_json(path,{'a':1})
    assert len(digest)==64 and json.loads(path.read_text())=={'a':1}
    with pytest.raises(FileExistsError):exclusive_json(path,{'a':2})


def test_forward_labels_wait_for_close_and_do_not_repeat(tmp_path,monkeypatch):
    store=ForwardStore(tmp_path/'capture',tmp_path/'model')
    start=1_800_000_000_000;now=start*10**6+30_000_000_000
    monkeypatch.setattr('research.diwali.prospective.time.time_ns',lambda:now)
    probabilities=np.ones((15,26))/26
    store.pending['forecast.json']={'record':{'target_start_ns':start*10**6,
        'prediction':{'reference':100.,'bin_probabilities':probabilities.tolist()}},'done':set()}
    store.inputs.candles[start]={'close_ms':start+59999,'values':[100,101,99,100.01],
                                'available_ns':now-1,'source':'test'}
    store.score_matured();assert not store.outcomes  # Even a cached row must not score an unfinished minute.
    now+=60_000_000_000;store.inputs.candles[start]['available_ns']=now+1
    store.score_matured();assert not store.outcomes  # A closed row not yet received cannot be used.
    now+=2;store.score_matured();assert len(store.outcomes)==1
    result=store.outcomes[0];assert result['horizon']==1 and result['target_start_ms']==start
    assert result['actual_class']==1 and result['actual_return_bp']==pytest.approx(1)
    store.score_matured();assert len(store.outcomes)==1
    assert len(list((store.root/'outcomes').glob('*.json')))==1
    store.finish()
