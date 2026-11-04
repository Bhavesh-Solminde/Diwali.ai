import numpy as np
import pytest

from research.diwali.coupled import reconcile
from research.diwali.path import propagate,path_events


def predictions():
    rng=np.random.default_rng(17);m=rng.dirichlet(np.ones(26),size=(2,15));t=rng.dirichlet(np.ones(26),size=(2,14,26));return m,t


def test_reconciled_joint_preserves_every_predicted_marginal():
    m,t=predictions();a,b,ledger=reconcile(m,t,1.5)
    np.testing.assert_allclose(b.sum(-1),1,atol=1e-12);np.testing.assert_allclose(propagate(a,b),m,atol=2e-8)
    assert ledger['maximum_marginal_difference']<2e-8
    s,v=path_events(a,b,0,25);np.testing.assert_allclose(s,1);np.testing.assert_allclose(v,1)


def test_zero_dependence_is_independent_product_and_fixed_chain_is_preserved():
    m,t=predictions();a,b,_=reconcile(m,t,0);np.testing.assert_allclose(b[:,:,0],m[:,1:])
    original=propagate(m[:,0],t);a,b,_=reconcile(original,t,1)
    np.testing.assert_allclose(b,t,atol=1e-8)


def test_explicit_nonconvergence_and_invalid_predictions_are_not_silently_returned():
    m,t=predictions()
    with pytest.raises(ValueError,match='did not converge'):reconcile(m,t,2,max_iterations=1)
    with pytest.raises(ValueError):reconcile(m*2,t)
    with pytest.raises(ValueError):reconcile(m,t,-1)
