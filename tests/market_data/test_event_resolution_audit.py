import numpy as np
from research.market_data.event_resolution_audit import event_starts
from research.market_data.event_resolution_audit import market_mask
import pyarrow as pa


def test_batch_boundary_does_not_double_count_a_multi_level_update():
    first=np.array([[10,1,9],[10,1,9],[11,1,10]])
    second=np.array([[11,1,10],[11,1,10],[11,2,11]])
    a,last=event_starts(first);b,last=event_starts(second,last)
    np.testing.assert_array_equal(a,[True,False,True]);np.testing.assert_array_equal(b,[False,False,True])
    combined,_=event_starts(np.concatenate([first,second]));np.testing.assert_array_equal(combined,np.r_[a,b])


def test_empty_batch_keeps_previous_identity():
    previous=np.array([1,2,3]);mask,last=event_starts(np.empty((0,3)),previous)
    assert not len(mask);np.testing.assert_array_equal(last,previous)


def test_na_positive_trade_is_not_a_zero_placeholder():
    b=pa.record_batch({'price':['100','0','100','100'],'quantity':['1','0','1','1'],'order_type':['NA','NA','ADL','MARKET']})
    assert market_mask(b).to_pylist()==[True,False,False,True]
