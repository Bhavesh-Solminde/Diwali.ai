"""Diwali0.7: controlled joint-plus-marginal training from frozen0.6 checkpoints."""
import argparse
import json
from pathlib import Path
import random
import time

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from .path import PathModel,propagate,chain_losses
from .path_evaluate import evaluate
from .probability import probabilities,calibrate
from ..market_data.build_pilot import WARMUP
from ..market_data.validate_archive import file_hash,save


def losses(a,t,y):
    """Joint conditional NLL and unconditional marginal NLL, both mean per step."""
    loga=F.log_softmax(a,dim=-1);logt=F.log_softmax(t,dim=-1);rows=torch.arange(len(y),device=y.device)[:,None];steps=torch.arange(14,device=y.device)[None]
    joint=(-loga.gather(1,y[:,:1]).squeeze(1)-logt[rows,steps,y[:,:-1],y[:,1:]].sum(1))/15
    p=loga.exp();tr=logt.exp();marginals=[p]
    for h in range(14):p=torch.bmm(p[:,None,:],tr[:,h]).squeeze(1);marginals.append(p)
    marginal=-torch.stack(marginals,1).clamp_min(1e-30).log().gather(2,y[:,:,None]).squeeze(2).mean(1)
    return joint.mean(),marginal.mean()


def development(model,part,device):
    model.eval();j=m=0
    with torch.inference_mode():
        for start in range(0,len(part['x']),64):
            x=torch.tensor(np.array(part['x'][start:start+64]),device=device);y=torch.tensor(part['y'][start:start+64],device=device)
            a,t,_=model.all_transitions(x);jj,mm=losses(a,t,y);j+=float(jj.cpu())*len(x);m+=float(mm.cpu())*len(x)
    return {'joint_per_step':j/len(part['x']),'marginal_per_step':m/len(part['x']),'composite':(j+m)/len(part['x'])}


def raw_logits(model,x,device):
    model.eval();aa=[];tt=[];cc=[]
    with torch.inference_mode():
        for start in range(0,len(x),64):
            a,t,c=model.all_transitions(torch.tensor(np.array(x[start:start+64]),device=device));aa.append(a.cpu().numpy());tt.append(t.cpu().numpy());cc.append(c.cpu().numpy())
    return np.concatenate(aa),np.concatenate(tt),np.concatenate(cc)


def calibrate_composite(a,t,y):
    grid=np.exp(np.linspace(np.log(.5),np.log(2),41));scores=[]
    for temp in grid:
        initial=probabilities(a,temp);transitions=probabilities(t,temp);m=propagate(initial,transitions)
        joint=float(chain_losses(initial,transitions,y).mean()/15);marginal=float(-np.log(np.maximum(np.take_along_axis(m,y[:,:,None],2),1e-15)).mean())
        scores.append(joint+marginal)
    best=int(np.argmin(scores));return float(grid[best]),{'grid':grid.tolist(),'composite_scores':scores,'selected_index':best,'bound_hit':best in [0,len(grid)-1]}


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path('data/models/diwali0.7'));a=p.parse_args();out=a.output;out.mkdir(parents=True,exist_ok=False);began=time.time()
    def status(stage,**kw):save(out/'status.json',{'model':'diwali0.7','stage':stage,'seconds':time.time()-began,**kw})
    parent=Path('data/models/diwali0.6');dataset=Path('data/models/diwali0.5');old=json.loads((parent/'report.json').read_text())
    if old['selected_mode']!='markov':raise ValueError('Expected frozen Markov parent')
    protocol={'model':'diwali0.7','task':'retain coherent joint15-close paths while reducing unconditional marginal error',
        'architecture':'unchanged21,308-parameter0.6 Markov model, warm-start corresponding seed checkpoint, reset optimizer',
        'variants':['joint_control','balanced'],'training_losses':'joint_control: mean joint NLL perstep+.25colourCE; balanced: joint+mean unconditional marginal NLL+.25colourCE',
        'marginal_calculation':'differentiable exact forward probability sum; floor1e-30 only for numerical log safety; no future labels supplied to transition generation',
        'seeds':[17,29,43],'extra_epochs':20,'patience':4,'batch':128,'learning_rate':.0001,'weight_decay':.0001,'gradient_clip':5,
        'selection':'same joint-perstep plus marginal-perstep development score for both variants; three-seed mean; deploy seed17 fixed; epoch0 parent is candidate',
        'calibration':'same one global conditional temperature for both variants,41loggrid .5..2, minimizes calibration joint-perstep+marginal-perstep; colour scalar separately',
        'cohort':'exact0.5 purged fit/development/calibration/inspected benchmark; verify against0.6 parent hashes; no new data/labels',
        'limitations':['Already-inspected October benchmark, no fresh test claim.','Coarse first-order future bins and historical receipt assumptions remain.','Weighted proper scores do not guarantee perfect probabilities or directional edge.'],
        'source_sha256':file_hash(Path(__file__)),'parent_report_sha256':file_hash(parent/'report.json'),'parent_checkpoints':{str(seed):file_hash(parent/f'markov-{seed}.pt') for seed in [17,29,43]}}
    save(out/'run-protocol.json',protocol);status('Verifying frozen parent arrays');torch.set_num_threads(4);device='mps' if torch.backends.mps.is_available() else 'cpu'
    hashes=json.loads((parent/'parent-hashes.json').read_text())
    for filename,expected in hashes.items():
        if file_hash(Path(filename))!=expected:raise ValueError('Changed parent data: '+filename)
    save(out/'parent-hashes.json',hashes);raw=np.load('data/btc-perp/button-pilot-202610-v1/candle-raw.npy');parts={}
    for name in ['fit','development','calibration','locked_test']:
        z=np.load(dataset/f'{name}-targets.npz');idx=z['indices'];vol=np.array([np.std(np.diff(np.log(raw[int(r[2])-16:int(r[2]),3])))*10000 for r in idx])
        parts[name]={'x':np.load(dataset/f'{name}-features.npy',mmap_mode='r'),'y':z['bin_labels'],'colour':z['colour_labels'],'indices':idx,'reference':z['reference'],'volatility':vol}
    runs=[];history=[]
    for variant in protocol['variants']:
        for seed in protocol['seeds']:
            random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);model=PathModel('markov').to(device);checkpoint=parent/f'markov-{seed}.pt'
            if file_hash(checkpoint)!=protocol['parent_checkpoints'][str(seed)]:raise ValueError('Changed warm-start checkpoint')
            model.load_state_dict(torch.load(checkpoint,weights_only=True,map_location='cpu')['state_dict']);opt=torch.optim.AdamW(model.parameters(),lr=.0001,weight_decay=.0001)
            dev=development(model,parts['development'],device);best=dev['composite'];bestepoch=0;beststate={k:v.detach().cpu().clone() for k,v in model.state_dict().items()};wait=0
            history.append({'variant':variant,'seed':seed,'epoch':0,'development':dev});fit=parts['fit']
            for epoch in range(1,21):
                model.train();order=np.random.permutation(len(fit['x']));total=0
                for start in range(0,len(order),128):
                    ids=order[start:start+128];x=torch.tensor(np.array(fit['x'][ids]),device=device);y=torch.tensor(fit['y'][ids],device=device);colour=torch.tensor(fit['colour'][ids],device=device)
                    opt.zero_grad(set_to_none=True)
                    if variant=='joint_control':
                        # Exact same joint objective; unused previous states have zero
                        # joint-likelihood gradient, so enumerating them is unnecessary.
                        z,c=model(x,y[:,:-1]);loss=F.cross_entropy(z.reshape(-1,26),y.reshape(-1))+.25*F.cross_entropy(c,colour)
                    else:
                        aa,t,c=model.all_transitions(x);jj,mm=losses(aa,t,y);loss=jj+mm+.25*F.cross_entropy(c,colour)
                    if not torch.isfinite(loss):raise ValueError('Nonfinite training loss')
                    loss.backward();nn.utils.clip_grad_norm_(model.parameters(),5);opt.step();total+=float(loss.detach().cpu())*len(ids)
                dev=development(model,parts['development'],device);item={'variant':variant,'seed':seed,'epoch':epoch,'development':dev,'training_loss':total/len(order)};history.append(item);status('Training',**item);print(json.dumps(item),flush=True)
                if dev['composite']<best:
                    best=dev['composite'];bestepoch=epoch;beststate={k:v.detach().cpu().clone() for k,v in model.state_dict().items()};wait=0
                else:wait+=1
                if wait>=4:break
            torch.save({'variant':variant,'seed':seed,'epoch':bestepoch,'state_dict':beststate},out/f'{variant}-{seed}.pt');runs.append({'variant':variant,'seed':seed,'epoch':bestepoch,'development_composite':best});save(out/'runs.json',runs)
            del model,opt
            if device=='mps':torch.mps.empty_cache()
    means={v:float(np.mean([r['development_composite'] for r in runs if r['variant']==v])) for v in protocol['variants']};chosen=min(means,key=means.get);save(out/'selection.json',{'variant':chosen,'seed':17,'development_three_seed_means':means,'before_calibration':True})
    report={'model':'diwali0.7','selected_mode':chosen,'runs':runs,'history':history,'protocol':protocol,'models':{},'device':device,'recent_live_accuracy':None}
    for variant in protocol['variants']:
        status('Calibrating same composite criterion',variant=variant);model=PathModel('markov').to(device);model.load_state_dict(torch.load(out/f'{variant}-17.pt',weights_only=True,map_location='cpu')['state_dict']);model.eval()
        cp=parts['calibration'];aa,t,c=raw_logits(model,cp['x'],device);temp,ledger=calibrate_composite(aa,t,cp['y']);ct=calibrate(c,cp['colour']);del aa,t,c
        info={'temperatures':[temp]*15,'colour_temperature':ct,'calibration':ledger,'checkpoint_sha256':file_hash(out/f'{variant}-17.pt'),'device':device}
        info['partitions']=evaluate(model,info,parts,out,variant,dataset,parent,status);report['models'][variant]=info
    report['wall_seconds']=time.time()-began;save(out/'report.json',report);status('Complete',selected_mode=chosen);print('COMPLETE',chosen,means,flush=True)


if __name__=='__main__':main()
