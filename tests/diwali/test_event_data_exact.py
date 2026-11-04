import numpy as np
import pytest
from research.diwali.event_data import one_second
from research.diwali.event_data_exact import exact_one_second


def test_float_clock_rounding_cannot_put_valid_last_event_outside_window():
    ns=np.array([59999999999],np.int64);x=np.zeros((1,103),np.float32);x[:,84]=ns/10**9;x[:,81]=1
    assert x[0,84]==60.
    with pytest.raises(ValueError,match='outside60-second'):one_second(x)
    result=exact_one_second(x,ns)
    assert result[59,81]>0 and not result[:59,81].any()


def test_internal_boundary_uses_exact_clock_and_future_is_still_rejected():
    ns=np.array([1999999999,2000000000],np.int64);x=np.zeros((2,103),np.float32);x[:,84]=ns/10**9;x[:,81]=1
    result=exact_one_second(x,ns)
    assert result[1,81]==result[2,81] and result[1,81]>0
    with pytest.raises(ValueError,match='outside input window'):exact_one_second(x,np.array([0,60000000000],np.int64))
    with pytest.raises(ValueError,match='integer event times'):exact_one_second(x,ns.astype(float))
