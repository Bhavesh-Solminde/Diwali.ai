"""Diwali 0.2: causal next-full-minute outcome probabilities, no rollout."""
import argparse
import json
from pathlib import Path
import random
import time

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from .model import Diwali, CANDLE_SIZE, BOOK_SIZE
from .train import Data
from ..market_data.validate_archive import save, file_hash

CLASSES = ['bearish', 'neutral', 'bullish']


def labels(close, reference, threshold=2.):
    move = (np.asarray(close) / reference - 1) * 10000
    # Inclusive outer thresholds; the neutral interval is open at both ends.
    return np.where(move <= -threshold, 0, np.where(move >= threshold, 2, 1)).astype(np.int64)


def observed_reference(trades, row):
    """Last nonempty COMPLETE received-second VWAP; never read target prices."""
    rows = trades[int(row[3]):int(row[4])]
    values = rows['x'][:, :4].astype(np.float64)
    nonempty = np.flatnonzero(values[:, :2].sum(axis=1) > 0)
    if not len(nonempty):
        raise ValueError('No observed execution reference in causal window')
    j = nonempty[-1]
    if max(int(rows[j]['receipt_ns']), int(rows[j]['event_ns'])) >= int(row[0])*10**6:
        raise ValueError('Reference includes future messages')
    price = values[j, 2:4].sum() / values[j, :2].sum()
    if not np.isfinite(price) or price <= 0:
        raise ValueError('Invalid observed reference')
    return price, (int(row[0])*10**6-int(rows[j]['receipt_ns']))/1e9


def summarize(x):
    c = x[:, :CANDLE_SIZE].reshape(-1, 1440, 8)
    b = x[:, CANDLE_SIZE:CANDLE_SIZE+BOOK_SIZE].reshape(-1, 60, 87)
    t = x[:, CANDLE_SIZE+BOOK_SIZE:-1].reshape(-1, 60, 5)
    return np.concatenate([c[:, -1], c[:, -15:].mean(1), c[:, -60:].mean(1),
                           c.mean(1), b[:, -1, 80:], b[:, :, 80:].mean(1),
                           t[:, -1], t.mean(1), x[:, -1:]], axis=1)


class ProbabilityModel(nn.Module):
    def __init__(self, architecture, width):
        super().__init__()
        self.architecture = architecture
        if architecture == 'logistic':
            self.body = nn.Linear(width, 6)
        else:
            self.encoder = Diwali(architecture, [1., 1., 1., 1.])
            self.encoder.head = nn.Identity()
            self.head = nn.Linear(33, 6)

    def forward(self, x):
        if self.architecture == 'logistic':
            return self.body(x).reshape(-1, 2, 3)
        e = self.encoder
        raw = x[:, :-1]
        if self.architecture == 'mlp':
            z = e.body(raw)
        else:
            c = raw[:, :CANDLE_SIZE].reshape(-1, 1440, 8).transpose(1, 2)
            _, ch = e.candle_gru(F.gelu(e.conv(c)).transpose(1, 2))
            b = raw[:, CANDLE_SIZE:CANDLE_SIZE+BOOK_SIZE].reshape(-1, 60, 87)
            t = raw[:, CANDLE_SIZE+BOOK_SIZE:].reshape(-1, 60, 5)
            _, fh = e.flow_gru(F.gelu(e.project(torch.cat([b, t], dim=2))))
            z = e.body(torch.cat([ch[-1], fh[-1]], dim=1))
        return self.head(torch.cat([z, x[:, -1:]], dim=1)).reshape(-1, 2, 3)


def probabilities(logits, temperature=1.):
    z = np.asarray(logits, dtype=np.float64) / temperature
    z -= z.max(axis=-1, keepdims=True)
    p = np.exp(z)
    return p/p.sum(axis=-1, keepdims=True)


def metrics(y, p):
    chosen = p.argmax(1)
    logloss = float(-np.log(np.maximum(p[np.arange(len(y)), y], 1e-15)).mean())
    bins = []
    for lo in np.arange(0, 1, .1):
        mask = (p.max(1) >= lo) & (p.max(1) < lo+.1 if lo < .9 else p.max(1) <= 1)
        if mask.any():
            bins.append({'lower':float(lo), 'upper':float(lo+.1), 'n':int(mask.sum()),
                         'mean_confidence':float(p.max(1)[mask].mean()),
                         'observed_accuracy':float((chosen[mask] == y[mask]).mean())})
    # Class-specific reliability is necessary: confidence-only bins can hide bias.
    reliability = {}
    for k, name in enumerate(CLASSES):
        rows = []
        for lo in np.arange(0, 1, .1):
            mask = (p[:, k] >= lo) & (p[:, k] < lo+.1 if lo < .9 else p[:, k] <= 1)
            if mask.any():
                rows.append({'lower':float(lo), 'n':int(mask.sum()),
                             'predicted':float(p[mask, k].mean()), 'observed':float((y[mask] == k).mean())})
        reliability[name] = rows
    return {'examples':len(y), 'log_loss':logloss,
            'brier_score_sum_over_classes':float(((p-np.eye(3)[y])**2).sum(1).mean()),
            'accuracy':float((chosen == y).mean()),
            'balanced_accuracy':float(np.mean([(chosen[y == k] == k).mean() for k in range(3) if np.any(y == k)])),
            'class_counts':np.bincount(y, minlength=3).tolist(),
            'confusion_actual_rows_predicted_columns':[[int(np.sum((y == i) & (chosen == j))) for j in range(3)] for i in range(3)],
            'confidence_bins':bins, 'class_reliability':reliability,
            'high_confidence':{str(cut):{'n':int((p.max(1) >= cut).sum()),
                'coverage':float((p.max(1) >= cut).mean()),
                'accuracy':float((chosen[p.max(1) >= cut] == y[p.max(1) >= cut]).mean()) if np.any(p.max(1) >= cut) else None}
                for cut in [.6, .7, .8, .9]}}


def infer(model, x, device):
    model.eval()
    with torch.inference_mode():
        return np.concatenate([model(torch.tensor(np.array(x[i:i+128]), device=device)).cpu().numpy()
                               for i in range(0, len(x), 128)])


def calibrate(logits, y):
    # One scalar per head. Bounded deterministic search, calibration block ONLY.
    grid = np.exp(np.linspace(np.log(.1), np.log(10), 161))
    loss = [-np.log(np.maximum(probabilities(logits, t)[np.arange(len(y)), y], 1e-15)).mean() for t in grid]
    return float(grid[int(np.argmin(loss))])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('data/models/diwali0.2'))
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    started = time.time()
    protocol = {'model':'diwali0.2', 'task':'one next full calendar minute; no recursive generation',
        'classes':CLASSES, 'primary_threshold_bp':2., 'boundaries':'bearish <= -2; bullish >= +2; neutral strictly between',
        'reference':'VWAP of latest nonempty complete received-second in 60-second input window; float32 archived additive amounts; NOT exact last trade or midpoint',
        'reference_quality':'exclude windows without observed executions or with reference older than 2 seconds at cutoff; never fall back to stale candle close',
        'secondary':'candle colour close vs own open; neutral exact equality; separate probabilities',
        'inputs':'1440 candles, 60 book/trade seconds, observed reference displacement from last completed close',
        'split':'fit Oct1-18; development Oct19-21; calibration Oct22-23; shared inspected benchmark Oct24-31, 2026 UTC',
        'selection':'lowest mean three-seed primary development log loss; inference seed17 fixed; early stopping per seed on primary development log loss',
        'architectures':['logistic', 'mlp', 'sequence'], 'seeds':[17,29,43], 'max_epochs':20,
        'patience':4, 'batch':128, 'learning_rate':.0003, 'weight_decay':.0001,
        'loss':'unweighted primary cross entropy + 0.25 secondary colour cross entropy',
        'calibration':'per-head scalar temperature, calibration log loss minimized on fixed 161-point log grid [.1,10]',
        'limitations':['Historical candle availability assumed; provider receipt clocks unverified.',
                       'October benchmark previously inspected; fresh confirmation required.',
                       'No trade win-rate, profitability, news, hidden orders or live accuracy claim.',
                       'Three outcomes do not identify a continuous price density or candle-path heatmap.'],
        'code_sha256':file_hash(Path(__file__))}
    save(out/'run-protocol.json', protocol)
    history = []; runs = []
    def status(stage, **fields):
        save(out/'status.json', {'model':'diwali0.2', 'stage':stage, 'elapsed_seconds':time.time()-started, **fields})
    status('Preparing verified historical inputs')
    torch.set_num_threads(4)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    data = Data(Path('data/btc-perp/aligned-button-pilot-202610-v1'), out/'cache')
    parts = {}; delta_mean = delta_std = None; summary_mean = summary_std = None
    def prepare(name):
        nonlocal delta_mean, delta_std, summary_mean, summary_std
        x, _, idx, oldanchor, targets = data.part(name)
        kept = []; observed = []; excluded = {'no_execution':0, 'reference_older_than_2s':0}
        for i, row in enumerate(idx):
            try:
                result = observed_reference(data.trades, row)
            except ValueError as exc:
                if str(exc) != 'No observed execution reference in causal window':raise
                excluded['no_execution'] += 1
                continue
            if result[1] > 2:
                excluded['reference_older_than_2s'] += 1
                continue
            kept.append(i); observed.append(result)
        save(out/f'{name}-reference-quality.json', {'original':len(idx), 'kept':len(kept), 'exclusions':excluded})
        if not kept:raise ValueError('No eligible fresh reference examples')
        x, idx, oldanchor, targets = x[kept], idx[kept], oldanchor[kept], targets[kept]
        ref_age = np.array(observed)
        reference = ref_age[:, 0]
        delta = (reference/oldanchor-1)*10000
        if name == 'fit':
            delta_mean, delta_std = float(delta.mean()), max(float(delta.std()), .01)
        full = np.concatenate([x, ((delta-delta_mean)/delta_std)[:, None]], axis=1).astype(np.float32)
        simple = summarize(full)
        if name == 'fit':
            summary_mean, summary_std = simple.mean(0), np.maximum(simple.std(0), .01)
        simple = ((simple-summary_mean)/summary_std).astype(np.float32)
        body = np.where(targets[:, 3] < targets[:, 0], 0, np.where(targets[:, 3] > targets[:, 0], 2, 1))
        y = np.column_stack([labels(targets[:, 3], reference), body])
        parts[name] = (full, simple, y, idx, reference, ref_age[:, 1])
        return parts[name]
    prepare('fit'); prepare('development')
    save(out/'preprocessing.json', {'delta_mean':delta_mean, 'delta_std':delta_std,
         'summary_mean':summary_mean.tolist(), 'summary_std':summary_std.tolist(),
         'dataset_fingerprint':data.manifest['fingerprint'], 'fit_only':True,
         'aligned_scaler_sha256':file_hash(data.aligned/'scalers.json')})
    for architecture in protocol['architectures']:
        slot = 1 if architecture == 'logistic' else 0
        fx, vx = parts['fit'][slot], parts['development'][slot]
        fy, vy = parts['fit'][2], parts['development'][2]
        for seed in protocol['seeds']:
            random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
            model = ProbabilityModel(architecture, fx.shape[1]).to(device)
            optimizer = torch.optim.AdamW(model.parameters(), lr=protocol['learning_rate'], weight_decay=protocol['weight_decay'])
            best = float('inf'); patience = 0; best_epoch = 0; best_state = None
            for epoch in range(1, protocol['max_epochs']+1):
                model.train(); total = 0.; perm = np.random.permutation(len(fx))
                for start in range(0, len(perm), protocol['batch']):
                    ids = perm[start:start+protocol['batch']]
                    xb = torch.tensor(fx[ids], device=device); yb = torch.tensor(fy[ids], device=device)
                    optimizer.zero_grad(set_to_none=True); logits = model(xb)
                    loss = F.cross_entropy(logits[:, 0], yb[:, 0]) + .25*F.cross_entropy(logits[:, 1], yb[:, 1])
                    if not torch.isfinite(loss):raise ValueError('Nonfinite training loss')
                    loss.backward(); nn.utils.clip_grad_norm_(model.parameters(), 5.); optimizer.step()
                    total += float(loss.detach().cpu())*len(ids)
                vp = probabilities(infer(model, vx, device)[:, 0])
                score = metrics(vy[:, 0], vp)['log_loss']
                history.append({'architecture':architecture, 'seed':seed, 'epoch':epoch,
                                'training_joint_loss':total/len(fx), 'development_primary_log_loss':score})
                if score < best:
                    best = score; best_epoch = epoch; patience = 0
                    best_state = {k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
                else:patience += 1
                status('Training', architecture=architecture, seed=seed, epoch=epoch, development_log_loss=score)
                print(json.dumps(history[-1]), flush=True)
                if patience >= protocol['patience']:break
            torch.save({'state_dict':best_state, 'architecture':architecture, 'input_width':fx.shape[1],
                        'seed':seed, 'epoch':best_epoch}, out/f'{architecture}-{seed}.pt')
            runs.append({'architecture':architecture, 'seed':seed, 'epoch':best_epoch,
                         'development_log_loss':best, 'parameters':sum(p.numel() for p in model.parameters())})
            del model, optimizer
            if device == 'mps':torch.mps.empty_cache()
    means = {a:float(np.mean([r['development_log_loss'] for r in runs if r['architecture'] == a])) for a in protocol['architectures']}
    winner = min(means, key=means.get)
    save(out/'selection.json', {'architecture':winner, 'seed':17, 'development_means':means,
                              'frozen_before_calibration_and_benchmark':True})
    saved = torch.load(out/f'{winner}-17.pt', weights_only=True, map_location='cpu')
    model = ProbabilityModel(winner, saved['input_width']).to(device)
    model.load_state_dict(saved['state_dict']); slot = 1 if winner == 'logistic' else 0
    status('Calibrating selected model')
    prepare('calibration'); logits = infer(model, parts['calibration'][slot], device)
    temperatures = [calibrate(logits[:, h], parts['calibration'][2][:, h]) for h in range(2)]
    save(out/'calibration.json', {'temperatures':temperatures, 'head_order':['primary', 'candle_colour']})
    status('Evaluating shared historical benchmark')
    prepare('locked_test')
    prior = (np.bincount(parts['fit'][2][:, 0], minlength=3)+1)/(len(parts['fit'][2])+3)
    report = {'model':'diwali0.2', 'architecture':winner, 'device':device, 'runs':runs, 'history':history,
              'protocol':protocol, 'development_means':means, 'temperatures':temperatures,
              'recent_live_accuracy':None, 'partitions':{}}
    for name, part in parts.items():
        logits = infer(model, part[slot], device)
        heads = [probabilities(logits[:, h], temperatures[h]) for h in range(2)]
        p = heads[0]; y = part[2][:, 0]
        days = np.array([time.strftime('%Y-%m-%d', time.gmtime(t/1000)) for t in part[3][:, 1]])
        report['partitions'][name] = {'primary':metrics(y, p), 'raw_primary':metrics(y, probabilities(logits[:, 0])),
            'candle_colour':metrics(part[2][:, 1], heads[1]),
            'fit_frequency_baseline':metrics(y, np.broadcast_to(prior, p.shape)),
            'uniform_baseline':metrics(y, np.full_like(p, 1/3)),
            'reference_age_seconds_max':float(part[5].max()),
            'by_day':{d:metrics(y[days == d], p[days == d]) for d in sorted(set(days))}}
        np.savez(out/f'{name}-predictions.npz', probabilities=p, colour_probabilities=heads[1],
                 labels=part[2], indices=part[3], reference=part[4], reference_age_seconds=part[5])
    report['checkpoint_sha256'] = file_hash(out/f'{winner}-17.pt')
    report['wall_seconds'] = time.time()-started
    save(out/'report.json', report)
    status('Complete', architecture=winner, benchmark=report['partitions']['locked_test']['primary'])
    print('COMPLETE', winner, report['partitions']['locked_test']['primary']['log_loss'], flush=True)


if __name__ == '__main__':
    main()
