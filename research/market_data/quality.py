"""Streaming integrity/coverage audit. A smoke capture never passes training readiness."""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path


def lines(path):
    with path.open() as stream:
        yield from stream


def audit(root):
    manifest=json.loads((root/'manifest.json').read_text())
    counts=Counter();connections=set();segments=set();minutes={};previous=None
    for name,expected in manifest['raw_sha256'].items():
        path=root/name
        with path.open('rb') as f:
            if hashlib.file_digest(f,'sha256').hexdigest()!=expected:
                raise ValueError('raw hash mismatch: '+name)
        for line in lines(path):
            row=json.loads(line);kind=row['kind'];p=row['payload'];counts[kind]+=1
            if previous is not None and row['receipt_monotonic_ns']<previous:
                raise ValueError('nonmonotonic record order')
            previous=row['receipt_monotonic_ns']
            if kind=='connection': connections.add((p['stream'],p['connection']))
            if kind=='book':
                if row['source_receipt_utc_ns']>row['receipt_utc_ns']:
                    raise ValueError('future receipt in book')
                if not p['bids'] or not p['asks'] or Decimal(p['bids'][0][0])>=Decimal(p['asks'][0][0]):
                    raise ValueError('invalid derived book')
                segments.add(row['connection'])
            if kind=='rest' and '/klines?' in row.get('path',''):
                for k in p:
                    if k[6]>=row['request_utc_ns']//1_000_000:
                        counts['unclosed_rest_candle_rows']+=1
                        continue
                    o,h,l,c,v=map(Decimal,k[1:6])
                    if min(o,h,l,c)<=0 or v<0 or h<max(o,c) or l>min(o,c):
                        raise ValueError('invalid exchange candle')
                    if int(k[0])%60000: raise ValueError('unaligned candle')
                    minutes[int(k[0])]=dict(open=str(o),high=str(h),low=str(l),close=str(c),
                        volume=str(v),quote_volume=k[7],available_utc_ns=row['receipt_utc_ns'])
    timestamps=sorted(minutes)
    missing=sum((b-a)//60000-1 for a,b in zip(timestamps,timestamps[1:]))
    return dict(raw_integrity_pass=True,counts=dict(counts),connections=len(connections),
        book_segments=len(segments),official_closed_minutes=len(minutes),missing_official_minutes=missing,
        duration_seconds=(manifest['end_utc_ns']-manifest['start_utc_ns'])/1e9,
        training_ready=False,
        reason='Integrity/engineering audit only. Paired coverage, feature windows, trade coverage and chronological splits still need dataset validation.',
        candle_source='exchange REST closed klines; aggregate-trade reconstruction is separate')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('capture',type=Path);args=parser.parse_args()
    result=audit(args.capture)
    (args.capture/'quality.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
