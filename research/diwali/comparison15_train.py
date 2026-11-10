"""One frozen Diwali1.5 development trial, or matched direct binary baseline."""
import argparse
import json
from pathlib import Path
import random
import time
import warnings

import joblib
import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from threadpoolctl import threadpool_limits
import torch

from .comparison15 import ComparisonData, CandleAttentionModel, loss_terms, protocol, source_hashes, ROOT
from .event_model import EventModel
from .event_data import normalize
from .event_train import infer, probabilities, calibrate, metrics, nll
from .event_direction_diagnostic import binary_metrics
from .event_evaluation import eligible_origins
from .event_lifetime import sigmoid
from ..market_data.validate_archive import file_hash, save


def score_direction(y, up):
    return {'per_horizon': [binary_metrics(y[:, h], up[:, h]) for h in range(15)],
            'final': binary_metrics(y[:, -1], up[:, -1])}


def run(cache, fold, config, seed, out):
    out.mkdir(parents=True, exist_ok=False); began = time.time(); settings = protocol()
    data = ComparisonData(cache, fold); parts = {}; counts = {}
    for name in ['fit', 'select', 'calibrate', 'score']:
        keep, counts[name] = eligible_origins(data.cutoffs, data.starts, fold, name); parts[name] = np.flatnonzero(keep)
        if len(parts[name]) < settings['minimum_partition_origins'][name]:
            raise ValueError('Insufficient unchanged development partition')
    run_protocol = {'version': 'diwali1.5', 'fold': fold, 'configuration': config, 'seed': seed,
                    'settings': settings, 'source_hashes': source_hashes(), 'cache_report_sha256': file_hash(cache/'report.json')}
    save(out/'run-protocol.json', run_protocol)
    save(out/'cohorts.json', {'partitions': counts, 'coverage': data.report['counts'][fold],
                             'ids_sha256': file_hash(cache/'row_ids.npy')})
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.set_num_threads(4)
    logits = {}; temperatures = []; history = []; selected = None
    if config == 'D_binary_logistic':
        x = normalize(data.arrays['summaries'], data.transform['summary']); y = data.y >= 13
        all_logits = []; convergence = []
        with threadpool_limits(limits=4):
            for h in range(15):
                model = LogisticRegression(C=1., solver='lbfgs', max_iter=1000, random_state=17)
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always', ConvergenceWarning)
                    model.fit(x[parts['fit']], y[parts['fit'], h])
                messages = [str(w.message) for w in caught if issubclass(w.category, ConvergenceWarning)]
                if messages:
                    raise ValueError('Binary logistic did not converge; retain failed run, do not silently increase budget')
                joblib.dump(model, out/f'horizon-{h+1:02d}.joblib')
                z = model.decision_function(x); all_logits.append(z)
                convergence.append(int(model.n_iter_[0]))
                grid = np.geomspace(.5, 4., 49)
                ids = parts['calibrate']
                losses = [binary_metrics(y[ids, h], sigmoid(z[ids]/t))['log_loss'] for t in grid] if len(ids) >= 100 else None
                temperatures.append(float(grid[np.argmin(losses)]) if losses is not None else 1.)
                print('binary horizon', h+1, 'iterations', convergence[-1], flush=True)
        all_logits = np.stack(all_logits, 1)
        logits = {name: all_logits[ids] for name, ids in parts.items() if name != 'fit'}
        selected = {'configuration': config, 'seed': seed, 'fit_objective': 'Direct binary log loss; fixed C1, no hyperparameter search',
                    'parameters': 15*(x.shape[1]+1), 'iterations_per_head': convergence, 'checkpoint_selection': 'Not applicable: fixed convex estimator.'}
    else:
        conf = settings['configurations'][config]
        device = 'mps' if torch.backends.mps.is_available() else 'cpu'
        model = (CandleAttentionModel() if conf['candle_attention'] else EventModel()).to(device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=conf['lr'], weight_decay=settings['weight_decay'])
        best = float('inf'); wait = 0; rng = np.random.default_rng(seed)
        for epoch in range(1, settings['max_epochs']+1):
            model.train(); perm = rng.permutation(parts['fit']); totals = np.zeros(3); seen = 0
            for start in range(0, len(perm), settings['batch_size']):
                ids = perm[start:start+settings['batch_size']]
                args, y = data.batch(ids, data.transform, device); optimizer.zero_grad(set_to_none=True)
                total, price, binary = loss_terms(model(*args), y, conf['direction_weight'])
                if not torch.isfinite(total):
                    raise ValueError('Nonfinite training loss')
                total.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(), settings['gradient_clip'], error_if_nonfinite=True)
                optimizer.step(); totals += np.array([float(v.detach().cpu()) for v in [total, price, binary]])*len(ids); seen += len(ids)
            z = infer(model, data, parts['select'], data.transform, device, settings['batch_size'])
            select_loss = nll(data.y[parts['select']], probabilities(z))
            history.append({'epoch': epoch, 'fit_loss': float(totals[0]/seen), 'fit_price_loss': float(totals[1]/seen),
                            'fit_direction_loss': float(totals[2]/seen), 'selection_range_loss': select_loss})
            if select_loss < best-1e-10:
                best = select_loss; chosen = epoch; wait = 0
                state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}; torch.save(state, out/'weights.pt')
            else:
                wait += 1
            save(out/'history.json', history)
            save(out/'status.json', {'state': 'fitting', 'epoch': epoch, 'best_epoch': chosen, 'elapsed_seconds': time.time()-began})
            print(fold, config, seed, epoch, select_loss, flush=True)
            if wait >= settings['patience']:
                break
        model.load_state_dict(state)
        selected = {'configuration': config, 'seed': seed, 'best_epoch': chosen, 'selection_range_loss': best,
                    'parameters': sum(p.numel() for p in model.parameters()), 'weights_sha256': file_hash(out/'weights.pt'),
                    'all_parameters_trainable': all(p.requires_grad for p in model.parameters())}
        logits = {name: infer(model, data, ids, data.transform, device, settings['batch_size']) for name, ids in parts.items() if name != 'fit'}
        temperatures = calibrate(data.y[parts['calibrate']], logits['calibrate'])
    save(out/'selection.json', selected)
    save(out/'calibration.json', {'temperatures': temperatures, 'origins': len(parts['calibrate']),
                                  'temperature_fitted': len(parts['calibrate']) >= 100,
                                  'objective': 'binary log loss' if config == 'D_binary_logistic' else '26-bin log loss'})
    result = {'state': 'complete', 'fold': fold, 'configuration': config, 'seed': seed, 'selection': selected,
              'coverage': data.report['counts'][fold], 'partitions': {}, 'daily_scores': {},
              'reserved_september_data_read': False, 'cache_report_sha256': file_hash(cache/'report.json')}
    for name, z in logits.items():
        ids = parts[name]; binary = data.y[ids] >= 13
        if config == 'D_binary_logistic':
            raw = sigmoid(z); calibrated = sigmoid(z/np.asarray(temperatures)[None])
            result['partitions'][name] = {'raw_direction': score_direction(binary, raw), 'calibrated_direction': score_direction(binary, calibrated),
                                          'range_score': None, 'scope': 'Direct binary model; no price-band predictions.'}
            np.savez_compressed(out/(name+'-predictions.npz'), row_ids=data.ids[ids], up_raw=raw, up_calibrated=calibrated)
        else:
            raw = probabilities(z); calibrated = probabilities(z, temperatures)
            result['partitions'][name] = {'raw_range': metrics(data.y[ids], raw), 'calibrated_range': metrics(data.y[ids], calibrated),
                                          'raw_direction': score_direction(binary, raw[:, :, 13:].sum(-1)),
                                          'calibrated_direction': score_direction(binary, calibrated[:, :, 13:].sum(-1))}
            np.savez_compressed(out/(name+'-predictions.npz'), row_ids=data.ids[ids], probabilities_raw=raw, probabilities=calibrated)
        if name == 'score':
            days = np.array([str(np.datetime64(int(t), 'ns'))[:10] for t in data.cutoffs[ids]])
            for day in sorted(set(days)):
                keep = days == day
                up = calibrated[keep] if config == 'D_binary_logistic' else calibrated[keep, :, 13:].sum(-1)
                result['daily_scores'][day] = {'direction': score_direction(binary[keep], up),
                                               'range': None if config == 'D_binary_logistic' else metrics(data.y[ids][keep], calibrated[keep])}
    result['elapsed_seconds'] = time.time()-began
    save(out/'report.json', result); save(out/'status.json', {'state': 'complete', 'elapsed_seconds': result['elapsed_seconds']})


def main():
    p = argparse.ArgumentParser(); p.add_argument('--cache', type=Path, required=True); p.add_argument('--fold', choices=['A', 'B', 'C'], required=True)
    p.add_argument('--configuration', choices=list(protocol()['configurations'])+['D_binary_logistic'], required=True)
    p.add_argument('--seed', type=int, choices=[17, 29], default=17); p.add_argument('--output', type=Path, required=True); a = p.parse_args()
    if a.configuration == 'D_binary_logistic' and a.seed != 17:
        raise ValueError('Deterministic logistic baseline runs once per fold, not duplicate seeds')
    run(a.cache, a.fold, a.configuration, a.seed, a.output)


if __name__ == '__main__':
    main()
