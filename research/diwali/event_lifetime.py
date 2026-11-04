"""Matched chronological simple-flow signal-lifetime diagnostic, auxiliary only."""
import argparse
import json
from pathlib import Path

import numpy as np
import joblib
from sklearn.linear_model import LogisticRegression
from threadpoolctl import threadpool_limits

from .event_data import EventData,Moments,normalize
from .event_baselines import summary
from .event_protocol import protocol
from ..market_data.validate_archive import file_hash,save


def sigmoid(x):
    x=np.clip(np.asarray(x,np.float64),-700,700)
    return 1/(1+np.exp(-x))


def binary_metrics(y,p):
    return {'origins':len(y),'log_loss':float(-(y*np.log(np.maximum(p,1e-15))+(1-y)*np.log(np.maximum(1-p,1e-15))).mean()),
            'brier':float(((p-y)**2).mean()),'accuracy':float(((p>=.5)==y).mean()),'up_fraction':float(y.mean())}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--cohort',type=Path,required=True);parser.add_argument('--features',type=Path,required=True);parser.add_argument('--content-audit',type=Path,required=True);parser.add_argument('--auxiliary',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--fold',choices=['A','B','C'],required=True);a=parser.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);settings=protocol();settings['active_fold']=a.fold
    settings['source_hashes']={n:file_hash(Path(__file__).with_name(n)) for n in ['event_lifetime.py','event_baselines.py','event_data.py','event_protocol.py','event_evaluation.py']};save(a.output/'run-protocol.json',settings)
    data=EventData(a.cohort,a.features,a.content_audit);ar=json.loads((a.auxiliary/'report.json').read_text())
    if ar['cohort_sha256']!=data.hashes['cohort'] or file_hash(a.auxiliary/'labels.json')!=ar['label_sha256']:raise ValueError('Changed or mismatched auxiliary labels')
    aux={r['input_row']:r for r in json.loads((a.auxiliary/'labels.json').read_text())}
    keep=np.array([all(aux[int(i)]['horizons'].get(str(h),{}).get('valid',False) for h in [5,15,30,60]) for i in data.ids])
    y=np.array([[aux[int(i)]['horizons'][str(h)]['return_bp']>0 for h in [5,15,30,60]] if keep[j] else [False]*4 for j,i in enumerate(data.ids)],np.int64)
    y=np.concatenate([y,(data.returns[:,[0,4,14]]>0).astype(int)],axis=1)
    parts={};counts={}
    for name in ['fit','select','calibrate','score']:
        indices,c=data.partition(a.fold,name);parts[name]=indices[keep[indices]];counts[name]={'primary_eligible':len(indices),'common_all_horizons':len(parts[name])}
        if len(parts[name])<settings['minimum_partition_origins'][name]:raise ValueError('Insufficient matched horizon cohort')
    union=np.unique(np.concatenate(list(parts.values())));lookup={int(j):k for k,j in enumerate(union)}
    x=np.stack([summary(data.raw(j))[0] for j in union]);fit=np.array([lookup[int(j)] for j in parts['fit']]);cal=np.array([lookup[int(j)] for j in parts['calibrate']]);score=np.array([lookup[int(j)] for j in parts['score']])
    moments=Moments(x.shape[1]);moments.add(x[fit]);transform=moments.record();x=normalize(x,transform);save(a.output/'fit-transforms.json',transform)
    yy=y[union];rows=[];temps=[]
    with threadpool_limits(limits=4):
        for k,h in enumerate(settings['lifetime_baseline']['horizons_seconds']):
            if len(np.unique(yy[fit,k]))!=2:raise ValueError('Single-class fit is insufficient')
            model=LogisticRegression(C=1.,solver='lbfgs',max_iter=1000);model.fit(x[fit],yy[fit,k]);joblib.dump(model,a.output/f'horizon-{h:03d}.joblib')
            logits=model.decision_function(x);grid=np.geomspace(.5,4,49)
            losses=[binary_metrics(yy[cal,k],sigmoid(logits[cal]/t))['log_loss'] for t in grid] if len(cal)>=settings['minimum_calibration_origins'] else None
            temperature=float(grid[np.argmin(losses)]) if losses is not None else 1.;temps.append(temperature)
            pred=sigmoid(logits[score]/temperature);rate=(yy[fit,k].sum()+1)/(len(fit)+2);base=np.full(len(score),rate)
            model_score=binary_metrics(yy[score,k],pred);baseline=binary_metrics(yy[score,k],base)
            days=np.array([str(np.datetime64(int(t),'ns'))[:10] for t in data.cutoffs[parts['score']]])
            rows.append({'horizon_seconds':h,'endpoint_definition':'availability-price' if h<105 else 'full-candle execution close',
                         'model':model_score,'fit_frequency':baseline,'log_loss_improvement_over_fit_frequency':baseline['log_loss']-model_score['log_loss'],
                         'daily':{day:{'model':binary_metrics(yy[score,k][days==day],pred[days==day]),'fit_frequency':binary_metrics(yy[score,k][days==day],base[days==day])} for day in sorted(set(days))}})
    report={'state':'complete','fold':a.fold,'cohorts':counts,'horizons':rows,'temperatures':temps,'source_hashes':data.hashes,
            'auxiliary_report_sha256':file_hash(a.auxiliary/'report.json'),'primary_task_unchanged':True,
            'scope':'Fixed simple-flow diagnostic on common origins; does not prove all models have the same signal lifetime.',
            'limitations':['Short availability-price and full-candle execution-close labels differ; microstructure noise remains.',
                           'Overlapping origins and same-month dates are correlated development evidence.',
                           'No reserved final data, entry prediction or profitability test.']}
    save(a.output/'report.json',report);print(json.dumps({'fold':a.fold,'horizon_improvements':{r['horizon_seconds']:r['log_loss_improvement_over_fit_frequency'] for r in rows}}))


if __name__=='__main__':main()
