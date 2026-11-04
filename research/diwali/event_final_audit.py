"""Audit saved one-use evaluation outputs, without rerunning or changing a model."""
import argparse
import json
from pathlib import Path

import numpy as np

from .event_data import labels
from .event_evaluation import eligible_origins
from .event_final_gate import check_release
from .event_train import metrics
from ..market_data.validate_archive import file_hash, save


def main():
    p = argparse.ArgumentParser(); p.add_argument('--result', type=Path, required=True)
    p.add_argument('--cohort', type=Path, required=True); p.add_argument('--release', type=Path, required=True)
    p.add_argument('--claim', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(); check_release(a.release)
    report = json.loads((a.result/'report.json').read_text()); ticket = json.loads(a.claim.read_text())
    sha = file_hash(a.result/'report.json')
    if report['state'] != 'reserved_final_evaluation_complete' or ticket['state'] != 'complete' or ticket['report_sha256'] != sha:
        raise ValueError('Missing completed one-use claim/report identity')
    if report['release_sha256'] != file_hash(a.release) or ticket['release_sha256'] != file_hash(a.release):
        raise ValueError('Evaluation release identity differs')
    cr = json.loads((a.cohort/'candles/report.json').read_text())
    for name in ['targets.json', 'input-metadata.json']:
        if file_hash(a.cohort/'candles'/name) != cr['artifact_sha256'][name]:
            raise ValueError('Changed final target or origin artifact')
    targets = json.loads((a.cohort/'candles/targets.json').read_text())
    meta = json.loads((a.cohort/'candles/input-metadata.json').read_text())
    ids = np.asarray([r['input_row'] for r in targets]); y = labels([r['returns_bp'] for r in targets])
    times = np.asarray([meta[int(i)]['input_cutoff_ns'] for i in ids], np.int64)
    starts = np.asarray([r['target_start_ns'] for r in targets], np.int64)
    keep, counts = eligible_origins(times, starts, 'final', 'score', final_release=a.release)
    if counts != report['origin_counts']:
        raise ValueError('Final origin counts changed')
    days = np.asarray([str(np.datetime64(int(t), 'ns'))[:10] for t in times[keep]])
    fields = ['mean15_bin_log_loss', 'ranked_probability_score', 'final_direction_log_loss',
              'final_direction_brier', 'final_direction_accuracy']
    maximum = 0.; evidence = {}; recomputed = {}
    for name, saved in report['models'].items():
        path = a.result/(name+'-predictions.npz')
        with np.load(path) as z:
            np.testing.assert_array_equal(z['row_ids'], ids[keep]); prob = z['probabilities']
        if prob.shape != (int(keep.sum()), 15, 26) or (prob < 0).any() or not np.isfinite(prob).all():
            raise ValueError('Invalid saved final forecasts')
        np.testing.assert_allclose(prob.sum(-1), 1, atol=1e-10, rtol=0)
        result = metrics(y[keep], prob); recomputed[name] = result
        for scope, direct, expected in [('overall', result, saved['overall']),
                                       *[(day, metrics(y[keep][days == day], prob[days == day]), saved['daily'][day]) for day in sorted(set(days))]]:
            for field in fields:
                delta = abs(direct[field]-expected[field]); maximum = max(maximum, delta)
                if delta > 1e-12:
                    raise ValueError('Saved aggregate metric differs from retained forecasts')
        up = prob[:, -1, 13:].sum(-1)
        evidence[name] = {'forecast_artifact_sha256': file_hash(path), 'origins': len(up),
                          'minimum_final_up_probability': float(up.min()),
                          'maximum_final_up_probability': float(up.max()),
                          'mean_final_up_probability': float(up.mean()),
                          'final_forecasts_favouring_up': int((up >= .5).sum()),
                          'final_forecasts_confident_at_least_60_percent': int((np.maximum(up, 1-up) >= .6).sum()),
                          'observed_final_up_fraction': float((y[keep, -1] >= 13).mean())}
        evidence[name]['direction_by_horizon'] = []
        for h in range(15):
            ph = prob[:, h, 13:].sum(-1); yh = y[keep, h] >= 13
            evidence[name]['direction_by_horizon'].append({
                'horizon': h+1, 'seconds_after_typical_freeze': 105+60*h,
                'minimum_up_probability': float(ph.min()), 'maximum_up_probability': float(ph.max()),
                'mean_up_probability': float(ph.mean()), 'up_probability_std': float(ph.std()),
                'forecasts_favouring_up': int((ph >= .5).sum()),
                'direction_accuracy': float(((ph >= .5) == yh).mean()),
                'observed_up_fraction': float(yh.mean()),
                'direction_log_loss': result['per_horizon_binary_log_loss'][h]})
    for name, paired in report['paired_differences'].items():
        actual = recomputed['diwali1.4']['mean15_bin_log_loss']-recomputed[name]['mean15_bin_log_loss']
        if abs(actual-paired['overall_model_minus_baseline_log_loss']) > 1e-12:
            raise ValueError('Paired comparison differs')
        for day, difference in paired['daily_model_minus_baseline_log_loss'].items():
            expected = report['models']['diwali1.4']['daily'][day]['mean15_bin_log_loss']-report['models'][name]['daily'][day]['mean15_bin_log_loss']
            if abs(expected-difference) > 1e-12:
                raise ValueError('Daily paired comparison differs')
    q = report['quality_coverage']
    if q['joined_contexts']+sum(q['input_rejections'].values()) != q['origins_considered'] or q['labelled_joined_origins']+sum(q['target_rejections'].values()) != q['joined_contexts']:
        raise ValueError('Quality ledger does not reconcile')
    save(a.output, {'state': 'complete', 'models_verified': len(evidence), 'origins_per_model': int(keep.sum()),
                    'daily_groups': len(set(days)), 'maximum_recomputed_metric_difference': maximum,
                    'probability_identity_diagnostics': evidence, 'quality_ledgers_reconciled': True,
                    'result_sha256': sha, 'release_sha256': file_hash(a.release), 'claim_sha256': file_hash(a.claim),
                    'source_sha256': file_hash(Path(__file__)),
                    'scope': 'Audit of existing saved forecasts and claimed one-use report only; no new predictions, fitting, selection or fresh-test claim.'})
    print('Verified', len(evidence), 'models across', int(keep.sum()), 'origins;', maximum, 'maximum metric difference.')


if __name__ == '__main__':
    main()
