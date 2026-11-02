"""Audit frozen pilot coverage and fixed development baselines. Never opens test targets."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import numpy as np
from .build_pilot import START, STOP, WARMUP, eligible_indices, feature_dtype, references
from .validate_archive import save, file_hash

PARTITIONS = ('fit', 'development', 'calibration', 'locked_test')
DELAYS = (0, 250, 1000)


def utc(ms):
    return datetime.fromtimestamp(int(ms)/1000, timezone.utc).isoformat()


def context_failures(valid, ci):
    return np.flatnonzero(~valid[max(0, ci-1440):ci]) + max(0, ci-1440)


def candle_reason(truth, seen):
    if truth is None: return 'missing_reference'
    if seen is None: return 'missing_execution_minute'
    if seen['bad']: return 'source_or_clock_audit_rejection'
    for k in ('open', 'high', 'low', 'close', 'volume', 'count'):
        if Decimal(str(seen[k])) != truth[k]: return 'execution_reference_mismatch'
    if abs(Decimal(seen['quote_volume'])-truth['quote_volume']) > Decimal('.01'):
        return 'quote_volume_mismatch'
    return 'unavailable_receipt'


def metrics(pred, actual):
    # OHLC errors relative to the same pre-origin close, in basis points.
    error = pred-actual
    sign = np.sign(actual[:, 3])
    guess = np.sign(pred[:, 3])
    recalls = [float(np.mean(guess[sign==s] == s)) for s in (-1, 0, 1) if (sign==s).any()]
    return {'samples': len(actual), 'ohlc_mae_bp': np.abs(error).mean(axis=0).tolist(),
            'ohlc_rmse_bp': np.sqrt((error**2).mean(axis=0)).tolist(),
            'close_direction_accuracy': float(np.mean(sign==guess)),
            'balanced_direction_accuracy': float(np.mean(recalls)),
            'direction_classes': {str(s): int(np.sum(sign==s)) for s in (-1,0,1)}}


def baseline_predictions(raw, indices, book, trades, fit_majority):
    ci = indices[:, 1]
    prev, prev2 = raw[ci-1], raw[ci-2]
    anchor = prev[:, 3]
    last_return = (anchor/prev2[:, 3]-1)*10000
    magnitude = np.abs(last_return)
    b = book[indices[:, 3]-1]['x']
    flow = np.array([trades[r[2]:r[3]]['x'][:, :2].sum(axis=0) for r in indices])
    signals = {'persistence': np.zeros(len(ci)), 'momentum': last_return,
               'reversal': -last_return, 'fit_majority': np.full(len(ci), fit_majority)*magnitude,
               'book_imbalance': np.sign(b[:, 83])*magnitude,
               'trade_flow': np.sign(flow[:, 0]-flow[:, 1])*magnitude}
    # All rules use the same previous completed candle excursions, placed around
    # current known close; no target open/high/low is used to form predictions.
    up = (prev[:, 1]-np.maximum(prev[:, 0], prev[:, 3]))/anchor*10000
    down = (np.minimum(prev[:, 0], prev[:, 3])-prev[:, 2])/anchor*10000
    return {name: np.column_stack((np.zeros(len(ci)), np.maximum(0,s)+up,
                                    np.minimum(0,s)-down, s)) for name,s in signals.items()}


def review(features, pilot, audit, out):
    out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((features/'dataset-manifest.json').read_text())
    if manifest['state'] != 'features_complete_leakage_checks_passed':
        raise ValueError('Incomplete feature build')
    for kind in ('book', 'trades'):
        extraction=json.loads((features/f'{kind}-extraction.json').read_text())
        if extraction['sha256'] != file_hash(features/f'{kind}-seconds.bin'):
            raise ValueError('Extracted feature bytes changed')
    raw = np.load(features/'candle-raw.npy')
    valid = np.load(features/'candle-valid.npy')
    receipt = np.load(features/'candle-receipt-ns.npy')
    book = np.memmap(features/'book-seconds.bin', mode='r', dtype=feature_dtype('book'))
    trades = np.memmap(features/'trades-seconds.bin', mode='r', dtype=feature_dtype('trades'))
    source = json.loads((features/'source-candles.json').read_text())
    official = references(audit)
    frozen = json.loads((pilot/'pilot-manifest.json').read_text())
    reasons = {}
    for i in np.flatnonzero(~valid):
        ms = int(WARMUP+i*60000)
        reasons[int(i)] = candle_reason(official.get(ms), source.get(str(ms)))
    daily, traces, hashes, delays = {}, [], {}, {}
    ledger_path = out/'exclusion-ledger.jsonl'
    with ledger_path.open('w') as ledger:
        for part in PARTITIONS:
            origin_path = pilot/f'{part}-origins.json'
            if file_hash(origin_path) != frozen['partitions'][part]['origin_file_sha256']:
                raise ValueError('Frozen origins changed')
            origins = json.loads(origin_path.read_text())
            eligible_sets = {}
            for delay in DELAYS:
                indices, counts = eligible_indices(origins, delay, valid, receipt, book, trades)
                stored = np.load(features/f'{part}-delay{delay}-indices.npy')
                if not np.array_equal(indices, stored): raise ValueError('Eligibility replay differs')
                eligible_sets[delay] = set(indices[:,0].tolist())
                delays[f'{part}:{delay}'] = len(indices)
                hashes[f'{part}:{delay}'] = file_hash(features/f'{part}-delay{delay}-indices.npy')
            for origin in origins:
                day = utc(origin)[:10]
                d = daily.setdefault(day, {'partition': part, 'candidates': 0, 'retained': 0,
                    'invalid_context': 0, 'late_context': 0, 'other': 0})
                d['candidates'] += 1
                ci = (origin-WARMUP)//60000
                bad = context_failures(valid, ci)
                reason = 'retained' if origin in eligible_sets[0] else ('invalid_context' if len(bad)
                    else 'late_context' if receipt[ci-1440:ci].max() >= origin*10**6 else 'other')
                d[reason] += 1
                late = np.flatnonzero(receipt[ci-1440:ci] >= origin*10**6)+ci-1440
                row = {'partition': part, 'origin_utc': utc(origin), 'reason': reason,
                       'bad_context_minutes': len(bad),
                       'first_bad_context_utc': utc(WARMUP+int(bad[0])*60000) if len(bad) else None,
                       'bad_context_causes': dict(Counter(reasons[int(i)] for i in bad)),
                       'late_context_minutes': len(late),
                       'latest_context_receipt_minus_cutoff_ms': float((receipt[ci-1440:ci].max()-origin*10**6)/1e6)}
                ledger.write(json.dumps(row)+'\n')
                if sum(t['reason']==reason for t in traces)<3: traces.append(row)
    # Distribution checks use PRE-origin official candles only, never future test labels.
    conditions = {}
    for part in PARTITIONS:
        origins = json.loads((pilot/f'{part}-origins.json').read_text())
        kept = set(np.load(features/f'{part}-delay0-indices.npy')[:,0].tolist())
        for keep in (False, True):
            values=[]
            for origin in origins:
                if (origin in kept)!=keep: continue
                ci=(origin-WARMUP)//60000
                prior=raw[ci-60:ci]
                if len(prior)!=60 or (prior[:,:4]<=0).any(): continue
                returns=np.diff(np.log(prior[:,3]))*10000
                values.append([np.std(returns),np.sum(prior[:,4]),
                               abs(np.log(prior[-1,3]/prior[0,0]))*10000])
            a=np.asarray(values)
            conditions[f'{part}:{"retained" if keep else "excluded"}']={
                'n':len(a),'columns':['past_hour_return_std_bp','past_hour_base_volume','past_hour_abs_move_bp'],
                'median':np.median(a,axis=0).tolist() if len(a) else [],
                'p10':np.quantile(a,.1,axis=0).tolist() if len(a) else [],
                'p90':np.quantile(a,.9,axis=0).tolist() if len(a) else []}
    # Freeze rule definitions before observing development scores. Test/calibration
    # TARGET arrays are deliberately never opened by this program.
    fit = np.load(features/'fit-delay0-indices.npy')
    dev = np.load(features/'development-delay0-indices.npy')
    fit_moves = np.sign(raw[fit[:,1],3]/raw[fit[:,1]-1,3]-1)
    fit_majority=int(max((-1,0,1),key=lambda s:int(np.sum(fit_moves==s))))
    dev_targets=np.load(features/'development-delay0-targets.npy')
    if not np.array_equal(dev_targets,raw[dev[:,1]]):
        raise ValueError('Development targets disagree with frozen reference array')
    actual=(dev_targets[:,:4]/raw[dev[:,1]-1,3,None]-1)*10000
    predictions=baseline_predictions(raw,dev,book,trades,fit_majority)
    scores={name:metrics(pred,actual) for name,pred in predictions.items()}
    baseline={'evaluation_partition':'development only', 'fit_majority_direction':fit_majority,
              'rules':'fixed persistence/momentum/reversal/fit-majority/book top20 imbalance/trade-flow; previous absolute move sets magnitude; previous wicks set excursions',
              'scores':scores, 'test_targets_opened':False, 'calibration_targets_opened':False,
              'training_started':False, 'probability_or_trade_success_claim':False}
    save(out/'development-baselines.json',baseline)
    summary={'feature_fingerprint':manifest['fingerprint'],'daily_coverage':daily,
             'retained_days':dict(Counter(d['partition'] for d in daily.values() if d['retained'])),
             'unique_invalid_context_minutes':len(reasons),'invalid_minute_causes':dict(Counter(reasons.values())),
             'delay_counts':delays,'input_only_condition_comparison':conditions,'selected_traces':traces,
             'origin_array_sha256':hashes,'ledger_sha256':file_hash(ledger_path),
             'eligibility_replay_identical':True, 'test_performance_evaluated':False}
    save(out/'coverage-review.json',summary)
    print(json.dumps({k:summary[k] for k in ['retained_days','unique_invalid_context_minutes','invalid_minute_causes','eligibility_replay_identical']}))
    print(json.dumps(baseline))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('features','pilot','audit','output'):p.add_argument(name,type=Path)
    a=p.parse_args();review(a.features,a.pilot,a.audit,a.output)
if __name__=='__main__': main()
