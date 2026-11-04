"""Frozen protocol: recent minute detail versus parameter-matched grouped control."""
import argparse
import json
from pathlib import Path
import random
import time

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from .refined import RecentResidual,RefinedJoint,cached_logits
from .coupled import parent_config
from .probability import probabilities,calibrate
from .path_evaluate import evaluate
from ..market_data.validate_archive import file_hash,save


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=Path('data/models/diwali0.9'));args=parser.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=False);began=time.time()
    def status(stage,**kw):save(out/'status.json',{'model':'diwali0.9','stage':stage,'seconds':time.time()-began,**kw})
    config=parent_config();protocol={'model':'diwali0.9','parents':config,'hypothesis':'Recent minute-level detail lost by15-candle compression can improve individual future-close probabilities.',
        'variants':['grouped','minute_detail'],'branch':'identical8-input16-hidden GRU plus15x26 and3-colour heads; grouped averages4groups of15 and repeats each group15 times; detail receives last60 completed candles intact',
        'initialization':'frozen selected calibrated0.5 probabilities plus zero-initialized residual output; epoch0 parent candidate',
        'loss':'same0.5 near-weighted CE: h1=.5, h2-15=.5/14 each; plus.25colourCE',
        'seeds':[17,29,43],'epochs':20,'patience':4,'batch':128,'learning_rate':.0003,'weight_decay':.0001,'gradient_clip':5,
        'selection':'lowest three-seed mean development equal15-horizon marginal log loss; fixedseed17; grouped wins exact ties. Save before calibration/benchmark.',
        'calibration':'fit one bounded scalar temperature per horizon and colour on same prior calibration period; parent already used calibration, no independent calibration claim',
        'cohort':'unchanged purged0.5 origins and scalers; verify raw/features/target parent hashes; no synthetic future inputs or extra data',
        'joint':'after marginal selection, same0.8 unit coupling to frozen0.7; no coefficient tuning or joint-based model selection',
        'limitations':['October benchmark repeatedly inspected; not fresh holdout.','Changes candle detail only, not book/trade granularity.','No causal attribution to detail unless matched control comparison supports it.','Perfect probabilities, 80-20 entries and profitability unproven.'],
        'source_sha256':file_hash(Path(__file__)),'model_source_sha256':file_hash(Path('research/diwali/refined.py'))}
    save(out/'run-protocol.json',protocol);status('Verifying frozen parent inputs');torch.set_num_threads(4);device='mps' if torch.backends.mps.is_available() else 'cpu';root=Path('data/models/diwali0.5');base=json.loads((root/'report.json').read_text());parent_mode=base['selected_mode'];parts={}
    hashes=json.loads(Path('data/models/diwali0.8/parent-hashes.json').read_text())
    for path,expected in hashes.items():
        if file_hash(Path(path))!=expected:raise ValueError('Changed parent input')
    save(out/'parent-hashes.json',hashes);raw=np.load('data/btc-perp/button-pilot-202610-v1/candle-raw.npy')
    for name in ['fit','development','calibration','locked_test']:
        target=np.load(root/f'{name}-targets.npz');old=np.load(root/f'{parent_mode}-{name}-predictions.npz');idx=target['indices'];np.testing.assert_array_equal(idx,old['indices'])
        parts[name]={'x':np.load(root/f'{name}-features.npy',mmap_mode='r'),'y':target['bin_labels'],'colour':target['colour_labels'],'indices':idx,'reference':target['reference'],
            'base':np.log(old['bin_probabilities']).astype(np.float32),'base_colour':np.log(old['colour_probabilities']).astype(np.float32),
            'volatility':np.array([np.std(np.diff(np.log(raw[int(r[2])-16:int(r[2]),3])))*10000 for r in idx])}
    fit=parts['fit'];dev=parts['development'];weights=torch.tensor(np.r_[.5,np.full(14,.5/14)],dtype=torch.float32,device=device);history=[];runs=[]
    def score(model):
        logits,_=cached_logits(model,dev,device);return float(-np.log(np.maximum(np.take_along_axis(probabilities(logits),dev['y'][:,:,None],2),1e-15)).mean())
    for mode in protocol['variants']:
        for seed in protocol['seeds']:
            random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);model=RecentResidual(mode).to(device);optimizer=torch.optim.AdamW(model.parameters(),lr=.0003,weight_decay=.0001)
            best=score(model);initial=best;best_epoch=0;wait=0;state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
            for epoch in range(1,21):
                model.train();order=np.random.permutation(len(fit['x']));total=0.
                for start in range(0,len(order),128):
                    ids=order[start:start+128];x=torch.tensor(np.array(fit['x'][ids]),device=device);y=torch.tensor(fit['y'][ids],device=device);c=torch.tensor(fit['colour'][ids],device=device)
                    optimizer.zero_grad(set_to_none=True);z,col=model(x);z=z+torch.tensor(fit['base'][ids],device=device);col=col+torch.tensor(fit['base_colour'][ids],device=device)
                    loss=(F.cross_entropy(z.reshape(-1,26),y.reshape(-1),reduction='none').reshape(-1,15)*weights).sum(1).mean()+.25*F.cross_entropy(col,c)
                    if not torch.isfinite(loss):raise ValueError('Nonfinite training loss')
                    loss.backward();nn.utils.clip_grad_norm_(model.parameters(),5);optimizer.step();total+=float(loss.detach().cpu())*len(ids)
                value=score(model);item={'mode':mode,'seed':seed,'epoch':epoch,'development_mean15_bin_log_loss':value,'training_loss':total/len(order)};history.append(item);status('Training',**item);print(json.dumps(item),flush=True)
                if value<best:best=value;best_epoch=epoch;wait=0;state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
                else:wait+=1
                if wait>=4:break
            torch.save({'mode':mode,'seed':seed,'epoch':best_epoch,'state_dict':state},out/f'{mode}-{seed}.pt');runs.append({'mode':mode,'seed':seed,'epoch':best_epoch,'development_mean15_bin_log_loss':best,'epoch0_development_loss':initial,'trainable_parameters':sum(p.numel() for p in model.parameters())})
            save(out/'runs.json',runs);save(out/'history.json',history);del model,optimizer
            if device=='mps':torch.mps.empty_cache()
    means={m:float(np.mean([v['development_mean15_bin_log_loss'] for v in runs if v['mode']==m])) for m in protocol['variants']};selected=min(means,key=means.get);save(out/'selection.json',{'mode':selected,'seed':17,'three_seed_mean_development_loss':means,'frozen_before_calibration_and_benchmark':True})
    report={'model':'diwali0.9','selected_mode':selected,'models':{},'runs':runs,'protocol':protocol,'device':device,'recent_live_accuracy':None}
    for mode in protocol['variants']:
        residual=RecentResidual(mode).to(device);residual.load_state_dict(torch.load(out/f'{mode}-17.pt',map_location='cpu',weights_only=True)['state_dict']);status('Calibrating',mode=mode)
        a,b=cached_logits(residual,parts['calibration'],device);temps=[calibrate(a[:,h],parts['calibration']['y'][:,h]) for h in range(15)];ct=calibrate(b,parts['calibration']['colour'])
        model=RefinedJoint(mode,out/f'{mode}-17.pt',config,temps).to(device).eval();info={'temperatures':[1.]*15,'residual_temperatures':temps,'colour_temperature':ct,'checkpoint_sha256':file_hash(out/f'{mode}-17.pt'),'device':device}
        info['partitions']=evaluate(model,info,parts,out,mode,root,Path('data/models/diwali0.6'),status)
        info['coupling_checks']={'maximum_marginal_difference':model.maximum_difference,'maximum_iterations':model.maximum_iterations};report['models'][mode]=info
    report['wall_seconds']=time.time()-began;save(out/'report.json',report);status('Complete',selected_mode=selected);print('COMPLETE',selected,means,flush=True)


if __name__=='__main__':main()
