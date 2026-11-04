"""Run the already frozen finite development comparison, resuming complete runs.

Never restart or overwrite an incomplete existing run. This is a scheduler for
local training, not a new model-selection search or a live trading process.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from .event_protocol import protocol
from ..market_data.validate_archive import file_hash,save


def choose_family(runs,settings):
    means={}
    for candidate in settings['neural_candidates']:
        subset=[r for r in runs if r['candidate']==candidate]
        keys={(r['fold'],r['seed']) for r in subset}
        expected={(f,s) for f in settings['development_folds'] for s in settings['seeds']}
        if keys!=expected or len(subset)!=len(expected):raise ValueError('Incomplete or duplicate bounded comparison')
        means[candidate]=float(np.mean([r['partitions']['score']['mean15_bin_log_loss'] for r in subset]))
    best=min(means,key=means.get);control='one_second_temporal_conv'
    if means[control]<=means[best]+.0001:best=control
    return {'selected_family':best,'mean_development_transfer_log_loss':means,
            'scope':'Development family selection only; not final independent evaluation or production promotion.'}


def verify_completed(out,module):
    report=out/'report.json';settings=json.loads((out/'run-protocol.json').read_text())
    for name,sha in settings['source_hashes'].items():
        if file_hash(Path(__file__).with_name(name))!=sha:raise ValueError('Changed frozen source for an existing run')
    if not report.exists():raise ValueError(f'Existing incomplete run must be inspected, never overwritten: {out}')
    result=json.loads(report.read_text())
    if module=='event_train' and file_hash(out/'weights.pt')!=result['selection']['weights_sha256']:raise ValueError('Changed selected weights')
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--cohort',type=Path,required=True);p.add_argument('--features',type=Path,required=True);p.add_argument('--content-audit',type=Path,required=True);p.add_argument('--auxiliary',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--resume',action='store_true');a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=a.resume);settings=protocol();began=time.time();runs=[];baselines={};lifetimes={}
    planned={**settings,'scheduler_sha256':file_hash(Path(__file__)),
             'data_hashes':{str(path):file_hash(path) for path in [a.cohort/'report.json',a.features/'report.json',a.content_audit,a.auxiliary/'report.json']}}
    own=a.output/'study-protocol.json'
    if own.exists() and json.loads(own.read_text())!=planned:raise ValueError('Study resume contract differs')
    save(own,planned)
    def invoke(module,name,extra):
        out=a.output/name
        if not out.exists():
            command=[sys.executable,'-m','research.diwali.'+module,'--cohort',str(a.cohort),'--features',str(a.features),'--content-audit',str(a.content_audit),'--output',str(out),*extra]
            log=a.output/(name+'.log')
            with log.open('w') as stream:
                child=subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT)
                save(a.output/'status.json',{'state':'running','active_run':name,'child_pid':child.pid,'log':str(log),'completed_neural_runs':len(runs),'elapsed_seconds':time.time()-began})
                print('started',name,child.pid,flush=True)
                code=child.wait()
            if code:raise ValueError(f'Run failed; inspect its retained log: {name}')
        result=verify_completed(out,module);print('complete',name,flush=True);return result
    try:
        for fold in settings['development_folds']:
            for candidate in settings['neural_candidates']:
                for seed in settings['seeds']:
                    name=f'{fold}-{candidate}-seed{seed}'
                    runs.append(invoke('event_train',name,['--fold',fold,'--candidate',candidate,'--seed',str(seed)]))
            baselines[fold]=invoke('event_baselines',f'{fold}-baselines',['--fold',fold])
            lifetimes[fold]=invoke('event_lifetime',f'{fold}-lifetime',['--fold',fold,'--auxiliary',str(a.auxiliary)])
            progress={'state':'development_in_progress','completed_folds':list(baselines),
                      'neural_runs':runs,'baselines':baselines,'lifetime':lifetimes,
                      'production_model_selected':False,'reserved_final_evaluated':False}
            save(a.output/'progress.json',progress)
            save(Path('results/diwali1.4/development-progress.json'),progress)
        decision=choose_family(runs,settings)
        report={'state':'development_complete','decision':decision,'neural_runs':runs,'baselines':baselines,'lifetime':lifetimes,
                'production_model_selected':False,'reserved_final_evaluated':False,'elapsed_seconds':time.time()-began,
                'next_required':'Build selected family on final fit dates; select/calibrate separately, deliberately release final test, then new prospective confirmation.'}
        save(a.output/'report.json',report);save(Path('results/diwali1.4/development-report.json'),report);save(a.output/'status.json',{'state':'development_complete','decision':decision})
    except Exception as error:
        save(a.output/'status.json',{'state':'failed','error':str(error),'completed_neural_runs':len(runs),'elapsed_seconds':time.time()-began});raise


if __name__=='__main__':main()
