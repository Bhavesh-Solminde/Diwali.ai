"""One-use reserved final comparison, after model/baseline artifacts are frozen."""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
import joblib
from threadpoolctl import threadpool_limits

from .event_final_gate import claim,finish,resolve,check_release
from .event_data_exact import ExactEventData
from .event_data import normalize
from .event_evaluation import eligible_origins,interval
from .event_model import EventModel
from .event_baselines import summary,full_class_probabilities
from .event_train import infer,probabilities,metrics
from ..market_data.validate_archive import file_hash,save


def baseline_predictions(data,ids,release,record):
    bp=resolve(release,record['baseline_report']);root=bp.parent;br=json.loads(bp.read_text());transforms=json.loads((root/'fit-transforms.json').read_text())
    xs=[];vols=[]
    for j in ids:
        x,v=summary(data.raw(j));xs.append(x);vols.append(v)
    x=normalize(np.stack(xs),transforms['summary']);groups=np.searchsorted(transforms['volatility_thresholds'],np.array(vols))
    with np.load(root/'histograms.npz') as hist:
        logits={'fit_histogram':np.broadcast_to(np.log(hist['fit_histogram']),(len(ids),15,26)).copy(),
                'fit_volatility_histogram':np.log(hist['volatility_histograms'][groups])}
    state=torch.load(root/'flow_logistic/weights.pt',map_location='cpu',weights_only=True)
    with torch.inference_mode():logits['flow_logistic']=torch.nn.functional.linear(torch.from_numpy(x),state['weight'],state['bias']).reshape(-1,15,26).numpy()
    tree=[]
    with threadpool_limits(limits=4):
        for h in range(1,16):
            model=joblib.load(root/f'flow_boosted_trees/horizon-{h:02d}.joblib');tree.append(full_class_probabilities(model,x))
    logits['flow_boosted_trees']=np.log(np.stack(tree,axis=1))
    return {name:probabilities(z,br['models'][name]['temperatures']) for name,z in logits.items()}


def main():
    p=argparse.ArgumentParser();p.add_argument('--release',type=Path,required=True);p.add_argument('--cohort',type=Path,required=True);p.add_argument('--features',type=Path,required=True);p.add_argument('--content-audit',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise ValueError('Final score output already exists; never overwrite')
    record=check_release(a.release);ticket=claim(a.release);began=time.time()
    try:
        # The claim is committed before constructing the loader that opens labels.
        data=ExactEventData(a.cohort,a.features,a.content_audit);start,stop=interval('final','score')
        if ((data.cutoffs<start)|(data.cutoffs>=stop)).any():raise ValueError('Final dataset contains origins outside the reserved interval')
        keep,counts=eligible_origins(data.cutoffs,data.starts,'final','score',final_release=a.release);ids=np.flatnonzero(keep)
        if not len(ids):raise ValueError('No passing final origins; interval remains consumed')
        model_protocol=json.loads(resolve(a.release,record['artifacts']['run_protocol']).read_text());candidate=model_protocol['candidate']
        model=EventModel('attention' if candidate=='event_attention' else 'temporal_conv',width=model_protocol['neural_width'],block=model_protocol['event_block_groups'])
        model.load_state_dict(torch.load(resolve(a.release,record['artifacts']['selected_model']),map_location='cpu',weights_only=True))
        transforms=json.loads(resolve(a.release,record['artifacts']['fit_transforms']).read_text());cal=json.loads(resolve(a.release,record['artifacts']['calibration']).read_text())
        torch.set_num_threads(4);device='mps' if torch.backends.mps.is_available() else 'cpu';model.to(device)
        logits=infer(model,data,ids,transforms,device,model_protocol['batch_size']);predictions={'diwali1.4':probabilities(logits,cal['temperatures'])}
        predictions.update(baseline_predictions(data,ids,a.release,record));a.output.mkdir(parents=True,exist_ok=False)
        days=np.array([str(np.datetime64(int(t),'ns'))[:10] for t in data.cutoffs[ids]]);results={}
        for name,prob in predictions.items():
            results[name]={'overall':metrics(data.y[ids],prob),
                           'daily':{day:metrics(data.y[ids][days==day],prob[days==day]) for day in sorted(set(days))}}
            np.savez_compressed(a.output/(name+'-predictions.npz'),row_ids=data.ids[ids],probabilities=prob)
        primary=results['diwali1.4']['overall']['mean15_bin_log_loss'];paired={}
        for name,r in results.items():
            if name=='diwali1.4':continue
            paired[name]={'overall_model_minus_baseline_log_loss':primary-r['overall']['mean15_bin_log_loss'],
                          'daily_model_minus_baseline_log_loss':{day:results['diwali1.4']['daily'][day]['mean15_bin_log_loss']-r['daily'][day]['mean15_bin_log_loss'] for day in sorted(set(days))}}
        report={'state':'reserved_final_evaluation_complete','model':'diwali1.4','selected_family':candidate,'period':['2026-09-15','2026-09-29'],
                'origin_counts':counts,'models':results,'paired_differences':paired,'data_hashes':data.hashes,'release_sha256':file_hash(a.release),
                'elapsed_seconds':time.time()-began,'limitations':['This reserved interval is now consumed; later changes cannot reuse it as fresh confirmation.',
                  'Overlapping target windows are correlated; daily results are descriptive, not independent confidence guarantees.',
                  'Only quality-approved book windows and masked-history contexts are represented.',
                  'Historical provider timing is not proven exchange-original receipt timing.',
                  'Probability scores do not establish profitability or perfect conditional probability prediction.']}
        save(a.output/'report.json',report);finish(ticket,a.release,'complete',a.output/'report.json')
    except Exception as error:
        finish(ticket,a.release,'failed_after_final_claim',error=error);raise


if __name__=='__main__':main()
