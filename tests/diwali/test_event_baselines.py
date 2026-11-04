import numpy as np
from research.diwali.event_baselines import histogram,summary,full_class_probabilities


def test_histogram_smoothing_and_absent_tree_classes_keep_all26_bins():
    y=np.zeros((10,15),np.int64);h=histogram(y)
    assert h.shape==(15,26) and (h>0).all()
    np.testing.assert_allclose(h.sum(-1),1.)
    class Fake:
        classes_=np.array([0,25])
        def predict_proba(self,x):return np.tile([.25,.75],(len(x),1))
    p=full_class_probabilities(Fake(),np.zeros((3,2)))
    assert p.shape==(3,26) and (p>0).all()
    np.testing.assert_allclose(p.sum(1),1.)


def test_summary_excludes_masked_candle_payload():
    e=np.zeros((3,103),np.float32);e[:,80]=1
    c=np.ones((1440,8),np.float32);m=np.ones(1440,bool);m[0]=False
    raw=(e,np.arange(3),c,m,np.zeros(80),np.zeros(1))
    x,v=summary(raw);c[0]=float('nan');other,w=summary(raw)
    np.testing.assert_array_equal(x,other);assert v==w
