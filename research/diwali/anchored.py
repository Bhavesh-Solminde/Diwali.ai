"""Diwali1.2: isolated midpoint-summary correction over raw frozen neural parents."""
import json
from pathlib import Path
import numpy as np
import torch
from torch import nn
from .model import CANDLE_SIZE,BOOK_SIZE
from .fan import FanModel
from .path import PathModel
from .probability import probabilities
from .coupled import reconcile
from ..market_data.validate_archive import file_hash
from ..market_data.midpoint import window_features
from ..market_data.midpoint_windows import summaries

OLD_WIDTH=17041


def raw_parents():
    configs={}
    for name,version in [('marginal','0.5'),('dependence','0.7')]:
        root=Path('data/models')/f'diwali{version}';report=json.loads((root/'report.json').read_text());mode=report['selected_mode'];path=root/f'{mode}-17.pt';expected=report['models'][mode]['checkpoint_sha256']
        if file_hash(path)!=expected:raise ValueError('Changed raw parent checkpoint')
        configs[name]={'root':str(root),'mode':mode,'checkpoint':str(path),'checkpoint_sha256':expected,'report_sha256':file_hash(root/'report.json')}
    return configs


def load_parent(model,config):
    if file_hash(Path(config['checkpoint']))!=config['checkpoint_sha256'] or file_hash(Path(config['root'])/'report.json')!=config['report_sha256']:raise ValueError('Changed raw parent')
    model.load_state_dict(torch.load(config['checkpoint'],map_location='cpu',weights_only=True)['state_dict']);return model.eval()


class JoinedFeatures:
    def __init__(self,old,extra):
        if old.shape[1:]!=(OLD_WIDTH,) or extra.shape!=(len(old),2):raise ValueError('Invalid midpoint join')
        self.old=old;self.extra=extra;self.shape=(len(old),OLD_WIDTH+2)
    def __len__(self):return len(self.old)
    def __getitem__(self,key):return np.concatenate([self.old[key],self.extra[key]],axis=-1)


class AnchoredResidual(nn.Module):
    def __init__(self,mode):
        super().__init__()
        if mode not in ['no_midpoint','with_midpoint']:raise ValueError('Unknown midpoint mode')
        self.mode=mode;self.sequence=nn.GRU(94,24,batch_first=True);self.head=nn.Linear(24,15*26);self.colour=nn.Linear(24,3)
        for head in [self.head,self.colour]:nn.init.zeros_(head.weight);nn.init.zeros_(head.bias)
    def inputs(self,x):
        if x.shape[-1]!=OLD_WIDTH+2:raise ValueError('Expected old inputs plus two midpoint summaries')
        b=x[:,CANDLE_SIZE:CANDLE_SIZE+BOOK_SIZE].reshape(-1,60,87);t=x[:,CANDLE_SIZE+BOOK_SIZE:OLD_WIDTH-1].reshape(-1,60,5);flow=torch.cat([b,t],-1).mean(1);mid=x[:,OLD_WIDTH:]
        if self.mode=='no_midpoint':mid=torch.zeros_like(mid)
        return torch.cat([flow,mid],1)[:,None,:].expand(-1,60,-1)
    def forward(self,x):
        _,h=self.sequence(self.inputs(x));return self.head(h[-1]).reshape(-1,15,26),self.colour(h[-1])


class AnchoredJoint(nn.Module):
    def __init__(self,checkpoint,config,temperatures,mode):
        super().__init__();self.parent=load_parent(FanModel(),config['marginal']);self.dependence=load_parent(PathModel('markov'),config['dependence']);self.branch=AnchoredResidual(mode);self.temperatures=temperatures
        self.branch.load_state_dict(torch.load(checkpoint,map_location='cpu',weights_only=True)['state_dict']);self.maximum_difference=0.;self.maximum_iterations=0
    def all_transitions(self,x):
        z,c=self.parent(x[:,:OLD_WIDTH]);a,b=self.branch(x);z=(z+a).detach().cpu().numpy();c=c+b;_,t,_=self.dependence.all_transitions(x[:,:OLD_WIDTH]);t=t.detach().cpu().numpy()
        marginal=np.stack([probabilities(z[:,h],self.temperatures[h]) for h in range(15)],1);prior=probabilities(t)
        initial,transition,ledger=reconcile(marginal,prior,1.);self.maximum_difference=max(self.maximum_difference,ledger['maximum_marginal_difference']);self.maximum_iterations=max(self.maximum_iterations,ledger['iterations'])
        return torch.from_numpy(np.log(initial)),torch.from_numpy(np.log(transition)),c


def augment_live(request,old_input,scaler):
    """Call after the original live_input validates the complete original contract."""
    from .prospective import book_features
    at=int(request['snapshot_utc_ns']);start,end=map(int,request['book_trade_window_ns']);books=request['book_seconds'];candle=request['candles'][-1]
    if len(books)!=60 or end-start!=60*10**9 or end>at or candle['available_ns']>=at or (candle['close_ms']+1)*10**6>at:raise ValueError('Invalid midpoint freeze')
    mids=[]
    for i,row in enumerate(books):
        grid=start+i*10**9;b=row['book']
        if row['grid_utc_ns']!=grid or grid>=at or b['available_ns']>grid or b['source_receipt_ns']>grid or b['exchange_event_ms']*10**6>grid or grid-b['available_ns']>10**9:raise ValueError('Future/stale midpoint')
        book_features(b['levels']);mids.append((float(b['levels']['bids'][0][0])+float(b['levels']['asks'][0][0]))/2)
    raw=summaries(window_features(mids,float(candle['values'][3]))[None])[0];std=np.asarray(scaler['std']);mean=np.asarray(scaler['mean'])
    if mean.shape!=(2,) or std.shape!=(2,) or (std<=0).any():raise ValueError('Invalid midpoint scaler')
    original=np.asarray(old_input,np.float32)
    if original.shape!=(OLD_WIDTH,):raise ValueError('Invalid original input width')
    result=np.concatenate([original,((raw-mean)/std).astype(np.float32)])
    if not np.isfinite(result).all():raise ValueError('Nonfinite augmented input')
    return result
