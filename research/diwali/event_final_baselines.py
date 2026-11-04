"""Freeze final-build baseline artifacts without accessing reserved final data."""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import joblib
import torch
from sklearn.ensemble import HistGradientBoostingClassifier
from threadpoolctl import threadpool_limits

from .event_data_exact import ExactEventData
from .event_final_data import FinalBuildData
from .event_data import Moments,normalize
from .event_baselines import summary,histogram,logistic
from .event_train import probabilities,calibrate,metrics
from .event_protocol import protocol
from ..market_data.validate_archive import file_hash,save


def fit(data,out):
    settings=protocol();parts={};counts={}
    for name in ['fit','select','calibrate']:
        parts[name],counts[name]=data.partition('final',name)
        if len(parts[name])<settings['minimum_partition_origins'][name]:raise ValueError('Insufficient final baseline partition')
    fit_ids,select,cal=parts['fit'],parts['select'],parts['calibrate'];features=[];vols=[]
    for j in range(len(data.ids)):
        x,v=summary(data.raw(j));features.append(x);vols.append(v)
    raw=np.stack(features);vols=np.array(vols);moments=Moments(raw.shape[1]);moments.add(raw[fit_ids]);transform=moments.record();x=normalize(raw,transform)
    quantiles=np.quantile(vols[fit_ids],[.25,.5,.75]);groups=np.searchsorted(quantiles,vols);base=histogram(data.y[fit_ids]);conditional=[]
    for group in range(4):
        chosen=fit_ids[groups[fit_ids]==group];conditional.append(histogram(data.y[chosen]) if len(chosen) else base)
    conditional=np.stack(conditional)
    save(out/'fit-transforms.json',{'summary':transform,'volatility_thresholds':quantiles.tolist(),'fit_origins':len(fit_ids),'data_hashes':data.hashes})
    np.savez_compressed(out/'histograms.npz',fit_histogram=base,volatility_histograms=conditional)
    predictions={'fit_histogram':np.broadcast_to(np.log(base),(len(data.ids),15,26)).copy(),
                 'fit_volatility_histogram':np.log(conditional[groups])}
    linear=out/'flow_logistic';linear.mkdir();predictions['flow_logistic']=logistic(x,data.y,fit_ids,select,settings['logistic'],linear)
    tree=out/'flow_boosted_trees';tree.mkdir();tree_cal=[]
    from .event_baselines import full_class_probabilities
    with threadpool_limits(limits=4):
        for h in range(15):
            model=HistGradientBoostingClassifier(**settings['boosted_trees']);model.fit(x[fit_ids],data.y[fit_ids,h]);joblib.dump(model,tree/f'horizon-{h+1:02d}.joblib')
            tree_cal.append(full_class_probabilities(model,x[cal]));print('final_baseline_tree',h+1,flush=True)
    cal_logits={name:value[cal] for name,value in predictions.items()};cal_logits['flow_boosted_trees']=np.log(np.stack(tree_cal,axis=1));models={}
    for name,z in cal_logits.items():
        temperatures=calibrate(data.y[cal],z)
        models[name]={'temperatures':temperatures,'temperature_fitted':len(cal)>=settings['minimum_calibration_origins'],
                      'calibration_partition_diagnostic':metrics(data.y[cal],probabilities(z,temperatures))}
    save(out/'calibration.json',models)
    files=['fit-transforms.json','histograms.npz','calibration.json','flow_logistic/weights.pt','flow_logistic/selection.json']+[f'flow_boosted_trees/horizon-{h:02d}.joblib' for h in range(1,16)]
    return {'state':'baselines_fitted_without_final_evaluation','models':models,'cohorts':counts,'artifact_hashes':{n:file_hash(out/n) for n in files},
            'data_hashes':data.hashes,'reserved_final_labels_loaded':False,'reserved_final_evaluated':False}


def main():
    p=argparse.ArgumentParser();p.add_argument('--august-cohort',type=Path,required=True);p.add_argument('--august-features',type=Path,required=True);p.add_argument('--august-audit',type=Path,required=True);p.add_argument('--september-cohort',type=Path,required=True);p.add_argument('--september-features',type=Path,required=True);p.add_argument('--september-audit',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    data=FinalBuildData(ExactEventData(a.august_cohort,a.august_features,a.august_audit),ExactEventData(a.september_cohort,a.september_features,a.september_audit));a.output.mkdir(parents=True,exist_ok=False)
    settings=protocol();settings['stage']='Final baseline fit/selection/calibration only';settings['source_hashes']={n:file_hash(Path(__file__).with_name(n)) for n in ['event_final_baselines.py','event_baselines.py','event_final_data.py','event_data_exact.py','event_data.py','event_train.py','event_protocol.py','event_evaluation.py']};save(a.output/'run-protocol.json',settings)
    began=time.time();torch.set_num_threads(4);report=fit(data,a.output);report['elapsed_seconds']=time.time()-began;save(a.output/'report.json',report);save(a.output/'status.json',{'state':report['state'],'seconds':report['elapsed_seconds']})


if __name__=='__main__':main()
