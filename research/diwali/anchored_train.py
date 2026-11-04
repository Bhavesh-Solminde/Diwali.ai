"""Matched midpoint-disabled versus midpoint-enabled raw-parent correction."""
import json
from pathlib import Path
import random,time
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from .directional import net_loss,calibrate_endpoint
from .anchored import AnchoredResidual,AnchoredJoint,JoinedFeatures,raw_parents,load_parent
from .fan import FanModel,infer
from .refined import cached_logits
from .net_direction import net_probabilities,net_metrics
from .probability import probabilities,calibrate
from .path_evaluate import evaluate
from ..market_data.validate_archive import save,file_hash


def main():
    out=Path('data/models/diwali1.2');out.mkdir(parents=True,exist_ok=False);began=time.time();prior=Path('data/models/diwali0.5');r=json.loads((prior/'report.json').read_text());mode=r['selected_mode'];info=r['models'][mode]
    parent=raw_parents()
    protocol={'model':'diwali1.2','parent':parent,'target':'15th future close > frozen reference versus <= reference; not first candle or monotone path',
        'variants':['no_midpoint','with_midpoint'],'branch':'zero-output94-input24-hidden GRU; repeated92 flow means plus two midpoint summaries, disabled or enabled; raw frozen0.5 parent',
        'loss':'both arms: near-weighted rangeCE +.25colourCE +1.0 final binary CE from summed price bins',
        'selection':'lowest3-seed mean development FINAL binary log loss, epoch0 allowed; fixedseed17; no_midpoint breaks ties; freeze before calibration/benchmark',
        'calibration':'same calibration for both arms: h1-14 binNLL; h15 binary endpointNLL using full26-bin temperature; .5..2 grid; colour separate. Raw neural parents used without old fitted temperatures; calibrate new marginal pipeline once. October dates still reused in research.',
        'seeds':[17,29,43],'epochs':20,'patience':4,'batch':128,'learning_rate':.0003,'weight_decay':.0001,'gradient_clip':5,
        'joint':'fixed unit coupling to raw0.7 transition kernel at temperature1; no old fitted temperatures',
        'cohort':'same0.5 purged October origins; no future features or changed target labels',
        'limitations':['Repeatedly inspected benchmark, not fresh holdout.','A correct distribution can assign probability to both sides; never erase downside after Reveal.','Direction might stay near50-50; no promise of confidence or profitable entries.','Equality belongs to down_or_unchanged, not silently pure down.'],
        'midpoint_preparation':{'root':'data/btc-perp/midpoint-windows-202610-v1','manifest_sha256':file_hash(Path('data/btc-perp/midpoint-windows-202610-v1/manifest.json'))},
        'source_sha256':file_hash(Path(__file__)),'model_source_sha256':file_hash(Path('research/diwali/anchored.py')),
        'dependency_sources':{str(p):file_hash(p) for p in [Path('research/diwali')/n for n in ['directional.py','refined.py','model.py','path.py','fan.py','probability.py','coupled.py','path_evaluate.py']]},
        'midpoint_transform_sources':{str(p):file_hash(p) for p in [Path('research/market_data')/n for n in ['midpoint.py','midpoint_windows.py']]}}
    save(out/'run-protocol.json',protocol)
    def status(stage,**kw):save(out/'status.json',{'model':'diwali1.2','stage':stage,'seconds':time.time()-began,**kw})
    torch.set_num_threads(4);device='mps' if torch.backends.mps.is_available() else 'cpu';status('Verifying parent and data');hashes=json.loads(Path('data/models/diwali0.8/parent-hashes.json').read_text())
    for path,value in hashes.items():
        if file_hash(Path(path))!=value:raise ValueError('Changed parent data')
    for config in parent.values():
        if file_hash(Path(config['checkpoint']))!=config['checkpoint_sha256']:raise ValueError('Changed parent weights')
    save(out/'parent-hashes.json',hashes);root=Path('data/models/diwali0.5');raw=np.load('data/btc-perp/button-pilot-202610-v1/candle-raw.npy');parts={}
    midroot=Path(protocol['midpoint_preparation']['root']);mid=json.loads((midroot/'manifest.json').read_text())
    if mid['state']!='complete':raise ValueError('Incomplete midpoint preparation')
    for name,expected in mid['artifacts'].items():
        if file_hash(midroot/name)!=expected:raise ValueError('Changed midpoint artifact')
    for name,expected in mid['inputs'].items():
        if file_hash(Path(name))!=expected:raise ValueError('Changed midpoint source')
    save(out/'midpoint-manifest.json',mid);raw_model=load_parent(FanModel(),parent['marginal']).to(device)
    for name in ['fit','development','calibration','locked_test']:
        z=np.load(root/f'{name}-targets.npz');idx=z['indices'];np.testing.assert_array_equal(idx,np.load(midroot/f'{name}-indices.npy'));oldx=np.load(root/f'{name}-features.npy',mmap_mode='r');extra=np.load(midroot/f'{name}-summary.npy')
        status('Caching raw uncalibrated neural parent logits',partition=name);a,b=infer(raw_model,oldx,device);np.savez(out/f'{name}-raw-parent-logits.npz',ranges=a,colour=b)
        parts[name]={'x':JoinedFeatures(oldx,extra),'y':z['bin_labels'],'colour':z['colour_labels'],'indices':idx,'reference':z['reference'],'base':a,'base_colour':b,'volatility':np.array([np.std(np.diff(np.log(raw[int(v[2])-16:int(v[2]),3])))*10000 for v in idx])}
    del raw_model
    fit=parts['fit'];dev=parts['development'];runs=[];history=[];weights=torch.tensor(np.r_[.5,np.full(14,.5/14)],dtype=torch.float32,device=device)
    def score(model):
        z,_=cached_logits(model,dev,device);p=net_probabilities(probabilities(z[:,-1]));y=(dev['y'][:,-1]>12).astype(int);return float(-np.log(np.maximum(p[np.arange(len(y)),y],1e-15)).mean())
    for variant in protocol['variants']:
        for seed in protocol['seeds']:
            random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);model=AnchoredResidual(variant).to(device);optimizer=torch.optim.AdamW(model.parameters(),lr=.0003,weight_decay=.0001);best=score(model);initial=best;epoch_best=0;wait=0;state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
            if variant=='no_midpoint' and seed==17:torch.save({'state_dict':state,'epoch':0,'seed':17,'variant':'epoch0_parent'},out/'epoch0_parent-17.pt')
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
    means={v:float(np.mean([i['development_final_binary_log_loss'] for i in runs if i['variant']==v])) for v in protocol['variants']};selected=min(means,key=means.get);save(out/'selection.json',{'mode':selected,'seed':17,'means':means,'frozen_before_calibration_and_benchmark':True});report={'model':'diwali1.2','selected_mode':selected,'protocol':protocol,'runs':runs,'models':{},'recent_live_accuracy':None,'device':device}
    for variant in [*protocol['variants'],'epoch0_parent']:
        branch_mode='no_midpoint' if variant=='epoch0_parent' else variant
        model=AnchoredResidual(branch_mode).to(device);model.load_state_dict(torch.load(out/f'{variant}-17.pt',map_location='cpu',weights_only=True)['state_dict']);status('Calibrating',variant=variant);a,b=cached_logits(model,parts['calibration'],device);temps=[calibrate(a[:,h],parts['calibration']['y'][:,h]) for h in range(14)];t,ledger=calibrate_endpoint(a[:,-1],parts['calibration']['y'][:,-1]);temps.append(t);ct=calibrate(b,parts['calibration']['colour']);joint=AnchoredJoint(out/f'{variant}-17.pt',parent,temps,branch_mode).to(device).eval();info={'branch_mode':branch_mode,'temperatures':[1.]*15,'residual_temperatures':temps,'colour_temperature':ct,'endpoint_calibration':ledger,'checkpoint_sha256':file_hash(out/f'{variant}-17.pt'),'device':device}
        info['partitions']=evaluate(joint,info,parts,out,variant,root,Path('data/models/diwali0.6'),status)
        for name,p in info['partitions'].items():
            saved=np.load(out/f'{variant}-{name}-predictions.npz');p['overall_direction']=net_metrics(parts[name]['y'][:,-1],saved['bin_probabilities'][:,-1]);old=np.load(prior/f'{mode}-{name}-predictions.npz');p['diwali0.5_original_overall_direction']=net_metrics(parts[name]['y'][:,-1],old['bin_probabilities'][:,-1])
            probability=(parts['fit']['y'][:,-1]>12).mean();truth=parts[name]['y'][:,-1]>12;p['fit_frequency_binary_log_loss']=float(-(truth*np.log(probability)+(~truth)*np.log1p(-probability)).mean());p['always_half_binary_log_loss']=float(np.log(2));p['fit_majority_direction_accuracy']=float((truth==(probability>=.5)).mean())
        info['coupling_checks']={'maximum_marginal_difference':joint.maximum_difference,'maximum_iterations':joint.maximum_iterations};report['models'][variant]=info
    report['wall_seconds']=time.time()-began;save(out/'report.json',report);status('Complete',selected_mode=selected);print('COMPLETE',selected,means,flush=True)


if __name__=='__main__':main()
