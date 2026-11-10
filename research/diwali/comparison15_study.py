"""Run exactly the declared small comparison; no reserved-test access or retries."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
import sklearn
import torch

from .comparison15 import protocol, source_hashes, prepare_cache, ROOT, ComparisonData
from .event_evaluation import eligible_origins
from .event_train import metrics
from ..market_data.validate_archive import file_hash, save


def aggregate(runs):
    settings = protocol(); expected = {(f, c, s) for f in ['A', 'B', 'C'] for c in settings['configurations'] for s in [17, 29]}
    neural = [r for r in runs if r['configuration'] != 'D_binary_logistic']
    actual = {(r['fold'], r['configuration'], r['seed']) for r in neural}
    if actual != expected or len(neural) != len(expected):
        raise ValueError('Incomplete or duplicate bounded neural study')
    direct_runs = [r for r in runs if r['configuration'] == 'D_binary_logistic']
    if len(direct_runs) != 3 or {(r['fold'], r['seed']) for r in direct_runs} != {(f, 17) for f in ['A', 'B', 'C']}:
        raise ValueError('Missing direct-binary folds')
    comparison = {}
    for name, conf in settings['configurations'].items():
        rs = [r for r in neural if r['configuration'] == name]
        comparison[name] = {
            'family': conf['family'], 'mean15_bin_log_loss': float(np.mean([r['partitions']['score']['calibrated_range']['mean15_bin_log_loss'] for r in rs])),
            'final_direction_log_loss': float(np.mean([r['partitions']['score']['calibrated_direction']['final']['log_loss'] for r in rs])),
            'final_direction_auc': float(np.mean([r['partitions']['score']['calibrated_direction']['final']['roc_auc'] for r in rs])),
            'final_direction_brier': float(np.mean([r['partitions']['score']['calibrated_direction']['final']['brier'] for r in rs])),
            'per_fold_range_loss': {f: float(np.mean([r['partitions']['score']['calibrated_range']['mean15_bin_log_loss'] for r in rs if r['fold'] == f])) for f in ['A', 'B', 'C']}}
    family_best = {family: min([n for n, c in comparison.items() if c['family'] == family], key=lambda n: comparison[n]['mean15_bin_log_loss']) for family in ['A', 'B', 'C']}
    lowest = min(v['mean15_bin_log_loss'] for v in comparison.values())
    selected = next(n for n in settings['configurations'] if comparison[n]['mean15_bin_log_loss'] <= lowest+.0001)
    ds = [r for r in runs if r['configuration'] == 'D_binary_logistic']
    direct = {'mean_final_direction_log_loss': float(np.mean([r['partitions']['score']['calibrated_direction']['final']['log_loss'] for r in ds])),
              'mean_final_direction_auc': float(np.mean([r['partitions']['score']['calibrated_direction']['final']['roc_auc'] for r in ds])),
              'primary_range_eligible': False}
    return {'selected_neural_configuration': selected, 'best_per_family': family_best, 'neural_comparison': comparison,
            'direct_binary': direct, 'scope': 'Development selection only; no new independent efficacy claim or production promotion.'}


def main():
    p = argparse.ArgumentParser(); p.add_argument('--output', type=Path, required=True); p.add_argument('--cache', type=Path, required=True)
    a = p.parse_args(); a.output.mkdir(parents=True, exist_ok=False); began = time.time()
    frozen = {'settings': protocol(), 'source_hashes': source_hashes(),
              'versions': {'python': sys.version, 'numpy': np.__version__, 'torch': torch.__version__, 'sklearn': sklearn.__version__}}
    save(a.output/'study-protocol.json', frozen)
    save(a.output/'status.json', {'state': 'preparing_cache', 'pid': __import__('os').getpid()})
    try:
        if not a.cache.exists():
            prepare_cache(a.cache)
        cache_report = json.loads((a.cache/'report.json').read_text())
        if cache_report['state'] != 'complete' or cache_report['preparer_sha256'] != frozen['source_hashes']['comparison15.py']:
            raise ValueError('Incomplete or changed prepared cache')
        save(a.output/'data-coverage.json', cache_report)
        # Bind reused baselines to exactly these origins before starting any new fit.
        benchmarks = json.loads((ROOT/'results/diwali1.4/development-report.json').read_text())['baselines']
        verified_baselines = {}
        for fold in ['A', 'B', 'C']:
            data = ComparisonData(a.cache, fold)
            keep, _ = eligible_origins(data.cutoffs, data.starts, fold, 'score')
            for name in ['fit_histogram', 'fit_volatility_histogram']:
                path = ROOT/f'data/models/diwali1.4-development-exact-v2/{fold}-baselines/{name}/score-predictions.npz'
                with np.load(path) as z:
                    np.testing.assert_array_equal(z['row_ids'], data.ids[keep])
                    direct = metrics(data.y[keep], z['probabilities'])
                expected = benchmarks[fold]['models'][name]['partitions']['score']
                if abs(direct['mean15_bin_log_loss']-expected['mean15_bin_log_loss']) > 1e-12 or abs(direct['final_direction_log_loss']-expected['final_direction_log_loss']) > 1e-12:
                    raise ValueError('Reused benchmark is not the same-scored cohort')
                verified_baselines[f'{fold}-{name}'] = file_hash(path)
        save(a.output/'baseline-identity.json', {'state': 'verified', 'forecasts': verified_baselines})
    except Exception as error:
        save(a.output/'status.json', {'state': 'preparation_failed', 'error': str(error), 'completed_runs': 0})
        raise
    runs = []
    schedule = ['D_binary_logistic', 'B_direction025', 'B_direction100', 'A_original', 'A_lower_lr',
                'C_attention_original_lr', 'C_attention_lower_lr']
    try:
        for fold in ['A', 'B', 'C']:
            for config in schedule:
                for seed in ([17] if config == 'D_binary_logistic' else [17, 29]):
                    if source_hashes() != frozen['source_hashes']:
                        raise ValueError('Study sources changed; stop rather than mix implementations')
                    name = f'{fold}-{config}-seed{seed}'; out = a.output/name
                    if out.exists():
                        raise ValueError('Run already exists; no overwrite or silent retry')
                    with (a.output/(name+'.log')).open('w') as log:
                        child = subprocess.Popen([sys.executable, '-m', 'research.diwali.comparison15_train',
                                                  '--cache', str(a.cache), '--fold', fold, '--configuration', config,
                                                  '--seed', str(seed), '--output', str(out)], stdout=log, stderr=subprocess.STDOUT)
                        save(a.output/'status.json', {'state': 'running', 'active_run': name, 'child_pid': child.pid,
                                                     'completed_runs': len(runs), 'planned_runs': 39, 'elapsed_seconds': time.time()-began})
                        print('started', name, child.pid, flush=True); code = child.wait()
                    if code:
                        raise ValueError(f'Run failed: {name}; preserve log and artifacts; no automatic retry')
                    rp = json.loads((out/'run-protocol.json').read_text())
                    if rp['source_hashes'] != frozen['source_hashes'] or rp['cache_report_sha256'] != file_hash(a.cache/'report.json'):
                        raise ValueError('Completed run identity differs')
                    run = json.loads((out/'report.json').read_text())
                    if run['state'] != 'complete':
                        raise ValueError('Incomplete run report')
                    if config != 'D_binary_logistic' and file_hash(out/'weights.pt') != run['selection']['weights_sha256']:
                        raise ValueError('Changed selected model')
                    runs.append(run)
                    progress = {'state': 'development_in_progress', 'completed_runs': len(runs), 'planned_runs': 39,
                                'runs': runs, 'coverage': cache_report['counts'], 'reserved_september_data_read': False}
                    save(a.output/'progress.json', progress)
                    save(ROOT/'results/diwali1.5/development-progress.json', public_metrics(progress))
                    print('complete', name, flush=True)
        decision = aggregate(runs)
        baselines = {name: {'mean15_bin_log_loss': float(np.mean([benchmarks[f]['models'][name]['partitions']['score']['mean15_bin_log_loss'] for f in ['A', 'B', 'C']])),
                            'final_direction_log_loss': float(np.mean([benchmarks[f]['models'][name]['partitions']['score']['final_direction_log_loss'] for f in ['A', 'B', 'C']]))}
                     for name in ['fit_histogram', 'fit_volatility_histogram']}
        previous = json.loads((ROOT/'results/diwali1.4/development-report.json').read_text())['neural_runs']
        reproduction = []
        for run in runs:
            if run['configuration'] != 'A_original':
                continue
            old = next(r for r in previous if r['candidate'] == 'one_second_temporal_conv' and r['fold'] == run['fold'] and r['seed'] == run['seed'])
            reproduction.append({'fold': run['fold'], 'seed': run['seed'],
                                 'old_best_epoch': old['selection']['best_epoch'], 'new_best_epoch': run['selection']['best_epoch'],
                                 'range_loss_difference': run['partitions']['score']['calibrated_range']['mean15_bin_log_loss']-old['partitions']['score']['mean15_bin_log_loss']})
        report = {'state': 'development_complete', 'decision': decision, 'runs': runs, 'baselines': baselines,
                  'original_control_reproduction': reproduction,
                  'always_half_direction_log_loss': float(np.log(2)), 'coverage': cache_report['counts'],
                  'reserved_september_data_read': False, 'source_hashes': frozen['source_hashes'],
                  'elapsed_seconds': time.time()-began, 'future_evaluation': 'Not performed; selected artifacts and rules must be frozen first.'}
        save(a.output/'report.json', report); save(ROOT/'results/diwali1.5/development-report.json', public_metrics(report))
        save(a.output/'status.json', {'state': 'development_complete', 'decision': decision})
    except Exception as error:
        save(a.output/'status.json', {'state': 'failed', 'error': str(error), 'completed_runs': len(runs), 'elapsed_seconds': time.time()-began})
        raise


def public_metrics(value):
    if isinstance(value, dict):
        if isinstance(value.get('origins'), int) and value['origins'] < 10:
            return {'origins': value['origins'], 'metrics_suppressed': 'Fewer than ten origins; complete metrics stay private.'}
        return {k: public_metrics(v) for k, v in value.items()}
    if isinstance(value, list):
        return [public_metrics(v) for v in value]
    return value


if __name__ == '__main__':
    main()
