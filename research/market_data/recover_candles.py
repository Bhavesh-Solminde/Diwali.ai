"""Recover rejected candle contents from checksum-verified official Binance trades.
Never invent provider receipt times or modify the original dataset.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import shutil
import time
import urllib.request
import zipfile
import numpy as np
import pyarrow.parquet as pq
from .build_pilot import WARMUP, references
from .review_pilot import utc, candle_reason
from .validate_archive import save, file_hash, decoded, raw_path

BASE='https://data.binance.vision/data/futures/um/daily/trades/BTCUSDT/'


def market_execution(row):
    # Binance's official market-trade archive excludes insurance-fund/ADL events.
    # Retain those raw records, but do not count them as candle executions.
    if row.get('order_type') in ('INSURANCE_FUND', 'ADL'):return False
    return not (row.get('order_type')=='NA' and Decimal(row['price'])==0 and Decimal(row['quantity'])==0)


def aggregate(rows):
    if not rows: return None
    rows=sorted(rows, key=lambda r:int(r[0]))
    ids=[int(r[0]) for r in rows]
    if len(ids)!=len(set(ids)): raise ValueError('Duplicate official execution ID')
    prices=[Decimal(r[1]) for r in rows]; qty=[Decimal(r[2]) for r in rows]
    if min(prices)<=0 or min(qty)<=0: raise ValueError('Invalid official execution')
    return {'open':prices[0], 'high':max(prices), 'low':min(prices), 'close':prices[-1],
            'volume':sum(qty), 'quote_volume':sum(p*q for p,q in zip(prices,qty)), 'count':len(rows)}


def agrees(values, truth):
    return values is not None and truth is not None and all(values[k]==truth[k]
        for k in ('open','high','low','close','volume','count')) and abs(values['quote_volume']-truth['quote_volume'])<=Decimal('.01')


def get_file(day, output):
    path=output/f'BTCUSDT-trades-{day}.zip';url=BASE+path.name
    error=None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url+'.CHECKSUM',timeout=30) as response:
                checksum=response.read(4096).decode()
            expected=checksum.split()[0]
            if len(expected)!=64 or any(c not in '0123456789abcdef' for c in expected):
                raise ValueError('Invalid official checksum')
            if path.exists() and file_hash(path)!=expected:
                raise ValueError('Cached archive differs from official checksum; preserve and investigate')
            if not path.exists():
                part=path.with_suffix('.part')
                with urllib.request.urlopen(url,timeout=60) as response,part.open('wb') as dest:
                    shutil.copyfileobj(response,dest)
                if file_hash(part)!=expected: raise ValueError('Official download checksum mismatch')
                part.replace(path)
            path.with_suffix('.CHECKSUM').write_text(checksum)
            return path,{'url':url,'sha256':expected,'bytes':path.stat().st_size,
                'checksum_verified':True,'checked_utc':datetime.now(timezone.utc).isoformat()}
        except Exception as exc:
            error=exc
            if isinstance(exc,ValueError):raise
            if attempt<2:time.sleep(2**attempt)
    raise error


def recover_day(day, minutes, root, records, official, source, output):
    path,provenance=get_file(day,output/'official')
    selected={m:[] for m in minutes}
    with zipfile.ZipFile(path) as archive:
        with archive.open(next(n for n in archive.namelist() if n.endswith('.csv'))) as raw:
            reader=csv.reader(io.TextIOWrapper(raw));header=next(reader)
            if header!=['id','price','qty','quote_qty','time','is_buyer_maker']:
                raise ValueError('Unexpected official futures trades schema')
            for row in reader:
                if len(row)!=6:raise ValueError('Malformed official trade row')
                minute=int(row[4])//60000*60000
                if minute in selected:selected[minute].append(row)
    # Compare IDs and values against the provider's adjacent arrival hours. This
    # verifies omissions/conflicts within the declared scope, not historical latency.
    provider={m:{} for m in minutes};excluded_types={m:Counter() for m in minutes};input_hashes=[]
    hours=sorted({m//3600000*3600000+offset for m in minutes for offset in (-3600000,0,3600000)})
    for hour in hours:
        stamp=utc(hour);key=f'binance_futures/{stamp[:10]}/{stamp[11:13]}/BTCUSDT_trades.parquet'
        if key not in records:continue
        record=records[key];p=raw_path(root,record)
        if file_hash(p)!=record['sha256']:raise ValueError('Provider raw bytes changed')
        input_hashes.append({'remote_file':key,'sha256':record['sha256']})
        with decoded(p,output) as plain:
            for batch in pq.ParquetFile(plain).iter_batches():
                t=batch.column(batch.schema.get_field_index('trade_time')).to_numpy()
                mask=np.isin(t//60000*60000,minutes)
                if not mask.any():continue
                for r in batch.filter(mask).to_pylist():
                    minute=r['trade_time']//60000*60000
                    if not market_execution(r):
                        excluded_types[minute][r.get('order_type','unknown')]+=1
                        continue
                    value=(Decimal(r['price']),Decimal(r['quantity']),r['trade_time'],r['is_buyer_maker'])
                    previous=provider[minute].get(r['trade_id'])
                    if previous is not None and previous!=value:raise ValueError('Conflicting provider duplicate ID')
                    provider[minute][r['trade_id']]=value
    ledger=[]
    for minute in minutes:
        rows=selected[minute];values=aggregate(rows)
        truth=official.get(minute);match=agrees(values,truth)
        original=provider[minute]
        observed={int(r[0]):(Decimal(r[1]),Decimal(r[2]),int(r[4]),r[5].lower()=='true') for r in rows}
        common=observed.keys() & original.keys()
        conflicts=sum(observed[i]!=original[i] for i in common)
        # Official daily files can also omit executions. A union is accepted only
        # when common native IDs agree exactly and the reconstructed full candle
        # independently reconciles; neither source is assumed perfect.
        union={**original,**observed}
        union_rows=[[str(i),str(v[0]),str(v[1]),'',str(v[2]),str(v[3]).lower()] for i,v in union.items()]
        union_values=aggregate(union_rows)
        union_match=agrees(union_values,truth)
        use_union=not match and conflicts==0 and union_match
        eligible=conflicts==0 and (match or use_union)
        chosen=union_values if use_union else values
        ledger.append({'minute_ms':minute,'minute_utc':utc(minute),
            'original_rejection':candle_reason(truth,source.get(str(minute))),
            'official_execution_count':len(rows),'provider_distinct_ids_in_scope':len(original),
            'provider_non_market_rows_excluded':dict(excluded_types[minute]),
            'missing_provider_ids':len(observed.keys()-original.keys()),
            'provider_extra_ids':len(original.keys()-observed.keys()),'conflicting_common_ids':conflicts,
            'matches_official_reference':match,'union_matches_reference':union_match,
            'recovery_source':'official_provider_native_id_union' if use_union else 'official_daily_trades',
            'recovered_execution_count':chosen['count'] if chosen else 0,
            'content_recovery_accepted':eligible,
            'official_reconstruction':{k:str(v) for k,v in values.items()} if values else None,
            'accepted_reconstruction':{k:str(v) for k,v in chosen.items()} if chosen and eligible else None,
            'original_receipt_recovered':False,'comparison_scope':'event minute in previous/current/next arrival hour'})
    result={'day':day,'official_file':provenance,'provider_files':input_hashes,'minutes':ledger}
    save(output/'days'/f'{day}.json',result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('archive','features','audit','output'):parser.add_argument(name,type=Path)
    parser.add_argument('--workers',type=int,default=3)
    args=parser.parse_args()
    if not 1<=args.workers<=3:parser.error('Use 1–3 capped workers')
    output=args.output;output.mkdir(parents=True,exist_ok=True);(output/'official').mkdir(exist_ok=True);(output/'days').mkdir(exist_ok=True)
    import fcntl
    lock=(output/'.recover.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    # Seed only the exact previously verified official sample; recheck checksum.
    seed=args.features.parent/'official-recovery-probe-20261102/BTCUSDT-trades-2026-09-30.zip'
    dest=output/'official'/seed.name
    if seed.exists() and not dest.exists():shutil.copyfile(seed,dest)
    valid=np.load(args.features/'candle-valid.npy')
    source=json.loads((args.features/'source-candles.json').read_text())
    official=references(args.audit)
    records={r['remote_file']:r for r in json.loads((args.archive/'manifest.json').read_text())}
    by_day={}
    for i in np.flatnonzero(~valid):
        ms=int(WARMUP+i*60000);by_day.setdefault(utc(ms)[:10],[]).append(ms)
    fingerprint=hashlib.sha256((file_hash(Path(__file__))+file_hash(args.features/'candle-valid.npy')+
        file_hash(args.features/'source-candles.json')+file_hash(args.archive/'manifest.json')).encode()).hexdigest()
    completed=[];errors=[];began=time.monotonic()
    save(output/'progress.json',{'state':'recovering','days_total':len(by_day),'days_done':0,'fingerprint':fingerprint})
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs={pool.submit(recover_day,day,minutes,args.archive,records,official,source,output):day for day,minutes in by_day.items()}
        for future in as_completed(jobs):
            try:completed.append(future.result())
            except Exception as exc:errors.append({'day':jobs[future],'error':repr(exc)})
            save(output/'progress.json',{'state':'recovering','days_total':len(by_day),
                'days_done':len(completed),'errors':errors,'elapsed_seconds':round(time.monotonic()-began,1),'fingerprint':fingerprint})
    ledger=sorted([r for d in completed for r in d['minutes']],key=lambda r:r['minute_ms'])
    result={'state':'content_recovery_complete' if not errors else 'content_recovery_incomplete',
        'fingerprint':fingerprint,'days_requested':len(by_day),'days_completed':len(completed),
        'minutes_requested':int((~valid).sum()),'minutes_checked':len(ledger),
        'minutes_content_recovered':sum(r['content_recovery_accepted'] for r in ledger),
        'missing_provider_execution_ids_found':sum(r['missing_provider_ids'] for r in ledger),
        'receipt_times_recovered':False,'original_dataset_changed':False,'errors':errors,'minutes':ledger}
    save(output/'recovery-manifest.json',result);save(output/'progress.json',{k:v for k,v in result.items() if k!='minutes'})
    print(json.dumps({k:v for k,v in result.items() if k!='minutes'},indent=2))
    if errors:raise SystemExit(1)

if __name__=='__main__':main()
