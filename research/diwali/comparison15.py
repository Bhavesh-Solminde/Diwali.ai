"""Frozen small architecture/objective comparison; Diwali 1.4 sources stay intact."""
import json
import math
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from .event_model import EventModel
from .event_data import Moments, normalize
from .event_data_exact import ExactEventData, exact_one_second
from .event_baselines import summary
from .event_protocol import protocol as parent_protocol
from ..market_data.validate_archive import file_hash, save

ROOT = Path(__file__).resolve().parents[2]


def protocol():
    p = parent_protocol()
    p.update(version='diwali1.5', stage='Reused August development only; September final interval consumed',
             neural_candidates=['A', 'B', 'C'], baselines=['constant_half', 'fit_histogram', 'fit_volatility_histogram', 'D_binary_logistic'],
             configurations={
                 'A_original': {'family': 'A', 'lr': .0003, 'direction_weight': 0., 'candle_attention': False},
                 'A_lower_lr': {'family': 'A', 'lr': .0001, 'direction_weight': 0., 'candle_attention': False},
                 'B_direction025': {'family': 'B', 'lr': .0003, 'direction_weight': .25, 'candle_attention': False},
                 'B_direction100': {'family': 'B', 'lr': .0003, 'direction_weight': 1., 'candle_attention': False},
                 'C_attention_original_lr': {'family': 'C', 'lr': .0003, 'direction_weight': 0., 'candle_attention': True},
                 'C_attention_lower_lr': {'family': 'C', 'lr': .0001, 'direction_weight': 0., 'candle_attention': True}},
             tuning_budget='Two fixed configurations per neural family, same two seeds/three folds, 12 epochs/patience3. All trials retained.',
             primary_selection='Equal-fold/equal-seed calibrated mean15-bin transfer log loss; tie within1e-4 favours A then B then C, and earlier configuration.',
             secondary_direction='Final-close binary log loss/Brier/AUC against 50–50 and volatility baseline. Report tradeoffs; never replace the range primary.',
             loss='Equal15-close categorical CE + lambda * equal15-close binary CE from summed positive/negative bin logits.',
             candle_change='C retains local candle processing and identical96 compressed tokens; adds one width64 four-head Transformer layer, feedforward128, dropout0, fixed positional encoding, only in the candle branch.',
             direct_binary='D:15 independent sklearn logistic heads on identical447-value summary inputs used by old flow_logistic; C1, lbfgs, max_iter1000, seed17. No range model; not eligible for primary range selection.',
             calibration='Neural: unchanged26-way horizon temperatures minimizing range loss. D: binary temperatures minimizing binary loss. Same49-point grid/minimum100 origins. Report raw and calibrated.',
             prospective='Freeze selected artifacts/rules before any new future-issued forecasts. Match all candidate/baseline eligible timestamps. No prospective efficacy claim from this development study.')
    return p


def source_hashes():
    names = ['comparison15.py', 'comparison15_train.py', 'comparison15_study.py',
             'event_model.py', 'event_data.py', 'event_data_exact.py', 'event_train.py',
             'event_evaluation.py', 'event_baselines.py', 'event_protocol.py',
             'event_direction_diagnostic.py', 'event_lifetime.py']
    return {name: file_hash(Path(__file__).with_name(name)) for name in names}


def loss_terms(logits, y, direction_weight):
    price = F.cross_entropy(logits.reshape(-1, 26), y.reshape(-1))
    binary_logits = torch.stack([torch.logsumexp(logits[..., :13], -1),
                                 torch.logsumexp(logits[..., 13:], -1)], -1)
    binary = F.cross_entropy(binary_logits.reshape(-1, 2), (y >= 13).long().reshape(-1))
    return price + direction_weight*binary, price, binary


class CandleAttentionModel(EventModel):
    def __init__(self, width=64, block=128):
        super().__init__('temporal_conv', width=width, block=block)
        self.candle_mixer = nn.TransformerEncoderLayer(width, 4, dim_feedforward=2*width,
                                                     dropout=0., batch_first=True, norm_first=True)
        positions = torch.arange(96)[:, None]
        frequencies = torch.exp(torch.arange(0, width, 2)*(-math.log(10000.)/width))
        pe = torch.zeros(96, width); pe[:, 0::2] = torch.sin(positions*frequencies)
        pe[:, 1::2] = torch.cos(positions*frequencies)
        self.register_buffer('candle_position', pe, persistent=True)

    def forward(self, events, mask, candles, seed, time_groups, candle_mask, reference_from_seed_bp):
        if candles.shape[1:] != (1440, 8) or seed.shape[1:] != (80,):
            raise ValueError('Invalid candle/seed context')
        if reference_from_seed_bp.shape != (len(events), 1) or not torch.isfinite(reference_from_seed_bp).all():
            raise ValueError('Explicit finite reference-to-seed coordinate required')
        e, em = self.event_tokens(events, mask, time_groups)
        if candle_mask.shape != candles.shape[:2] or candle_mask.dtype != torch.bool:
            raise ValueError('Explicit candle validity mask required')
        cm = torch.ones(candles.shape[:2], dtype=torch.bool, device=candles.device)
        known = candles.masked_fill(~candle_mask[:, :, None], 0)
        c = self.candle_project(known)+self.candle_missing[None, None]*(~candle_mask[:, :, None])
        c = self.candle_local(c, cm).reshape(len(c), 96, 15, self.width).mean(2)
        c = self.candle_mixer(c+self.candle_position[None])
        context = torch.cat([c+self.modality[0], self.seed_project(seed)[:, None]+self.modality[1],
                             self.reference_project(reference_from_seed_bp)[:, None]+self.modality[1], e+self.modality[2]], 1)
        valid = torch.cat([torch.ones((len(e), 98), dtype=torch.bool, device=e.device), em], 1)
        context = self.context_conv(context, valid)
        query = self.horizons[None].expand(len(e), -1, -1)
        return self.head(query+self.read(query, context, valid))


def prepare_cache(output):
    cohort = ROOT/'data/btc-perp/event-month-cohort-august-v1'
    if json.loads((cohort/'protocol.json').read_text())['origins'] != ['2026-08-01', '2026-08-31']:
        raise ValueError('August development scope required before opening labels')
    data = ExactEventData(cohort, ROOT/'data/btc-perp/event-inputs-august-fast-v1', ROOT/'results/event-joined-cohort/august-month-audit.json')
    if len(data.ids) != 5391:
        raise ValueError('Prepared primary cohort changed')
    output.mkdir(parents=True, exist_ok=False)
    events = []; seeds = []; refs = []; summaries = []
    for j in range(len(data.ids)):
        raw = data.raw(j); e, _, _, _, s, r = raw
        events.append(exact_one_second(e, data.exact_elapsed(j))); seeds.append(s); refs.append(r)
        summaries.append(summary(raw)[0])
    arrays = {'seconds': np.stack(events), 'seeds': np.stack(seeds), 'references': np.stack(refs),
              'summaries': np.stack(summaries), 'candles': np.array(data.candles[data.ids]),
              'candle_masks': np.array(data.candle_masks[data.ids]), 'row_ids': data.ids,
              'labels': data.y, 'cutoffs': data.cutoffs, 'starts': data.starts}
    for name, value in arrays.items():
        np.save(output/(name+'.npy'), value)
    if arrays['summaries'].shape != (5391, 447):
        raise ValueError('Expected unchanged447-channel logistic summary')
    counts = {}; transforms = {}
    for fold in ['A', 'B', 'C']:
        parts = {name: data.partition(fold, name)[0] for name in ['fit', 'select', 'calibrate', 'score']}
        counts[fold] = {}
        for name, indices in parts.items():
            times = data.cutoffs[indices]
            counts[fold][name] = {'origins': len(indices), 'first_freeze_utc': str(np.datetime64(int(times.min()), 'ns')),
                                  'last_freeze_utc': str(np.datetime64(int(times.max()), 'ns')),
                                  'distinct_days': len(set(str(np.datetime64(int(t), 'ns'))[:10] for t in times))}
        stats = {n: Moments(w) for n, w in [('event', 103), ('candle', 8), ('seed', 80), ('reference', 1), ('summary', 447)]}
        for j in parts['fit']:
            stats['event'].add(arrays['seconds'][j]); stats['candle'].add(arrays['candles'][j][arrays['candle_masks'][j]])
            stats['seed'].add(arrays['seeds'][j][None]); stats['reference'].add(arrays['references'][j][None]); stats['summary'].add(arrays['summaries'][j][None])
        transforms[fold] = {n: st.record() for n, st in stats.items()}
        old = json.loads((ROOT/f'data/models/diwali1.4-development-exact-v2/{fold}-one_second_temporal_conv-seed17/fit-transforms.json').read_text())
        for name in ['event', 'candle', 'seed', 'reference']:
            if transforms[fold][name] != old['moments'][name]:
                raise ValueError('Cache changed the original fit-only transforms')
        # Compare actual model inputs, not just a cache manifest.
        for j in np.linspace(0, len(data.ids)-1, 10, dtype=int):
            original, _ = data.batch([j], old, 'cpu')
            actual = cache_batch(arrays, [j], transforms[fold], 'cpu')[0]
            for a, b in zip(original, actual):
                if not torch.equal(a, b):
                    raise ValueError('Cached tensor differs from exact original input')
    save(output/'transforms.json', transforms)
    report = {'state': 'complete', 'version': 'diwali1.5-input-cache', 'origins': len(data.ids),
              'cohort_scope': 'All5391 prepared quality-approved August labelled origins; not a diagnostic subsample and not the full twelve-month archive.',
              'counts': counts, 'source_data_hashes': data.hashes, 'input_tensor_parity': '30 per-fold origin checks, seven tensors each: bitwise exact.',
              'all_fold_fit_transforms_equal_original': True,
              'artifact_hashes': {p.name: file_hash(p) for p in output.iterdir() if p.is_file()},
              'preparer_sha256': file_hash(Path(__file__)), 'future_inputs_or_targets_used_in_features': False}
    save(output/'report.json', report); return report


def cache_batch(arrays, ids, transform, device):
    ids = np.asarray(ids); mask = np.array(arrays['candle_masks'][ids])
    c = normalize(arrays['candles'][ids], transform['candle']); c[~mask] = 0
    x = [normalize(arrays['seconds'][ids], transform['event']), np.ones((len(ids), 60), bool), c,
         normalize(arrays['seeds'][ids], transform['seed']), np.tile(np.arange(60, dtype=np.int64), (len(ids), 1)),
         mask, normalize(arrays['references'][ids], transform['reference'])]
    return tuple(torch.as_tensor(v, device=device) for v in x), torch.as_tensor(arrays['labels'][ids], dtype=torch.long, device=device)


class ComparisonData:
    def __init__(self, cache, fold):
        self.root = Path(cache); self.report = json.loads((self.root/'report.json').read_text())
        if self.report['state'] != 'complete':
            raise ValueError('Incomplete input cache')
        for name, sha in self.report['artifact_hashes'].items():
            if file_hash(self.root/name) != sha:
                raise ValueError('Changed cached inputs')
        self.arrays = {p.stem: np.load(p, mmap_mode='r') for p in self.root.glob('*.npy')}
        self.ids = self.arrays['row_ids']; self.y = self.arrays['labels']; self.cutoffs = self.arrays['cutoffs']; self.starts = self.arrays['starts']
        self.transform = json.loads((self.root/'transforms.json').read_text())[fold]

    def batch(self, ids, transforms, device):
        return cache_batch(self.arrays, ids, transforms, device)
