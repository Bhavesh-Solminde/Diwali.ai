import numpy as np
from research.market_data.event_features import price_changes,build,NAMES
from research.market_data.event_replay import DTYPE as BOOK
from research.market_data.trade_events import DTYPE as TRADE
from research.market_data.event_windows import window


def test_matching_by_price_does_not_treat_rank_shift_as_qty_change():
    previous=np.array([[100-i,100000000] for i in range(20)]);current=previous.copy();current[:,0]+=1
    out=price_changes(previous,current)
    np.testing.assert_allclose(out,[0,0,np.log(2),np.log(2),.95])
    current[1,1]+=200000000
    assert price_changes(previous,current)[0]>0


def sample():
    b=np.zeros(4,dtype=BOOK);b['receipt_ns']=[10,20,30,50];b['event_ns']=b['receipt_ns'];b['valid']=1;b['accepted_update']=1
    for i in range(4):b['levels'][i]=np.array([[100-j,1,101+j,2] for j in range(20)])*100000000
    t=np.zeros(3,dtype=TRADE);t['receipt_ns']=[25,30,50];t['event_ns']=t['receipt_ns'];t['trade_ns']=t['receipt_ns'];t['price']=10000000000;t['quantity']=100000000;t['buyer_maker']=[0,1,0]
    return b,t


def test_trade_side_feature_width_and_future_poison_invariance():
    b,t=sample();s=window(b,t,20,50,max_stale_ns=30);a=build(b,t,s,20,50)
    assert a['features'].shape==(4,len(NAMES)) and not a['truncated']
    qty=a['features'][:,NAMES.index('signed_log_trade_quantity')];assert (qty>0).sum()==1 and (qty<0).sum()==1
    b['levels'][-1]=999;t['price'][-1]=999
    c=build(b,t,window(b,t,20,50,max_stale_ns=30),20,50)
    np.testing.assert_array_equal(a['features'],c['features'])


def test_same_time_trade_cannot_read_book_payload_as_if_after_it():
    b,t=sample();s=window(b,t,20,50,max_stale_ns=30);a=build(b,t,s,20,50)
    b['levels'][2,:,1]*=5;c=build(b,t,s,20,50)
    trade=s['events']['kind']==1
    np.testing.assert_array_equal(a['features'][trade],c['features'][trade])
