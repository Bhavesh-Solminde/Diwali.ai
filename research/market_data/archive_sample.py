"""Download resumable CryptoHFTData book/trade history without logging credentials.

This preserves provider files; a successful download is not training approval.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import threading
import fcntl
from itertools import zip_longest
import tempfile

import pyarrow as pa
import pyarrow.parquet as pq
import requests

BASE = "https://api.cryptohftdata.com/v1"


class ArchiveHTTPError(RuntimeError):
    def __init__(self, status):
        super().__init__(f'Archive HTTP {status}')
        self.status = status


def inspect_file(path):
    with path.open('rb') as source:
        magic = source.read(4)
    if magic == b'PAR1':
        return pq.ParquetFile(path), 'parquet'
    if magic != bytes.fromhex('28b52ffd'):
        raise ValueError('Unsupported archive encoding')
    # Older provider files wrap Parquet in a Zstandard frame. Preserve wire bytes.
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix='.decoded') as decoded:
        with pa.input_stream(str(path), compression='zstd') as source:
            size = 0
            while chunk := source.read(1024 * 1024):
                size += len(chunk)
                if size > 4 * 1024**3:
                    raise ValueError('Decoded sample exceeded 4 GiB bound')
                decoded.write(chunk)
        decoded.flush()
        metadata = pq.ParquetFile(decoded.name)
        # Only detached metadata/schema are used after this temporary file closes.
        return metadata, 'zstd-wrapped-parquet'


def build_jobs(start, days, hour=None):
    jobs = [(start + timedelta(days=d), h, kind)
            for d in range(days)
            for h in ([hour] if hour is not None else range(24))
            for kind in ("orderbook", "trades")]
    monthly_jobs = {}
    for job in jobs:
        monthly_jobs.setdefault(str(job[0])[:7], []).append(job)
    return [job for group in zip_longest(*monthly_jobs.values())
            for job in group if job is not None]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--date", required=True, type=date.fromisoformat)
    parser.add_argument("--hour", type=int, choices=range(24))
    parser.add_argument("--days", type=int, default=1, choices=range(1, 367))
    parser.add_argument("--workers", type=int, default=4, choices=range(1, 9))
    parser.add_argument("--monthly", action="store_true")
    parser.add_argument("--key-ring", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    process_lock = (args.output / '.download.lock').open('a')
    fcntl.flock(process_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if args.key_ring:
        keys = json.loads(args.key_ring.read_text())
    else:
        keys = [os.environ.get("CRYPTOHFTDATA_API_KEY") or
                (Path.home() / ".config/trading-ai/cryptohftdata-key").read_text().strip()]
    if not keys or len(set(keys)) != len(keys):
        raise RuntimeError('Credential list is empty or contains duplicates')
    tokens = {}
    auth_lock = threading.Lock()
    months = sorted({str(args.date + timedelta(days=d))[:7] for d in range(args.days)})
    assignments = {month: i % len(keys) for i, month in enumerate(months)}

    locks = [threading.Lock() for _ in keys]
    next_request = [0.0 for _ in keys]
    cooldown_lock = threading.Lock()
    cooldown_until = [0.0]

    def throttle(slot):
        with locks[slot]:
            delay = max(0, next_request[slot] - time.monotonic(),
                        cooldown_until[0] - time.monotonic())
            time.sleep(delay)
            next_request[slot] = time.monotonic() + 1.1

    def token_for(slot, refresh=False):
        with auth_lock:
            if not refresh and slot in tokens and time.monotonic() < tokens[slot][1]:
                return tokens[slot][0]
            throttle(slot)
            response = requests.post(BASE + '/jwt-token',
                headers={'X-API-Key': keys[slot], 'Content-Type': 'application/json'}, timeout=30)
            if response.status_code != 200:
                raise RuntimeError(f'Credential slot {slot + 1}: authentication HTTP {response.status_code}')
            tokens[slot] = (response.json()['jwt_token'], time.monotonic() + 3 * 3600)
            return tokens[slot][0]

    for slot in range(len(keys)):
        token_for(slot)
    print(json.dumps({'authenticated_slots': len(keys), 'month_assignments':
                     {month: slot + 1 for month, slot in assignments.items()}}), flush=True)

    def download(job):
        day, hour, kind = job
        remote = f"binance_futures/{day}/{hour:02d}/BTCUSDT_{kind}.parquet"
        root = args.output / str(day)[:7] if args.monthly else args.output
        folder = root / str(day) / f"{hour:02d}"
        folder.mkdir(parents=True, exist_ok=True)
        dest = folder / f"BTCUSDT_{kind}.parquet"
        meta = dest.with_suffix(".metadata.json")
        if not dest.exists() and dest.with_suffix('.parquet.zst').exists():
            dest = dest.with_suffix('.parquet.zst')
        if dest.exists() and meta.exists():
            record = json.loads(meta.read_text())
            with dest.open("rb") as source:
                digest = hashlib.file_digest(source, "sha256").hexdigest()
            if digest == record['sha256'] and dest.stat().st_size == record['bytes']:
                return record
            raise RuntimeError(f"Existing file checksum mismatch: {remote}")
        if dest.exists():
            raise RuntimeError(f"Existing file lacks metadata: {remote}")
        part = dest.with_suffix(".parquet.part")
        started = time.monotonic()
        for attempt in range(4):
            slot = assignments[str(day)[:7]]
            token = token_for(slot)
            throttle(slot)
            digest = hashlib.sha256()
            size = 0
            try:
                result = requests.get(
                BASE + "/download", params={"file": remote},
                headers={"Authorization": f"Bearer {token}"},
                stream=True, timeout=(20, 90),
                )
            except requests.RequestException:
                time.sleep(2 ** attempt)
                continue
            with result:
                if result.status_code == 401:
                    token_for(slot, refresh=True)
                    continue
                if result.status_code == 429 or result.status_code >= 500:
                    delay = max(1, float(result.headers.get('Retry-After', 5)))
                    if result.status_code == 429:
                        # Respect potential IP/account-wide throttling; never key-hop.
                        with cooldown_lock:
                            cooldown_until[0] = max(cooldown_until[0], time.monotonic() + delay)
                    time.sleep(delay)
                    continue
                if result.status_code != 200:
                    raise ArchiveHTTPError(result.status_code)
                with part.open("wb") as target:
                    for chunk in result.iter_content(1024 * 1024):
                        if shutil.disk_usage(args.output).free < 30 * 1024**3:
                            raise RuntimeError("Stopped: less than 30 GiB disk space remains")
                        size += len(chunk)
                        if size > 4 * 1024**3:
                            raise RuntimeError("Sample file exceeded 4 GiB bound")
                        target.write(chunk)
                        digest.update(chunk)
            metadata, encoding = inspect_file(part)
            record = {
                "provider": "CryptoHFTData", "remote_file": remote,
                "bytes": size, "sha256": digest.hexdigest(),
                "rows": metadata.metadata.num_rows,
                "schema": str(metadata.schema_arrow),
                "encoding": encoding,
                "elapsed_seconds": round(time.monotonic() - started, 2),
                "training_ready": False,
            }
            if encoding == 'zstd-wrapped-parquet':
                dest = folder / f'BTCUSDT_{kind}.parquet.zst'
            part.rename(dest)
            meta.write_text(json.dumps(record, indent=2) + "\n")
            print(json.dumps({k: v for k, v in record.items() if k != "schema"}), flush=True)
            return record
        raise RuntimeError(f"{kind}: retries exhausted")

    # Round-robin monthly queues: distinct file keys, distributed credential slots.
    jobs = build_jobs(args.date, args.days, args.hour)
    assert len(jobs) == len(set(jobs)), 'Duplicate archive jobs'
    records, failures = [], []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        pending = {pool.submit(download, job): job for job in jobs}
        for future in as_completed(pending):
            try:
                records.append(future.result())
            except Exception as exc:
                job = pending[future]
                # Exception bodies/URLs are deliberately not logged (credentials).
                failures.append({'date': str(job[0]), 'hour': job[1], 'kind': job[2],
                                 'error_type': type(exc).__name__,
                                 'http_status': getattr(exc, 'status', None)})
            status = {'completed_files': len(records), 'total_files': len(jobs),
                      'bytes': sum(r['bytes'] for r in records), 'failures': failures,
                      'training_ready': False}
            status['months'] = {month: {'completed_files': sum(
                1 for r in records if r['remote_file'].split('/')[1].startswith(month)),
                'credential_slot': assignments[month] + 1} for month in months}
            temporary = args.output / 'status.tmp'
            temporary.write_text(json.dumps(status, indent=2) + '\n')
            temporary.replace(args.output / 'status.json')
    (args.output / "manifest.json").write_text(json.dumps(records, indent=2) + "\n")
    if failures:
        raise SystemExit(f"{len(failures)} files failed; resume the same command to retry")


if __name__ == "__main__":
    main()
