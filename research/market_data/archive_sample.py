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

import pyarrow.parquet as pq
import requests

BASE = "https://api.cryptohftdata.com/v1"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--date", required=True, type=date.fromisoformat)
    parser.add_argument("--hour", type=int, choices=range(24))
    parser.add_argument("--days", type=int, default=1, choices=range(1, 91))
    parser.add_argument("--workers", type=int, default=4, choices=range(1, 9))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    key = os.environ.get("CRYPTOHFTDATA_API_KEY")
    if not key:
        key = (Path.home() / ".config/trading-ai/cryptohftdata-key").read_text().strip()
    response = requests.post(
        BASE + "/jwt-token",
        headers={"X-API-Key": key, "Content-Type": "application/json"}, timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Authentication HTTP {response.status_code}")
    token = response.json()["jwt_token"]
    del key, response

    lock = threading.Lock()
    next_request = [0.0]

    def throttle():
        with lock:
            delay = max(0, next_request[0] - time.monotonic())
            time.sleep(delay)
            next_request[0] = time.monotonic() + 1.1

    def download(job):
        day, hour, kind = job
        remote = f"binance_futures/{day}/{hour:02d}/BTCUSDT_{kind}.parquet"
        folder = args.output / str(day) / f"{hour:02d}"
        folder.mkdir(parents=True, exist_ok=True)
        dest = folder / f"BTCUSDT_{kind}.parquet"
        meta = dest.with_suffix(".metadata.json")
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
            throttle()
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
                if result.status_code == 429 or result.status_code >= 500:
                    time.sleep(min(30, max(1, int(result.headers.get("Retry-After", 5)))))
                    continue
                if result.status_code != 200:
                    raise RuntimeError(f"{kind}: HTTP {result.status_code}")
                with part.open("wb") as target:
                    for chunk in result.iter_content(1024 * 1024):
                        if shutil.disk_usage(args.output).free < 10 * 1024**3:
                            raise RuntimeError("Stopped: less than 10 GiB disk space remains")
                        size += len(chunk)
                        if size > 4 * 1024**3:
                            raise RuntimeError("Sample file exceeded 4 GiB bound")
                        target.write(chunk)
                        digest.update(chunk)
            metadata = pq.ParquetFile(part)
            record = {
                "provider": "CryptoHFTData", "remote_file": remote,
                "bytes": size, "sha256": digest.hexdigest(),
                "rows": metadata.metadata.num_rows,
                "schema": str(metadata.schema_arrow),
                "elapsed_seconds": round(time.monotonic() - started, 2),
                "training_ready": False,
            }
            part.rename(dest)
            meta.write_text(json.dumps(record, indent=2) + "\n")
            print(json.dumps({k: v for k, v in record.items() if k != "schema"}), flush=True)
            return record
        raise RuntimeError(f"{kind}: retries exhausted")

    jobs = [(args.date + timedelta(days=d), h, kind)
            for d in range(args.days)
            for h in ([args.hour] if args.hour is not None else range(24))
            for kind in ("orderbook", "trades")]
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
                                 'error_type': type(exc).__name__})
            status = {'completed_files': len(records), 'total_files': len(jobs),
                      'bytes': sum(r['bytes'] for r in records), 'failures': failures,
                      'training_ready': False}
            temporary = args.output / 'status.tmp'
            temporary.write_text(json.dumps(status, indent=2) + '\n')
            temporary.replace(args.output / 'status.json')
    (args.output / "manifest.json").write_text(json.dumps(records, indent=2) + "\n")
    if failures:
        raise SystemExit(f"{len(failures)} files failed; resume the same command to retry")


if __name__ == "__main__":
    main()
