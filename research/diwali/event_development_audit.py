"""Recompute held development scores and audit fold/transform/weight identities."""
import argparse
import json
from pathlib import Path

import numpy as np

from .event_data_exact import ExactEventData
from .event_protocol import protocol
from .event_train import metrics
from .event_study import verify_completed,choose_family
from ..market_data.validate_archive import file_hash,save


def main():
    p=argparse.ArgumentParser();p.add_argument('--study',type=Path,required=True);p.add_argument('--cohort',type=Path,required=True);p.add_argument('--features',type=Path,required=True);p.add_argument('--content-audit',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    data=ExactEventData(a.cohort,a.features,a.content_audit);s=protocol();runs=[];evidence=[];max_difference=0.
    for fold in s['development_folds']:
        fit,_=data.partition(fold,'fit');score,_=data.partition(fold,'score')
        for candidate in s['neural_candidates']:
            for seed in s['seeds']:
                root=a.study/f'{fold}-{candidate}-seed{seed}';r=verify_completed(root,'event_train_exact' if candidate.startswith('one_second') else 'event_train')
                if file_hash(root/'weights.pt')!=r['selection']['weights_sha256']:raise ValueError('Selected weight hash mismatch')
                history=json.loads((root/'history.json').read_text());chosen=min(history,key=lambda x:x['selection_loss'])
                if chosen['epoch']!=r['selection']['best_epoch'] or abs(chosen['selection_loss']-r['selection']['selection_loss'])>1e-10:raise ValueError('Checkpoint did not follow frozen selection rule')
                tr=json.loads((root/'fit-transforms.json').read_text())
                if tr['fit_origins']!=len(fit) or tr['fit_cutoff_min_ns']!=int(data.cutoffs[fit].min()) or tr['fit_cutoff_max_ns']!=int(data.cutoffs[fit].max()):raise ValueError('Transform fitting dates/origins differ')
                events=60*len(fit) if candidate.startswith('one_second') else sum(data.entries[int(data.ids[j])]['event_rows'] for j in fit)
                if tr['moments']['event']['count']!=events:raise ValueError('Transform event count differs from fit-only cohort')
                cal=json.loads((root/'calibration.json').read_text());cal_ids,_=data.partition(fold,'calibrate')
                if cal['weights_sha256']!=r['selection']['weights_sha256'] or len(cal['temperatures'])!=15:raise ValueError('Calibration/weight mismatch')
                if len(cal_ids)<100 and cal['temperatures']!=[1.]*15:raise ValueError('Sparse calibration fold was fitted')
                with np.load(root/'score-predictions.npz') as z:
                    np.testing.assert_array_equal(z['row_ids'],data.ids[score]);pred=z['probabilities']
                    if pred.shape!=(len(score),15,26) or not np.isfinite(pred).all() or (pred<0).any():raise ValueError('Invalid saved development probabilities')
                    np.testing.assert_allclose(pred.sum(-1),1,rtol=0,atol=1e-10)
                    direct=metrics(data.y[score],pred)
                for name in ['mean15_bin_log_loss','ranked_probability_score','final_direction_log_loss','final_direction_brier','final_direction_accuracy']:
                    delta=abs(direct[name]-r['partitions']['score'][name]);max_difference=max(max_difference,delta)
                    if delta>1e-12:raise ValueError('Reported metric differs from saved forecasts and original targets')
                runs.append(r);evidence.append({'fold':fold,'candidate':candidate,'seed':seed,'score_origins':len(score),'weights_sha256':r['selection']['weights_sha256'],
                                               'fit_only_transform_counts_verified':True,'checkpoint_rule_verified':True,'saved_forecast_metrics_recomputed':True})
    result={'state':'complete','neural_runs_verified':len(runs),'maximum_metric_recomputation_difference':max_difference,
            'neural_family_rule_recomputed':choose_family(runs,s),'evidence':evidence,
            'baseline_verification_scope':'This audit verifies neural runs; baseline comparison remains in the full study report.',
            'data_hashes':data.hashes,'audit_source_sha256':file_hash(Path(__file__)),
            'scope':'Completed August development artifact audit. It is not final independent evaluation or new model fitting.'}
    save(a.output,result);print(json.dumps({k:result[k] for k in ['neural_runs_verified','maximum_metric_recomputation_difference','neural_family_rule_recomputed']}))


if __name__=='__main__':main()
