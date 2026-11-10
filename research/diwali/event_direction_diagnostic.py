"""Existing August forecasts: directional ranking before/after range calibration."""
import argparse
import json
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score
import torch

from .event_data import EDGES, labels
from .event_data_exact import ExactEventData
from .event_model import EventModel
from .event_study import verify_completed
from .event_train import probabilities, metrics
from ..market_data.validate_archive import file_hash, save


def uncalibrated_bins(calibrated, temperatures):
    p = np.asarray(calibrated, np.float64)
    t = np.asarray(temperatures, np.float64)
    if p.ndim != 3 or p.shape[1:] != (15, 26) or t.shape != (15,):
        raise ValueError('Expected 15 calibrated 26-bin heads and temperatures')
    if not np.isfinite(p).all() or (p <= 0).any() or not np.isfinite(t).all() or (t <= 0).any():
        raise ValueError('Positive finite probabilities and temperatures required')
    np.testing.assert_allclose(p.sum(-1), 1, rtol=0, atol=1e-10)
    # log(p_cal)*T recovers raw logits up to an irrelevant per-head constant.
    raw = probabilities(np.log(p)*t[None, :, None])
    np.testing.assert_allclose(probabilities(np.log(raw), t), p, rtol=0, atol=1e-12)
    return raw


def binary_metrics(y, p):
    y = np.asarray(y); p = np.asarray(p, np.float64)
    if y.ndim != 1 or p.shape != y.shape or not len(y) or not np.isin(y, [0, 1]).all():
        raise ValueError('Aligned nonempty binary targets required')
    if not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError('Invalid directional probability')
    return {'origins': len(y), 'up_count': int(y.sum()), 'observed_up_frequency': float(y.mean()),
            'mean_up_probability': float(p.mean()), 'minimum_up_probability': float(p.min()),
            'maximum_up_probability': float(p.max()), 'up_probability_std': float(p.std()),
            'log_loss': float(-np.log(np.maximum(np.where(y, p, 1-p), 1e-15)).mean()),
            'brier': float(((p-y)**2).mean()), 'accuracy': float(((p >= .5) == y).mean()),
            'roc_auc': float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else None,
            'forecasts_favouring_up': int((p >= .5).sum())}


def probability_groups(y, p, rank=False):
    y = np.asarray(y); p = np.asarray(p)
    edges = np.unique(np.quantile(p, [.25, .5, .75])) if rank else np.array([.4, .45, .475, .49, .5, .51, .525, .55, .6])
    # Equal scores always remain together; never split ties by the outcome.
    assignment = np.searchsorted(edges, p, side='right')
    groups = []
    for k in sorted(set(assignment)):
        take = assignment == k
        groups.append({'group': int(k), 'lower_inclusive': None if k == 0 else float(edges[k-1]),
                       'upper_exclusive': None if k == len(edges) else float(edges[k]),
                       **binary_metrics(y[take], p[take])})
    return groups


def directional_view(y, p):
    return [{**binary_metrics(y[:, h], p[:, h]), 'horizon': h+1,
             'fixed_probability_groups': probability_groups(y[:, h], p[:, h]),
             'rank_quartile_groups': probability_groups(y[:, h], p[:, h], rank=True)}
            for h in range(15)]


def mapping_audit(data):
    targets = json.loads((data.root/'candles/targets.json').read_text())
    close = np.asarray([r['closes'] for r in targets], np.float64)
    reference = np.asarray([data.metadata[int(i)]['reference'] for i in data.ids])[:, None]
    computed = (close/reference-1)*10000
    np.testing.assert_allclose(computed, data.returns, atol=1e-9, rtol=0)
    if not np.array_equal(close > reference, data.y >= 13):
        raise ValueError('Price direction and bin direction disagree')
    probes = np.array([np.nextafter(0., -np.inf), 0., np.nextafter(0., np.inf), -.5, .5, -2., 2.])
    bins = labels(np.repeat(probes[:, None], 15, axis=1))[:, 0]
    if not np.array_equal(bins >= 13, probes > 0):
        raise ValueError('Sign/equality boundary mismatch')
    if int(np.flatnonzero(EDGES == 0)[0]) != 12:
        raise ValueError('Zero is not the expected bin edge')
    return {'state': 'passed', 'origin_count': len(data.ids), 'target_close_coordinates': int(close.size),
            'price_direction_vs_bin_label_mismatches': int(((close > reference) != (data.y >= 13)).sum()),
            'maximum_recomputed_return_difference_bp': float(np.abs(computed-data.returns).max()),
            'exact_unchanged_targets': int((close == reference).sum()),
            'zero_return_bin': 12, 'up_bins': [13, 25], 'down_or_unchanged_bins': [0, 12],
            'bin_straddles_zero': False, 'probability_split_inside_bin_required': False,
            'boundary_probes_bp_and_bins': [{'return_bp': float(v), 'bin': int(b)} for v, b in zip(probes, bins)],
            'reference': 'Same stored frozen completed-second VWAP for return labels and price-band direction.',
            'convention': 'Up iff actual future close > frozen reference; exact equality is down-or-unchanged. No bin straddles zero.',
            'separate_two_bp_convention': 'Exact +2bp moves to bin16; this does not affect the sign boundary.'}


def main():
    p = argparse.ArgumentParser(); p.add_argument('--study', type=Path, required=True)
    p.add_argument('--cohort', type=Path, required=True); p.add_argument('--features', type=Path, required=True)
    p.add_argument('--content-audit', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        raise ValueError('Do not overwrite a completed diagnostic')
    data = ExactEventData(a.cohort, a.features, a.content_audit)
    if ((data.cutoffs < np.datetime64('2026-08-01', 'ns').astype(np.int64)) |
        (data.cutoffs >= np.datetime64('2026-09-01', 'ns').astype(np.int64))).any():
        raise ValueError('Only August development inputs allowed')
    original = json.loads((a.study/'report.json').read_text())
    if original['state'] != 'development_complete':
        raise ValueError('Completed study required')
    torch.set_num_threads(4)
    families = ['event_temporal_conv', 'event_attention', 'one_second_temporal_conv']
    runs = []; hashes = {}; maximum_sample_error = 0.
    mapping = mapping_audit(data)
    for fold in ['A', 'B', 'C']:
        parts = {n: data.partition(fold, n)[0] for n in ['select', 'calibrate', 'score']}
        definitions = [(f'{fold}-{family}-seed{seed}', family, seed) for family in families for seed in [17, 29]]
        definitions += [(f'{fold}-baselines/{name}', name, None) for name in original['baselines'][fold]['models']]
        for folder, family, seed in definitions:
            root = a.study/folder
            if seed is not None:
                report = verify_completed(root, 'event_train_exact' if family.startswith('one_second') else 'event_train')
                expected = next(r for r in original['neural_runs'] if r['fold'] == fold and r['candidate'] == family and r['seed'] == seed)
                if report != expected or file_hash(root/'weights.pt') != report['selection']['weights_sha256']:
                    raise ValueError('Study/checkpoint report identity changed')
            else:
                verify_completed(a.study/f'{fold}-baselines', 'event_baselines')
                report = json.loads((root/'report.json').read_text())
                if report != original['baselines'][fold]['models'][family]:
                    raise ValueError('Baseline study/report mismatch')
            cal = json.loads((root/'calibration.json').read_text()); t = cal['temperatures']
            if cal['origins'] != len(parts['calibrate']) or (len(parts['calibrate']) < 100 and t != [1.]*15):
                raise ValueError('Calibration period identity differs')
            if seed is not None and t != report['calibration_temperatures']:
                raise ValueError('Calibration temperatures changed')
            if seed is None and t != report['temperatures']:
                raise ValueError('Baseline temperatures changed')
            hashes[str(root/'calibration.json')] = file_hash(root/'calibration.json')
            entry = {'fold': fold, 'family': family, 'seed': seed, 'temperatures': t,
                     'calibration_origin_count': len(parts['calibrate']), 'partitions': {}}
            raw_score = None
            for name, indices in parts.items():
                path = root/(name+'-predictions.npz'); hashes[str(path)] = file_hash(path)
                with np.load(path) as z:
                    np.testing.assert_array_equal(z['row_ids'], data.ids[indices]); calibrated = z['probabilities']
                if calibrated.shape != (len(indices), 15, 26):
                    raise ValueError('Saved prediction shape differs')
                scored = metrics(data.y[indices], calibrated)
                for key in ['mean15_bin_log_loss', 'final_direction_log_loss', 'final_direction_brier', 'final_direction_accuracy']:
                    if abs(scored[key]-report['partitions'][name][key]) > 1e-12:
                        raise ValueError('Saved score does not match existing run report')
                raw = uncalibrated_bins(calibrated, t)
                days = np.asarray([str(np.datetime64(int(v), 'ns'))[:10] for v in data.cutoffs[indices]])
                y = data.y[indices] >= 13
                period = {'origins': len(indices), 'earliest_freeze_utc': str(np.datetime64(int(data.cutoffs[indices].min()), 'ns')),
                          'latest_freeze_utc': str(np.datetime64(int(data.cutoffs[indices].max()), 'ns')),
                          'role': 'Used to choose calibration; in-sample for this adjustment.' if name == 'calibrate' else
                                  'Used to choose checkpoint; not independent model evaluation.' if name == 'select' else
                                  'Already-inspected development transfer period; not a new holdout.',
                          'raw': directional_view(y, raw[:, :, 13:].sum(-1)),
                          'calibrated': directional_view(y, calibrated[:, :, 13:].sum(-1)),
                          'daily': {}}
                for day in sorted(set(days)):
                    keep = days == day
                    period['daily'][day] = {
                        mode: [{'horizon': h+1, **binary_metrics(y[keep, h], v[keep, h, 13:].sum(-1))} for h in range(15)]
                        for mode, v in [('raw', raw), ('calibrated', calibrated)]}
                entry['partitions'][name] = period
                if name == 'score':
                    raw_score = raw
            if seed is not None:
                protocol = json.loads((root/'run-protocol.json').read_text())
                model = EventModel('attention' if family == 'event_attention' else 'temporal_conv', width=protocol['neural_width'], block=protocol['event_block_groups'])
                model.load_state_dict(torch.load(root/'weights.pt', map_location='cpu', weights_only=True)); model.eval()
                transforms = json.loads((root/'fit-transforms.json').read_text())
                errors = []
                for j in np.linspace(0, len(parts['score'])-1, 3, dtype=int):
                    args, _ = data.batch(parts['score'][j:j+1], transforms, 'cpu')
                    with torch.inference_mode():
                        actual_raw = probabilities(model(*args).numpy())[0]
                    errors.append(float(np.max(np.abs(actual_raw-raw_score[j]))))
                maximum_sample_error = max(maximum_sample_error, max(errors))
                if max(errors) > 2e-6:
                    raise ValueError('Recovered raw probabilities differ from checkpoint inference')
                entry['raw_checkpoint_verification'] = {'sample_origins': 3, 'maximum_bin_probability_difference': max(errors),
                                                        'weights_sha256': file_hash(root/'weights.pt')}
            runs.append(entry); print('complete', folder, flush=True)
    means = {}
    for family in families + list(original['baselines']['A']['models']):
        chosen = [r for r in runs if r['family'] == family]
        means[family] = {}
        for mode in ['raw', 'calibrated']:
            means[family][mode] = []
            for h in range(15):
                rows = [r['partitions']['score'][mode][h] for r in chosen]
                means[family][mode].append({'horizon': h+1, **{
                    k: float(np.mean([r[k] for r in rows if r[k] is not None]))
                    for k in ['log_loss', 'brier', 'accuracy', 'roc_auc', 'up_probability_std', 'mean_up_probability', 'observed_up_frequency']}})
    save(a.output, {'state': 'complete', 'version': 'diwali1.4-existing-development-diagnostic',
                    'new_training_runs': 0, 'reserved_september_data_read': False, 'label_mapping': mapping,
                    'raw_recovery': 'Invert the saved 26-way temperature transform: softmax(log(p_cal)*T); exact round trip checked on every head.',
                    'raw_checkpoint_verification': {'model_runs': 18, 'origins_per_run': 3, 'maximum_bin_probability_difference': maximum_sample_error},
                    'calibration': {'method': 'One scalar temperature per horizon chosen on 49 log-spaced values 0.5–4 to minimize 26-bin log loss on separate calibration dates.',
                                    'binary_objective': False, 'minimum_origins': 100, 'fold_C': '25 origins: no temperature fit, all T=1.',
                                    'ranking_warning': '26-way temperature then sum positive bins is not necessarily monotone in the original binary sum; AUC can change.'},
                    'baseline_objective': {'flow_logistic': 'Linear 15×26 multiclass logits trained by categorical cross entropy; NOT direct binary logistic.',
                                           'lifetime_logistic': 'An existing direct binary diagnostic exists at 105/345/945 seconds, but uses the subset with all auxiliary short-horizon labels available; not the full matched primary cohort.'},
                    'equal_fold_equal_seed_transfer_means': means, 'runs': runs, 'input_hashes': data.hashes,
                    'study_report_sha256': file_hash(a.study/'report.json'), 'artifact_hashes': hashes,
                    'source_sha256': file_hash(Path(__file__)),
                    'limitations': ['All August periods are reused development evidence; no fresh improvement claim.',
                                    'Overlapping targets and few calendar days make group frequencies and AUC descriptive; no IID significance claim.',
                                    'AUC is undefined for single-class daily/horizon slices; reported as null, never replaced with 0.5.',
                                    'Probability quartiles are computed per period from predictions only, keep equal scores together, and do not define a trading threshold.',
                                    'Raw reconstruction is sampled against neural checkpoints, not re-inferred for every original forecast.']})
    print('Saved development-only direction diagnostic:', a.output)


if __name__ == '__main__':
    main()
