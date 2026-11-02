"""Train diwali0.1 within the predeclared two-architecture/three-seed pilot budget."""
import argparse
import json
import math
import os
from pathlib import Path
import random
import resource
import time
from datetime import datetime,timezone
import numpy as np
import torch
from .model import Diwali,WIDTH
from ..market_data.build_pilot import feature_dtype,WARMUP
from ..market_data.trade_alignment import transform
from ..market_data.review_pilot import metrics,utc
from ..market_data.button_baselines import predict as baseline_predict
from ..market_data.validate_archive import save,file_hash


class Data:
    def __init__(self,aligned,cache):
        self.aligned=aligned;self.cache=cache;cache.mkdir(parents=True,exist_ok=True)
        self.contract=json.loads((aligned/'alignment-contract.json').read_text())
        self.root=Path(self.contract['parent_dataset']);self.manifest=json.loads((self.root/'dataset-manifest.json').read_text())
        if self.manifest['fingerprint']!=self.contract['parent_dataset_fingerprint']:raise ValueError('Changed dataset')
        if file_hash(aligned/'scalers.json')!=self.contract['scaler_sha256']:raise ValueError('Changed scaling')
        self.scalers=json.loads((aligned/'scalers.json').read_text())
        self.candles=np.load(self.root/'candle-features.npy');self.raw=np.load(self.root/'candle-raw.npy')
        self.book=np.memmap(self.manifest['book_source'],mode='r',dtype=feature_dtype('book'))
        self.trades=np.memmap(self.manifest['trade_source'],mode='r',dtype=feature_dtype('trades'))
        self.parts={}
    def feature(self,row):
        ci,b,e=int(row[2]),int(row[3]),int(row[4]);anchor=self.raw[ci-1,3]
        arrays=[self.candles[ci-1440:ci],self.book[b:e]['x'],transform(self.trades[b:e]['x'][:,:4],anchor)]
        result=[]
        for values,name in zip(arrays,['candles','book','trades']):
            s=self.scalers[name];result.append(((values-np.asarray(s['mean']))/np.asarray(s['std'])).astype(np.float32).ravel())
        x=np.concatenate(result)
        if len(x)!=WIDTH or not np.isfinite(x).all():raise ValueError('Invalid model inputs')
        return x
    def part(self,name):
        if name in self.parts:return self.parts[name]
        ip=self.root/f'{name}-phase15-grace1000-indices.npy';tp=self.root/f'{name}-phase15-grace1000-targets.npy'
        for p in (ip,tp):
            if file_hash(p)!=self.manifest['artifact_sha256'][p.name]:raise ValueError('Changed partition')
        idx=np.load(ip);targets=np.load(tp);anchor=self.raw[idx[:,2]-1,3]
        y=((targets[:,:4]/anchor[:,None]-1)*10000).astype(np.float32)
        path=self.cache/f'{name}-x.npy'
        # Run cache is derived, not reused across runs without preparation.
        x=np.lib.format.open_memmap(path,mode='w+',dtype=np.float32,shape=(len(idx),WIDTH))
        for i,row in enumerate(idx):x[i]=self.feature(row)
        x.flush();self.parts[name]=(x,y,idx,anchor,targets)
        return self.parts[name]


def infer(model,x,device,batch=128):
    model.eval();values=[];start=time.perf_counter()
    with torch.inference_mode():
        for i in range(0,len(x),batch):values.append(model(torch.from_numpy(np.array(x[i:i+batch])).to(device)).cpu().numpy())
    return np.concatenate(values),time.perf_counter()-start


def score(actual,pred,idx):
    days=np.array([utc(t)[:10] for t in idx[:,1]])
    result=metrics(pred,actual);result['mean_ohlc_mae_bp']=float(np.abs(pred-actual).mean())
    result['candle_colour_accuracy']=float(np.mean(np.sign(pred[:,3]-pred[:,0])==np.sign(actual[:,3]-actual[:,0])))
    result['by_day']={day:metrics(pred[days==day],actual[days==day]) for day in sorted(set(days))}
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--aligned',type=Path,default=Path('data/btc-perp/aligned-button-pilot-202610-v1'))
    p.add_argument('--protocol',type=Path,default=Path('configs/experiments/btc-button-pilot-v1.json'))
    p.add_argument('--output',type=Path,default=Path('data/models/diwali0.1'))
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    protocol=json.loads(a.protocol.read_text());device='mps' if torch.backends.mps.is_available() else 'cpu'
    torch.set_num_threads(4)
    started=time.time();history=[];runs=[]
    def status(stage,**kw):save(a.output/'status.json',{'model':'diwali0.1','stage':stage,'elapsed_seconds':round(time.time()-started,1),'history':history,'runs':runs,**kw})
    save(a.output/'run-protocol.json',{'model':'diwali0.1','protocol':protocol,'protocol_sha256':file_hash(a.protocol),
        'colour_metric_addition':'Supplementary predicted close-vs-open candle colour; not selection criterion. Frozen before neural fitting.',
        'device':device,'torch_version':torch.__version__,'started_utc':datetime.now(timezone.utc).isoformat(),
        'code_sha256':{n:file_hash(Path(__file__).parent/n) for n in ('train.py','model.py')},
        'historical_availability':'assumed; not certified historical live receipt','test_not_used_for_selection':True})
    status('Preparing training and development inputs')
    data=Data(a.aligned,a.output/'cache');fx,fy,fi,_,_=data.part('fit');vx,vy,vi,_,_=data.part('development')
    scales=np.maximum(fy.std(axis=0),.1).astype(np.float32);save(a.output/'target-scales.json',scales.tolist())
    settings=protocol['training']
    for architecture in ('mlp','sequence'):
        for seed in settings['seeds']:
            random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
            model=Diwali(architecture,scales).to(device);params=sum(p.numel() for p in model.parameters())
            assert params<=protocol['models'][architecture]['parameter_limit']
            opt=torch.optim.AdamW(model.parameters(),lr=settings['learning_rate'],weight_decay=settings['weight_decay'])
            scale=torch.tensor(scales,device=device);best=float('inf');patience=0;began=time.monotonic();epochs=0
            path=a.output/f'{architecture}-{seed}.pt';status('Training',architecture=architecture,seed=seed,epoch=0,parameters=params)
            for epoch in range(1,settings['max_epochs']+1):
                model.train();perm=np.random.permutation(len(fx));loss_total=0
                for lo in range(0,len(perm),settings['batch_size']):
                    ids=perm[lo:lo+settings['batch_size']]
                    x=torch.from_numpy(np.array(fx[ids])).to(device);y=torch.from_numpy(fy[ids]).to(device)
                    opt.zero_grad(set_to_none=True);pred=model(x);loss=(((pred-y)/scale)**2).mean();loss.backward();opt.step()
                    loss_total+=float(loss.detach().cpu())*len(ids)
                prediction,_=infer(model,vx,device);mae=float(np.abs(prediction-vy).mean());epochs=epoch
                memory=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                if not np.isfinite(mae) or memory>settings['peak_memory_budget_gb']*1024**3:
                    raise RuntimeError('Nonfinite training result or process memory budget exceeded')
                item={'peak_rss_gb':memory/1024**3,'architecture':architecture,'seed':seed,'epoch':epoch,'training_loss':loss_total/len(fx),
                    'development_ohlc_mae_bp':mae,'seconds':round(time.monotonic()-began,2)};history.append(item)
                if mae<best:
                    best=mae;patience=0;torch.save({'state_dict':{k:v.detach().cpu() for k,v in model.state_dict().items()},'architecture':architecture,'scales':scales.tolist(),'seed':seed,'epoch':epoch},path)
                else:patience+=1
                status('Training',architecture=architecture,seed=seed,epoch=epoch,parameters=params)
                print(json.dumps(item),flush=True)
                if patience>=settings['early_stopping_patience'] or time.monotonic()-began>=settings['max_wall_minutes_per_seed']*60:break
            saved=torch.load(path,map_location='cpu',weights_only=True);model.load_state_dict(saved['state_dict']);model.to(device)
            pred,_=infer(model,vx,device)
            runs.append({'architecture':architecture,'seed':seed,'parameters':params,'epochs_run':epochs,
                'selected_epoch':saved['epoch'],'development':score(vy,pred,vi),'checkpoint_sha256':file_hash(path),
                'wall_seconds':round(time.monotonic()-began,2),'resource_capped':time.monotonic()-began>=settings['max_wall_minutes_per_seed']*60})
            status('Run complete',architecture=architecture,seed=seed)
            del model,opt
            if device=='mps':torch.mps.empty_cache()
    means={arch:float(np.mean([r['development']['mean_ohlc_mae_bp'] for r in runs if r['architecture']==arch])) for arch in ('mlp','sequence')}
    winner=min(means,key=means.get)
    if abs(means['mlp']-means['sequence'])<=.01:
        winner=min(('mlp','sequence'),key=lambda arch:next(r['parameters'] for r in runs if r['architecture']==arch))
    selected=next(r for r in runs if r['architecture']==winner and r['seed']==17)
    save(a.output/'selection.json',{'architecture':winner,'seed':17,'development_three_seed_means':means,
        'selection_complete_before_test':True,'selected_epoch':selected['selected_epoch']})
    saved=torch.load(a.output/f'{winner}-17.pt',map_location='cpu',weights_only=True)
    model=Diwali(winner,scales).to(device);model.load_state_dict(saved['state_dict'])
    # Calibration precedes the single final test evaluation.
    status('Calibrating uncertainty')
    cx,cy,ci,_,_=data.part('calibration');cp,_=infer(model,cx,device)
    intervals={str(level):np.sort(np.abs(cp-cy),axis=0)[min(len(cy),math.ceil((len(cy)+1)*level))-1].tolist() for level in (.8,.95)}
    save(a.output/'calibration.json',{'per_output_marginal_absolute_error_radii_bp':intervals,'examples':len(cy),'iid_guarantee':False})
    status('Evaluating selected model on untouched test')
    tx,ty,ti,anchors,targets=data.part('locked_test');tp,seconds=infer(model,tx,device)
    fp,_=infer(model,fx,device);vp,_=infer(model,vx,device)
    majority=max((-1,0,1),key=lambda s:int(np.sum(np.sign(fy[:,3])==s)))
    bp=baseline_predict(data.raw,ti,data.book,data.trades,majority)
    report={'model':'diwali0.1','architecture':winner,'seed':17,'parameters':selected['parameters'],
        'historical_candle_availability':'ASSUMED','device':device,'runs':runs,'history':history,
        'selection':json.loads((a.output/'selection.json').read_text()),
        'training':score(fy,fp,fi),'development':score(vy,vp,vi),'test':score(ty,tp,ti),
        'test_baselines':{name:score(ty,pred,ti) for name,pred in bp.items()},
        'recent_market_error':None,'recent_market_note':'No prospective model predictions have been evaluated.',
        'intervals':{level:{'radius_bp':radius,'test_coverage_per_ohlc':np.mean(np.abs(tp-ty)<=np.asarray(radius),axis=0).tolist(),
            'width_bp':(2*np.asarray(radius)).tolist()} for level,radius in intervals.items()},
        'batch_test_inference_seconds':seconds,'batch_test_seconds_per_example':seconds/len(tx),
        'latency_note':'Batched throughput, not interactive single-request latency.',
        'example_counts':{'training':len(fy),'development':len(vy),'calibration':len(cy),'test':len(ty)},
        'direction_note':'Close direction is relative to last input candle close. Candle colour compares close with open; neither is a trade win rate.',
        'limitations':['One conditional historical month, assumed candle arrival times.','No certified live accuracy or profit claim.','Three development days and two calibration days limit generalization.'],
        'wall_seconds':time.time()-started,'checkpoint_sha256':file_hash(a.output/f'{winner}-17.pt')}
    np.savez(a.output/'test-predictions.npz',prediction_bp=tp,actual_bp=ty,indices=ti,anchors=anchors,targets=targets)
    save(a.output/'report.json',report);status('Complete',selected_architecture=winner)
    print('COMPLETE',winner,report['test']['mean_ohlc_mae_bp'],flush=True)

if __name__=='__main__':main()
