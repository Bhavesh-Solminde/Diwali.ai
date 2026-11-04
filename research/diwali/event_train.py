"""End-to-end event model comparison on chronological development partitions."""
import argparse
import json
import random
import time
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F

from .event_model import EventModel
from .event_data import EventData
from .event_protocol import protocol
from ..market_data.validate_archive import file_hash,save


def probabilities(logits,temperatures=None):
    x=np.asarray(logits,np.float64)
    if temperatures is not None:x=x/np.asarray(temperatures)[None,:,None]
    x=x-x.max(-1,keepdims=True);p=np.exp(x);return p/p.sum(-1,keepdims=True)


def nll(y,p):
    return float(-np.log(np.maximum(np.take_along_axis(p,y[...,None],axis=-1)[...,0],1e-15)).mean())


def calibrate(y,logits):
    if len(y)<100:return [1.]*15
    grid=np.geomspace(.5,4.,49);temps=[]
    for h in range(15):
        losses=[nll(y[:,h:h+1],probabilities(logits[:,h:h+1]/t)) for t in grid]
        temps.append(float(grid[int(np.argmin(losses))]))
    return temps


def metrics(y,p):
    per=-np.log(np.maximum(np.take_along_axis(p,y[...,None],axis=-1)[...,0],1e-15))
    truth=y[:,:,None]<=np.arange(25)[None,None,:]
    up=p[:,:,13:].sum(-1);actual=y>=13;binary=-(actual*np.log(np.maximum(up,1e-15))+(~actual)*np.log(np.maximum(1-up,1e-15)))
    confidence=np.maximum(up,1-up);correct=(up>=.5)==actual
    reliability={}
    for lo,hi in [(.5,.6),(.6,.7),(.7,.8),(.8,.9),(.9,1.000001)]:
        take=(confidence[:,-1]>=lo)&(confidence[:,-1]<hi)
        reliability[f'{lo:.1f}-{min(hi,1):.1f}']={'count':int(take.sum()),'mean_confidence':float(confidence[:,-1][take].mean()) if take.any() else None,'correct_fraction':float(correct[:,-1][take].mean()) if take.any() else None}
    return {'origins':len(y),'mean15_bin_log_loss':float(per.mean()),'per_horizon_bin_log_loss':per.mean(0).tolist(),
            'ranked_probability_score':float(((p.cumsum(-1)[:,:,:-1]-truth)**2).mean()),
            'per_horizon_binary_log_loss':binary.mean(0).tolist(),'final_direction_log_loss':float(binary[:,-1].mean()),
            'final_direction_brier':float(((up[:,-1]-actual[:,-1])**2).mean()),
            'final_direction_accuracy':float(correct[:,-1].mean()),'final_direction_reliability':reliability,
            'always_half_final_log_loss':float(np.log(2)),
            'scope':'Overlapping origins; descriptive development scores, not independent trials or entry success.'}


def infer(model,data,indices,transforms,device,batch=8):
    model.eval();rows=[]
    with torch.inference_mode():
        for start in range(0,len(indices),batch):
            args,_=data.batch(indices[start:start+batch],transforms,device)
            rows.append(model(*args).cpu().numpy())
    return np.concatenate(rows)


def train(data,fold,candidate,seed,out,transforms,indices,settings,device):
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
    mode='attention' if candidate=='event_attention' else 'temporal_conv'
    model=EventModel(mode,width=settings['neural_width'],block=settings['event_block_groups']).to(device)
    optimizer=torch.optim.AdamW(model.parameters(),lr=settings['learning_rate'],weight_decay=settings['weight_decay'])
    best=float('inf');best_epoch=0;wait=0;history=[];began=time.time()
    fit,select=indices['fit'],indices['select'];rng=np.random.default_rng(seed)
    for epoch in range(1,settings['max_epochs']+1):
        model.train();perm=rng.permutation(fit);total=0.;seen=0
        for start in range(0,len(perm),settings['batch_size']):
            ids=perm[start:start+settings['batch_size']]
            args,y=data.batch(ids,transforms,device)
            optimizer.zero_grad(set_to_none=True);logits=model(*args);loss=F.cross_entropy(logits.reshape(-1,26),y.reshape(-1))
            if not torch.isfinite(loss):raise ValueError('Nonfinite training loss')
            loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),settings['gradient_clip'],error_if_nonfinite=True);optimizer.step()
            total+=float(loss.detach().cpu())*len(ids);seen+=len(ids)
        selected=infer(model,data,select,transforms,device,settings['batch_size']);score=nll(data.y[select],probabilities(selected))
        history.append({'epoch':epoch,'fit_loss':total/seen,'selection_loss':score,'elapsed_seconds':time.time()-began})
        if score<best-1e-10:
            best=score;best_epoch=epoch;wait=0
            state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
            torch.save(state,out/'weights.pt')
        else:wait+=1
        save(out/'history.json',history)
        save(out/'status.json',{'state':'fitting','epoch':epoch,'best_epoch':best_epoch,'selection_loss':score,'seconds':time.time()-began})
        print(fold,candidate,seed,epoch,round(total/seen,6),round(score,6),flush=True)
        if wait>=settings['patience']:break
    model.load_state_dict(state)
    selection={'state':'checkpoint_selected','candidate':candidate,'seed':seed,'best_epoch':best_epoch,
               'selection_loss':best,'parameters':sum(p.numel() for p in model.parameters()),
               'weights_sha256':file_hash(out/'weights.pt'),'all_trainable':all(p.requires_grad for p in model.parameters())}
    save(out/'selection.json',selection)
    # The selected weight hash is written before calibration or transfer inference.
    cal=infer(model,data,indices['calibrate'],transforms,device,settings['batch_size']);temps=calibrate(data.y[indices['calibrate']],cal)
    save(out/'calibration.json',{'temperatures':temps,'weights_sha256':selection['weights_sha256'],'partition':'calibrate','origins':len(indices['calibrate']),'temperature_fitted':len(indices['calibrate'])>=settings['minimum_calibration_origins']})
    result={'fold':fold,'candidate':candidate,'seed':seed,'selection':selection,'calibration_temperatures':temps,'partitions':{}}
    for name in ['select','calibrate','score']:
        ids=indices[name];z=cal if name=='calibrate' else infer(model,data,ids,transforms,device,settings['batch_size'])
        prob=probabilities(z,temps);result['partitions'][name]=metrics(data.y[ids],prob)
        np.savez_compressed(out/(name+'-predictions.npz'),row_ids=data.ids[ids],probabilities=prob)
        if name=='score':
            days=np.asarray([str(np.datetime64(int(t),'ns'))[:10] for t in data.cutoffs[ids]])
            result['daily_scores']={day:metrics(data.y[ids][days==day],prob[days==day]) for day in sorted(set(days))}
    result['elapsed_seconds']=time.time()-began;save(out/'report.json',result);save(out/'status.json',{'state':'complete','seconds':time.time()-began})
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--cohort',type=Path,required=True);p.add_argument('--features',type=Path,required=True);p.add_argument('--content-audit',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--fold',choices=['A','B','C'],required=True);p.add_argument('--candidate',choices=['event_temporal_conv','event_attention','one_second_temporal_conv'],required=True);p.add_argument('--seed',type=int,choices=[17,29],required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);settings=protocol()
    source_names=['event_train.py','event_data.py','event_model.py','event_protocol.py','event_evaluation.py']
    settings['source_hashes']={n:file_hash(Path(__file__).with_name(n)) for n in source_names};settings['active_fold']=a.fold;settings['active_candidate']=a.candidate;settings['active_seed']=a.seed
    save(a.output/'run-protocol.json',settings)
    data=EventData(a.cohort,a.features,a.content_audit);indices={};counts={}
    for name in ['fit','select','calibrate','score']:
        indices[name],counts[name]=data.partition(a.fold,name)
        if len(indices[name])<settings['minimum_partition_origins'][name]:raise ValueError('Insufficient partition coverage; do not silently change dates')
    save(a.output/'cohorts.json',{'source_hashes':data.hashes,'partitions':counts})
    representation='one_second' if a.candidate.startswith('one_second') else 'events'
    transforms=data.fit_transforms(indices['fit'],representation);save(a.output/'fit-transforms.json',transforms)
    torch.set_num_threads(4);device='mps' if torch.backends.mps.is_available() else 'cpu'
    train(data,a.fold,a.candidate,a.seed,a.output,transforms,indices,settings,device)


if __name__=='__main__':main()
