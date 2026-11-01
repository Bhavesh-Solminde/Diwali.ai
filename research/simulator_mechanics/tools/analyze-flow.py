"""Predefined rule diagnostics, never model fitting; see PREREGISTRATION-B.md."""
import argparse
import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict, deque
from pathlib import Path

import numpy as np


def quant(values, q):
    return float(np.quantile(values, q))


def stats(values):
    a = np.asarray(values, dtype=float)
    if not len(a):
        return {'n': 0}
    return dict(n=len(a), mean=float(a.mean()), median=quant(a, .5),
                p05=quant(a, .05), p95=quant(a, .95), min=float(a.min()), max=float(a.max()),
                sd=float(a.std(ddof=1)) if len(a) > 1 else None)


def interval(values):
    out = stats(values)
    if len(values) >= 2:
        rng = np.random.default_rng(901)
        a = np.asarray(values, dtype=float)
        means = a[rng.integers(0, len(a), (2000, len(a)))].mean(axis=1)
        out['parent_bootstrap_mean_ci95'] = [quant(means, .025), quant(means, .975)]
    return out


def sign(value, threshold=1.):
    return 1 if value > threshold else -1 if value < -threshold else 0


def bp(price, reference):
    return 10000 * (price / reference - 1)


def outcome(rows, c, side):
    origin = rows[c]['close']
    future = rows[c + 1:c + 31]
    result = {f'return_{h}_bp': bp(rows[c + h]['close'], origin) for h in (1, 5, 15, 30)}
    favorable = [side * bp(r['high' if side == 1 else 'low'], origin) for r in future]
    adverse = [-side * bp(r['low' if side == 1 else 'high'], origin) for r in future]
    first = 'timeout'
    first_candle = None
    for i, (fav, adv) in enumerate(zip(favorable, adverse), 1):
        if fav >= 10 or adv >= 10:
            first = 'ambiguous' if fav >= 10 and adv >= 10 else 'target' if fav >= 10 else 'stop'
            first_candle = i
            break
    result.update(mfe_bp=max(0., *favorable), mae_bp=max(0., *adverse),
                  first_outcome=first, first_outcome_candle=first_candle)
    return result


def patterns(rows, c, previous_returns):
    if c < 119:
        return []
    r = rows[c-19:c+1]
    hi = np.array([x['high'] for x in r], dtype=float)
    lo = np.array([x['low'] for x in r], dtype=float)
    old_ranges = [max(x['high'] for x in rows[j-19:j+1]) - min(x['low'] for x in rows[j-19:j+1])
                  for j in range(c-100, c)]
    labels = []
    if hi.max() - lo.min() <= quant(old_ranges, .5):
        labels.append('range')
    x = np.arange(20, dtype=float)
    slope_hi, intercept_hi = np.polyfit(x, hi, 1)
    slope_lo, intercept_lo = np.polyfit(x, lo, 1)
    width0 = intercept_hi - intercept_lo
    width1 = width0 + 19 * (slope_hi - slope_lo)
    if slope_hi < 0 < slope_lo and 0 < width1 <= .5 * width0:
        labels.append('triangle')
    pole = bp(rows[c-10]['close'], rows[c-20]['close'])
    retrace = bp(rows[c]['close'], rows[c-10]['close'])
    vol = float(np.std(previous_returns, ddof=1))
    if abs(pole) >= 2 * (10 ** .5) * vol and pole * retrace < 0 and abs(retrace) <= .5 * abs(pole):
        labels.append('flag')
    return labels


def audit_run(prefix, rows):
    books = {'bid': {}, 'ask': {}}
    totals = Counter()
    removals_large = Counter()
    rows_by_candle = {r['candle']: r for r in rows}
    with gzip.open(str(prefix) + '.changes.csv.gz', 'rt', newline='') as f:
        groups = defaultdict(list)
        for event in csv.DictReader(f):
            for field in ('candle', 'sweep', 'price', 'before', 'after'):
                event[field] = int(event[field])
            groups[event['candle']].append(event)
    for c in range(600):
        for event in groups[c]:
            b = books[event['side']]
            assert b.get(event['price'], 0) == event['before'], (prefix, c, 'before_mismatch')
            change = event['after'] - event['before']
            assert event['after'] >= 0
            if event['cause'] != 'agent_sweep_net':
                assert change < 0
                totals[event['cause'] + '_removed_qty'] -= change
                totals[event['cause'] + '_changed_levels'] += 1
                if event['before'] > 30:
                    removals_large[event['cause']] += 1
            else:
                totals['agent_sweep_net_' + ('added' if change > 0 else 'depleted') + '_qty'] += abs(change)
            if event['after']:
                b[event['price']] = event['after']
            else:
                b.pop(event['price'], None)
        row = rows_by_candle[c]
        assert books['bid'] == dict(row['bids']) and books['ask'] == dict(row['asks'])
        assert row['low'] <= min(row['open'], row['close']) <= max(row['open'], row['close']) <= row['high']
        assert row['low'] > 0 and row['volume'] >= 0
    return {'rows': 600, 'event_reconstruction_pass': True, 'candle_invariants_pass': True,
            'changes': dict(totals), 'removal_events_pre_quantity_over30': dict(removals_large)}


def analyze(raw, output):
    output.mkdir(parents=True, exist_ok=False)
    all_rules, all_events, audits, runs = [], [], {}, []
    for manifest_path in sorted(raw.glob('*.manifest.json')):
        manifest = json.loads(manifest_path.read_text())
        assert manifest['status'] == 'ok'
        prefix = raw / manifest['run_id']
        with gzip.open(str(prefix) + '.candles.jsonl.gz', 'rt') as f:
            rows = [json.loads(line) for line in f]
        assert [r['candle'] for r in rows] == list(range(600))
        audits[manifest['run_id']] = audit_run(prefix, rows)
        ages = {'bid': {}, 'ask': {}}
        history_qty = deque(maxlen=100)
        used_walls = set()
        valid_count = locked = 0
        for c, r in enumerate(rows):
            book = {'bid': dict(r['bids']), 'ask': dict(r['asks'])}
            for side in ages:
                ages[side] = {p: ages[side].get(p, 0) + 1 for p in book[side]}
            if 100 <= c <= 569:
                past = rows[c-100:c]
                prev_vol = [x['volume'] for x in past]
                prev_ranges = [bp(x['high'], x['low']) for x in past]
                previous_returns = [bp(rows[j]['close'], rows[j-1]['close']) for j in range(c-99, c)]
                valid = bool(book['bid'] and book['ask'] and 0 < r['best_bid'] < r['best_ask'] < 2147483647)
                if not valid:
                    locked += 1
                else:
                    valid_count += 1
                    depth_bid = sum(q for p, q in book['bid'].items() if 0 <= 10000*(r['close']-p)/r['close'] <= 10)
                    depth_ask = sum(q for p, q in book['ask'].items() if 0 <= bp(p, r['close']) <= 10)
                    imbalance = (depth_bid-depth_ask)/(depth_bid+depth_ask) if depth_bid+depth_ask else None
                    label = sign(bp(rows[c+1]['close'], r['close']))
                    momentum = sign(bp(r['close'], rows[c-1]['close']))
                    pats = patterns(rows, c, previous_returns)
                    groups = ['all'] + pats
                    volume_stratum = 'low' if r['volume'] <= quant(prev_vol, .5) else 'high' if r['volume'] >= quant(prev_vol, .9) else 'middle'
                    for group in groups:
                        all_rules.append(dict(run_id=r['run_id'], phase=r['phase'], candle=c, group=group,
                            actual=label, momentum=momentum, book=sign(imbalance, .2) if imbalance is not None else None,
                            neutral=0, volume_stratum=volume_stratum, depth_imbalance=imbalance))
                    if history_qty:
                        quantities = [q for snap in history_qty for q in snap]
                        q50, q90 = quant(quantities, .5), quant(quantities, .9)
                        for side, direction in [('bid', 1), ('ask', -1)]:
                            for strength in ('strong', 'weak'):
                                key = (side, strength)
                                candidates = [(abs(bp(p, r['close'])), p, q) for p, q in book[side].items()
                                    if 0 <= direction*10000*(r['close']-p)/r['close'] <= 10 and ages[side][p] >= 5
                                    and (q >= q90 if strength == 'strong' else q <= q50)]
                                if key not in used_walls and candidates:
                                    distance, price, quantity = min(candidates)
                                    event = dict(run_id=r['run_id'], phase=r['phase'], candle=c, type='wall', side=side,
                                        strength=strength, level=price, quantity=quantity, persistence_boundaries=ages[side][price],
                                        distance_bp=distance, past_q50=q50, past_q90=q90, volume_stratum=volume_stratum,
                                        momentum=momentum, depth_imbalance=imbalance)
                                    event.update(outcome(rows, c, direction));all_events.append(event);used_walls.add(key)
                    candle_range = bp(r['high'], r['low'])
                    if r['volume'] >= quant(prev_vol, .9) and candle_range >= quant(prev_ranges, .9):
                        all_events.append(dict(run_id=r['run_id'], phase=r['phase'], candle=c, type='sweep_proxy',
                            volume=r['volume'], range_bp=candle_range, **outcome(rows, c, 1)))
                    if r['volume'] >= quant(prev_vol, .9) and abs(bp(r['close'], r['open'])) <= 5 and candle_range <= quant(prev_ranges, .5):
                        all_events.append(dict(run_id=r['run_id'], phase=r['phase'], candle=c, type='absorption_candidate',
                            volume=r['volume'], range_bp=candle_range, **outcome(rows, c, 1)))
            history_qty.append([q for side in book.values() for q in side.values()])
        runs.append(dict(**manifest, valid_origins=valid_count, excluded_locked_or_absent_origins=locked))
    summaries = {}
    for phase in ('pilot', 'main'):
        rules = [r for r in all_rules if r['phase'] == phase]
        events = [r for r in all_events if r['phase'] == phase]
        data = dict(parents=len([r for r in runs if r['phase'] == phase]), rule_comparisons={}, walls={}, proxies={})
        for group in ('all', 'range', 'triangle', 'flag'):
            eligible = [r for r in rules if r['group'] == group and r['book'] is not None]
            parents = sorted({r['run_id'] for r in eligible})
            rule_report = dict(origins=len(eligible), parents=len(parents), labels=dict(Counter(r['actual'] for r in eligible)), scores={})
            for rule in ('neutral', 'momentum', 'book'):
                parent_accuracy = [np.mean([r[rule] == r['actual'] for r in eligible if r['run_id'] == parent]) for parent in parents]
                recall = [np.mean([r[rule] == label for r in eligible if r['actual'] == label]) for label in (-1, 0, 1)
                          if any(r['actual'] == label for r in eligible)]
                rule_report['scores'][rule] = dict(accuracy=float(np.mean([r[rule] == r['actual'] for r in eligible])) if eligible else None,
                    balanced_accuracy=float(np.mean(recall)) if recall else None, parent_accuracy=interval(parent_accuracy))
            diffs = [np.mean([int(r['book'] == r['actual'])-int(r['momentum'] == r['actual']) for r in eligible if r['run_id'] == parent]) for parent in parents]
            rule_report['book_minus_momentum_parent_accuracy'] = interval(diffs)
            data['rule_comparisons'][group] = rule_report
        for side in ('bid', 'ask'):
            for strength in ('strong', 'weak'):
                selected = [e for e in events if e['type'] == 'wall' and e['side'] == side and e['strength'] == strength]
                data['walls'][side+'_'+strength] = dict(parents=len(selected), outcomes=dict(Counter(e['first_outcome'] for e in selected)),
                    returns={str(h): interval([e[f'return_{h}_bp'] * (1 if side == 'bid' else -1) for e in selected]) for h in (1, 5, 15, 30)},
                    distance_bp=stats([e['distance_bp'] for e in selected]), quantity=stats([e['quantity'] for e in selected]),
                    persistence_boundaries=stats([e['persistence_boundaries'] for e in selected]))
        for kind in ('sweep_proxy', 'absorption_candidate'):
            selected = [e for e in events if e['type'] == kind]
            parents = sorted({e['run_id'] for e in selected})
            data['proxies'][kind] = dict(events=len(selected), parents=len(parents),
                parent_mean_return_1_bp=interval([np.mean([e['return_1_bp'] for e in selected if e['run_id'] == p]) for p in parents]))
        summaries[phase] = data
    report = dict(evidence_type='original_DLL_CLR_flow_host', runs=runs, audits=audits, summaries=summaries,
        notes=['No model fitted. Rules and thresholds fixed before collection.', 'Net sweep deltas are not individual fill or gross cancellation events.',
               'Wall outcomes begin at origin, not first touch. Strong and weak groups observational and unmatched.',
               'All valid origins share a parent; confidence intervals resample parents.', 'Missing ten-bp depth is excluded from common-rule comparisons.'])
    (output/'statistics.json').write_text(json.dumps(report, indent=2, default=lambda x: float(x)))
    for name, data in [('origins', all_rules), ('events', all_events)]:
        with gzip.open(output/f'{name}.jsonl.gz', 'wt') as f:
            for row in data:
                f.write(json.dumps(row)+'\n')
    hashes = {str(p.relative_to(raw)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(raw.glob('*'))}
    (output/'raw-sha256.json').write_text(json.dumps(hashes, indent=2))
    print(json.dumps({phase: {'parents': d['parents'], 'all_origins': d['rule_comparisons']['all']['origins'],
          'book_minus_momentum': d['rule_comparisons']['all']['book_minus_momentum_parent_accuracy'],
          'wall_counts': {k: v['parents'] for k, v in d['walls'].items()}} for phase, d in summaries.items()}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('raw', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    analyze(args.raw, args.output)
