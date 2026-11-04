import numpy as np
import pytest
from research.market_data.event_features import build as slow,price_changes
from research.market_data.event_features_fast import build as fast,changes
from research.market_data.event_replay import DTYPE as BOOK
from research.market_data.trade_events import DTYPE as TRADE
from research.market_data.event_windows import window


def test_vectorized_price_matching_agrees_with_dictionary_reference():
    rng=np.random.default_rng(29);a=[];b=[]
    for i in range(150):
        a.append(np.stack([rng.choice(np.arange(100,150),20,replace=False),rng.integers(1,10**9,size=20)],1))
        b.append(np.stack([rng.choice(np.arange(100,150),20,replace=False),rng.integers(1,10**9,size=20)],1))
    actual=changes(np.array(a),np.array(b));expected=np.stack([price_changes(x,y) for x,y in zip(a,b)])
    np.testing.assert_allclose(actual,expected,rtol=1e-14,atol=1e-14)


def test_full_event_features_match_with_group_ties_rank_changes_and_nonmarket():
    b=np.zeros(31,dtype=BOOK);b['receipt_ns']=np.arange(1,32)*10**8;b['event_ns']=b['receipt_ns'];b['valid']=b['accepted_update']=1
    for i in range(len(b)):
        shift=i%5
        b['levels'][i,:,0]=(10000+shift-np.arange(20))*10**8
        b['levels'][i,:,2]=(10002+shift+np.arange(20))*10**8
        b['levels'][i,:,1]=np.arange(1,21)*10**8+i*100
        b['levels'][i,:,3]=np.arange(2,22)*10**8+i*100
    t=np.zeros(15,dtype=TRADE);t['receipt_ns']=np.arange(2,32,2)*10**8;t['event_ns']=t['trade_ns']=t['receipt_ns'];t['price']=10000*10**8;t['quantity']=10**8;t['buyer_maker'][::2]=1;t['nonmarket'][::3]=1
    start,cut=2*10**8,31*10**8;chosen=window(b,t,start,cut)
    a=slow(b,t,chosen,start,cut);c=fast(b,t,chosen,start,cut)
    np.testing.assert_array_equal(a['features'],c['features'])
    np.testing.assert_array_equal(a['seed_features'],c['seed_features'])
