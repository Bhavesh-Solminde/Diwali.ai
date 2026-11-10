"""Check completed 1.5 comparison artifacts without retraining or final-test access."""
import argparse
import json
from pathlib import Path

import numpy as np
import joblib
import torch

from .comparison15 import ComparisonData, CandleAttentionModel, source_hashes
from .comparison15_study import aggregate, public_metrics
from .comparison15_train import score_direction
from .event_data import normalize
from .event_model import EventModel
from .event_lifetime import sigmoid
from .event_evaluation import eligible_origins
from .event_train import metrics, probabilities
from ..market_data.validate_archive import file_hash, save


def main():
    p = argparse.ArgumentParser(); p.add_argument('--study', type=Path, required=True)
    p.add_argument('--cache', type=Path, required=True); p.add_argument('--output', type=Path, required=True); a = p.parse_args()
    report = json.loads((a.study/'report.json').read_text())
    if report['state'] != 'development_complete' or report['source_hashes'] != source_hashes():
        raise ValueError('Incomplete study or changed frozen source')
    if aggregate(report['runs']) != report['decision']:
        raise ValueError('Selection rule does not reproduce')
    data = {f: ComparisonData(a.cache, f) for f in ['A', 'B', 'C']}
    torch.set_num_threads(4)
    results = []; maximum = 0.; maximum_inference_difference = 0.
    for run in report['runs']:
        f = run['fold']; name = run['configuration']; seed = run['seed']; root = a.study/f'{f}-{name}-seed{seed}'
        d = data[f]; rp = json.loads((root/'run-protocol.json').read_text())
        if rp['source_hashes'] != source_hashes() or rp['cache_report_sha256'] != file_hash(a.cache/'report.json'):
            raise ValueError('Run/cache identity differs')
        cal = json.loads((root/'calibration.json').read_text()); t = np.array(cal['temperatures'])
        if t.shape != (15,) or not np.isfinite(t).all() or ((t < .5) | (t > 4)).any():
            raise ValueError('Unexpected calibration settings')
        if f == 'C' and not np.array_equal(t, np.ones(15)):
            raise ValueError('Sparse calibration was fitted')
        weights = {}
        if name != 'D_binary_logistic':
            if file_hash(root/'weights.pt') != run['selection']['weights_sha256']:
                raise ValueError('Selected weights changed')
            history = json.loads((root/'history.json').read_text()); chosen = min(history, key=lambda h: h['selection_range_loss'])
            if chosen['epoch'] != run['selection']['best_epoch'] or chosen['selection_range_loss'] != run['selection']['selection_range_loss']:
                raise ValueError('Checkpoint rule differs from frozen selection')
            weights['weights.pt'] = file_hash(root/'weights.pt')
        else:
            weights = {p.name: file_hash(p) for p in sorted(root.glob('horizon-*.joblib'))}
            if len(weights) != 15:
                raise ValueError('Missing binary heads')
        model = None
        if name != 'D_binary_logistic':
            model = CandleAttentionModel() if rp['settings']['configurations'][name]['candle_attention'] else EventModel()
            model.load_state_dict(torch.load(root/'weights.pt', weights_only=True, map_location='cpu')); model.eval()
        for part in ['select', 'calibrate', 'score']:
            keep, _ = eligible_origins(d.cutoffs, d.starts, f, part); ids = np.flatnonzero(keep)
            path = root/(part+'-predictions.npz')
            with np.load(path) as z:
                np.testing.assert_array_equal(z['row_ids'], d.ids[ids])
                binary = d.y[ids] >= 13
                if name == 'D_binary_logistic':
                    raw_up = z['up_raw']; up = z['up_calibrated']
                    if part == 'score':
                        x = normalize(d.arrays['summaries'][ids], d.transform['summary'])
                        logits = np.stack([joblib.load(root/f'horizon-{h+1:02d}.joblib').decision_function(x) for h in range(15)], 1)
                        np.testing.assert_allclose(sigmoid(logits), raw_up, atol=1e-12, rtol=0)
                        np.testing.assert_allclose(sigmoid(logits/t[None]), up, atol=1e-12, rtol=0)
                else:
                    raw = z['probabilities_raw']; prob = z['probabilities']
                    if prob.shape != (len(ids), 15, 26) or not np.isfinite(prob).all() or (prob <= 0).any():
                        raise ValueError('Invalid saved probability fan')
                    np.testing.assert_allclose(prob.sum(-1), 1, atol=1e-10, rtol=0)
                    np.testing.assert_allclose(probabilities(np.log(raw), t), prob, atol=1e-12, rtol=0)
                    direct = metrics(d.y[ids], prob)
                    for metric in ['mean15_bin_log_loss', 'ranked_probability_score', 'final_direction_log_loss', 'final_direction_brier', 'final_direction_accuracy']:
                        difference = abs(direct[metric]-run['partitions'][part]['calibrated_range'][metric])
                        maximum = max(maximum, difference)
                        if difference > 1e-12:
                            raise ValueError('Range report differs from retained forecast')
                    raw_up = raw[:, :, 13:].sum(-1); up = prob[:, :, 13:].sum(-1)
                    if part == 'score':
                        for j in np.linspace(0, len(ids)-1, 3, dtype=int):
                            args, _ = d.batch(ids[j:j+1], d.transform, 'cpu')
                            with torch.inference_mode():
                                actual = probabilities(model(*args).numpy())[0]
                            difference = float(np.max(np.abs(actual-raw[j])))
                            maximum_inference_difference = max(maximum_inference_difference, difference)
                            if difference > 2e-6:
                                raise ValueError('Saved neural raw forecast differs from selected checkpoint inference')
                for mode, value in [('raw_direction', raw_up), ('calibrated_direction', up)]:
                    if value.shape != binary.shape or not np.isfinite(value).all() or ((value < 0) | (value > 1)).any():
                        raise ValueError('Invalid directional probability')
                    direct = score_direction(binary, value)
                    for h in range(15):
                        for metric in ['log_loss', 'brier', 'accuracy', 'roc_auc']:
                            left = direct['per_horizon'][h][metric]; right = run['partitions'][part][mode]['per_horizon'][h][metric]
                            if left is None or right is None:
                                if left != right:
                                    raise ValueError('Undefined ranking metric differs')
                            else:
                                maximum = max(maximum, abs(left-right))
                                if abs(left-right) > 1e-12:
                                    raise ValueError('Directional report differs from retained forecasts')
        results.append({'fold': f, 'configuration': name, 'seed': seed, 'weights': weights,
                        'saved_forecast_metrics_verified': True, 'cohort_identity_verified': True})
    save(a.output, public_metrics({'state': 'complete', 'runs_verified': len(results), 'maximum_metric_difference': maximum,
                                   'maximum_cpu_saved_neural_probability_difference': maximum_inference_difference,
                                   'neural_checkpoint_samples_per_run': 3, 'direct_binary_all_transfer_inference_verified': True,
                                   'selection_recomputed': report['decision'], 'runs': results,
                                   'study_report_sha256': file_hash(a.study/'report.json'),
                                   'cache_report_sha256': file_hash(a.cache/'report.json'),
                                   'audit_source_sha256': file_hash(Path(__file__)), 'reserved_september_data_read': False,
                                   'scope': 'Saved development artifact verification, not independent future performance.'}))
    print('Verified', len(results), 'runs; maximum metric difference', maximum)


if __name__ == '__main__':
    main()
