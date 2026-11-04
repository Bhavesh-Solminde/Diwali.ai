"""Diwali0.6: context-conditioned finite-state joint distribution of 15 closes."""
import argparse
import json
from pathlib import Path
import random
import time

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from .distribution import DistributionModel
from .fan import EDGES,direction,range_metrics
from .probability import probabilities,calibrate,metrics
from .multiscale import directional,SHORT_WIDTH
from ..market_data.build_pilot import WARMUP
from ..market_data.freeze_pilot import SPLITS,timestamp
from ..market_data.validate_archive import file_hash,save

BANDS={'5bp':(8,17),'12bp':(6,19),'20bp':(5,20)}


class PathModel(nn.Module):
    def __init__(self,mode='markov'):
        super().__init__()
        if mode not in ['markov','independent_control']:raise ValueError('Unknown path mode')
        self.mode=mode;self.encoder=DistributionModel();self.encoder.head=nn.Identity()
        self.previous=nn.Embedding(27,8);self.position=nn.Embedding(14,8)
        self.first=nn.Linear(33,26);self.decoder=nn.Sequential(nn.Linear(49,64),nn.GELU(),nn.Linear(64,26));self.colour=nn.Linear(33,3)

    def decode(self,z,previous,positions):
        if self.mode=='independent_control':previous=torch.full_like(previous,26)
        shape=previous.shape;context=z.reshape(z.shape[0],*([1]*(len(shape)-1)),33).expand(*shape,33)
        time=self.position(positions).expand(*shape,8)
        return self.decoder(torch.cat([context,self.previous(previous),time],dim=-1))

    def forward(self,x,previous_labels):
        """Likelihood evaluation/training only: labels for horizons1..14, shifted right."""
        z=self.encoder(x);positions=torch.arange(14,device=x.device)
        rest=self.decode(z,previous_labels,positions)
        return torch.cat([self.first(z)[:,None],rest],dim=1),self.colour(z)

    def all_transitions(self,x):
        """Forecast API: no future labels, exact enumeration of all26 possible previous bins."""
        z=self.encoder(x);previous=torch.arange(26,device=x.device)[None,None].expand(len(x),14,26)
        positions=torch.arange(14,device=x.device)[None,:,None]
        return self.first(z),self.decode(z,previous,positions),self.colour(z)


def propagate(initial,transitions,allowed=None):
    """Exact marginal recursion; with a mask, returns surviving joint subprobabilities."""
    p=np.asarray(initial,dtype=np.float64);t=np.asarray(transitions,dtype=np.float64)
    if t.shape!=(len(p),14,26,26) or p.shape[1:]!=(26,):raise ValueError('Invalid chain shape')
    mask=np.ones(26) if allowed is None else np.asarray(allowed,dtype=float)
    if mask.shape!=(26,) or ((mask!=0)&(mask!=1)).any():raise ValueError('Invalid allowed-bin mask')
    current=p*mask;rows=[current]
    for h in range(14):
        current=np.einsum('bi,bij->bj',current,t[:,h])*mask;rows.append(current)
    return np.stack(rows,axis=1)


def path_events(initial,transitions,lo,hi):
    if not 0<=lo<=hi<26:raise ValueError('Invalid range')
    mask=np.zeros(26);mask[lo:hi+1]=1
    stay=propagate(initial,transitions,mask)[:,-1].sum(1)
    visit=1-propagate(initial,transitions,1-mask)[:,-1].sum(1)
    return np.clip(stay,0,1),np.clip(visit,0,1)


def chain_losses(initial,transitions,y):
    n=len(y);rows=np.arange(n);loss=-np.log(np.maximum(initial[rows,y[:,0]],1e-15))
    for h in range(14):loss-=np.log(np.maximum(transitions[rows,h,y[:,h],y[:,h+1]],1e-15))
    return loss


def fit_chain(y):
    initial=(np.bincount(y[:,0],minlength=26)+1)/(len(y)+26)
    tables=[]
    for h in range(14):
        count=np.bincount(y[:,h]*26+y[:,h+1],minlength=26*26).reshape(26,26)+1
        tables.append(count/count.sum(1,keepdims=True))
    return initial,np.asarray(tables)


def event_metrics(truth,p):
    p=np.asarray(p);truth=np.asarray(truth,bool);q=np.clip(p,1e-15,1-1e-15)
    bins=[]
    for lo in np.arange(0,1,.1):
        keep=(p>=lo)&(p<(lo+.1) if lo<.9 else p<=1)
        if keep.any():bins.append({'lower':float(lo),'n':int(keep.sum()),'mean_probability':float(p[keep].mean()),'observed_frequency':float(truth[keep].mean())})
    return {'n':len(p),'brier':float(((p-truth)**2).mean()),'log_loss':float(-(truth*np.log(q)+(1-truth)*np.log1p(-q)).mean()),
            'mean_probability':float(p.mean()),'observed_frequency':float(truth.mean()),'reliability':bins}


def teacher_logits(model,x,y,device):
    model.eval();rows=[];colours=[]
    with torch.inference_mode():
        for start in range(0,len(x),128):
            z,c=model(torch.tensor(np.array(x[start:start+128]),device=device),torch.tensor(y[start:start+128,:-1],device=device))
            rows.append(z.cpu().numpy());colours.append(c.cpu().numpy())
    return np.concatenate(rows),np.concatenate(colours)


def forecast(model,x,temps,device):
    with torch.inference_mode():a,b,c=model.all_transitions(torch.tensor(np.array(x),device=device))
    initial=probabilities(a.cpu().numpy(),temps[0]);logits=b.cpu().numpy()
    transitions=np.stack([probabilities(logits[:,h],temps[h+1]) for h in range(14)],axis=1)
    return initial,transitions,propagate(initial,transitions),c.cpu().numpy()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=Path('data/models/diwali0.6'));a=parser.parse_args()
    out=a.output;out.mkdir(parents=True,exist_ok=False);began=time.time();parent=Path('data/models/diwali0.5')
    def status(stage,**kw):save(out/'status.json',{'model':'diwali0.6','stage':stage,'seconds':time.time()-began,**kw})
    protocol={'model':'diwali0.6','task':'joint finite-state15-close distribution conditioned on one frozen past snapshot',
        'factorization':'P(y1|x) product_h2..15 P(yh|x,yh-1); first-order future bin dependence, not full-history dependence',
        'price_edges_bp':EDGES.tolist(),'inputs':'exact0.5 fit/development/calibration/benchmark features; actual future labels only in likelihood training/scoring, NEVER forecasting',
        'models':['independent_control','markov'],'seeds':[17,29,43],'selection':'lowest three-seed mean development joint log loss per15-step path; deploy seed17 fixed',
        'training':'equal mean15 conditional CE + .25h1 colour CE; AdamW .0003 wd.0001 batch128 clip5 max20epochs patience4',
        'calibration':'per-horizon scalar temperature on calibration-only conditional likelihood;161 loggrid .1..10',
        'forecasting':'enumerate26 previous states and forward-sum exact marginals; no future actuals, random samples or Monte Carlo approximation',
        'baselines':'0.5 independent-column product; fit-only per-horizon Markov counts add-one; fit past-volatility-quartile Markov counts add-one',
        'path_events':'all15 closes in a bin union; at least one close in a bin union; NOT intraminute touch or stop ordering',
        'limitations':['Already-inspected October benchmark, not fresh test.','Historical candle availability/receipt clocks remain assumed.','Coarse26-bin Markov approximation loses within-bin state and longer future dependence.','Unknown future orders and trades remain unknown; no perfect/live trading claim.'],
        'source_sha256':file_hash(Path(__file__)),'parent_report_sha256':file_hash(parent/'report.json'),
        'references':['https://arxiv.org/abs/1704.04110','https://www.fceia.unr.edu.ar/prodivoz/Rabiner_1989.pdf']}
    save(out/'run-protocol.json',protocol);status('Verifying parent and preparing fixed baselines')
    torch.set_num_threads(4);device='mps' if torch.backends.mps.is_available() else 'cpu';parts={};hashes={}
    raw_path=Path('data/btc-perp/button-pilot-202610-v1/candle-raw.npy');raw=np.load(raw_path);hashes[str(raw_path)]=file_hash(raw_path)
    for name,(_,hi) in SPLITS.items():
        xp=parent/f'{name}-features.npy';yp=parent/f'{name}-targets.npz';x=np.load(xp,mmap_mode='r');z=np.load(yp);y=z['bin_labels']
        for p in [xp,yp]:hashes[str(p)]=file_hash(p)
        idx=z['indices'];targetrows=(idx[:,1,None]-WARMUP)//60000+np.arange(15)
        from .fan import range_labels
        np.testing.assert_array_equal(y,range_labels((raw[targetrows,3]/z['reference'][:,None]-1)*10000))
        if len(x)!=len(y) or x.shape[1]!=SHORT_WIDTH or (idx[:,1]+15*60000>timestamp(hi)).any():raise ValueError('Invalid parent shape/split')
        vol=np.array([np.std(np.diff(np.log(raw[int(r[2])-16:int(r[2]),3])))*10000 for r in idx])
        parts[name]={'x':x,'y':y,'colour':z['colour_labels'],'indices':idx,'reference':z['reference'],'volatility':vol}
    save(out/'parent-hashes.json',hashes)
    fit=parts['fit'];cuts=np.quantile(fit['volatility'],[.25,.5,.75]);fitgroup=np.searchsorted(cuts,fit['volatility'],side='right')
    initial,transitions=fit_chain(fit['y']);conditional=[fit_chain(fit['y'][fitgroup==g]) for g in range(4)]
    save(out/'baselines.json',{'initial':initial.tolist(),'transitions':transitions.tolist(),'cuts':cuts.tolist(),
        'conditional':[{'initial':i.tolist(),'transitions':t.tolist()} for i,t in conditional],'fit_only':True})
    runs=[];history=[]
    for mode in protocol['models']:
        for seed in protocol['seeds']:
            random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);model=PathModel(mode).to(device)
            opt=torch.optim.AdamW(model.parameters(),lr=.0003,weight_decay=.0001);best=float('inf');wait=0;beststate=None
            for epoch in range(1,21):
                model.train();order=np.random.permutation(len(fit['x']));total=0
                for start in range(0,len(order),128):
                    ids=order[start:start+128];x=torch.tensor(np.array(fit['x'][ids]),device=device);y=torch.tensor(fit['y'][ids],device=device);col=torch.tensor(fit['colour'][ids],device=device)
                    opt.zero_grad(set_to_none=True);z,c=model(x,y[:,:-1]);loss=F.cross_entropy(z.reshape(-1,26),y.reshape(-1))+.25*F.cross_entropy(c,col)
                    if not torch.isfinite(loss):raise ValueError('Nonfinite training loss')
                    loss.backward();nn.utils.clip_grad_norm_(model.parameters(),5);opt.step();total+=float(loss.detach().cpu())*len(ids)
                dev=parts['development'];z,_=teacher_logits(model,dev['x'],dev['y'],device);p=probabilities(z);score=float(-np.log(np.maximum(np.take_along_axis(p,dev['y'][:,:,None],2),1e-15)).sum(1).mean())
                item={'mode':mode,'seed':seed,'epoch':epoch,'development_joint_log_loss':score,'training_loss':total/len(order)};history.append(item);status('Training',**item);print(json.dumps(item),flush=True)
                if score<best:
                    best=score;wait=0;bestepoch=epoch;beststate={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
                else:wait+=1
                if wait>=4:break
            torch.save({'mode':mode,'seed':seed,'epoch':bestepoch,'state_dict':beststate},out/f'{mode}-{seed}.pt')
            runs.append({'mode':mode,'seed':seed,'epoch':bestepoch,'development_joint_log_loss':best,'parameters':sum(p.numel() for p in model.parameters())});save(out/'runs.json',runs)
            del model,opt
            if device=='mps':torch.mps.empty_cache()
    means={m:float(np.mean([r['development_joint_log_loss'] for r in runs if r['mode']==m])) for m in protocol['models']};chosen=min(means,key=means.get)
    save(out/'selection.json',{'mode':chosen,'seed':17,'development_three_seed_means':means,'before_calibration':True})
    parent_report=json.loads((parent/'report.json').read_text());report={'model':'diwali0.6','selected_mode':chosen,'runs':runs,'history':history,'protocol':protocol,'models':{},'device':device,'recent_live_accuracy':None}
    for mode in protocol['models']:
        status('Calibrating conditional probabilities',mode=mode);model=PathModel(mode).to(device);state=torch.load(out/f'{mode}-17.pt',weights_only=True,map_location='cpu');model.load_state_dict(state['state_dict']);model.eval()
        cp=parts['calibration'];z,c=teacher_logits(model,cp['x'],cp['y'],device);temps=[calibrate(z[:,h],cp['y'][:,h]) for h in range(15)];ct=calibrate(c,cp['colour'])
        info={'temperatures':temps,'colour_temperature':ct,'checkpoint_sha256':file_hash(out/f'{mode}-17.pt'),'partitions':{}}
        for name,part in parts.items():
            status('Exact marginal/path evaluation',mode=mode,partition=name);x,y=part['x'],part['y'];preds=[];losses=[];baseline_losses=[];conditional_losses=[];events={k:{'stay':[],'visit':[]} for k in BANDS};baseevents={k:{'stay':[],'visit':[]} for k in BANDS};colours=[]
            group=np.searchsorted(cuts,part['volatility'],side='right')
            for start in range(0,len(x),64):
                sl=slice(start,start+64);a,t,p,c=forecast(model,x[sl],temps,device);preds.append(p.astype(np.float32));colours.append(probabilities(c,ct));losses.append(chain_losses(a,t,y[sl]))
                bi=np.broadcast_to(initial,a.shape);bt=np.broadcast_to(transitions,t.shape);baseline_losses.append(chain_losses(bi,bt,y[sl]))
                ci=np.asarray([conditional[g][0] for g in group[sl]]);tr=np.asarray([conditional[g][1] for g in group[sl]]);conditional_losses.append(chain_losses(ci,tr,y[sl]))
                for key,(lo,hi) in BANDS.items():
                    s,v=path_events(a,t,lo,hi);events[key]['stay'].extend(s);events[key]['visit'].extend(v)
                    s,v=path_events(ci,tr,lo,hi);baseevents[key]['stay'].extend(s);baseevents[key]['visit'].extend(v)
            p=np.concatenate(preds);joint=np.concatenate(losses);baseline=np.concatenate(baseline_losses);volbase=np.concatenate(conditional_losses);col=np.concatenate(colours);dp=direction(p)
            old=np.load(parent/f"{parent_report['selected_mode']}-{name}-predictions.npz");np.testing.assert_array_equal(part['indices'],old['indices']);indloss=-np.log(np.maximum(np.take_along_axis(old['bin_probabilities'],y[:,:,None],2),1e-15)).sum(1)
            byh={str(h+1):{'ranges':range_metrics(y[:,h],p[:,h]),'primary':metrics(np.where(y[:,h]<10,0,np.where(y[:,h]>=16,2,1)),dp[:,h]),'directional':directional(np.where(y[:,h]<10,0,np.where(y[:,h]>=16,2,1)),dp[:,h])} for h in range(15)}
            event_results={}
            for key,(lo,hi) in BANDS.items():
                inside=(y>=lo)&(y<=hi);event_results[key]={}
                for kind,truth in [('stay',inside.all(1)),('visit',inside.any(1))]:event_results[key][kind]={'model':event_metrics(truth,events[key][kind]),'volatility_markov':event_metrics(truth,baseevents[key][kind])}
            days=np.array([time.strftime('%Y-%m-%d',time.gmtime(v/1000)) for v in part['indices'][:,1]])
            info['partitions'][name]={'examples':len(y),'joint_log_loss':float(joint.mean()),'joint_log_loss_per_step':float(joint.mean()/15),
                'diwali0.5_independent_product_joint_log_loss':float(indloss.mean()),'count_markov_joint_log_loss':float(baseline.mean()),'volatility_markov_joint_log_loss':float(volbase.mean()),
                'mean15_marginal_bin_log_loss':float(np.mean([h['ranges']['bin_log_loss'] for h in byh.values()])),
                'horizons':byh,'path_events':event_results,'h1_colour':metrics(part['colour'],col),
                'by_day':{d:{'n':int((days==d).sum()),'joint_log_loss':float(joint[days==d].mean()),'volatility_markov_joint_log_loss':float(volbase[days==d].mean()),'diwali0.5_independent_joint_log_loss':float(indloss[days==d].mean())} for d in sorted(set(days))}}
            np.savez(out/f'{mode}-{name}-predictions.npz',bin_probabilities=p,probabilities=dp,joint_losses=joint,baseline_losses=baseline,volatility_losses=volbase,diwali05_joint_losses=indloss,indices=part['indices'],reference=part['reference'],bin_labels=y,colour_probabilities=col,
                     **{f'{key}_{kind}':np.asarray(v[kind]) for key,v in events.items() for kind in ['stay','visit']})
        report['models'][mode]=info
    report['wall_seconds']=time.time()-began;save(out/'report.json',report);status('Complete',selected_mode=chosen);print('COMPLETE',chosen,means,flush=True)


if __name__=='__main__':main()
