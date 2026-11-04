"""Diwali0.4: next-full-minute closing-return histogram with coherent direction."""
import argparse
import json
from pathlib import Path
import time
import random

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from .model import CANDLE_SIZE,BOOK_SIZE
from .probability import ProbabilityModel,probabilities,calibrate,metrics,labels
from .multiscale import SHORT_WIDTH,directional
from .train import Data
from ..market_data.build_pilot import WARMUP
from ..market_data.validate_archive import file_hash,save

EDGES=np.array([-20,-12,-8,-5,-3,-2,-1,-.5,0,.5,1,2,3,5,8,12,20],dtype=np.float64)


def range_labels(returns):
    r=np.asarray(returns)
    if not np.isfinite(r).all():raise ValueError('Nonfinite target')
    # All edges inclusive on upper bin boundary except +2 belongs to bullish.
    b=np.searchsorted(EDGES,r,side='left')
    return np.where(r>=2,np.maximum(b,12),b).astype(np.int64)


def direction(p):
    p=np.asarray(p)
    if p.shape[-1]!=18:raise ValueError('Expected 18 price ranges')
    return np.stack([p[...,:6].sum(-1),p[...,6:12].sum(-1),p[...,12:].sum(-1)],axis=-1)


def rps_torch(logits,y):
    cdf=logits.softmax(-1).cumsum(-1)[:,:-1]
    truth=(y[:,None]<=torch.arange(17,device=y.device)[None]).to(cdf.dtype)
    return ((cdf-truth)**2).mean()


def range_metrics(y,p):
    truth=(y[:,None]<=np.arange(17)[None])
    out={'examples':len(y),'bin_log_loss':float(-np.log(np.maximum(p[np.arange(len(y)),y],1e-15)).mean()),
         'ranked_probability_score_mean_17_thresholds':float(((p.cumsum(1)[:,:-1]-truth)**2).mean()),
         'bin_accuracy':float((p.argmax(1)==y).mean()),'actual_counts':np.bincount(y,minlength=18).tolist(),
         'mean_probabilities':p.mean(0).tolist()}
    intervals={}
    for mass in [.8,.95]:
        lower=(p.cumsum(1)<(1-mass)/2).sum(1)
        upper=(p.cumsum(1)<1-(1-mass)/2).sum(1)
        lower=np.minimum(lower,17);upper=np.minimum(upper,17)
        intervals[str(mass)]={'actual_coverage':float(((y>=lower)&(y<=upper)).mean()),
            'mean_predicted_mass':float(np.mean([p[i,lo:hi+1].sum() for i,(lo,hi) in enumerate(zip(lower,upper))])),
            'unbounded_fraction':float(((lower==0)|(upper==17)).mean()),
            'note':'Equal-tail bin intervals; may exceed nominal mass due coarse bins, no conformal/live guarantee.'}
    out['intervals']=intervals
    return out


class DistributionModel(nn.Module):
    def __init__(self):
        super().__init__();self.encoder=ProbabilityModel('sequence',SHORT_WIDTH)
        self.encoder.head=nn.Identity();self.head=nn.Linear(33,21)

    def forward(self,x):
        e=self.encoder.encoder;raw=x[:,:-1]
        c=raw[:,:CANDLE_SIZE].reshape(-1,1440,8).transpose(1,2)
        _,ch=e.candle_gru(F.gelu(e.conv(c)).transpose(1,2))
        b=raw[:,CANDLE_SIZE:CANDLE_SIZE+BOOK_SIZE].reshape(-1,60,87)
        t=raw[:,CANDLE_SIZE+BOOK_SIZE:].reshape(-1,60,5)
        _,fh=e.flow_gru(F.gelu(e.project(torch.cat([b,t],dim=2))))
        z=e.body(torch.cat([ch[-1],fh[-1]],dim=1))
        return self.head(torch.cat([z,x[:,-1:]],dim=1))


def infer_bins(model,x,device):
    model.eval()
    with torch.inference_mode():
        return np.concatenate([model(torch.tensor(np.array(x[i:i+128]),device=device)).cpu().numpy() for i in range(0,len(x),128)])


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=Path('data/models/diwali0.4'));a=parser.parse_args()
    out=a.output;out.mkdir(parents=True,exist_ok=False);began=time.time()
    protocol={'model':'diwali0.4','target':'closing return at end of next full calendar minute relative observed snapshot VWAP',
        'price_edges_bp':EDGES.tolist(),'tails':'first (-infinity,-20], last (20,+infinity); no clipping, invented within-bin density or finite tail mean',
        'boundary_rule':'upper edges inclusive except +2 included in bullish bin12; directional aggregation exactly matches0.2',
        'inputs':'exact0.2 one-day candles/60-second book/trades/reference displacement; no added long summary after negative0.3',
        'cohort':'exact saved0.2 origins, references, primary and colour labels',
        'models':['categorical','ordinal_penalty'],'seeds':[17,29,43],
        'loss':'18-bin cross entropy +0.25 colour cross entropy; ordinal variant adds0.5 mean17-threshold RPS',
        'selection':'lowest three-seed mean development 18-bin log loss; seed17 fixed; checkpoint early stop on development bin log loss',
        'max_epochs':20,'patience':4,'batch':128,'learning_rate':.0003,'weight_decay':.0001,'gradient_clip':5,
        'split':'fitOct1-18; developmentOct19-21; calibrationOct22-23; inspected comparisonOct24-31,2026 UTC',
        'calibration':'scalar temperature minimized on calibration bin log loss; colour separate; direction always aggregated from calibrated bins',
        'baselines':'fit-only empirical18-bin frequencies, fit-conditional past15-minute volatility histogram; fixed fit quartiles, add-one smoothing',
        'limitations':['Perfect market probabilities cannot be certified from a finite historical sample.',
         'Histogram is one endpoint, not an intra-candle path, touching probability, high/low distribution or15-minute fan.',
         'Historical candle availability assumed, original receipt clocks not verified; no prospective model accuracy.',
         'October inspected benchmark is reused for descriptive comparisons only; new confirmation remains required.'],
        'source_sha256':file_hash(Path(__file__)),
        'parent_report_sha256':file_hash(Path('data/models/diwali0.2/report.json'))}
    save(out/'run-protocol.json',protocol)
    def status(stage,**kw):save(out/'status.json',{'model':'diwali0.4','stage':stage,'seconds':time.time()-began,**kw})
    status('Checking and preparing distribution targets');torch.set_num_threads(4);device='mps' if torch.backends.mps.is_available() else 'cpu'
    parent=Path('data/models/diwali0.2');prep=json.loads((parent/'preprocessing.json').read_text())
    data=Data(Path('data/btc-perp/aligned-button-pilot-202610-v1'),out/'verification-cache')
    if prep['dataset_fingerprint']!=data.manifest['fingerprint']:raise ValueError('Changed dataset')
    parts={}
    for name in ['fit','development','calibration','locked_test']:
        old=np.load(parent/f'{name}-predictions.npz');idx=old['indices'];refs=old['reference'];y=old['labels']
        ip=data.root/f'{name}-phase15-grace1000-indices.npy';tp=data.root/f'{name}-phase15-grace1000-targets.npy'
        for path in [ip,tp]:
            if file_hash(path)!=data.manifest['artifact_sha256'][path.name]:raise ValueError('Changed cohort bytes')
        base=np.load(ip);ids=np.searchsorted(base[:,0],idx[:,0])
        if not np.array_equal(base[ids],idx):raise ValueError('Changed origins')
        target=np.load(tp)[ids];returns=(target[:,3]/refs-1)*10000;bins=range_labels(returns)
        if not np.array_equal(np.where(bins<6,0,np.where(bins>=12,2,1)),y[:,0]):raise ValueError('Bin/direction label mismatch')
        raw=np.load(parent/f'cache/{name}-x.npy',mmap_mode='r')[ids]
        for i,row in enumerate(idx):
            if not np.array_equal(raw[i],data.feature(row)):raise ValueError('Changed source input')
        anchor=data.raw[idx[:,2]-1,3];delta=((refs/anchor-1)*10000-prep['delta_mean'])/prep['delta_std']
        full=np.column_stack([raw,delta]).astype(np.float32);np.save(out/f'{name}-features.npy',full)
        volatility=np.array([np.std(np.diff(np.log(data.raw[int(row[2])-16:int(row[2]),3])))*10000 for row in idx])
        parts[name]=(full,bins,y,idx,refs,returns,volatility)
    save(out/'preprocessing.json',prep)
    fit=parts['fit'];cuts=np.quantile(fit[6],[.25,.5,.75]);groups=np.searchsorted(cuts,fit[6],side='right')
    prior=(np.bincount(fit[1],minlength=18)+1)/(len(fit[1])+18)
    conditional=np.array([(np.bincount(fit[1][groups==g],minlength=18)+1)/(int((groups==g).sum())+18) for g in range(4)])
    save(out/'baseline-definitions.json',{'fit_volatility_quartile_edges_bp':cuts.tolist(),'empirical_bin_probabilities':prior.tolist(),'conditional_probabilities':conditional.tolist(),'fit_only':True})
    history=[];runs=[]
    for mode in protocol['models']:
        for seed in protocol['seeds']:
            random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
            model=DistributionModel().to(device);opt=torch.optim.AdamW(model.parameters(),lr=.0003,weight_decay=.0001)
            fx,fy,fc=fit[:3];vx,vy=parts['development'][:2];best=float('inf');wait=0;epoch_best=0;saved_state=None
            for epoch in range(1,21):
                model.train();order=np.random.permutation(len(fx));total=0
                for start in range(0,len(order),128):
                    ids=order[start:start+128];xb=torch.tensor(fx[ids],device=device);yb=torch.tensor(fy[ids],device=device);colour=torch.tensor(fc[ids,1],device=device)
                    opt.zero_grad(set_to_none=True);z=model(xb);loss=F.cross_entropy(z[:,:18],yb)+.25*F.cross_entropy(z[:,18:],colour)
                    if mode=='ordinal_penalty':loss=loss+.5*rps_torch(z[:,:18],yb)
                    if not torch.isfinite(loss):raise ValueError('Nonfinite loss')
                    loss.backward();nn.utils.clip_grad_norm_(model.parameters(),5);opt.step();total+=float(loss.detach().cpu())*len(ids)
                logits=infer_bins(model,vx,device)[:,:18];p=probabilities(logits);value=float(-np.log(np.maximum(p[np.arange(len(vy)),vy],1e-15)).mean())
                item={'mode':mode,'seed':seed,'epoch':epoch,'development_bin_log_loss':value,'training_joint_loss':total/len(fx)}
                history.append(item);status('Training',**item);print(json.dumps(item),flush=True)
                if value<best:
                    best=value;epoch_best=epoch;wait=0;saved_state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
                else:wait+=1
                if wait>=4:break
            torch.save({'mode':mode,'seed':seed,'epoch':epoch_best,'state_dict':saved_state},out/f'{mode}-{seed}.pt')
            runs.append({'mode':mode,'seed':seed,'epoch':epoch_best,'development_bin_log_loss':best,'parameters':sum(p.numel() for p in model.parameters())})
            del model,opt
            if device=='mps':torch.mps.empty_cache()
    means={m:float(np.mean([r['development_bin_log_loss'] for r in runs if r['mode']==m])) for m in protocol['models']};selected=min(means,key=means.get)
    save(out/'selection.json',{'mode':selected,'seed':17,'development_three_seed_means':means,'frozen_before_calibration':True})
    report={'model':'diwali0.4','selected_mode':selected,'runs':runs,'history':history,'protocol':protocol,'models':{},'recent_live_accuracy':None,'device':device}
    for mode in protocol['models']:
        status('Calibrating and evaluating',mode=mode)
        saved=torch.load(out/f'{mode}-17.pt',map_location='cpu',weights_only=True);model=DistributionModel().to(device);model.load_state_dict(saved['state_dict'])
        c=parts['calibration'];z=infer_bins(model,c[0],device);temperatures=[calibrate(z[:,:18],c[1]),calibrate(z[:,18:],c[2][:,1])]
        result={'temperatures':temperatures,'partitions':{},'checkpoint_sha256':file_hash(out/f'{mode}-17.pt')}
        for name,part in parts.items():
            x,y,colour,idx,refs,returns,vol=part;z=infer_bins(model,x,device);p=probabilities(z[:,:18],temperatures[0]);dp=direction(p);cp=probabilities(z[:,18:],temperatures[1])
            baseline=np.broadcast_to(prior,p.shape);conditional_p=conditional[np.searchsorted(cuts,vol,side='right')]
            old=np.load(parent/f'{name}-predictions.npz')['probabilities'];days=np.array([time.strftime('%Y-%m-%d',time.gmtime(v/1000)) for v in idx[:,1]])
            result['partitions'][name]={'ranges':range_metrics(y,p),'primary':metrics(colour[:,0],dp),'directional':directional(colour[:,0],dp),
                'colour':metrics(colour[:,1],cp),'empirical_range_baseline':range_metrics(y,baseline),
                'volatility_range_baseline':range_metrics(y,conditional_p),'volatility_direction_baseline':metrics(colour[:,0],direction(conditional_p)),
                'diwali0.2':metrics(colour[:,0],old),'by_day':{d:{'ranges':range_metrics(y[days==d],p[days==d]),'primary':metrics(colour[days==d,0],dp[days==d]),'diwali0.2':metrics(colour[days==d,0],old[days==d])} for d in sorted(set(days))}}
            np.savez(out/f'{mode}-{name}-predictions.npz',bin_probabilities=p,probabilities=dp,colour_probabilities=cp,labels=colour,bin_labels=y,indices=idx,reference=refs,returns_bp=returns)
        report['models'][mode]=result
    report['wall_seconds']=time.time()-began;save(out/'report.json',report);status('Complete',selected_mode=selected);print('COMPLETE',selected,means,flush=True)


if __name__=='__main__':main()
