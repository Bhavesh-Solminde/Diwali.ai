import numpy as np
from research.diwali.event_data import Moments,normalize,one_second,labels


def test_streaming_fit_moments_equal_direct_and_no_test_values_enter():
    rng=np.random.default_rng(17);x=rng.normal(size=(31,3));m=Moments(3);m.add(x[:10]);m.add(x[10:]);r=m.record()
    np.testing.assert_allclose(r['mean'],x.mean(0),atol=1e-14)
    np.testing.assert_allclose(r['std'],x.std(0),atol=1e-14)
    test=np.full((4,3),10000.);normalize(test,r)
    np.testing.assert_allclose(r['mean'],x.mean(0),atol=1e-14)


def test_one_second_control_discards_trade_sequence_but_keeps_count_and_final_book():
    x=np.zeros((3,103),np.float32);x[:,84]=[.1,.2,1.1];x[:2,81]=1;x[2,80]=1;x[2,:80]=3
    x[:2,99]=[1,9];other=x.copy();other[:2,99]=[9,1]
    np.testing.assert_array_equal(one_second(x),one_second(other))
    out=one_second(x);assert out.shape==(60,103) and out[0,81]==np.float32(np.log1p(2))
    np.testing.assert_array_equal(out[1,:80],3*np.ones(80))


def test_zero_return_and_inclusive_positive_threshold_have_consistent_bins():
    x=np.zeros((2,15));x[0,0]=2;x[1,0]=-2;y=labels(x)
    assert y[0,0]==16 and y[1,0]==9 and y[0,1]==12
