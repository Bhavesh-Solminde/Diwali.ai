"""Continue to final fitting/preflight after the verified live development job.

Stops before release or reserved-test preparation/scoring. It never restarts a
failed/incomplete model run or overwrites collaborator artifacts.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from .event_final_train import selected_family
from .event_protocol import protocol
from ..market_data.validate_archive import file_hash,save


def main():
    p=argparse.ArgumentParser();p.add_argument('--study',type=Path,required=True);p.add_argument('--study-pid',type=int,required=True);p.add_argument('--model-output',type=Path,required=True);p.add_argument('--baselines',type=Path,required=True);p.add_argument('--state',type=Path,required=True);a=p.parse_args()
    began=time.time();a.state.mkdir(parents=True,exist_ok=False);report=a.study/'report.json'
    save(a.state/'protocol.json',{'source_sha256':file_hash(Path(__file__)),'study':str(a.study),'study_pid':a.study_pid,
                                 'stop_after':'Final fit/selection/calibration and nonfinal inference preflight. No final release/scoring.'})
    def run(module,args,log_name):
        command=[sys.executable,'-m','research.diwali.'+module,*args]
        with (a.state/log_name).open('w') as log:
            child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
            save(a.state/'status.json',{'state':'running','module':module,'pid':child.pid,'elapsed_seconds':time.time()-began})
            code=child.wait()
        if code:raise ValueError(f'Continuation stage failed; inspect retained log: {module}')
    try:
        save(a.state/'status.json',{'state':'waiting_on_verified_development_process','pid':a.study_pid})
        while not report.exists():
            observation=subprocess.run(['ps','-p',str(a.study_pid),'-o','command='],capture_output=True,text=True)
            if observation.returncode or 'research.diwali.event_study_exact' not in observation.stdout or str(a.study) not in observation.stdout:
                raise ValueError('Development process is terminal or changed without a complete report; inspect it, never restart automatically')
            time.sleep(5)
        development=json.loads(report.read_text());chosen=selected_family(development,protocol())
        save(a.state/'development-decision.json',{'selected_family':chosen,'development_report_sha256':file_hash(report)})
        common=['--august-cohort','data/btc-perp/event-month-cohort-august-v1','--august-features','data/btc-perp/event-inputs-august-fast-v1',
                '--august-audit','results/event-joined-cohort/august-month-audit.json','--september-cohort','data/btc-perp/event-month-cohort-september-selection-v1',
                '--september-features','data/btc-perp/event-inputs-september-selection-fast-v1','--september-audit','results/event-joined-cohort/september-selection-audit.json']
        if a.model_output.exists():raise ValueError('Final-build destination already exists; inspect rather than overwrite or repeat')
        run('event_final_train',[*common,'--development-report',str(report),'--output',str(a.model_output)],'final-model-fit.log')
        run('event_final_preflight',['--model',str(a.model_output),'--baselines',str(a.baselines),
            '--cohort','data/btc-perp/event-month-cohort-september-selection-v1','--features','data/btc-perp/event-inputs-september-selection-fast-v1',
            '--content-audit','results/event-joined-cohort/september-selection-audit.json','--output',str(a.model_output/'inference-preflight.json')],'inference-preflight.log')
        save(a.state/'status.json',{'state':'final_build_and_nonfinal_preflight_complete','selected_family':chosen,
                                  'model_report_sha256':file_hash(a.model_output/'report.json'),
                                  'preflight_sha256':file_hash(a.model_output/'inference-preflight.json'),
                                  'reserved_final_released':False,'reserved_final_evaluated':False,'elapsed_seconds':time.time()-began})
    except Exception as error:
        save(a.state/'status.json',{'state':'failed','error':str(error),'elapsed_seconds':time.time()-began});raise


if __name__=='__main__':main()
