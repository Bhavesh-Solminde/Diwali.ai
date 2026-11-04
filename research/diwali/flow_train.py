"""Matched mean-flow versus full temporal-flow correction training."""
import json
from pathlib import Path
import random,time
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from .directional import net_loss,calibrate_endpoint
from .flow import FlowResidual,FlowJoint
from .refined import cached_logits
from .net_direction import net_probabilities,net_metrics
from .probability import probabilities,calibrate
from .path_evaluate import evaluate
from ..market_data.validate_archive import save,file_hash


def main():
    out=Path('data/models/diwali1.1');out.mkdir(parents=True,exist_ok=False);began=time.time();prior=Path('data/models/diwali0.9');r=json.loads((prior/'report.json').read_text());mode=r['selected_mode'];info=r['models'][mode]
    parent={'root':str(prior),'mode':mode,'checkpoint':str(prior/f'{mode}-17.pt'),'checkpoint_sha256':info['checkpoint_sha256'],'report_sha256':file_hash(prior/'report.json'),'temperatures':info['residual_temperatures'],'colour_temperature':info['colour_temperature'],'config':r['protocol']['parents']}
    protocol={'model':'diwali1.1','parent':parent,'target':'15th future close > frozen reference versus <= reference; not first candle or monotone path',
        'variants':['mean_control','flow_sequence'],'branch':'zero-output92-input24-hidden GRU over60seconds book87+trade5; mean control repeats channel means, sequence preserves order',
        'loss':'both arms: near-weighted rangeCE +.25colourCE +1.0 final binary CE from summed price bins',
        'selection':'lowest3-seed mean development FINAL binary log loss, epoch0 allowed; fixedseed17; mean_control breaks ties; freeze before calibration/benchmark',
        'calibration':'same calibration for both arms: h1-14 binNLL; h15 binary endpointNLL using full26-bin temperature; .5..2 grid; colour separate. Parent calibration already reused, not fresh.',
        'seeds':[17,29,43],'epochs':20,'patience':4,'batch':128,'learning_rate':.0003,'weight_decay':.0001,'gradient_clip':5,
        'joint':'same fixed unit coupling to frozen0.7, no new dependence search',
        'cohort':'same0.5 purged October origins; no future features or changed target labels',
        'limitations':['Repeatedly inspected benchmark, not fresh holdout.','A correct distribution can assign probability to both sides; never erase downside after Reveal.','Direction might stay near50-50; no promise of confidence or profitable entries.','Equality belongs to down_or_unchanged, not silently pure down.'],
        'source_sha256':file_hash(Path(__file__)),'model_source_sha256':file_hash(Path('research/diwali/flow.py')),
        'dependency_sources':{str(p):file_hash(p) for p in [Path('research/diwali')/n for n in ['directional.py','refined.py','path.py','fan.py','probability.py','coupled.py','path_evaluate.py']]}}
    save(out/'run-protocol.json',protocol)
    def status(stage,**kw):save(out/'status.json',{'model':'diwali1.1','stage':stage,'seconds':time.time()-began,**kw})
    torch.set_num_threads(4);device='mps' if torch.backends.mps.is_available() else 'cpu';status('Verifying parent and data');hashes=json.loads((prior/'parent-hashes.json').read_text())
    for path,value in hashes.items():
        if file_hash(Path(path))!=value:raise ValueError('Changed parent data')
    if file_hash(Path(parent['checkpoint']))!=parent['checkpoint_sha256']:raise ValueError('Changed parent weights')
    save(out/'parent-hashes.json',hashes);root=Path('data/models/diwali0.5');raw=np.load('data/btc-perp/button-pilot-202610-v1/candle-raw.npy');parts={}
    for name in ['fit','development','calibration','locked_test']:
        z=np.load(root/f'{name}-targets.npz');p=np.load(prior/f'{mode}-{name}-predictions.npz');idx=z['indices'];np.testing.assert_array_equal(idx,p['indices'])
        parts[name]={'x':np.load(root/f'{name}-features.npy',mmap_mode='r'),'y':z['bin_labels'],'colour':z['colour_labels'],'indices':idx,'reference':z['reference'],'base':np.log(p['bin_probabilities']).astype(np.float32),'base_colour':np.log(p['colour_probabilities']).astype(np.float32),'volatility':np.array([np.std(np.diff(np.log(raw[int(v[2])-16:int(v[2]),3])))*10000 for v in idx])}
    fit=parts['fit'];dev=parts['development'];runs=[];history=[];weights=torch.tensor(np.r_[.5,np.full(14,.5/14)],dtype=torch.float32,device=device)
    def score(model):
        z,_=cached_logits(model,dev,device);p=net_probabilities(probabilities(z[:,-1]));y=(dev['y'][:,-1]>12).astype(int);return float(-np.log(np.maximum(p[np.arange(len(y)),y],1e-15)).mean())
    for variant in protocol['variants']:
        for seed in protocol['seeds']:
            random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);model=FlowResidual(variant).to(device);optimizer=torch.optim.AdamW(model.parameters(),lr=.0003,weight_decay=.0001);best=score(model);initial=best;epoch_best=0;wait=0;state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
            for epoch in range(1,21):
                model.train();order=np.random.permutation(len(fit['x']));total=0.
                for start in range(0,len(order),128):
                    ids=order[start:start+128];x=torch.tensor(np.array(fit['x'][ids]),device=device);y=torch.tensor(fit['y'][ids],device=device);c=torch.tensor(fit['colour'][ids],device=device);optimizer.zero_grad(set_to_none=True);a,b=model(x);a=a+torch.tensor(fit['base'][ids],device=device);b=b+torch.tensor(fit['base_colour'][ids],device=device)
                    loss=(F.cross_entropy(a.reshape(-1,26),y.reshape(-1),reduction='none').reshape(-1,15)*weights).sum(1).mean()+.25*F.cross_entropy(b,c)
                    loss=loss+net_loss(a,y)
                    if not torch.isfinite(loss):raise ValueError('Nonfinite loss')
                    loss.backward();nn.utils.clip_grad_norm_(model.parameters(),5);optimizer.step();total+=float(loss.detach().cpu())*len(ids)
                value=score(model);item={'variant':variant,'seed':seed,'epoch':epoch,'development_final_binary_log_loss':value,'training_loss':total/len(order)};history.append(item);status('Training',**item);print(json.dumps(item),flush=True)
                if value<best:best=value;epoch_best=epoch;wait=0;state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
                else:wait+=1
                if wait>=4:break
            torch.save({'state_dict':state,'epoch':epoch_best,'seed':seed,'variant':variant},out/f'{variant}-{seed}.pt');runs.append({'variant':variant,'seed':seed,'epoch':epoch_best,'development_final_binary_log_loss':best,'epoch0_loss':initial});save(out/'runs.json',runs);save(out/'history.json',history);del model,optimizer
            if device=='mps':torch.mps.empty_cache()
    means={v:float(np.mean([i['development_final_binary_log_loss'] for i in runs if i['variant']==v])) for v in protocol['variants']};selected=min(means,key=means.get);save(out/'selection.json',{'mode':selected,'seed':17,'means':means,'frozen_before_calibration_and_benchmark':True});report={'model':'diwali1.1','selected_mode':selected,'protocol':protocol,'runs':runs,'models':{},'recent_live_accuracy':None,'device':device}
    for variant in protocol['variants']:
        model=FlowResidual(variant).to(device);model.load_state_dict(torch.load(out/f'{variant}-17.pt',map_location='cpu',weights_only=True)['state_dict']);status('Calibrating',variant=variant);a,b=cached_logits(model,parts['calibration'],device);temps=[calibrate(a[:,h],parts['calibration']['y'][:,h]) for h in range(14)];t,ledger=calibrate_endpoint(a[:,-1],parts['calibration']['y'][:,-1]);temps.append(t);ct=calibrate(b,parts['calibration']['colour']);joint=FlowJoint(out/f'{variant}-17.pt',parent,temps,variant).to(device).eval();info={'temperatures':[1.]*15,'residual_temperatures':temps,'colour_temperature':ct,'endpoint_calibration':ledger,'checkpoint_sha256':file_hash(out/f'{variant}-17.pt'),'device':device}
        info['partitions']=evaluate(joint,info,parts,out,variant,root,Path('data/models/diwali0.6'),status)
        for name,p in info['partitions'].items():
            saved=np.load(out/f'{variant}-{name}-predictions.npz');p['overall_direction']=net_metrics(parts[name]['y'][:,-1],saved['bin_probabilities'][:,-1]);old=np.load(prior/f'{mode}-{name}-predictions.npz');p['diwali0.9_overall_direction']=net_metrics(parts[name]['y'][:,-1],old['bin_probabilities'][:,-1])
            probability=(parts['fit']['y'][:,-1]>12).mean();truth=parts[name]['y'][:,-1]>12;p['fit_frequency_binary_log_loss']=float(-(truth*np.log(probability)+(~truth)*np.log1p(-probability)).mean());p['always_half_binary_log_loss']=float(np.log(2));p['fit_majority_direction_accuracy']=float((truth==(probability>=.5)).mean())
        info['coupling_checks']={'maximum_marginal_difference':joint.maximum_difference,'maximum_iterations':joint.maximum_iterations};report['models'][variant]=info
    report['wall_seconds']=time.time()-began;save(out/'report.json',report);status('Complete',selected_mode=selected);print('COMPLETE',selected,means,flush=True)


if __name__=='__main__':main()
