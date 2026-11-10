"""Resume checksum-verified historical snapshot downloads using an existing account.

Keys and signed download URLs remain private. Missing entitlements are reported,
never retried through another account or treated as recovered data.
"""
import argparse
from datetime import date
import json
from pathlib import Path
import time
from urllib.parse import urlparse

import requests

from .validate_archive import file_hash, save

BASE = 'https://candlefeed.ai/api/v1/l2/files'


def download_file(record, folder):
    name = record['name']
    if name not in ('snapshot.parquet', 'manifest.json'):
        raise ValueError('Only snapshot/manifest files are part of this recovery download')
    size = int(record['size'])
    if size <= 0 or size > 64*1024**2 or len(record['sha256']) != 64:
        raise ValueError('Invalid or unexpectedly large snapshot metadata')
    target = folder/name
    if target.exists():
        if target.stat().st_size == size and file_hash(target) == record['sha256']:
            return 'already_verified'
        raise ValueError('Existing file differs; preserve it and investigate')
    url = urlparse(record['url'])
    if url.scheme != 'https' or not url.hostname or url.username or url.password:
        raise ValueError('Unsafe download location')
    part = target.with_suffix(target.suffix+'.part')
    if part.exists():
        raise ValueError('An earlier partial file remains; preserve it for inspection')
    # The provider API key is deliberately absent from the file-host request.
    with requests.get(record['url'], stream=True, timeout=(15, 90)) as response:
        if response.status_code != 200:
            raise ValueError(f'File download HTTP {response.status_code}; signed URL withheld')
        if any(urlparse(r.url).scheme != 'https' for r in [*response.history, response]):
            raise ValueError('Non-HTTPS download redirect')
        count = 0
        with part.open('xb') as output:
            for chunk in response.iter_content(1024*1024):
                count += len(chunk)
                if count > size:
                    raise ValueError('Download exceeds its declared size')
                output.write(chunk)
    if count != size or file_hash(part) != record['sha256']:
        raise ValueError('Downloaded file failed size/SHA-256 verification')
    part.replace(target)
    return 'downloaded'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--start', type=date.fromisoformat, required=True)
    p.add_argument('--end', type=date.fromisoformat, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if not 0 <= (args.end-args.start).days < 31:
        p.error('Request between one and 31 days')
    args.output.mkdir(parents=True, exist_ok=True, mode=0o700)
    key = (Path.home()/'.config/trading-ai/candlefeed-key').read_text().strip()
    response = requests.get(BASE, params={'dataset':'book', 'symbol':'BTCUSDT',
        'start':str(args.start), 'end':str(args.end)}, headers={'X-API-Key':key},
        timeout=(15, 60), allow_redirects=False)
    listing = response.json()
    save(args.output/f'private-listing-{time.time_ns()}.json', listing)
    if response.status_code != 200:
        code = listing.get('detail', {}).get('code')
        save(args.output/'status.json', {'state':'access_or_source_error', 'http_status':response.status_code, 'code':code})
        raise ValueError(f'CandleFeed HTTP {response.status_code}, code {code}; private response withheld')
    records = []
    for day in listing['days']:
        stamp = date.fromisoformat(day['date'])
        if not args.start <= stamp <= args.end:
            raise ValueError('Listing returned a day outside the request')
        folder = args.output/day['date'];folder.mkdir(exist_ok=True)
        for record in day['files']:
            if record['name'] not in ('snapshot.parquet', 'manifest.json'):
                continue
            state = download_file(record, folder)
            public_metadata = {k:record[k] for k in ['name','size','sha256','rows'] if k in record}
            save(folder/(record['name']+'.metadata.json'), public_metadata)
            records.append({'day':day['date'], **public_metadata, 'state':state})
            print(day['date'], record['name'], state, flush=True)
    result = {'state':'complete_with_restricted_dates' if listing.get('missing') else 'complete',
        'plan':listing.get('plan'), 'requested_start':str(args.start), 'requested_end':str(args.end),
        'available_days':[d['date'] for d in listing['days']], 'missing':listing.get('missing',[]),
        'files':records, 'raw_redistribution':False}
    save(args.output/'status.json', result)
    print('Available days',len(result['available_days']),'unavailable',len(result['missing']),flush=True)


if __name__ == '__main__':
    main()
