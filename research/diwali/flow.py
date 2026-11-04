"""Diwali1.1: direct order-book/trade sequence correction with a mean control."""
from pathlib import Path
import torch
from torch import nn
from .model import CANDLE_SIZE,BOOK_SIZE
from .directional import DirectionalJoint
from .refined import RefinedMarginal
from .path import PathModel
from ..market_data.validate_archive import file_hash


class FlowResidual(nn.Module):
    def __init__(self,mode):
        super().__init__()
        if mode not in ['mean_control','flow_sequence']:raise ValueError('Unknown flow mode')
        self.mode=mode;self.sequence=nn.GRU(92,24,batch_first=True);self.head=nn.Linear(24,15*26);self.colour=nn.Linear(24,3)
        nn.init.zeros_(self.head.weight);nn.init.zeros_(self.head.bias);nn.init.zeros_(self.colour.weight);nn.init.zeros_(self.colour.bias)

    def inputs(self,x):
        b=x[:,CANDLE_SIZE:CANDLE_SIZE+BOOK_SIZE].reshape(-1,60,87);t=x[:,CANDLE_SIZE+BOOK_SIZE:-1].reshape(-1,60,5);flow=torch.cat([b,t],-1)
        return flow.mean(1,keepdim=True).expand(-1,60,-1) if self.mode=='mean_control' else flow

    def forward(self,x):
        _,h=self.sequence(self.inputs(x));return self.head(h[-1]).reshape(-1,15,26),self.colour(h[-1])


class FlowJoint(DirectionalJoint):
    def __init__(self,checkpoint,parent,temperatures,mode):
        nn.Module.__init__(self);self.parent=RefinedMarginal(parent['mode'],parent['config']['marginal']);self.branch=FlowResidual(mode);self.dependence=PathModel('markov');self.temperatures=temperatures;self.parent_config=parent
        if file_hash(Path(parent['checkpoint']))!=parent['checkpoint_sha256'] or file_hash(Path(parent['root'])/'report.json')!=parent['report_sha256']:raise ValueError('Changed0.9 parent')
        self.parent.residual.load_state_dict(torch.load(parent['checkpoint'],map_location='cpu',weights_only=True)['state_dict']);self.branch.load_state_dict(torch.load(checkpoint,map_location='cpu',weights_only=True)['state_dict']);c=parent['config']['dependence']
        if file_hash(Path(c['checkpoint']))!=c['checkpoint_sha256'] or file_hash(Path(c['root'])/'report.json')!=c['report_sha256']:raise ValueError('Changed dependence parent')
        self.dependence.load_state_dict(torch.load(c['checkpoint'],map_location='cpu',weights_only=True)['state_dict']);self.maximum_difference=0.;self.maximum_iterations=0
        self.register_buffer('parent_t',torch.tensor(parent['temperatures'],dtype=torch.float32)[None,:,None])
