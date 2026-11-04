"""Fit a dependence coefficient over two frozen neural parents; no future inputs."""
import argparse
import json
from pathlib import Path
import time

import numpy as np
import torch

from .coupled import reconcile,parent_config,make_model
from .path import PathModel,forecast,chain_losses
from .path_evaluate import evaluate
from ..market_data.build_pilot import WARMUP
from ..market_data.validate_archive import save,file_hash


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=Path('data/models/diwali0.8'));args=parser.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=False);began=time.time()
    def status(stage,**kw):save(out/'status.json',{'model':'diwali0.8','stage':stage,'seconds':time.time()-began,**kw})
    config=parent_config();protocol={'model':'diwali0.8','task':'fit coherent dependence while preserving0.5 predicted marginal distributions',
        'parents':config,'learned_parameters':'one dependence exponent gamma; both neural networks frozen, no neural retraining',
        'training_gamma_grid':[0,.25,.5,.75,1,1.25,1.5,1.75,2],'fit_origins':'2048 deterministic evenly spaced fit origins only; conditional target labels used only in joint loss',
        'variants':['independent','unit_dependence','fitted_dependence'],'selection':'lowest development joint log loss among three declared variants, fixed order breaks ties',
        'matrix_scaling':'positive kernel max(T,1e-30)^gamma; predicted row/column constraints; relative tolerance1e-8,max2000; failure stops run',
        'invariant':'normalized chain forward marginal differs from0.5 targets by at most2e-7 absolute probability',
        'calibration':'no new temperature fit; use frozen parents including their prior calibration; calibration partition is descriptive, not independent',
        'data_flow':'parents used fit/development/calibration previously; scalar fit uses their frozen outputs. No pure-crossfit or fresh calibration claim.',
        'limitations':['Repeatedly inspected October benchmark.','Scalar coupling cannot improve direction because marginals are preserved.','Finite price bins, unknown within-bin state and hidden/future orders.','No exact market-probability or trading guarantee.'],
        'reference':'https://proceedings.neurips.cc/paper_files/paper/2013/file/af21d0c97db2e27e13572cbf59eb343d-Paper.pdf',
        'source_sha256':file_hash(Path(__file__)),'coupling_source_sha256':file_hash(Path('research/diwali/coupled.py'))}
    save(out/'run-protocol.json',protocol);status('Verifying fixed cohort and preparing data');torch.set_num_threads(4);device='mps' if torch.backends.mps.is_available() else 'cpu'
    hashes=json.loads(Path('data/models/diwali0.7/parent-hashes.json').read_text())
    for path,expected in hashes.items():
        if file_hash(Path(path))!=expected:raise ValueError('Changed parent data')
    save(out/'parent-hashes.json',hashes);parts={};raw=np.load('data/btc-perp/button-pilot-202610-v1/candle-raw.npy');parent05=Path('data/models/diwali0.5');parent06=Path('data/models/diwali0.6')
    for name in ['fit','development','calibration','locked_test']:
        z=np.load(parent05/f'{name}-targets.npz');idx=z['indices'];parts[name]={'x':np.load(parent05/f'{name}-features.npy',mmap_mode='r'),'y':z['bin_labels'],'colour':z['colour_labels'],'indices':idx,'reference':z['reference'],
            'volatility':np.asarray([np.std(np.diff(np.log(raw[int(r[2])-16:int(r[2]),3])))*10000 for r in idx])}
    # A single scalar needs a bounded fitting set; full development/evaluation stay intact.
    ids=np.linspace(0,len(parts['fit']['x'])-1,2048,dtype=int);np.save(out/'gamma-fit-origin-ids.npy',ids)
    dependence=PathModel('markov').to(device);dependence.load_state_dict(torch.load(config['dependence']['checkpoint'],weights_only=True,map_location='cpu')['state_dict']);dependence.eval()
    sets={};old=json.loads((parent05/'report.json').read_text())['selected_mode']
    for name,rows in [('fit',ids),('development',np.arange(len(parts['development']['x'])))]:
        status('Building past-only parent prediction cache',partition=name);priors=[];x=parts[name]['x'];p=np.load(parent05/f'{old}-{name}-predictions.npz');m=p['bin_probabilities'][rows];y=parts[name]['y'][rows]
        for start in range(0,len(rows),64):
            _,t,_,_=forecast(dependence,x[rows[start:start+64]],config['dependence']['temperatures'],device);priors.append(t)
        sets[name]=(m,np.concatenate(priors),y)
        np.savez(out/f'{name}-coefficient-cache.npz',marginals=m,prior_transitions=sets[name][1],labels=y)
    ledger=[]
    def score(gamma,name):
        m,t,y=sets[name];loss=[];maximum=0;iterations=0
        for start in range(0,len(y),64):
            sl=slice(start,start+64);a,b,l=reconcile(m[sl],t[sl],gamma);loss.extend(chain_losses(a,b,y[sl]));maximum=max(maximum,l['maximum_marginal_difference']);iterations=max(iterations,l['iterations'])
        return {'gamma':gamma,'joint_log_loss':float(np.mean(loss)),'maximum_marginal_difference':maximum,'maximum_iterations':iterations}
    for gamma in protocol['training_gamma_grid']:
        status('Fitting dependence coefficient',gamma=gamma);item=score(gamma,'fit');ledger.append(item);print(json.dumps(item),flush=True)
    fitted=min(ledger,key=lambda r:r['joint_log_loss'])['gamma'];save(out/'fit-gamma-search.json',{'scores':ledger,'fitted_gamma':fitted,'boundary_hit':fitted in [0,2]})
    variants={'independent':0.,'unit_dependence':1.,'fitted_dependence':fitted};development={}
    for variant,gamma in variants.items():status('Development comparison',variant=variant);development[variant]=score(gamma,'development')
    selected=min(variants,key=lambda v:development[v]['joint_log_loss']);save(out/'selection.json',{'mode':selected,'gamma':variants[selected],'development':development,'before_benchmark':True})
    report={'model':'diwali0.8','selected_mode':selected,'protocol':protocol,'models':{},'device':device,'recent_live_accuracy':None}
    for variant,gamma in variants.items():
        definition={'model':'diwali0.8','gamma':gamma,'parents':config,'coupling_source_sha256':protocol['coupling_source_sha256']};save(out/f'{variant}-definition.json',definition)
        model=make_model(config,gamma,device);info={'gamma':gamma,'temperatures':[1.]*15,'colour_temperature':config['marginal']['colour_temperature'],'definition_sha256':file_hash(out/f'{variant}-definition.json'),'device':device}
        info['partitions']=evaluate(model,info,parts,out,variant,parent05,parent06,status)
        for name,part in info['partitions'].items():
            z=np.load(out/f'{variant}-{name}-predictions.npz');parent=np.load(parent05/f'{old}-{name}-predictions.npz');difference=float(abs(z['bin_probabilities']-parent['bin_probabilities']).max())
            if difference>1e-6:raise ValueError('Evaluated endpoint invariant violated')
            part['maximum_saved_marginal_difference_from0.5']=difference
            previous=np.load(Path('data/models/diwali0.7')/f'joint_control-{name}-predictions.npz');part['diwali0.7_joint_log_loss']=float(previous['joint_losses'].mean())
        info['coupling_checks']={'maximum_model_marginal_difference':model.maximum_difference,'maximum_iterations':model.maximum_iterations};report['models'][variant]=info
    report['wall_seconds']=time.time()-began;save(out/'report.json',report);status('Complete',selected_mode=selected);print('COMPLETE',selected,variants[selected],flush=True)


if __name__=='__main__':main()
