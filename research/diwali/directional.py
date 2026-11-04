"""Diwali1.0: coherent endpoint direction loss on an actual price distribution."""
from pathlib import Path
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from .refined import RefinedMarginal,RecentResidual
from .path import PathModel
from .probability import probabilities
from .coupled import reconcile
from ..market_data.validate_archive import file_hash


def net_loss(logits,labels):
    z=logits[:,-1];two=torch.stack([torch.logsumexp(z[:,:13],-1),torch.logsumexp(z[:,13:],-1)],-1)
    return F.cross_entropy(two,(labels[:,-1]>12).long())


def calibrate_endpoint(logits,labels):
    grid=np.exp(np.linspace(np.log(.5),np.log(2),41));y=(labels>12).astype(int);scores=[]
    for t in grid:
        p=probabilities(logits,t);q=np.stack([p[:,:13].sum(1),p[:,13:].sum(1)],1);scores.append(float(-np.log(np.maximum(q[np.arange(len(y)),y],1e-15)).mean()))
    i=int(np.argmin(scores));return float(grid[i]),{'grid':grid.tolist(),'binary_losses':scores,'index':i,'boundary_hit':i in [0,40]}


class DirectionalJoint(nn.Module):
    def __init__(self,checkpoint,parent,temperatures):
        super().__init__();self.parent=RefinedMarginal(parent['mode'],parent['config']['marginal']);self.branch=RecentResidual('minute_detail');self.dependence=PathModel('markov');self.temperatures=temperatures;self.parent_config=parent
        if file_hash(Path(parent['checkpoint']))!=parent['checkpoint_sha256'] or file_hash(Path(parent['root'])/'report.json')!=parent['report_sha256']:raise ValueError('Changed0.9 parent')
        self.parent.residual.load_state_dict(torch.load(parent['checkpoint'],map_location='cpu',weights_only=True)['state_dict'])
        self.branch.load_state_dict(torch.load(checkpoint,map_location='cpu',weights_only=True)['state_dict']);c=parent['config']['dependence']
        if file_hash(Path(c['checkpoint']))!=c['checkpoint_sha256'] or file_hash(Path(c['root'])/'report.json')!=c['report_sha256']:raise ValueError('Changed dependence parent')
        self.dependence.load_state_dict(torch.load(c['checkpoint'],map_location='cpu',weights_only=True)['state_dict']);self.maximum_difference=0.;self.maximum_iterations=0
        self.register_buffer('parent_t',torch.tensor(parent['temperatures'],dtype=torch.float32)[None,:,None])

    def all_transitions(self,x):
        z,c=self.parent(x);dz,dc=self.branch(x);z=z/self.parent_t+dz;c=c/self.parent_config['colour_temperature']+dc
        _,t,_=self.dependence.all_transitions(x);z=z.detach().cpu().numpy();t=t.detach().cpu().numpy()
        m=np.stack([probabilities(z[:,h],self.temperatures[h]) for h in range(15)],1);prior=np.stack([probabilities(t[:,h],self.parent_config['config']['dependence']['temperatures'][h+1]) for h in range(14)],1)
        a,b,l=reconcile(m,prior,1);self.maximum_difference=max(self.maximum_difference,l['maximum_marginal_difference']);self.maximum_iterations=max(self.maximum_iterations,l['iterations'])
        return torch.from_numpy(np.log(a)),torch.from_numpy(np.log(b)),c
