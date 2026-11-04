"""Resume the frozen study with corrected second-bin timestamps for controls.

Completed raw-event fits are imported unchanged. Failed controls are retained in
the prior study and excluded. No dates, targets, optimizer settings or candidate
families are changed by this implementation amendment.
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .event_protocol import protocol
from .event_study import choose_family,verify_completed
from ..market_data.validate_archive import file_hash,save


def main():
    p=argparse.ArgumentParser();p.add_argument('--cohort',type=Path,required=True);p.add_argument('--features',type=Path,required=True);p.add_argument('--content-audit',type=Path,required=True);p.add_argument('--auxiliary',type=Path,required=True);p.add_argument('--prior-study',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--resume',action='store_true');a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=a.resume);settings=protocol();began=time.time();runs=[];baselines={};lifetimes={}
    planned={**settings,'implementation_amendment':'Use exact availability nanoseconds for one-second buckets; preserve/import completed raw-event fits, retrain controls.',
             'source_hashes':{n:file_hash(Path(__file__).with_name(n)) for n in ['event_study_exact.py','event_data_exact.py','event_train_exact.py','event_study.py','event_protocol.py']},
             'data_hashes':{str(path):file_hash(path) for path in [a.cohort/'report.json',a.features/'report.json',a.content_audit,a.auxiliary/'report.json']}}
    own=a.output/'study-protocol.json'
    if own.exists() and json.loads(own.read_text())!=planned:raise ValueError('Corrected study resume contract differs')
    save(own,planned)
    imports=[]
    for source in sorted(a.prior_study.iterdir()):
        if not source.is_dir() or not (source/'report.json').exists():continue
        settings_path=source/'run-protocol.json'
        if not settings_path.exists():continue
        old=json.loads(settings_path.read_text())
        if old.get('active_candidate','').startswith('one_second'):continue
        module='event_baselines' if source.name.endswith('-baselines') else 'event_train'
        verify_completed(source,module)
        destination=a.output/source.name
        if not destination.exists():shutil.copytree(source,destination)
        if file_hash(source/'report.json')!=file_hash(destination/'report.json'):raise ValueError('Changed imported report')
        imports.append({'run':source.name,'prior_report_sha256':file_hash(source/'report.json'),'retrained':False})
    save(a.output/'imported-completed-runs.json',imports)
    def invoke(module,name,extra):
        out=a.output/name
        if not out.exists():
            command=[sys.executable,'-m','research.diwali.'+module,'--cohort',str(a.cohort),'--features',str(a.features),'--content-audit',str(a.content_audit),'--output',str(out),*extra]
            log=a.output/(name+'.log')
            with log.open('w') as stream:
                child=subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT)
                save(a.output/'status.json',{'state':'running','active_run':name,'child_pid':child.pid,'log':str(log),'completed_neural_runs':len(runs),'elapsed_seconds':time.time()-began})
                print('started',name,child.pid,flush=True);code=child.wait()
            if code:raise ValueError(f'Run failed; retained log: {name}')
        result=verify_completed(out,module)
        if module=='event_train_exact' and file_hash(out/'weights.pt')!=result['selection']['weights_sha256']:raise ValueError('Changed corrected control weights')
        print('complete',name,flush=True);return result
    try:
        for fold in settings['development_folds']:
            for candidate in settings['neural_candidates']:
                for seed in settings['seeds']:
                    module='event_train_exact' if candidate.startswith('one_second') else 'event_train'
                    runs.append(invoke(module,f'{fold}-{candidate}-seed{seed}',['--fold',fold,'--candidate',candidate,'--seed',str(seed)]))
            baselines[fold]=invoke('event_baselines',f'{fold}-baselines',['--fold',fold])
            lifetimes[fold]=invoke('event_lifetime',f'{fold}-lifetime',['--fold',fold,'--auxiliary',str(a.auxiliary)])
            progress={'state':'development_in_progress','completed_folds':list(baselines),'neural_runs':runs,'baselines':baselines,'lifetime':lifetimes,
                      'production_model_selected':False,'reserved_final_evaluated':False,'implementation_amendment':planned['implementation_amendment']}
            save(a.output/'progress.json',progress);save(Path('results/diwali1.4/development-progress.json'),progress)
        decision=choose_family(runs,settings)
        report={'state':'development_complete','decision':decision,'neural_runs':runs,'baselines':baselines,'lifetime':lifetimes,
                'production_model_selected':False,'reserved_final_evaluated':False,'elapsed_seconds':time.time()-began,
                'implementation_amendment':planned['implementation_amendment'],
                'next_required':'Final fit/selection/calibration, deliberate final release, then new prospective confirmation.'}
        save(a.output/'report.json',report);save(Path('results/diwali1.4/development-report.json'),report);save(a.output/'status.json',{'state':'development_complete','decision':decision})
    except Exception as error:
        save(a.output/'status.json',{'state':'failed','error':str(error),'completed_neural_runs':len(runs),'elapsed_seconds':time.time()-began});raise


if __name__=='__main__':main()
