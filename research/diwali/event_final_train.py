"""Build one development-selected family; never open reserved final labels."""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F

from .event_data_exact import ExactEventData
from .event_final_data import FinalBuildData
from .event_model import EventModel
from .event_protocol import protocol
from .event_study import choose_family
from .event_train import infer,calibrate,metrics,nll,probabilities
from ..market_data.validate_archive import file_hash,save


def selected_family(report,settings):
    if report.get('state')!='development_complete':raise ValueError('Bounded development comparison is incomplete')
    decision=choose_family(report['neural_runs'],settings)
    if decision!=report['decision']:raise ValueError('Development family selection differs')
    return decision['selected_family']


def main():
    p=argparse.ArgumentParser();p.add_argument('--august-cohort',type=Path,required=True);p.add_argument('--august-features',type=Path,required=True);p.add_argument('--august-audit',type=Path,required=True);p.add_argument('--september-cohort',type=Path,required=True);p.add_argument('--september-features',type=Path,required=True);p.add_argument('--september-audit',type=Path,required=True);p.add_argument('--development-report',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    settings=protocol();candidate=selected_family(json.loads(a.development_report.read_text()),settings)
    august=ExactEventData(a.august_cohort,a.august_features,a.august_audit);september=ExactEventData(a.september_cohort,a.september_features,a.september_audit);data=FinalBuildData(august,september)
    parts={};counts={}
    for name in ['fit','select','calibrate']:
        parts[name],counts[name]=data.partition('final',name)
        if len(parts[name])<settings['minimum_partition_origins'][name]:raise ValueError('Insufficient final-build partition; keep frozen dates')
    a.output.mkdir(parents=True,exist_ok=False);began=time.time()
    settings.update({'stage':'Final fit/selection/calibration only; no reserved final labels loaded','candidate':candidate,
                     'seed':settings['final_build_seed'],'development_report_sha256':file_hash(a.development_report),
                     'source_hashes':{n:file_hash(Path(__file__).with_name(n)) for n in ['event_final_train.py','event_final_data.py','event_data_exact.py','event_data.py','event_model.py','event_train.py','event_protocol.py','event_evaluation.py','event_study.py']}})
    save(a.output/'run-protocol.json',settings);save(a.output/'cohorts.json',{'partitions':counts,'data_hashes':data.hashes})
    representation='one_second' if candidate.startswith('one_second') else 'events'
    transforms=data.fit_transforms(parts['fit'],representation);save(a.output/'fit-transforms.json',transforms)
    torch.manual_seed(settings['seed']);torch.set_num_threads(4);device='mps' if torch.backends.mps.is_available() else 'cpu'
    model=EventModel('attention' if candidate=='event_attention' else 'temporal_conv',width=settings['neural_width'],block=settings['event_block_groups']).to(device)
    opt=torch.optim.AdamW(model.parameters(),lr=settings['learning_rate'],weight_decay=settings['weight_decay']);rng=np.random.default_rng(settings['seed']);best=float('inf');wait=0;history=[]
    for epoch in range(1,settings['max_epochs']+1):
        model.train();perm=rng.permutation(parts['fit']);loss_total=0.;seen=0
        for start in range(0,len(perm),settings['batch_size']):
            ids=perm[start:start+settings['batch_size']];args,y=data.batch(ids,transforms,device);opt.zero_grad(set_to_none=True)
            loss=F.cross_entropy(model(*args).reshape(-1,26),y.reshape(-1))
            if not torch.isfinite(loss):raise ValueError('Nonfinite final-build fit loss')
            loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),settings['gradient_clip'],error_if_nonfinite=True);opt.step();loss_total+=float(loss.detach().cpu())*len(ids);seen+=len(ids)
        z=infer(model,data,parts['select'],transforms,device,settings['batch_size']);score=nll(data.y[parts['select']],probabilities(z))
        history.append({'epoch':epoch,'fit_loss':loss_total/seen,'selection_loss':score})
        if score<best-1e-10:
            best=score;chosen=epoch;wait=0;state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()};torch.save(state,a.output/'weights.pt')
        else:wait+=1
        save(a.output/'history.json',history);save(a.output/'status.json',{'state':'final_build_fitting','epoch':epoch,'best_epoch':chosen,'elapsed_seconds':time.time()-began})
        print('final_build',candidate,epoch,loss_total/seen,score,flush=True)
        if wait>=settings['patience']:break
    model.load_state_dict(state);selection={'candidate':candidate,'seed':settings['seed'],'best_epoch':chosen,'selection_loss':best,'weights_sha256':file_hash(a.output/'weights.pt'),'development_report_sha256':settings['development_report_sha256']};save(a.output/'selection.json',selection)
    z=infer(model,data,parts['calibrate'],transforms,device,settings['batch_size']);temperatures=calibrate(data.y[parts['calibrate']],z)
    calibration={'temperatures':temperatures,'origins':len(parts['calibrate']),'temperature_fitted':len(parts['calibrate'])>=settings['minimum_calibration_origins'],'weights_sha256':selection['weights_sha256']};save(a.output/'calibration.json',calibration)
    result={'state':'fitted_selected_calibrated_without_final_evaluation','model':'diwali1.4','candidate':candidate,'selection':selection,'calibration':calibration,'cohorts':counts,
            'calibration_partition_diagnostic':metrics(data.y[parts['calibrate']],probabilities(z,temperatures)),
            'reserved_final_labels_loaded':False,'reserved_final_evaluated':False,'elapsed_seconds':time.time()-began,
            'next_required':'Freeze baseline artifacts and final-evaluation source; deliberate one-use release, final test and new prospective confirmation.'}
    save(a.output/'report.json',result);save(a.output/'status.json',{'state':result['state'],'elapsed_seconds':result['elapsed_seconds']})


if __name__=='__main__':main()
