"""Finite released final-data preparation and one-use scoring pipeline."""
import argparse
import subprocess
import sys
import time
from pathlib import Path

from .event_final_gate import check_release
from ..market_data.validate_archive import file_hash,save


def main():
    p=argparse.ArgumentParser();p.add_argument('--release',type=Path,required=True);p.add_argument('--root',type=Path,required=True);p.add_argument('--result',type=Path,required=True);a=p.parse_args()
    check_release(a.release)
    if a.result.exists():raise ValueError('Final result destination already exists')
    a.root.mkdir(parents=True,exist_ok=False);began=time.time()
    save(a.root/'pipeline-protocol.json',{'release_sha256':file_hash(a.release),'pipeline_sha256':file_hash(Path(__file__)),
                                        'fixed_period':['2026-09-15','2026-09-29'],'no_training_or_selection':True})
    shards=a.root/'shards';cohort=a.root/'cohort';features=a.root/'features';audit=a.root/'content-audit.json'
    stages=[('replay','research.market_data.event_shards_final',['--release',str(a.release),'--output',str(shards)]),
            ('contexts','research.market_data.event_month_cohort',['--source',str(shards),'--output',str(cohort),'--period','reserved-final','--final-release',str(a.release)]),
            ('content_audit','research.market_data.event_month_audit',['--source',str(shards),'--cohort',str(cohort),'--output',str(audit),'--final-release',str(a.release)]),
            ('features','research.market_data.event_prepare_fast',['--source',str(shards),'--candles',str(cohort/'candles'),'--windows',str(cohort/'windows'),'--output',str(features)]),
            ('one_use_score','research.diwali.event_final_score',['--release',str(a.release),'--cohort',str(cohort),'--features',str(features),'--content-audit',str(audit),'--output',str(a.result)])]
    completed=[]
    try:
        for name,module,args in stages:
            check_release(a.release)
            with (a.root/(name+'.log')).open('w') as log:
                child=subprocess.Popen([sys.executable,'-m',module,*args],stdout=log,stderr=subprocess.STDOUT)
                save(a.root/'status.json',{'state':'running','stage':name,'pid':child.pid,'completed_stages':completed,'elapsed_seconds':time.time()-began})
                print('started',name,child.pid,flush=True);code=child.wait()
            if code:raise ValueError(f'Final stage failed: {name}; retain artifacts and inspect, never auto-retry scoring')
            completed.append(name);print('complete',name,flush=True)
        save(a.root/'status.json',{'state':'complete','completed_stages':completed,'result_sha256':file_hash(a.result/'report.json'),'elapsed_seconds':time.time()-began})
    except Exception as error:
        save(a.root/'status.json',{'state':'failed','error':str(error),'completed_stages':completed,'elapsed_seconds':time.time()-began});raise


if __name__=='__main__':main()
