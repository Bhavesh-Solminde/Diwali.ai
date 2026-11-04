"""Separate direction and within-side range errors on existing development scores."""
import argparse
import json
from pathlib import Path

import numpy as np

from .event_data import labels
from .event_evaluation import eligible_origins
from ..market_data.validate_archive import file_hash, save


def decompose(y, p):
    y = np.asarray(y); p = np.asarray(p, np.float64)
    if p.shape != (*y.shape, 26) or not np.isfinite(p).all() or (p <= 0).any():
        raise ValueError('Expected positive 26-bin forecast probabilities')
    np.testing.assert_allclose(p.sum(-1), 1, atol=1e-9, rtol=0)
    chosen = np.take_along_axis(p, y[..., None], axis=-1)[..., 0]
    up = p[..., 13:].sum(-1); mass = np.where(y >= 13, up, p[..., :13].sum(-1))
    direction = -np.log(mass); conditional = -np.log(chosen/mass); total = -np.log(chosen)
    np.testing.assert_allclose(direction+conditional, total, atol=1e-12, rtol=0)
    return {'mean15_total_bin_log_loss': float(total.mean()),
            'mean15_direction_log_loss': float(direction.mean()),
            'mean15_within_side_log_loss': float(conditional.mean()),
            'per_horizon_direction_log_loss': direction.mean(0).tolist(),
            'per_horizon_within_side_log_loss': conditional.mean(0).tolist(),
            'final_mean_up_probability': float(up[:, -1].mean()),
            'final_observed_up_fraction': float((y[:, -1] >= 13).mean()),
            'final_fraction_favouring_up': float((up[:, -1] >= .5).mean()),
            'final_fraction_confident_at_least_60_percent': float((np.maximum(up[:, -1], 1-up[:, -1]) >= .6).mean()),
            'maximum_decomposition_difference': float(np.max(np.abs(total-direction-conditional)))}


def main():
    p = argparse.ArgumentParser(); p.add_argument('--study', type=Path, required=True)
    p.add_argument('--cohort', type=Path, required=True); p.add_argument('--audit', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True); a = p.parse_args()
    audit = json.loads(a.audit.read_text())
    if audit['state'] != 'complete' or audit['neural_runs_verified'] != 18 or audit['data_hashes']['cohort'] != file_hash(a.cohort/'report.json'):
        raise ValueError('Completed development audit required')
    cr = json.loads((a.cohort/'candles/report.json').read_text()); tp = a.cohort/'candles/targets.json'
    if file_hash(tp) != cr['artifact_sha256']['targets.json']:
        raise ValueError('Changed development targets')
    targets = json.loads(tp.read_text()); meta = json.loads((a.cohort/'candles/input-metadata.json').read_text())
    ids = np.asarray([r['input_row'] for r in targets]); y = labels([r['returns_bp'] for r in targets])
    cutoffs = np.asarray([meta[int(i)]['input_cutoff_ns'] for i in ids], np.int64)
    starts = np.asarray([r['target_start_ns'] for r in targets], np.int64)
    result = {}; hashes = {}
    names = ['event_temporal_conv', 'event_attention', 'one_second_temporal_conv']
    for fold in ['A', 'B', 'C']:
        keep, _ = eligible_origins(cutoffs, starts, fold, 'score'); fold_result = {}
        for name in names+['fit_histogram', 'fit_volatility_histogram', 'flow_logistic', 'flow_boosted_trees']:
            runs = []
            for seed in ([17, 29] if name in names else [None]):
                root = a.study/(f'{fold}-{name}-seed{seed}' if seed is not None else f'{fold}-baselines/{name}')
                path = root/'score-predictions.npz'; hashes[str(path)] = file_hash(path)
                with np.load(path) as z:
                    np.testing.assert_array_equal(z['row_ids'], ids[keep])
                    runs.append(decompose(y[keep], z['probabilities']))
            fold_result[name] = {k: np.mean([r[k] for r in runs], axis=0).tolist() for k in runs[0]}
        result[fold] = fold_result
    means = {name: {k: np.mean([result[f][name][k] for f in result], axis=0).tolist()
                    for k in result['A'][name]} for name in result['A']}
    save(a.output, {'state': 'complete', 'scope': 'Already-used August development predictions only; no reserved test access or fitting.',
                    'identity': '26-bin negative log probability equals binary direction error plus within-side conditional range error.',
                    'interpretation': 'A model can improve conditional magnitude without improving up/down probability. This decomposition is not a causal feature attribution.',
                    'folds': result, 'equal_fold_equal_seed_means': means,
                    'prediction_artifact_hashes': hashes, 'targets_sha256': file_hash(tp),
                    'source_sha256': file_hash(Path(__file__))})
    for name, m in means.items():
        print(name, json.dumps({k: m[k] for k in ['mean15_total_bin_log_loss', 'mean15_direction_log_loss', 'mean15_within_side_log_loss']}))


if __name__ == '__main__':
    main()
