"""Diwali0.8: reconcile predicted marginals with a learned finite-state dependence kernel."""
import numpy as np


def reconcile(marginals,prior_transitions,gamma=1.,tol=1e-8,max_iterations=2000):
    """Positive matrix scaling; no actual future observations are accepted here.

    Scale each adjacent pair kernel to model-predicted row/column masses.
    Return a normalized Markov chain, and check its propagated marginals.
    """
    from .path import propagate
    m=np.asarray(marginals,dtype=np.float64);prior=np.asarray(prior_transitions,dtype=np.float64)
    if m.ndim!=3 or m.shape[1:]!=(15,26) or prior.shape!=(len(m),14,26,26):raise ValueError('Invalid coupling shapes')
    if not np.isfinite(m).all() or not np.isfinite(prior).all() or (m<=0).any() or (prior<0).any() or not 0<=gamma<=2:raise ValueError('Invalid coupling values')
    if not np.allclose(m.sum(-1),1,atol=1e-8,rtol=0) or not np.allclose(prior.sum(-1),1,atol=1e-5,rtol=0):raise ValueError('Unnormalized parent predictions')
    if gamma==0:
        t=np.broadcast_to(m[:,1:,None,:],prior.shape).copy()
        return m[:,0].copy(),t,{'iterations':0,'maximum_marginal_difference':float(abs(propagate(m[:,0],t)-m).max()),'relative_pair_error':0.}
    row=m[:,:-1].reshape(-1,26);col=m[:,1:].reshape(-1,26)
    kernel=np.exp(gamma*np.log(np.maximum(prior.reshape(-1,26,26),1e-30)))
    # Row scaling of a positive kernel changes no constrained coupling solution.
    kernel/=kernel.max(-1,keepdims=True);v=np.ones_like(col);error=float('inf')
    for iteration in range(1,max_iterations+1):
        u=row/np.einsum('nij,nj->ni',kernel,v)
        v=col/np.einsum('nij,ni->nj',kernel,u)
        if iteration%5==0 or iteration==max_iterations:
            actual_row=u*np.einsum('nij,nj->ni',kernel,v)
            error=float(np.max(np.abs(actual_row-row)/row))
            if error<=tol:break
    if error>tol:raise ValueError(f'Coupling did not converge: relative row error {error}')
    pairs=u[:,:,None]*kernel*v[:,None,:]
    transitions=pairs/pairs.sum(-1,keepdims=True);transitions=transitions.reshape(prior.shape)
    actual=propagate(m[:,0],transitions);difference=float(abs(actual-m).max())
    if difference>2e-7 or not np.isfinite(transitions).all():raise ValueError('Reconciled marginal invariant failed')
    return m[:,0].copy(),transitions,{'iterations':iteration,'maximum_marginal_difference':difference,'relative_pair_error':error}


def parent_config():
    import json
    from pathlib import Path
    from ..market_data.validate_archive import file_hash
    result={}
    for key,dirname in [('marginal','diwali0.5'),('dependence','diwali0.7')]:
        root=Path('data/models')/dirname;report=json.loads((root/'report.json').read_text());mode=report['selected_mode'];info=report['models'][mode];checkpoint=root/f'{mode}-17.pt'
        if file_hash(checkpoint)!=info['checkpoint_sha256']:raise ValueError('Changed parent checkpoint')
        result[key]={'root':str(root),'checkpoint':str(checkpoint),'checkpoint_sha256':file_hash(checkpoint),'report_sha256':file_hash(root/'report.json'),
                     'temperatures':info['temperatures'],'colour_temperature':info['colour_temperature']}
    return result


def make_model(config,gamma,device='cpu'):
    import json
    from pathlib import Path
    import torch
    from torch import nn
    from .fan import FanModel
    from .path import PathModel
    from .probability import probabilities
    from ..market_data.validate_archive import file_hash
    class CoupledModel(nn.Module):
        def __init__(self):
            super().__init__();self.marginal=FanModel();self.dependence=PathModel('markov');self.gamma=gamma;self.maximum_difference=0.;self.maximum_iterations=0
            for key,model in [('marginal',self.marginal),('dependence',self.dependence)]:
                c=config[key]
                if file_hash(Path(c['checkpoint']))!=c['checkpoint_sha256'] or file_hash(Path(c['root'])/'report.json')!=c['report_sha256']:raise ValueError('Changed frozen parent')
                model.load_state_dict(torch.load(c['checkpoint'],map_location='cpu',weights_only=True)['state_dict'])
        def all_transitions(self,x):
            z,colour=self.marginal(x);_,t,_=self.dependence.all_transitions(x);z=z.detach().cpu().numpy();t=t.detach().cpu().numpy()
            m=np.stack([probabilities(z[:,h],config['marginal']['temperatures'][h]) for h in range(15)],axis=1)
            prior=np.stack([probabilities(t[:,h],config['dependence']['temperatures'][h+1]) for h in range(14)],axis=1)
            a,b,ledger=reconcile(m,prior,gamma);self.maximum_difference=max(self.maximum_difference,ledger['maximum_marginal_difference']);self.maximum_iterations=max(self.maximum_iterations,ledger['iterations'])
            # Logs let the existing exact-chain interface normalize this one joint law.
            return torch.from_numpy(np.log(a)),torch.from_numpy(np.log(b)),colour
    return CoupledModel().to(device).eval()
