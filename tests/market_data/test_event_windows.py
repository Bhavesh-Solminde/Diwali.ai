import numpy as np
import pytest
from research.market_data.event_replay import DTYPE as BOOK
from research.market_data.trade_events import DTYPE as TRADE
from research.market_data.event_windows import release_times,window


def sources():
    b=np.zeros(5,dtype=BOOK);b['receipt_ns']=[10,20,30,40,50];b['event_ns']=b['receipt_ns'];b['valid']=1;b['accepted_update']=1
    t=np.zeros(3,dtype=TRADE);t['receipt_ns']=[25,30,50];t['event_ns']=t['receipt_ns'];t['trade_ns']=t['receipt_ns']
    return b,t


def test_grouped_merge_seed_boundary_and_no_truncation():
    b,t=sources();a=window(b,t,20,50,max_stale_ns=20)
    assert a['book_seed_row']==0 and a['book_events']==3 and a['trade_rows']==2 and not a['truncated']
    assert a['events']['available_ns'].tolist()==[20,25,30,30,40]
    assert a['events']['time_group'].tolist()==[0,1,2,2,3]


def test_later_clock_event_blocks_following_source_rows():
    np.testing.assert_array_equal(release_times([10,20,30],[10,100,30]),[10,100,100])
    b,t=sources();b['event_ns'][2]=100
    a=window(b,t,20,50,max_stale_ns=40)
    assert a['events']['source_row'][a['events']['kind']==0].tolist()==[1]


def test_future_payload_does_not_change_window_and_markers_or_stale_rejected():
    b,t=sources();a=window(b,t,20,50,max_stale_ns=20);b['levels'][-1]=999;t['price'][-1]=999
    np.testing.assert_array_equal(a['events'],window(b,t,20,50,max_stale_ns=20)['events'])
    b['valid'][2]=0
    with pytest.raises(ValueError,match='invalid marker'):window(b,t,20,50,max_stale_ns=20)
    b['valid'][2]=1
    with pytest.raises(ValueError,match='Stale'):window(b,t,20,50,max_stale_ns=5)
