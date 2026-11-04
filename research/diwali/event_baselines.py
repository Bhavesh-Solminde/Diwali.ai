"""Simple fixed baselines on the same chronological event/candle origins."""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
import joblib
from torch import nn
from torch.nn import functional as F
from sklearn.ensemble import HistGradientBoostingClassifier
from threadpoolctl import threadpool_limits

from .event_data import EventData,Moments,normalize
from .event_protocol import protocol
from .event_train import probabilities,nll,calibrate,metrics
from ..market_data.validate_archive import file_hash,save


def summary(raw):
    e,g,c,m,s,r=raw
    book=e[e[:,80]>0];trades=e[(e[:,81]>0)&(e[:,82]==0)]
    candles=[]
    for length in [1,15,60,1440]:
        known=c[-length:][m[-length:]]
        candles.append(known.mean(0) if len(known) else np.zeros(8))
    x=np.r_[e.mean(0),e.std(0),book[-1] if len(book) else np.zeros(103),
            trades[-1,80:] if len(trades) else np.zeros(23),s,r,*candles,
            1-m.mean(),np.log1p(len(e))].astype(np.float32)
    known=c[-60:,0][m[-60:]]
    vol=float(known.std()) if len(known)>1 else 0.
    if not np.isfinite(x).all():raise ValueError('Nonfinite baseline input')
    return x,vol


def histogram(y):
    result=np.stack([np.bincount(y[:,h],minlength=26)+1 for h in range(15)]).astype(float)
    return result/result.sum(-1,keepdims=True)


def full_class_probabilities(model,x):
    p=np.full((len(x),26),1e-8)
    p[:,model.classes_.astype(int)]+=model.predict_proba(x)
    return p/p.sum(1,keepdims=True)


def logistic(x,y,fit,select,settings,out):
    torch.manual_seed(settings['seed']);torch.set_num_threads(4)
    model=nn.Linear(x.shape[1],15*26)
    opt=torch.optim.AdamW(model.parameters(),lr=settings['learning_rate'],weight_decay=settings['weight_decay'])
    rng=np.random.default_rng(settings['seed']);best=float('inf');wait=0;history=[]
    for epoch in range(1,settings['epochs']+1):
        model.train();perm=rng.permutation(fit)
        for start in range(0,len(perm),settings['batch_size']):
            ids=perm[start:start+settings['batch_size']];opt.zero_grad(set_to_none=True)
            z=model(torch.from_numpy(x[ids])).reshape(-1,15,26)
            loss=F.cross_entropy(z.reshape(-1,26),torch.tensor(y[ids].reshape(-1)))
            loss.backward();opt.step()
        with torch.no_grad():pred=model(torch.from_numpy(x[select])).reshape(-1,15,26).numpy()
        score=nll(y[select],probabilities(pred));history.append({'epoch':epoch,'selection_loss':score})
        if score<best-1e-10:
            best=score;wait=0;state={k:v.detach().clone() for k,v in model.state_dict().items()};chosen=epoch
        else:wait+=1
        if wait>=settings['patience']:break
    model.load_state_dict(state);torch.save(state,out/'weights.pt');save(out/'selection.json',{'best_epoch':chosen,'selection_loss':best,'history':history})
    with torch.no_grad():return model(torch.from_numpy(x)).reshape(-1,15,26).numpy()


def run(data,fold,out):
    settings=protocol();parts={};counts={}
    for name in ['fit','select','calibrate','score']:
        parts[name],counts[name]=data.partition(fold,name)
        if len(parts[name])<settings['minimum_partition_origins'][name]:raise ValueError('Insufficient frozen-partition coverage')
    fit=parts['fit'];select=parts['select'];cal=parts['calibrate'];score=parts['score']
    features=[];vols=[]
    for j in range(len(data.ids)):
        x,v=summary(data.raw(j));features.append(x);vols.append(v)
    x=np.stack(features);vols=np.array(vols);moments=Moments(x.shape[1]);moments.add(x[fit]);transform=moments.record();x=normalize(x,transform)
    thresholds=np.quantile(vols[fit],[.25,.5,.75]);group=np.searchsorted(thresholds,vols);hist=histogram(data.y[fit]);conditional=[]
    for k in range(4):
        ids=fit[group[fit]==k];conditional.append(histogram(data.y[ids]) if len(ids) else hist)
    logits={'fit_histogram':np.broadcast_to(np.log(hist),(len(x),15,26)).copy(),
            'fit_volatility_histogram':np.log(np.stack(conditional)[group])}
    save(out/'fit-transforms.json',{'summary':transform,'volatility_thresholds':thresholds.tolist(),'fit_origins':len(fit),'source_hashes':data.hashes})
    linear=out/'flow_logistic';linear.mkdir();logits['flow_logistic']=logistic(x,data.y,fit,select,settings['logistic'],linear)
    tree=out/'flow_boosted_trees';tree.mkdir();pred=[]
    with threadpool_limits(limits=4):
        for h in range(15):
            model=HistGradientBoostingClassifier(**settings['boosted_trees']);model.fit(x[fit],data.y[fit,h])
            joblib.dump(model,tree/f'horizon-{h+1:02d}.joblib')
            pred.append(full_class_probabilities(model,x));print(fold,'boosted_horizon',h+1,flush=True)
    logits['flow_boosted_trees']=np.log(np.stack(pred,axis=1))
    result={'state':'complete','fold':fold,'cohorts':counts,'models':{},'fit_direction_up_fraction':float((data.y[fit,-1]>=13).mean()),'source_hashes':data.hashes}
    for name,z in logits.items():
        target=out/name;target.mkdir(exist_ok=True)
        temps=calibrate(data.y[cal],z[cal]);save(target/'calibration.json',{'temperatures':temps,'partition':'calibrate','origins':len(cal),'temperature_fitted':len(cal)>=settings['minimum_calibration_origins']})
        entry={'temperatures':temps,'partitions':{}}
        for part in ['select','calibrate','score']:
            ids=parts[part];p=probabilities(z[ids],temps);entry['partitions'][part]=metrics(data.y[ids],p)
            np.savez_compressed(target/(part+'-predictions.npz'),row_ids=data.ids[ids],probabilities=p)
            if part=='score':
                days=np.array([str(np.datetime64(int(t),'ns'))[:10] for t in data.cutoffs[ids]])
                entry['daily_scores']={day:metrics(data.y[ids][days==day],p[days==day]) for day in sorted(set(days))}
        save(target/'report.json',entry);result['models'][name]=entry
    save(out/'report.json',result);return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--cohort',type=Path,required=True);p.add_argument('--features',type=Path,required=True);p.add_argument('--content-audit',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--fold',choices=['A','B','C'],required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);settings=protocol();settings['active_fold']=a.fold
    settings['source_hashes']={n:file_hash(Path(__file__).with_name(n)) for n in ['event_baselines.py','event_data.py','event_train.py','event_protocol.py','event_evaluation.py']}
    save(a.output/'run-protocol.json',settings);began=time.time();data=EventData(a.cohort,a.features,a.content_audit);run(data,a.fold,a.output)
    save(a.output/'status.json',{'state':'complete','seconds':time.time()-began})


if __name__=='__main__':main()
