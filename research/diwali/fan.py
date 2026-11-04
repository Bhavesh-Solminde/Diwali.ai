"""Diwali0.5: direct marginal closing-price distributions for 15 candle closes."""
import argparse
import json
from pathlib import Path
import time
import random

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from .distribution import DistributionModel,range_labels as labels18,range_metrics as metrics18
from .probability import probabilities,calibrate,metrics
from .multiscale import SHORT_WIDTH,directional
from .train import Data
from ..market_data.build_pilot import WARMUP
from ..market_data.freeze_pilot import SPLITS,timestamp
from ..market_data.validate_archive import save,file_hash

HORIZONS=15
EDGES=np.array([-100,-60,-40,-30,-20,-12,-8,-5,-3,-2,-1,-.5,0,.5,1,2,3,5,8,12,20,30,40,60,100],dtype=float)


def range_labels(returns):
    r=np.asarray(returns)
    if not np.isfinite(r).all():raise ValueError('Nonfinite target')
    b=np.searchsorted(EDGES,r,side='left')
    return np.where(r>=2,np.maximum(b,16),b).astype(np.int64)


def collapse18(p):
    p=np.asarray(p)
    if p.shape[-1]!=26:raise ValueError('Expected 26 bins')
    return np.concatenate([p[...,:5].sum(-1,keepdims=True),p[...,5:21],p[...,21:].sum(-1,keepdims=True)],axis=-1)


def direction(p):
    return np.stack([p[...,:10].sum(-1),p[...,10:16].sum(-1),p[...,16:].sum(-1)],axis=-1)


def target_rows(indices,raw,content_valid,stop):
    starts=(indices[:,1]-WARMUP)//60000
    rows=starts[:,None]+np.arange(HORIZONS)
    inside=(indices[:,1]+HORIZONS*60000<=stop)&(rows[:,-1]<len(raw))
    safe=np.minimum(rows,len(raw)-1)
    good=content_valid[safe].all(1)&np.isfinite(raw[safe,:4]).all(axis=(1,2))&(raw[safe,:4]>0).all(axis=(1,2))
    keep=inside&good
    return keep,rows[keep],{'original':len(indices),'kept':int(keep.sum()),'split_boundary_or_outside':int((~inside).sum()),'bad_future_label_content':int((inside&~good).sum())}


class FanModel(nn.Module):
    def __init__(self):
        super().__init__();self.encoder=DistributionModel();self.encoder.head=nn.Identity()
        self.head=nn.Linear(33,HORIZONS*26);self.colour=nn.Linear(33,3)

    def forward(self,x):
        z=self.encoder(x)
        return self.head(z).reshape(-1,HORIZONS,26),self.colour(z)


def infer(model,x,device):
    model.eval();prices=[];colours=[]
    with torch.inference_mode():
        for i in range(0,len(x),128):
            a,b=model(torch.tensor(np.array(x[i:i+128]),device=device));prices.append(a.cpu().numpy());colours.append(b.cpu().numpy())
    return np.concatenate(prices),np.concatenate(colours)


def range_metrics(y,p):
    truth=y[:,None]<=np.arange(25)[None]
    score={'examples':len(y),'bin_log_loss':float(-np.log(np.maximum(p[np.arange(len(y)),y],1e-15)).mean()),
           'ranked_probability_score_mean_25_thresholds':float(((p.cumsum(1)[:,:-1]-truth)**2).mean()),
           'actual_counts':np.bincount(y,minlength=26).tolist(),'mean_probabilities':p.mean(0).tolist()}
    intervals={}
    for mass in [.8,.95]:
        lower=np.minimum((p.cumsum(1)<(1-mass)/2).sum(1),25);upper=np.minimum((p.cumsum(1)<1-(1-mass)/2).sum(1),25)
        intervals[str(mass)]={'coverage':float(((y>=lower)&(y<=upper)).mean()),
            'predicted_mass':float(np.mean([p[i,lo:hi+1].sum() for i,(lo,hi) in enumerate(zip(lower,upper))])),
            'unbounded_fraction':float(((lower==0)|(upper==25)).mean()),'scope':'per-horizon bin intervals; not simultaneous path coverage'}
    score['intervals']=intervals
    return score


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=Path('data/models/diwali0.5'));a=parser.parse_args()
    out=a.output;out.mkdir(parents=True,exist_ok=False);began=time.time()
    protocol={'model':'diwali0.5','task':'direct distributions for each of next15 full-minute candle closes from ONE causal snapshot',
        'horizon_definition':'h1 closes at first_target_start+60s; h15 at first_target_start+15*60s; not minutes since click',
        'price_edges_bp':EDGES.tolist(),'tails':'unbounded first/last; no clipping or assumed within-bin density',
        'boundary':'upper bounds inclusive except+2 goes bullish; aggregate <=-2 / (-2,2) / >=+2',
        'inputs':'same0.4 causal candle/book/trade features once; no generated feedback, future book/trade/candle inputs or invented updates',
        'cohort':'0.4 origins purged when any15 target spans cross split boundary; all target minute contents valid',
        'models':['equal_horizons','near_weighted'],'loss':'range CE weighted across15 outputs +0.25 h1 candle colour CE',
        'weights':'equal1/15; near_weighted h1=.5 and each h2-15=.5/14',
        'selection':'three-seed mean development equal-average15-horizon26-bin log loss; seed17 fixed; early stop same score',
        'seeds':[17,29,43],'max_epochs':20,'patience':4,'batch':128,'learning_rate':.0003,'weight_decay':.0001,'gradient_clip':5,
        'splits':SPLITS,'normalization':'reuse0.2/0.4 fit-only scalers; no new outcome-normalized features',
        'calibration':'separate scalar temperature per horizon on calibration only; colour scalar separately; same bounded grid',
        'baselines':'fit-only per-horizon empirical26-bin histogram; fit-quartile past15-minute volatility conditional histograms; add-one smoothing',
        'evaluation':'per-horizon range log loss, ordinal RPS, direction, reliability, bin coverage, daily results; matched h1 comparison collapsed18 bins vs0.4',
        'limitations':['Marginal forecast columns are not a joint path distribution or target-before-stop probabilities.',
          'Historical candle availability assumed and provider receipt clocks unverified.',
          'October benchmark previously inspected; no prospective model validation or perfect probability claim.',
          'Subsecond events absent from existing source features; future order arrivals remain unknown.'],
        'source_sha256':file_hash(Path(__file__)),'parent_report_sha256':file_hash(Path('data/models/diwali0.4/report.json'))}
    save(out/'run-protocol.json',protocol)
    def status(stage,**kw):save(out/'status.json',{'model':'diwali0.5','stage':stage,'seconds':time.time()-began,**kw})
    status('Preparing causal inputs and purged target sequences');torch.set_num_threads(4);device='mps' if torch.backends.mps.is_available() else 'cpu'
    parent=Path('data/models/diwali0.4');parent_report=json.loads((parent/'report.json').read_text());parent_mode=parent_report['selected_mode']
    prep=json.loads((parent/'preprocessing.json').read_text());data=Data(Path('data/btc-perp/aligned-button-pilot-202610-v1'),out/'verification-cache')
    if prep['dataset_fingerprint']!=data.manifest['fingerprint']:raise ValueError('Changed dataset')
    content_path=data.root/'candle-content-valid.npy'
    if file_hash(content_path)!=data.manifest['artifact_sha256'][content_path.name]:raise ValueError('Changed target-content quality')
    content=np.load(content_path);parts={};cohorts={}
    for name,(_,hi) in SPLITS.items():
        old=np.load(parent/f'{parent_mode}-{name}-predictions.npz');idx=old['indices'];keep,rows,ledger=target_rows(idx,data.raw,content,timestamp(hi));ids=np.flatnonzero(keep)
        if not len(ids):raise ValueError('Empty purged cohort')
        idx=idx[ids];refs=old['reference'][ids];colour=old['labels'][ids,1];returns=(data.raw[rows,3]/refs[:,None]-1)*10000;y=range_labels(returns)
        targets=(idx[:,1,None]+np.arange(15)*60000)
        if not np.array_equal(np.where(y[:,0]<10,0,np.where(y[:,0]>=16,2,1)),old['labels'][ids,0]):raise ValueError('Changed h1 outcomes')
        raw_features=np.load(parent/f'{name}-features.npy',mmap_mode='r');x=np.array(raw_features[ids])
        for i,row in enumerate(idx):
            if not np.array_equal(x[i,:-1],data.feature(row)):raise ValueError('Changed causal features')
        volatility=np.array([np.std(np.diff(np.log(data.raw[int(row[2])-16:int(row[2]),3])))*10000 for row in idx])
        parts[name]=(x,y,colour,idx,refs,returns,volatility,ids);cohorts[name]=ledger
        np.savez(out/f'{name}-targets.npz',bin_labels=y,colour_labels=colour,indices=idx,reference=refs,returns_bp=returns,target_start_ms=targets,parent_ids=ids)
        np.save(out/f'{name}-features.npy',x)
    save(out/'cohort-quality.json',cohorts);save(out/'preprocessing.json',prep)
    fit=parts['fit'];cuts=np.quantile(fit[6],[.25,.5,.75]);g=np.searchsorted(cuts,fit[6],side='right')
    prior=np.array([(np.bincount(fit[1][:,h],minlength=26)+1)/(len(fit[1])+26) for h in range(15)])
    cond=np.array([[(np.bincount(fit[1][g==v,h],minlength=26)+1)/(int((g==v).sum())+26) for h in range(15)] for v in range(4)])
    save(out/'baseline-definitions.json',{'volatility_quartile_edges':cuts.tolist(),'prior':prior.tolist(),'conditional':cond.tolist(),'fit_only':True})
    runs=[];history=[]
    for mode in protocol['models']:
        weights=np.full(15,1/15) if mode=='equal_horizons' else np.r_[.5,np.full(14,.5/14)]
        wt=torch.tensor(weights,dtype=torch.float32,device=device)
        for seed in protocol['seeds']:
            random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
            model=FanModel().to(device);opt=torch.optim.AdamW(model.parameters(),lr=.0003,weight_decay=.0001)
            fx,fy,fc=fit[:3];vx,vy=parts['development'][:2];best=float('inf');wait=0;epoch_best=0;state=None
            for epoch in range(1,21):
                model.train();order=np.random.permutation(len(fx));total=0
                for start in range(0,len(order),128):
                    ids=order[start:start+128];x=torch.tensor(fx[ids],device=device);y=torch.tensor(fy[ids],device=device);colour=torch.tensor(fc[ids],device=device)
                    opt.zero_grad(set_to_none=True);z,c=model(x);ce=F.cross_entropy(z.reshape(-1,26),y.reshape(-1),reduction='none').reshape(-1,15)
                    loss=(ce*wt).sum(1).mean()+.25*F.cross_entropy(c,colour)
                    if not torch.isfinite(loss):raise ValueError('Nonfinite loss')
                    loss.backward();nn.utils.clip_grad_norm_(model.parameters(),5);opt.step();total+=float(loss.detach().cpu())*len(ids)
                z,_=infer(model,vx,device);p=probabilities(z);score=float(-np.log(np.maximum(np.take_along_axis(p,vy[:,:,None],axis=2),1e-15)).mean())
                item={'mode':mode,'seed':seed,'epoch':epoch,'development_mean15_bin_log_loss':score,'training_joint_loss':total/len(fx)};history.append(item);status('Training',**item);print(json.dumps(item),flush=True)
                if score<best:
                    best=score;wait=0;epoch_best=epoch;state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
                else:wait+=1
                if wait>=4:break
            torch.save({'mode':mode,'seed':seed,'epoch':epoch_best,'state_dict':state},out/f'{mode}-{seed}.pt')
            runs.append({'mode':mode,'seed':seed,'epoch':epoch_best,'development_mean15_bin_log_loss':best,'parameters':sum(p.numel() for p in model.parameters())})
            del model,opt
            if device=='mps':torch.mps.empty_cache()
    means={m:float(np.mean([r['development_mean15_bin_log_loss'] for r in runs if r['mode']==m])) for m in protocol['models']};chosen=min(means,key=means.get)
    save(out/'selection.json',{'mode':chosen,'seed':17,'development_three_seed_means':means,'frozen_before_calibration':True})
    report={'model':'diwali0.5','selected_mode':chosen,'runs':runs,'history':history,'protocol':protocol,'cohorts':cohorts,'models':{},'recent_live_accuracy':None,'device':device}
    for mode in protocol['models']:
        status('Calibrating each horizon and evaluating',mode=mode)
        state=torch.load(out/f'{mode}-17.pt',map_location='cpu',weights_only=True);model=FanModel().to(device);model.load_state_dict(state['state_dict'])
        cp=parts['calibration'];cl,cc=infer(model,cp[0],device)
        temps=[calibrate(cl[:,h],cp[1][:,h]) for h in range(15)];colour_temp=calibrate(cc,cp[2])
        info={'temperatures':temps,'colour_temperature':colour_temp,'checkpoint_sha256':file_hash(out/f'{mode}-17.pt'),'partitions':{}}
        for name,part in parts.items():
            x,y,col,idx,refs,returns,vol,parent_ids=part;logits,cl=infer(model,x,device);p=np.stack([probabilities(logits[:,h],temps[h]) for h in range(15)],axis=1);dp=direction(p)
            byh={};vol_groups=np.searchsorted(cuts,vol,side='right');days=np.array([time.strftime('%Y-%m-%d',time.gmtime(t/1000)) for t in idx[:,1]])
            for h in range(15):
                primary=np.where(y[:,h]<10,0,np.where(y[:,h]>=16,2,1));baseline=np.broadcast_to(prior[h],p[:,h].shape);conditional=cond[vol_groups,h]
                byh[str(h+1)]={'ranges':range_metrics(y[:,h],p[:,h]),'primary':metrics(primary,dp[:,h]),'directional':directional(primary,dp[:,h]),
                    'prior_range_baseline':range_metrics(y[:,h],baseline),'volatility_range_baseline':range_metrics(y[:,h],conditional)}
            old=np.load(parent/f'{parent_mode}-{name}-predictions.npz');common=collapse18(p[:,0]);primary=np.where(y[:,0]<10,0,np.where(y[:,0]>=16,2,1))
            summary={'horizons':byh,'mean15_bin_log_loss':float(np.mean([v['ranges']['bin_log_loss'] for v in byh.values()])),
                'h1_common18':metrics18(labels18(returns[:,0]),common),'h1_diwali0.4_ranges':metrics18(old['bin_labels'][parent_ids],old['bin_probabilities'][parent_ids]),
                'h1_diwali0.4_direction':metrics(primary,old['probabilities'][parent_ids]),'h1_colour':metrics(col,probabilities(cl,colour_temp)),
                'by_day':{d:{'h1':metrics(primary[days==d],dp[days==d,0]),'mean15_bin_log_loss':float(-np.log(np.maximum(np.take_along_axis(p[days==d],y[days==d,:,None],axis=2),1e-15)).mean())} for d in sorted(set(days))}}
            info['partitions'][name]=summary
            np.savez(out/f'{mode}-{name}-predictions.npz',bin_probabilities=p,probabilities=dp,bin_labels=y,indices=idx,reference=refs,returns_bp=returns,colour_probabilities=probabilities(cl,colour_temp),parent_ids=parent_ids)
        report['models'][mode]=info
    report['wall_seconds']=time.time()-began;save(out/'report.json',report);status('Complete',selected_mode=chosen);print('COMPLETE',chosen,means,flush=True)


if __name__=='__main__':main()
