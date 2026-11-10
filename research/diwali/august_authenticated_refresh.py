"""Re-fetch fixed recovery hours with existing keys, preserving original archive bytes."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
import json
from pathlib import Path
import time

import requests

from ..market_data.archive_sample import BASE, inspect_file
from ..market_data.validate_archive import file_hash, save

GIB = 1024**3


def recovery_hours(sample):
    """Fetch each selected origin's hour and its preceding hour exactly once."""
    dates = sorted({r['stratum'][:10] for r in sample['strata'] if r['cutoff_ns'] is not None})
    result = []
    for day in dates:
        hours = set()
        for row in sample['strata']:
            if row['stratum'].startswith(day) and row['cutoff_ns'] is not None:
                stamp = datetime.fromisoformat(row['stratum']+':00:00')
                hours.update((stamp, stamp-timedelta(hours=1)))
        result.append(sorted(hours))
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    root = args.output
    root.mkdir(exist_ok=False, parents=True)
    keys = json.loads((Path.home()/'.config/trading-ai/cryptohftdata-keys.json').read_text())
    if len(keys) != len(set(keys)) or not keys:
        raise ValueError('Expected existing unique archive credentials')
    tokens = []
    auth = []
    for i,key in enumerate(keys):
        response = requests.post(BASE+'/jwt-token', headers={'X-API-Key':key},timeout=30)
        auth.append({'credential_slot':i+1,'http_status':response.status_code})
        if response.status_code != 200:
            save(root/'status.json',{'state':'authentication_failed','slots':auth})
            raise ValueError(f'Existing credential slot {i+1} failed authentication')
        tokens.append(response.json()['jwt_token'])
    sample = json.loads(Path('data/btc-perp/august-book-recovery-v1/fixed-sample.json').read_text())
    original_root = Path('data/btc-perp/cryptohftdata-monthly')
    manifest = {r['remote_file']:r for r in json.loads((original_root/'manifest.json').read_text())}
    jobs = [(i % len(tokens), hours) for i, hours in enumerate(recovery_hours(sample))]
    if len(jobs) > len(tokens):
        raise ValueError('Bounded refresh requires a distinct credential per worker')
    save(root/'protocol.json',{'purpose':'Authenticated fresh download of selected recovery hours and preceding hours',
                              'fixed_sample_sha256':file_hash(Path('data/btc-perp/august-book-recovery-v1/fixed-sample.json')),
                              'authenticated_slots':auth,'file_count':sum(len(h) for _,h in jobs),
                              'original_archive_overwritten':False})
    def run(slot, hours):
        results=[]
        for stamp in hours:
            remote=f'binance_futures/{stamp:%Y-%m-%d}/{stamp:%H}/BTCUSDT_orderbook.parquet'
            folder=root/f'{stamp:%Y-%m-%dT%H}'
            folder.mkdir()
            dest=folder/'orderbook.wire'
            began=time.monotonic()
            response=requests.get(BASE+'/download',params={'file':remote},
                                  headers={'Authorization':'Bearer '+tokens[slot]},stream=True,timeout=(15,90))
            record={'remote_file':remote,'credential_slot':slot+1,'http_status':response.status_code,
                    'original_sha256':manifest[remote]['sha256']}
            if response.status_code==200:
                count=0
                with dest.open('xb') as output:
                    for chunk in response.iter_content(1024*1024):
                        count+=len(chunk)
                        if count>GIB:
                            raise ValueError('Bounded refresh download exceeded 1GiB')
                        output.write(chunk)
                metadata,encoding=inspect_file(dest)
                digest = file_hash(dest)
                record.update(bytes=count,sha256=digest,rows=metadata.metadata.num_rows,
                              encoding=encoding,unchanged=digest==manifest[remote]['sha256'])
            else:
                response.close()
                if response.status_code==429:
                    # Stop this slot rather than shifting the request to another credential.
                    raise ValueError(f'Credential slot {slot+1} was rate-limited; respect its limit')
            record['elapsed_seconds']=time.monotonic()-began
            save(folder/'download.json',record)
            results.append(record)
            print(stamp.isoformat(),record['http_status'],record.get('unchanged'),flush=True)
            time.sleep(1.1)
        return results
    results=[]
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futures=[pool.submit(run,*job) for job in jobs]
        for f in as_completed(futures):
            results.extend(f.result())
            save(root/'status.json',{'state':'refreshing','completed_files':len(results),
                                    'total_files':sum(len(h) for _,h in jobs)})
    save(root/'report.json',{'state':'complete','files':results,'authenticated_slots':auth,
                            'unchanged_files':sum(r.get('unchanged',False) for r in results),
                            'changed_files':sum(r.get('unchanged') is False for r in results),
                            'original_archive_overwritten':False})
    save(root/'status.json',{'state':'complete','completed_files':len(results)})
    print('Authenticated refresh complete',len(results),flush=True)


if __name__=='__main__':
    main()
