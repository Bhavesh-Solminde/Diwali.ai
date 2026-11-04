"""Diwali0.9: frozen calibrated parent plus a controlled recent-candle residual."""
import json
from pathlib import Path

import numpy as np
import torch
from torch import nn

from .fan import FanModel
from .model import CANDLE_SIZE
from .path import PathModel
from .coupled import reconcile
from .probability import probabilities
from ..market_data.validate_archive import file_hash


class RecentResidual(nn.Module):
    def __init__(self,mode):
        super().__init__()
        if mode not in ['grouped','minute_detail']:raise ValueError('Unknown residual mode')
        self.mode=mode;self.sequence=nn.GRU(8,16,batch_first=True);self.head=nn.Linear(16,15*26);self.colour=nn.Linear(16,3)
        # Epoch zero is the exact parent; both controls start with zero correction.
        nn.init.zeros_(self.head.weight);nn.init.zeros_(self.head.bias);nn.init.zeros_(self.colour.weight);nn.init.zeros_(self.colour.bias)

    def inputs(self,x):
        recent=x[:,:CANDLE_SIZE].reshape(-1,1440,8)[:,-60:]
        if self.mode=='grouped':recent=recent.reshape(-1,4,15,8).mean(2).repeat_interleave(15,dim=1)
        return recent

    def forward(self,x):
        _,h=self.sequence(self.inputs(x));return self.head(h[-1]).reshape(-1,15,26),self.colour(h[-1])


class RefinedMarginal(nn.Module):
    def __init__(self,mode,parent):
        super().__init__();self.parent=FanModel();self.residual=RecentResidual(mode)
        if file_hash(Path(parent['checkpoint']))!=parent['checkpoint_sha256'] or file_hash(Path(parent['root'])/'report.json')!=parent['report_sha256']:raise ValueError('Changed marginal parent')
        self.parent.load_state_dict(torch.load(parent['checkpoint'],map_location='cpu',weights_only=True)['state_dict']);self.parent.requires_grad_(False)
        self.register_buffer('parent_temperatures',torch.tensor(parent['temperatures'],dtype=torch.float32)[None,:,None]);self.parent_colour_temperature=parent['colour_temperature']

    def forward(self,x):
        with torch.no_grad():z,c=self.parent(x)
        a,b=self.residual(x);return z/self.parent_temperatures+a,c/self.parent_colour_temperature+b


class RefinedJoint(nn.Module):
    def __init__(self,mode,checkpoint,config,temperatures):
        super().__init__();self.marginal=RefinedMarginal(mode,config['marginal']);self.dependence=PathModel('markov');self.config=config;self.temperatures=temperatures
        self.marginal.residual.load_state_dict(torch.load(checkpoint,map_location='cpu',weights_only=True)['state_dict'])
        p=config['dependence']
        if file_hash(Path(p['checkpoint']))!=p['checkpoint_sha256'] or file_hash(Path(p['root'])/'report.json')!=p['report_sha256']:raise ValueError('Changed dependence parent')
        self.dependence.load_state_dict(torch.load(p['checkpoint'],map_location='cpu',weights_only=True)['state_dict'])
        self.maximum_difference=0.;self.maximum_iterations=0

    def all_transitions(self,x):
        z,c=self.marginal(x);_,t,_=self.dependence.all_transitions(x);z=z.detach().cpu().numpy();t=t.detach().cpu().numpy()
        m=np.stack([probabilities(z[:,h],self.temperatures[h]) for h in range(15)],1)
        prior=np.stack([probabilities(t[:,h],self.config['dependence']['temperatures'][h+1]) for h in range(14)],1)
        a,b,ledger=reconcile(m,prior,1.);self.maximum_difference=max(self.maximum_difference,ledger['maximum_marginal_difference']);self.maximum_iterations=max(self.maximum_iterations,ledger['iterations'])
        return torch.from_numpy(np.log(a)),torch.from_numpy(np.log(b)),c


def cached_logits(model,part,device):
    model.eval();aa=[];bb=[]
    with torch.inference_mode():
        for start in range(0,len(part['x']),128):
            x=torch.tensor(np.array(part['x'][start:start+128]),device=device);a,b=model(x)
            aa.append(a.cpu().numpy()+part['base'][start:start+128]);bb.append(b.cpu().numpy()+part['base_colour'][start:start+128])
    return np.concatenate(aa),np.concatenate(bb)
