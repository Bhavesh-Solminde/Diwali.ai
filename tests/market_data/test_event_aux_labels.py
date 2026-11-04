import numpy as np
from research.market_data.event_aux_labels import endpoint_price
from research.market_data.trade_events import DTYPE


def test_auxiliary_endpoint_is_strict_and_ignores_future_or_nonmarket_price():
    rows=np.zeros(3,dtype=DTYPE);rows['price']=[10000000000,99900000000,99900000000];rows['nonmarket'][1]=1
    times=np.array([10,15,20])*10**9
    assert endpoint_price(rows,times,12*10**9)==100.
    assert endpoint_price(rows,times,20*10**9) is None
    assert endpoint_price(rows,times,9*10**9,last_market=(8*10**9,9900000000))==99.
