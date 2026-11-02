"""Full resumable local archive audit. No training and no modification of raw files."""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import zipfile

import pyarrow as pa
import pyarrow.parquet as pq
import requests

VERSION = 'full-archive-audit-v1'
HERE = Path(__file__).resolve().parent
HARD_CLOCK = ('receipt_outside_file_hour_rows', 'invalid_exchange_clock_rows',
              'exchange_ahead_over_1s_rows', 'invalid_transaction_clock_rows')


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(path.suffix + '.tmp')
    part.write_text(json.dumps(value, indent=2) + '\n')
    part.replace(path)


def file_hash(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def compile_scanner(output):
    library = Path(pa.get_library_dirs()[0])
    binary = output / 'archive-scan'
    source = HERE / 'archive_scan.cpp'
    arrow = sorted(library.glob('libarrow.[0-9]*.dylib'))[0]
    parquet = sorted(library.glob('libparquet.[0-9]*.dylib'))[0]
    subprocess.run(['clang++', '-std=c++20', '-O3', str(source), '-I' + pa.get_include(),
                    str(arrow), str(parquet), '-Wl,-rpath,' + str(library), '-o', str(binary)],
                   check=True, capture_output=True, text=True)
    return binary


@contextmanager
def decoded(path, scratch):
    with path.open('rb') as source:
        magic = source.read(4)
    if magic == b'PAR1':
        yield path
    elif magic == bytes.fromhex('28b52ffd'):
        with tempfile.NamedTemporaryFile(dir=scratch, suffix='.parquet') as target:
            with pa.input_stream(str(path), compression='zstd') as stream:
                size = 0
                while chunk := stream.read(1024 * 1024):
                    size += len(chunk)
                    if size > 4 * 1024**3 or shutil.disk_usage(scratch).free < 10 * 1024**3:
                        raise ValueError('Decode size or disk guard')
                    target.write(chunk)
            target.flush()
            yield Path(target.name)
    else:
        raise ValueError('Unsupported file encoding')


def raw_path(root, record):
    _, day, hour, name = record['remote_file'].split('/')
    path = root / day[:7] / day / hour / name
    return path if path.exists() else path.with_suffix('.parquet.zst')


def hour_ns(remote):
    _, day, hour, _ = remote.split('/')
    return int(datetime.fromisoformat(day).replace(hour=int(hour), tzinfo=timezone.utc).timestamp()) * 10**9


def inventory(root, records):
    expected = {f'binance_futures/{(datetime(2025, 11, 1) + timedelta(days=d)):%Y-%m-%d}/{h:02d}/BTCUSDT_{kind}.parquet'
                for d in range(365) for h in range(24) for kind in ('orderbook', 'trades')}
    seen = set()
    duplicates, unexpected, missing_local, size_mismatch = [], [], [], []
    for record in records:
        remote = record['remote_file']
        if remote in seen:
            duplicates.append(remote)
        seen.add(remote)
        if remote not in expected:
            unexpected.append(remote)
        path = raw_path(root, record)
        if not path.exists():
            missing_local.append(remote)
        elif path.stat().st_size != record['bytes']:
            size_mismatch.append(remote)
    return dict(expected_files=len(expected), manifest_files=len(records), unique_files=len(seen),
                missing_remote_files=sorted(expected - seen), duplicate_remote_files=duplicates,
                unexpected_files=unexpected, missing_local_files=missing_local,
                size_mismatches=size_mismatch, raw_bytes=sum(r['bytes'] for r in records),
                book_rows_expected=sum(r['rows'] for r in records if '_orderbook.' in r['remote_file']),
                trade_rows_expected=sum(r['rows'] for r in records if '_trades.' in r['remote_file']))


def reference_candles(output):
    """Independent Binance monthly closed klines, SHA-256 verified against its checksum."""
    refs = output / 'reference'
    refs.mkdir(exist_ok=True)
    status = []
    for month in [f'2025-{m:02d}' for m in (11, 12)] + [f'2026-{m:02d}' for m in range(1, 11)]:
        name = f'BTCUSDT-1m-{month}.zip'
        url = 'https://data.binance.vision/data/futures/um/monthly/klines/BTCUSDT/1m/' + name
        path = refs / name
        try:
            checksum = requests.get(url + '.CHECKSUM', timeout=30)
            if checksum.status_code != 200:
                status.append({'month': month, 'available': False, 'http_status': checksum.status_code})
                continue
            expected = checksum.text.split()[0]
            if len(expected) != 64:
                raise ValueError('Invalid checksum response')
            if not path.exists() or file_hash(path) != expected:
                with requests.get(url, timeout=(20, 90), stream=True) as result:
                    result.raise_for_status()
                    part = path.with_suffix('.part')
                    with part.open('wb') as target:
                        for chunk in result.iter_content(1024 * 1024):
                            target.write(chunk)
                    if file_hash(part) != expected:
                        raise ValueError('Reference checksum mismatch')
                    part.replace(path)
            status.append({'month': month, 'available': True, 'sha256': expected})
        except Exception as exc:
            status.append({'month': month, 'available': False, 'error_type': type(exc).__name__})
        save(refs / 'status.json', status)
    return status


def run(root, output, workers, only_month=None, limit_hours=None):
    output.mkdir(parents=True, exist_ok=True)
    # A validator process is exclusive; raw data and downloader locks are separate.
    import fcntl
    lock = (output / '.validation.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    records = json.loads((root / 'manifest.json').read_text())
    inv = inventory(root, records)
    save(output / 'inventory.json', inv)
    if inv['duplicate_remote_files'] or inv['unexpected_files']:
        raise ValueError('Invalid manifest inventory')
    binary = compile_scanner(output)
    fingerprint = hashlib.sha256((file_hash(root / 'manifest.json') + file_hash(HERE / 'archive_scan.cpp')
                                 + file_hash(Path(__file__))).encode()).hexdigest()
    jobs = defaultdict(list)
    for record in records:
        month = record['remote_file'].split('/')[1][:7]
        if only_month and month != only_month:
            continue
        kind = 'book' if '_orderbook.' in record['remote_file'] else 'trades'
        jobs[(month, kind)].append(record)
    for key in jobs:
        jobs[key].sort(key=lambda r: r['remote_file'])
        if limit_hours:
            jobs[key] = jobs[key][:limit_hours]
    total = sum(len(v) for v in jobs.values())
    progress_lock = threading.Lock()
    progress = {'state': 'validating', 'files_done': 0, 'files_total': total, 'rows_scanned': 0,
                'raw_bytes_checked': 0, 'errors': 0, 'started_utc': datetime.now(timezone.utc).isoformat(),
                'training_ready': False, 'fingerprint': fingerprint, 'shards_done': 0}
    save(output / 'progress.json', progress)

    def shard(key, files):
        month, kind = key
        done = output / 'shards' / f'{month}-{kind}.json'
        if done.exists():
            prior = json.loads(done.read_text())
            if prior.get('fingerprint') == fingerprint and prior.get('files_expected') == len(files):
                with progress_lock:
                    progress['files_done'] += prior['files_done']
                    progress['rows_scanned'] += prior['rows_scanned']
                    progress['raw_bytes_checked'] += prior['raw_bytes_checked']
                    progress['errors'] += prior['errors']
                    progress['shards_done'] += 1
                    save(output / 'progress.json', progress)
                return
        process = subprocess.Popen([str(binary.resolve()), kind], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
        summary = {'month': month, 'kind': kind, 'fingerprint': fingerprint,
                   'files_expected': len(files), 'files_done': 0, 'rows_scanned': 0,
                   'raw_bytes_checked': 0, 'errors': 0}
        try:
            for record in files:
                start = time.monotonic()
                path = raw_path(root, record)
                result = {'remote_file': record['remote_file'], 'hour_ns': hour_ns(record['remote_file']),
                          'manifest_sha256': record['sha256'], 'training_ready': False}
                try:
                    if path.stat().st_size != record['bytes'] or file_hash(path) != record['sha256']:
                        raise ValueError('Raw size/hash mismatch')
                    result['raw_integrity_pass'] = True
                    with decoded(path, output) as plain:
                        process.stdin.write(f"{result['hour_ns']}\t{plain.resolve()}\n")
                        process.stdin.flush()
                        line = process.stdout.readline()
                        if not line:
                            raise RuntimeError('Scanner stopped unexpectedly')
                        result.update(json.loads(line))
                    if result.get('ok') and result['counts'].get('rows', 0) != record['rows']:
                        result.update(ok=False, error='manifest_row_count_mismatch')
                except Exception as exc:
                    result.update(ok=False, error_type=type(exc).__name__)
                    # Restart on IO/hash errors: no state may carry across an unverified file.
                    process.stdin.close()
                    process.wait()
                    process = subprocess.Popen([str(binary.resolve()), kind], stdin=subprocess.PIPE,
                                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
                result['elapsed_seconds'] = round(time.monotonic() - start, 3)
                result['fingerprint'] = fingerprint
                _, day, hour, name = record['remote_file'].split('/')
                save(output / 'hours' / day / hour / (name + '.quality.json'), result)
                rows = result.get('counts', {}).get('rows', 0)
                summary['files_done'] += 1
                summary['rows_scanned'] += rows
                summary['raw_bytes_checked'] += record['bytes'] if result.get('raw_integrity_pass') else 0
                summary['errors'] += not result.get('ok', False)
                with progress_lock:
                    progress['files_done'] += 1
                    progress['rows_scanned'] += rows
                    progress['raw_bytes_checked'] += record['bytes'] if result.get('raw_integrity_pass') else 0
                    progress['errors'] += not result.get('ok', False)
                    progress['last_file'] = record['remote_file']
                    progress['updated_utc'] = datetime.now(timezone.utc).isoformat()
                    save(output / 'progress.json', progress)
            save(done, summary)
            with progress_lock:
                progress['shards_done'] += 1
                save(output / 'progress.json', progress)
        finally:
            if process.stdin and not process.stdin.closed:
                process.stdin.close()
            process.wait()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(shard, key, value) for key, value in sorted(jobs.items())]
        for future in as_completed(futures):
            future.result()
    progress['state'] = 'scan_complete_reconciliation_pending'
    save(output / 'progress.json', progress)
    if not only_month and not limit_hours:
        refs = reference_candles(output)
        reconcile(output, inv, refs)
        progress['state'] = 'complete'
        progress['finished_utc'] = datetime.now(timezone.utc).isoformat()
        save(output / 'progress.json', progress)


def reconcile(output, inv, references):
    """Compare every reconstructed execution minute with independent exchange OHLCV/counts."""
    official = {}
    for ref in references:
        if not ref['available']:
            continue
        with zipfile.ZipFile(output / 'reference' / f"BTCUSDT-1m-{ref['month']}.zip") as archive:
            names = [n for n in archive.namelist() if n.endswith('.csv')]
            if len(names) != 1:
                raise ValueError('Unexpected official candle archive')
            with archive.open(names[0]) as raw:
                for row in csv.reader(io.TextIOWrapper(raw)):
                    if not row[0].isdigit():
                        continue
                    minute = int(row[0])
                    if minute % 60000:
                        raise ValueError('Official candle not aligned to milliseconds')
                    official[minute] = {'open': Decimal(row[1]), 'high': Decimal(row[2]),
                        'low': Decimal(row[3]), 'close': Decimal(row[4]), 'volume': Decimal(row[5]),
                        'quote_volume': Decimal(row[7]), 'count': int(row[8])}
    totals = Counter()
    trade_minutes = {}
    book_minutes = {}
    file_errors = []
    for path in sorted((output / 'hours').rglob('*.quality.json')):
        q = json.loads(path.read_text())
        if not q.get('ok'):
            file_errors.append(q['remote_file'])
            continue
        kind = 'book' if '_orderbook.' in q['remote_file'] else 'trades'
        for k, v in q['counts'].items():
            totals[kind + '.' + k] += v
        hard_clock = any(q['counts'].get(k, 0) for k in HARD_CLOCK)
        # Backward receipt time is a causal-input issue even if sequence replay succeeds.
        hard_clock |= q['counts'].get('backward_receipt_rows', 0) > 0
        if kind == 'book':
            for i, seconds in enumerate(q['good_seconds_per_minute']):
                book_minutes[q['hour_ns'] // 1000000 + i * 60000] = seconds == 60 and not hard_clock
        else:
            for candle in q['candles']:
                minute = candle['minute_ms']
                value = {k: Decimal(candle[k]) for k in ('open', 'high', 'low', 'close', 'volume', 'quote_volume')}
                value.update(count=candle['count'], bad=candle['bad'] or hard_clock,
                             first_id=candle['first_id'], last_id=candle['last_id'])
                if minute not in trade_minutes:
                    trade_minutes[minute] = value
                else:
                    prior = trade_minutes[minute]
                    prior['high'] = max(prior['high'], value['high'])
                    prior['low'] = min(prior['low'], value['low'])
                    for key in ('volume', 'quote_volume', 'count'):
                        prior[key] += value[key]
                    if value['first_id'] < prior['first_id']:
                        prior['open'], prior['first_id'] = value['open'], value['first_id']
                    if value['last_id'] > prior['last_id']:
                        prior['close'], prior['last_id'] = value['close'], value['last_id']
                    prior['bad'] |= value['bad']
    mismatches = Counter()
    checked = 0
    good_trade_minutes = set()
    for minute, value in trade_minutes.items():
        truth = official.get(minute)
        if not truth:
            mismatches['no_independent_reference'] += 1
            continue
        checked += 1
        bad = value['bad']
        for key in ('open', 'high', 'low', 'close', 'volume', 'count'):
            if value[key] != truth[key]:
                mismatches[key] += 1
                bad = True
        # Binance quote-volume strings are rounded; report separately from exact base/price/count.
        if abs(value['quote_volume'] - truth['quote_volume']) > Decimal('0.01'):
            mismatches['quote_volume_over_0.01_USDT'] += 1
            bad = True
        if not bad:
            good_trade_minutes.add(minute)
    good_origins = []
    run = 0
    previous = None
    for minute in sorted(official):
        run = run + 1 if previous is not None and minute == previous + 60000 else 1
        # Origin = next minute open, target is that next minute. Context is 1,440 closed candles.
        if run >= 1440 and minute + 60000 in official and book_minutes.get(minute) and minute in good_trade_minutes:
            good_origins.append(minute + 60000)
        previous = minute
    save(output / 'usable-origin-times.json', good_origins)
    report = {'validation_version': VERSION, 'scan_complete': True, 'training_ready': False,
              'inventory': inv, 'counts': dict(totals), 'file_errors': file_errors,
              'independent_reference_months': references, 'official_minutes': len(official),
              'trade_minutes': len(trade_minutes), 'trade_minutes_compared': checked,
              'trade_candle_mismatches': dict(mismatches),
              'trade_minutes_passing': len(good_trade_minutes),
              'book_minutes_passing': sum(book_minutes.values()),
              'candidate_1440_context_origins': len(good_origins),
              'limitations': ['Candidate origins still need split, latency and leakage review before training.',
                  'Native monthly shards conservatively restart at month boundaries; no inherited unverified book.',
                  'Book freshness/top20 checked at one-second grid; full events are replayed, not sampled.',
                  'Recorded receipt timestamps/checkpoints cannot prove original collector clock accuracy.',
                  'Snapshot omission on empty/halts is a provider limitation that cannot be fully recovered.']}
    save(output / 'report.json', report)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--workers', type=int, choices=range(1, 5), default=3)
    parser.add_argument('--month')
    parser.add_argument('--limit-hours', type=int)
    args = parser.parse_args()
    run(args.archive, args.output, args.workers, args.month, args.limit_hours)
