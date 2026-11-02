"""Build receipt-causal October inputs, indexed windows and fit-only scalers. No training."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import subprocess
import time
import zipfile

import numpy as np
import pyarrow as pa

from .validate_archive import decoded, raw_path, hour_ns, file_hash, save, HARD_CLOCK
from .freeze_pilot import timestamp

START = timestamp('2026-10-01')
STOP = timestamp('2026-11-01')
WARMUP = timestamp('2026-09-30')
SECONDS = (STOP - START) // 1000
CANDLE_NAMES = ['log_close_open', 'log_high_open', 'log_low_open', 'log1p_base_volume',
                'log1p_quote_volume', 'log1p_execution_count', 'minute_sin', 'minute_cos']
BOOK_NAMES = [name for i in range(1, 21) for name in
              (f'bid_{i}_distance_bp', f'bid_{i}_log1p_qty', f'ask_{i}_distance_bp', f'ask_{i}_log1p_qty')]
BOOK_NAMES += ['spread_bp', 'imbalance_1', 'imbalance_5', 'imbalance_20',
               'log1p_bid_qty_20', 'log1p_ask_qty_20', 'microprice_distance_bp']
TRADE_NAMES = ['log1p_buy_qty', 'log1p_sell_qty', 'log1p_buy_notional', 'log1p_sell_notional',
               'log1p_count', 'log1p_buy_count', 'log1p_sell_count', 'vwap_vs_origin_close_bp']


def feature_dtype(kind):
    return np.dtype([('time_ns', '<i8'), ('receipt_ns', '<i8'), ('event_ns', '<i8'),
                     ('sequence', '<i8'), ('age_ns', '<i8'), ('valid', '<i8'),
                     ('x', '<f4', (87 if kind == 'book' else 8,))])


def compile_features(output):
    here = Path(__file__).resolve().parent
    lib = Path(pa.get_library_dirs()[0])
    binary = output / 'feature-scan'
    subprocess.run(['clang++', '-std=c++20', '-O3', str(here / 'feature_scan.cpp'),
                    '-I' + pa.get_include(), str(sorted(lib.glob('libarrow.[0-9]*.dylib'))[0]),
                    str(sorted(lib.glob('libparquet.[0-9]*.dylib'))[0]),
                    '-Wl,-rpath,' + str(lib), '-o', str(binary)], check=True,
                   capture_output=True, text=True)
    return binary


def extract(root, audit, output, binary, kind, records, fingerprint):
    destination = output / f'{kind}-seconds.bin'
    summary_path = output / f'{kind}-extraction.json'
    if summary_path.exists() and destination.exists():
        old = json.loads(summary_path.read_text())
        if old['fingerprint'] == fingerprint and old['sha256'] == file_hash(destination):
            return
    part = destination.with_suffix('.part')
    process = subprocess.Popen([str(binary.resolve()), kind], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    candles = {}
    availability = {}
    count = 0
    started = time.monotonic()
    try:
        with part.open('wb') as stream:
            for record in records:
                path = raw_path(root, record)
                if file_hash(path) != record['sha256']:
                    raise ValueError('Raw archive checksum changed')
                key = record['remote_file'].split('/')
                qpath = audit / 'hours' / key[1] / key[2] / (key[3] + '.quality.json')
                quality = json.loads(qpath.read_text())
                if not quality.get('ok') or quality['manifest_sha256'] != record['sha256']:
                    raise ValueError('Source hour has not passed structural audit')
                hour = hour_ns(record['remote_file'])
                temporary = output / f'{kind}-hour.bin'
                with decoded(path, output) as plain:
                    process.stdin.write(f'{hour}\t{plain.resolve()}\t{temporary.resolve()}\n')
                    process.stdin.flush()
                    line = process.stdout.readline()
                    if not line:
                        raise ValueError('Native feature process exited')
                    reconstructed = json.loads(line)
                if not reconstructed.get('ok') or reconstructed['counts']['rows'] != record['rows']:
                    raise ValueError('Feature row count disagrees with validated archive')
                features = np.fromfile(temporary, dtype=feature_dtype(kind))
                if len(features) != 3600 or not np.array_equal(features['time_ns'], hour + np.arange(3600) * 10**9):
                    raise ValueError('Feature second alignment error')
                if not np.isfinite(features['x']).all():
                    raise ValueError('Nonfinite features')
                # Never upgrade audit exclusions during feature extraction.
                clock_bad = any(quality['counts'].get(k, 0) for k in HARD_CLOCK + ('backward_receipt_rows',))
                if clock_bad:
                    features['valid'] = 0
                if START * 10**6 <= hour < STOP * 10**6:
                    features.tofile(stream)
                if kind == 'trades':
                    available = json.loads(Path(str(temporary) + '.availability.json').read_text())
                    for minute, receipt in available.items():
                        availability[minute] = max(availability.get(minute, 0), receipt)
                    for candle in reconstructed['candles']:
                        minute = str(candle['minute_ms'])
                        value = {**candle, 'bad': candle['bad'] or clock_bad}
                        if minute not in candles:
                            candles[minute] = value
                        else:
                            old = candles[minute]
                            for name in ('volume', 'quote_volume'):
                                old[name] = str(Decimal(old[name]) + Decimal(value[name]))
                            old['count'] += value['count']
                            old['high'] = str(max(Decimal(old['high']), Decimal(value['high'])))
                            old['low'] = str(min(Decimal(old['low']), Decimal(value['low'])))
                            if value['first_id'] < old['first_id']:
                                old['open'], old['first_id'] = value['open'], value['first_id']
                            if value['last_id'] > old['last_id']:
                                old['close'], old['last_id'] = value['close'], value['last_id']
                            old['bad'] |= value['bad']
                temporary.unlink()
                if kind == 'trades':
                    Path(str(temporary) + '.availability.json').unlink()
                count += 1
                save(output / f'{kind}-progress.json', {'state': 'extracting', 'hours_done': count,
                     'hours_total': len(records), 'last_file': record['remote_file'],
                     'elapsed_seconds': round(time.monotonic() - started, 1)})
        if part.stat().st_size != SECONDS * feature_dtype(kind).itemsize:
            raise ValueError('Incomplete feature month')
        part.replace(destination)
        if kind == 'trades':
            save(output / 'source-candles.json', candles)
            save(output / 'candle-availability.json', availability)
        save(summary_path, {'fingerprint': fingerprint, 'sha256': file_hash(destination),
                            'hours': count, 'seconds': SECONDS, 'complete': True})
    finally:
        process.stdin.close()
        process.wait()


def references(audit):
    official = {}
    def add(row):
        if not str(row[0]).isdigit():
            return
        minute = int(row[0])
        if WARMUP <= minute < STOP:
            value = {k: Decimal(row[i]) for k, i in [('open', 1), ('high', 2), ('low', 3),
                     ('close', 4), ('volume', 5), ('quote_volume', 7)]}
            value['count'] = int(row[8])
            if minute in official and official[minute] != value:
                raise ValueError('Conflicting independent candle reference')
            official[minute] = value
    for name in ('2026-09', '2026-10'):
        path = audit / 'reference' / f'BTCUSDT-1m-{name}.zip'
        expected = next(r['sha256'] for r in json.loads((audit / 'reference/status.json').read_text()) if r['month'] == name)
        if file_hash(path) != expected:
            raise ValueError('Official reference changed')
        with zipfile.ZipFile(path) as archive:
            with archive.open(next(n for n in archive.namelist() if n.endswith('.csv'))) as raw:
                for row in csv.reader(io.TextIOWrapper(raw)):
                    add(row)
    for path in (audit / 'reference').glob('REST-BTCUSDT-1m-*.json'):
        if path.name.endswith('.metadata.json'):
            continue
        meta = json.loads(path.with_suffix('.metadata.json').read_text())
        if file_hash(path) != meta['sha256']:
            raise ValueError('Supplement changed')
        for row in json.loads(path.read_text()):
            add(row)
    return official


def make_candles(official, source, available):
    times = np.arange(WARMUP, STOP, 60000, dtype=np.int64)
    x = np.zeros((len(times), 8), np.float32)
    raw = np.zeros((len(times), 7), np.float64)
    valid = np.zeros(len(times), bool)
    receipt = np.zeros(len(times), np.int64)
    for i, minute in enumerate(times):
        truth = official.get(int(minute))
        seen = source.get(str(minute))
        if truth is None:
            continue
        raw[i] = [float(truth[k]) for k in ('open', 'high', 'low', 'close', 'volume', 'quote_volume', 'count')]
        o, h, l, c, v, q, n = raw[i]
        angle = (minute // 60000 % 1440) / 1440 * 2 * np.pi
        x[i] = [np.log(c/o), np.log(h/o), np.log(l/o), np.log1p(v), np.log1p(q), np.log1p(n), np.sin(angle), np.cos(angle)]
        if seen is None or seen['bad']:
            continue
        if any(Decimal(str(seen[k])) != truth[k] for k in ('open', 'high', 'low', 'close', 'volume', 'count')):
            continue
        if abs(Decimal(seen['quote_volume']) - truth['quote_volume']) > Decimal('0.01'):
            continue
        receipt[i] = available.get(str(minute), 0)
        valid[i] = receipt[i] > 0
    return times, x, raw, valid, receipt


def eligible_indices(origins, delay_ms, candle_valid, candle_receipt, book, trades):
    """Require complete past context and complete receipt buckets strictly before cutoff."""
    result = []
    rejected = Counter()
    invalid_prefix = np.r_[0, np.cumsum(~candle_valid)]
    for origin in origins:
        ci = (origin - WARMUP) // 60000
        cutoff = origin * 10**6 - delay_ms * 10**6
        # Last fully observed receipt second. Positive delays omit unfinished seconds.
        end_second = (cutoff // 10**9) - START // 1000
        begin = end_second - 60
        if ci < 1440 or begin < 0 or end_second > len(book):
            rejected['outside_history'] += 1
            continue
        if invalid_prefix[ci] != invalid_prefix[ci-1440]:
            rejected['incomplete_or_mismatched_candle_context'] += 1
            continue
        if np.max(candle_receipt[ci-1440:ci]) >= cutoff:
            rejected['candle_not_fully_received_by_cutoff'] += 1
            continue
        rows_b, rows_t = book[begin:end_second], trades[begin:end_second]
        if not rows_b['valid'].all() or not rows_t['valid'].all():
            rejected['invalid_book_or_trade_seconds'] += 1
            continue
        if any(np.max(rows[name]) >= cutoff for rows in (rows_b, rows_t) for name in ('receipt_ns', 'event_ns')):
            rejected['late_or_future_book_trade_input'] += 1
            continue
        if not np.isfinite(rows_b['x']).all() or not np.isfinite(rows_t['x']).all():
            rejected['nonfinite_inputs'] += 1
            continue
        result.append((origin, ci, begin, end_second))
    return np.asarray(result, dtype=np.int64).reshape(-1, 4), dict(rejected)


def fit_scaler(chunks, width):
    count = 0
    total = np.zeros(width, np.float64)
    square = np.zeros(width, np.float64)
    for values in chunks:
        values = np.asarray(values, np.float64).reshape(-1, width)
        if not np.isfinite(values).all():
            raise ValueError('Scaler encountered invalid feature')
        count += len(values)
        total += values.sum(axis=0)
        square += np.square(values).sum(axis=0)
    if not count:
        raise ValueError('No eligible fitting samples')
    mean = total / count
    std = np.sqrt(np.maximum(0, square / count - mean**2))
    std[std < 1e-8] = 1
    return {'count': count, 'mean': mean.tolist(), 'std': std.tolist()}


def trade_values(rows, anchor):
    x = rows['x'].astype(np.float64).copy()
    x[:, :7] = np.log1p(x[:, :7])
    x[:, 7] = np.where(rows['x'][:, 4] > 0, (rows['x'][:, 7] / anchor - 1) * 10000, 0)
    return x


def assemble(audit, pilot, output, fingerprint):
    official = references(audit)
    source = json.loads((output / 'source-candles.json').read_text())
    available = json.loads((output / 'candle-availability.json').read_text())
    times, candles, raw, valid, receipt = make_candles(official, source, available)
    np.save(output / 'candle-features.npy', candles)
    np.save(output / 'candle-raw.npy', raw)
    np.save(output / 'candle-receipt-ns.npy', receipt)
    np.save(output / 'candle-valid.npy', valid)
    book = np.memmap(output / 'book-seconds.bin', mode='r', dtype=feature_dtype('book'))
    trades = np.memmap(output / 'trades-seconds.bin', mode='r', dtype=feature_dtype('trades'))
    manifest = json.loads((pilot / 'pilot-manifest.json').read_text())
    counts = {}
    fit = None
    split_targets = set()
    for name, partition in manifest['partitions'].items():
        origin_path = pilot / f'{name}-origins.json'
        if file_hash(origin_path) != partition['origin_file_sha256']:
            raise ValueError('Frozen origin list changed')
        origins = json.loads(origin_path.read_text())
        if split_targets.intersection(origins):
            raise ValueError('Targets overlap across partitions')
        split_targets.update(origins)
        counts[name] = {}
        for delay in (0, 250, 1000):
            indices, exclusions = eligible_indices(origins, delay, valid, receipt, book, trades)
            stop = timestamp(partition['end_exclusive_utc'])
            if len(indices) and (indices[:, 0] + 60000 > stop).any():
                raise ValueError('Target crosses partition boundary')
            np.save(output / f'{name}-delay{delay}-indices.npy', indices)
            targets = raw[indices[:, 1]].copy()
            if len(targets) and (not np.isfinite(targets).all() or (targets[:, :4] <= 0).any()
                    or (targets[:, 1] < np.maximum(targets[:, 0], targets[:, 3])).any()
                    or (targets[:, 2] > np.minimum(targets[:, 0], targets[:, 3])).any()):
                raise ValueError('Invalid next-minute target')
            np.save(output / f'{name}-delay{delay}-targets.npy', targets)
            counts[name][str(delay)] = {'eligible': len(indices), 'excluded': exclusions}
            if name == 'fit' and delay == 0:
                fit = indices
    # Only windows actually belonging to fit origins contribute to preprocessing.
    def candle_chunks():
        for row in fit:
            yield candles[row[1]-1440:row[1]]
    def book_chunks():
        for row in fit:
            yield book[row[2]:row[3]]['x']
    def trade_chunks():
        for row in fit:
            yield trade_values(trades[row[2]:row[3]], raw[row[1]-1, 3])
    if len(fit):
        scalers = {'candles': fit_scaler(candle_chunks(), 8), 'book': fit_scaler(book_chunks(), 87),
                   'trades': fit_scaler(trade_chunks(), 8), 'fit_partition_only': True,
                   'weighting': 'Every fitting example input window; no development/calibration/test windows'}
        save(output / 'scalers.json', scalers)
    result = {'state': ('features_complete_leakage_checks_passed' if len(fit)
                        else 'features_complete_no_eligible_fit_origins'), 'training_started': False,
              'live_readiness': False, 'fingerprint': fingerprint,
              'audit_fingerprint': manifest['quality_audit_fingerprint'],
              'context_minutes': 1440, 'second_history': 60, 'partition_counts_by_delay_ms': counts,
              'feature_names': {'candles': CANDLE_NAMES, 'book': BOOK_NAMES, 'trades': TRADE_NAMES},
              'target_columns': ['open', 'high', 'low', 'close', 'base_volume', 'quote_volume', 'execution_count'],
              'cutoff_policy': 'Strictly received/generated before origin minus delay; complete second buckets only',
              'candle_policy': 'Reconstructed executions must match independent OHLCV/count and every used row must have arrived before cutoff',
              'limitations': ['Archive receipt/checkpoint provenance remains uncertain; not independently certified book authenticity.',
                              'Delay scenarios change eligible samples; performance comparisons require common origins.',
                              'Exclusions can bias retained market conditions; report per-day coverage before training.',
                              'No model performance or probability calibration is established by this build.']}
    save(output / 'dataset-manifest.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('audit', type=Path)
    parser.add_argument('pilot', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    import fcntl
    lock = (args.output / '.build.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    here = Path(__file__).resolve().parent
    fingerprint = hashlib.sha256(''.join(file_hash(p) for p in [here / 'feature_scan.cpp',
            here / 'archive_scan.cpp', Path(__file__), args.pilot / 'pilot-manifest.json',
            args.archive / 'manifest.json']).encode()).hexdigest()
    binary = compile_features(args.output)
    records = json.loads((args.archive / 'manifest.json').read_text())
    jobs = {}
    for kind in ('book', 'trades'):
        jobs[kind] = sorted([r for r in records if
            ('_orderbook.' if kind == 'book' else '_trades.') in r['remote_file']
            and ('2026-10-01' if kind == 'book' else '2026-09-30') <= r['remote_file'].split('/')[1] < '2026-11-01'],
            key=lambda r: r['remote_file'])
    save(args.output / 'build-state.json', {'state': 'extracting', 'fingerprint': fingerprint,
         'started_utc': datetime.now(timezone.utc).isoformat(), 'training_started': False})
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(extract, args.archive, args.audit, args.output, binary, kind, records, fingerprint)
                       for kind, records in jobs.items()]
            for future in futures:
                future.result()
        result = assemble(args.audit, args.pilot, args.output, fingerprint)
        save(args.output / 'build-state.json', {'state': result['state'], 'training_started': False})
        print(json.dumps(result, indent=2), flush=True)
    except Exception as exc:
        save(args.output / 'build-state.json', {'state': 'failed', 'error_type': type(exc).__name__,
                                             'training_started': False})
        raise


if __name__ == '__main__':
    main()
