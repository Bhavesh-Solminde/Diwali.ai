"""Issue and score the declared three-model comparison on native receipts."""
import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
from functools import partial
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import time

import numpy as np

from .comparison15 import ROOT, source_hashes
from .comparison15_capture import DEPTH, TRADES, GIB, trade_session
from .comparison15_live_inputs import MINUTE, SCALE, SECOND, NativeInputs, units
from .comparison15_predict import Predictor
from .comparison15_train import score_direction
from .event_data import EDGES, labels
from .event_train import metrics
from .prospective import exclusive_json
from ..market_data.collect import Store, depth_session, rest, retry
from ..market_data.validate_archive import file_hash, save

DAY = 1440*MINUTE
CADENCE = 15*MINUTE
TARGETS = 15
GRACE = 60*SECOND
DAYS = 10
MODELS = ('control', 'volatility', 'attention')


def source_identity():
    names = ('comparison15_capture.py', 'comparison15_live_inputs.py', 'comparison15_predict.py',
             'comparison15_forward.py', 'comparison15_final_attention.py', 'prospective.py')
    market = ROOT/'research/market_data'
    files = [Path(__file__).with_name(n) for n in names]
    files += [market/n for n in ('collect.py', 'book.py', 'candle_tape.py', 'event_windows.py',
                                 'event_features_fast.py', 'event_features.py', 'validate_archive.py')]
    return {**source_hashes(), **{str(p.relative_to(ROOT)): file_hash(p) for p in files}}


def utc(ns):
    return datetime.fromtimestamp(ns/SECOND, timezone.utc).isoformat()


def check_predictions(p):
    expected = {name+suffix for name in MODELS for suffix in ('', '_raw')} | {'half'}
    if set(p) != expected or not np.array_equal(p['half'], np.full(15, .5)):
        raise ValueError('Unexpected forward forecast models')
    for key in expected-{'half'}:
        x = np.asarray(p[key])
        if x.shape != (15, 26) or not np.isfinite(x).all() or (x < 0).any():
            raise ValueError('Invalid forecast distribution')
        np.testing.assert_allclose(x.sum(-1), 1, atol=1e-12, rtol=0)


def input_hash(raw, elapsed):
    digest = hashlib.sha256()
    for arr in (*raw, elapsed):
        digest.update(repr((arr.shape, arr.dtype.str)).encode())
        digest.update(arr.tobytes())
    return digest.hexdigest()


class Forward(Store):
    def __init__(self, root, predictor):
        super().__init__(root)
        self.predictor = predictor
        self.sources = source_identity()
        self.inputs = NativeInputs()
        self.warmup_first = (self.started//MINUTE+1442)*MINUTE+15*SECOND
        self.warmup = []
        self.release = None
        self.release_hash = None
        self.slot = None
        self.pending = {}
        self.fatal = None
        self.rejections = Counter()

    def save(self, kind, payload, **extra):
        row = super().save(kind, payload, **extra)
        if self.fatal is None:
            try:
                if row.get('clock_step_ns'):
                    raise ValueError('Recorder clock discontinuity')
                self.tick(row['receipt_utc_ns'])
                self.inputs.ingest(row)
            except Exception as exc:
                self.fatal = exc
        return row

    def check_input(self, at, cutoff):
        if not cutoff <= at <= cutoff+2*SECOND:
            raise ValueError('Missed cutoff processing deadline')
        raw, elapsed, context = self.inputs.freeze(cutoff)
        prediction = self.predictor.predict(raw, elapsed)
        check_predictions(prediction)
        return raw, elapsed, context, prediction

    def freeze_release(self, at):
        if source_identity() != self.sources:
            raise ValueError('Changed source during warmup')
        if any(file_hash(ROOT/p) != sha for p, sha in self.predictor.artifacts.items()):
            raise ValueError('Changed model or comparator during warmup')
        start = (at//DAY+1)*DAY
        stop = start+DAYS*DAY
        self.release = {
            'state': 'frozen_before_first_forecast', 'models': list(MODELS),
            'primary': 'control minus volatility mean15 price-bin log loss',
            'challenger': 'C_attention_lower_lr, fixed seed 17, compared to both primary models',
            'direction_reference': 'close > frozen price reference; equality is down or unchanged',
            'start_utc_ns': start, 'stop_utc_ns': stop, 'start_utc': utc(start), 'stop_exclusive_utc': utc(stop),
            'cadence_ns': CADENCE, 'cutoff_offset_ns': 15*SECOND, 'scheduled_slots': 960,
            'minimum_scored_origins': 300, 'minimum_days': 7, 'target_close_count': TARGETS,
            'target_grace_seconds': GRACE//SECOND, 'price_edges_bp': EDGES.tolist(),
            'minimum_passing_warmup_checks': 2,
            'target_gate': '15 native closes, counts and volumes match exchange closed candles',
            'input_gate': 'Full native warmup, latest candle valid, >=99% valid 1440 candles; causal 60-second event window',
            'warmup_checks': self.warmup, 'artifacts': self.predictor.artifacts, 'source_hashes': self.sources,
            'feeds': [DEPTH, TRADES], 'frozen_utc_ns': time.time_ns(),
            'frozen_monotonic_ns': time.monotonic_ns()}
        self.release_hash = exclusive_json(self.root/'release.json', self.release)
        self.slot = start+15*SECOND
        print('Frozen comparison starts', utc(start), 'ends', utc(stop), flush=True)

    def tick(self, at):
        if self.release is None:
            cutoff = self.warmup_first+len(self.warmup)*MINUTE
            if at >= cutoff:
                try:
                    raw, _, _, _ = self.check_input(at, cutoff)
                except ValueError as exc:
                    self.warmup.append({'cutoff_ns': cutoff, 'passed': False, 'reason': str(exc)})
                else:
                    self.warmup.append({'cutoff_ns': cutoff, 'passed': True, 'valid_candles': int(raw[3].sum())})
                if len(self.warmup) == 3:
                    exclusive_json(self.root/'warmup-checks.json', self.warmup)
                    if sum(w['passed'] for w in self.warmup) < 2:
                        raise ValueError('Fewer than two prespecified warmup checks passed')
                    self.freeze_release(at)
            return
        while self.slot < self.release['stop_utc_ns'] and at >= self.slot:
            cutoff = self.slot
            self.slot += CADENCE
            try:
                self.issue(at, cutoff)
            except ValueError as exc:
                reason = str(exc)
                self.rejections[reason] += 1
                exclusive_json(self.root/'skipped'/f'{cutoff}.json', {'cutoff_ns': cutoff, 'reason': reason})

    def issue(self, at, cutoff):
        raw, elapsed, context, prediction = self.check_input(at, cutoff)
        start = context['target_start_ns']
        self.file.flush()
        os.fsync(self.file.fileno())
        ready, mono = time.time_ns(), time.monotonic_ns()
        if not cutoff <= ready < start:
            raise ValueError('Forecast missed target start')
        path = self.root/'forecasts'/f'{cutoff}.json'
        sha = exclusive_json(path, {
            'cutoff_ns': cutoff, 'target_start_ns': start, 'target_end_ns': start+TARGETS*MINUTE,
            'reference': context['reference'], 'input_sha256': input_hash(raw, elapsed),
            'last_input_receipt_utc_ns': self.inputs.last_receipt,
            'last_input_receipt_monotonic_ns': self.inputs.last_clock,
            'ready_utc_ns': ready, 'ready_monotonic_ns': mono,
            'release_sha256': self.release_hash,
            'probabilities': {k: v.tolist() for k,v in prediction.items()}})
        committed, committed_mono = time.time_ns(), time.monotonic_ns()
        if not ready <= committed < start or committed_mono < mono:
            raise ValueError('Forecast file did not finish writing before target start')
        proof = {'forecast_sha256': sha, 'committed_utc_ns': committed,
                 'committed_monotonic_ns': committed_mono}
        exclusive_json(self.root/'committed'/path.name, proof)
        self.pending[cutoff] = start

    async def mature(self, cutoff, start):
        end = start+TARGETS*MINUTE
        path = self.root/'outcomes'/f'{cutoff}.json'
        try:
            server = await rest(self, '/fapi/v1/time')
            if server['serverTime']*10**6 < end+GRACE:
                raise ValueError('Exchange maturity clock below frozen grace')
            bars = await rest(self, f'/fapi/v1/klines?symbol=BTCUSDT&interval=1m&startTime={start//10**6}'
                              f'&endTime={end//10**6-1}&limit=15')
            self.inputs.advance(time.time_ns())
            prices = reconcile(bars, self.inputs.tape.minutes, start)
        except (ValueError, OSError, KeyError) as exc:
            exclusive_json(path, {'cutoff_ns': cutoff, 'state': 'rejected', 'reason': str(exc)})
        else:
            exclusive_json(path, {'cutoff_ns': cutoff, 'state': 'matured', 'closes': prices,
                                  'recorded_utc_ns': time.time_ns()})


def reconcile(bars, minutes, start):
    if len(bars) != TARGETS:
        raise ValueError('Missing exchange target candles')
    closes = []
    for i, bar in enumerate(bars):
        at = start+i*MINUTE
        native = minutes.get(at)
        if (bar[0]*10**6 != at or (bar[6]+1)*10**6 != at+MINUTE
                or not native or native['bad'] or not native['n']):
            raise ValueError('Missing or invalid native target candle')
        if (units(bar[4]) != native['c'] or units(bar[5]) != native['v'] or bar[8] != native['n']):
            raise ValueError('Native close, volume or trade count disagrees with exchange')
        closes.append(native['c']/SCALE)
    return closes


def compress_hour(path):
    target = path.with_suffix('.jsonl.gz')
    tmp = target.with_suffix('.tmp')
    if target.exists():
        raise ValueError('Raw hour already compressed')
    original = file_hash(path)
    with path.open('rb') as source, gzip.open(tmp, 'wb', compresslevel=3) as out:
        shutil.copyfileobj(source, out)
    with gzip.open(tmp, 'rb') as source:
        if hashlib.file_digest(source, 'sha256').hexdigest() != original:
            raise ValueError('Raw archive compression verification failed')
    with tmp.open('rb') as compressed:
        os.fsync(compressed.fileno())
    tmp.replace(target)
    path.unlink()
    return {'uncompressed_sha256': original, 'gzip_sha256': file_hash(target)}


def finish_score(root, release):
    release_sha = file_hash(root/'release.json')
    paths, days, outcomes = [], [], []
    for stamp in range(release['start_utc_ns']+15*SECOND, release['stop_utc_ns'], CADENCE):
        name = f'{stamp}.json'
        target = root/'outcomes'/name
        if not target.exists():
            continue
        outcome = json.loads(target.read_text())
        if outcome['state'] != 'matured':
            continue
        path = root/'forecasts'/name
        forecast = json.loads(path.read_text())
        proof = json.loads((root/'committed'/name).read_text())
        if (forecast['release_sha256'] != release_sha or proof['forecast_sha256'] != file_hash(path)
                or forecast['cutoff_ns'] != stamp or outcome['cutoff_ns'] != stamp
                or forecast['last_input_receipt_utc_ns'] >= stamp
                or not stamp <= forecast['ready_utc_ns'] <= proof['committed_utc_ns'] < forecast['target_start_ns']
                or not forecast['last_input_receipt_monotonic_ns'] <= forecast['ready_monotonic_ns']
                <= proof['committed_monotonic_ns']
                or forecast['target_start_ns'] != (stamp//MINUTE+1)*MINUTE
                or forecast['target_end_ns'] != forecast['target_start_ns']+TARGETS*MINUTE
                or outcome['recorded_utc_ns'] < forecast['target_end_ns']+GRACE):
            raise ValueError('Invalid paired forecast/outcome evidence')
        p = {k: np.array(v) for k,v in forecast['probabilities'].items()}
        check_predictions(p)
        paths.append(p)
        days.append(stamp//DAY)
        outcomes.append((np.array(outcome['closes'])/forecast['reference']-1)*10000)
    coverage = {'scheduled_slots': release['scheduled_slots'],
                'issued': len(list((root/'committed').glob('*.json'))),
                'input_skips': len(list((root/'skipped').glob('*.json'))),
                'target_rejects': len(list((root/'outcomes').glob('*.json')))-len(paths),
                'matched_matured': len(paths), 'distinct_days': len(set(days))}
    if coverage['issued']+coverage['input_skips'] != release['scheduled_slots']:
        raise ValueError('Missing slot decisions')
    if coverage['issued'] != coverage['matched_matured']+coverage['target_rejects']:
        raise ValueError('Missing outcome decisions')
    report = {'release_sha256': release_sha, 'coverage': coverage, 'state': 'insufficient_coverage'}
    if len(paths) < release['minimum_scored_origins'] or len(set(days)) < release['minimum_days']:
        return report
    y = labels(outcomes)
    day_array = np.asarray(days)
    result = {}
    losses = {}
    for name in MODELS:
        result[name] = {}
        for mode, key in [('raw', name+'_raw'), ('calibrated', name)]:
            p = np.stack([x[key] for x in paths])
            result[name][mode] = {'range': metrics(y, p),
                                  'direction': score_direction(y >= 13, p[:,:,13:].sum(-1))}
            if mode == 'calibrated':
                losses[name] = -np.log(np.maximum(np.take_along_axis(p,y[:,:,None],axis=2)[:,:,0],1e-15)).mean(1)
    pairs = {}
    for left,right in [('control','volatility'),('attention','control'),('attention','volatility')]:
        delta = losses[left]-losses[right]
        pairs[left+'_minus_'+right] = {'mean':float(delta.mean()),
            'daily':{utc(int(day)*DAY)[:10]:float(delta[day_array==day].mean())
                     for day in sorted(set(days)) if (day_array==day).sum()>=10}}
    report.update(state='complete', models=result, paired_range_losses=pairs,
                  constant_half=score_direction(y>=13,np.full(y.shape,.5)))
    return report


async def record(root):
    predictor = Predictor(attention=ROOT/'data/models/diwali1.5-final-attention-v1', include_binary=False)
    store = Forward(root, predictor)
    tasks = []
    archives = {}
    failure = None
    try:
        market = await rest(store, '/fapi/v1/exchangeInfo')
        instrument = next(x for x in market['symbols'] if x['symbol']=='BTCUSDT')
        if (instrument['contractType'], instrument['status']) != ('PERPETUAL','TRADING'):
            raise ValueError('Wrong instrument or unavailable market')
        tasks = [asyncio.create_task(retry(store, 'depth', partial(depth_session, endpoint=DEPTH))),
                 asyncio.create_task(retry(store, 'individual_trade', trade_session))]
        health_at = 0
        while True:
            if store.fatal:
                raise store.fatal
            for task in tasks:
                if task.done():
                    task.result()
                    raise RuntimeError('Receiver stopped unexpectedly')
            at = time.time_ns()
            store.tick(at)
            if at >= health_at:
                if shutil.disk_usage(root).free < 20*GIB:
                    raise RuntimeError('Recorder disk safety limit reached')
                await rest(store, '/fapi/v1/time')
                store.status('issuing_or_waiting' if store.release else 'warming_up')
                for path in sorted(root.glob('events-*.jsonl')):
                    if path.name != f'events-{store.hour}.jsonl':
                        archives[path.name] = await asyncio.to_thread(compress_hour, path)
                        save(root/'archive-ledger.json', archives)
                health_at = at+MINUTE
            for cutoff,start in list(store.pending.items()):
                if at >= start+TARGETS*MINUTE+GRACE+5*SECOND:
                    await store.mature(cutoff,start)
                    del store.pending[cutoff]
            if store.release and at >= store.release['stop_utc_ns']+16*MINUTE and not store.pending:
                break
            await asyncio.sleep(.1)
    except Exception as exc:
        failure = str(exc)
        raise
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        store.finish()
        path = root/'manifest.json'
        manifest = json.loads(path.read_text())
        manifest.update(compressed_hours=archives, state='failed' if failure else 'stopped', failure=failure,
                        limitations=['Finite public order book. Native receive clocks audited at each cutoff.'])
        save(path,manifest)
    exclusive_json(root/'score-report.json',finish_score(root,store.release))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    asyncio.run(record(parser.parse_args().output))
