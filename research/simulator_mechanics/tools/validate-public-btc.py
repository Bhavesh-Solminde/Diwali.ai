"""Offline bounded-capture sequence audit; incomplete segments never become clean books."""
import argparse
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path


def validate(rawdir,out):
    manifest=json.loads((rawdir/'manifest.json').read_text())
    assert hashlib.sha256((rawdir/'raw.jsonl.gz').read_bytes()).hexdigest()==manifest['raw_sha256']
    with gzip.open(rawdir/'raw.jsonl.gz','rt') as f:records=[json.loads(line) for line in f]
    book={'b':{},'a':{}};buffer=[];snapshot=None;last=None;sync=False;requires_snapshot=False;counts=Counter();quality=[];latencies=[]
    agg=[];klines={};restklines={};lastagg=None;bookstates=[];lastmono=None;exchangeinfo=None
    def depth(event,receipt):
        nonlocal last,sync,requires_snapshot
        if requires_snapshot:counts['invalid_segment_depth_discarded']+=1;return
        if snapshot is None:buffer.append((event,receipt));return
        if not sync:
            if event['u']<snapshot:counts['bootstrap_stale_dropped']+=1;return
            if not event['U']<=snapshot<=event['u']:
                counts['bootstrap_unbridgeable']+=1;return
            sync=True
        elif event['u']<=last:counts['duplicate_or_old_depth']+=1;return
        elif event.get('pu')!=last:
            counts['sequence_gaps']+=1;quality.append(dict(kind='pu_gap',expected=last,actual=event.get('pu'),receipt_ns=receipt))
            sync=False;last=None;requires_snapshot=True
            # This engineering capture has no replacement snapshot. Never bridge old snapshot again.
            return
        for side in ('b','a'):
            for p,q in event.get(side,[]):
                p,q=Decimal(p),Decimal(q)
                if p<=0 or q<0:raise ValueError('invalid_depth_value')
                if q==0:book[side].pop(p,None)
                else:book[side][p]=q
        last=event['u'];counts['depth_applied']+=1
        if not book['b'] or not book['a'] or max(book['b'])>=min(book['a']):
            counts['invalid_or_crossed_books']+=1
        else:
            counts['valid_book_updates']+=1
            if len(bookstates)<5 or counts['valid_book_updates']%100==0:
                bookstates.append(dict(receipt_ns=receipt,exchange_event_ms=event.get('E'),exchange_transaction_ms=event.get('T'),update_id=last,
                    bids=[[str(p),str(book['b'][p])] for p in sorted(book['b'],reverse=True)[:20]],
                    asks=[[str(p),str(book['a'][p])] for p in sorted(book['a'])[:20]]))
    for rec in records:
        if lastmono is not None and rec['receipt_monotonic_ns']<lastmono:counts['receipt_monotonic_reversals']+=1
        lastmono=rec['receipt_monotonic_ns']
        payload=rec['payload']
        if rec['kind']=='rest':
            url=rec['url']
            if '/depth?' in url:
                requires_snapshot=False;sync=False;last=None
                snapshot=payload['lastUpdateId'];book={'b':{Decimal(p):Decimal(q) for p,q in payload['bids'] if Decimal(q)>0},
                                                     'a':{Decimal(p):Decimal(q) for p,q in payload['asks'] if Decimal(q)>0}}
                pending=buffer;buffer=[]
                for event,receipt in pending:depth(event,receipt)
            elif '/klines?' in url:
                for k in payload:restklines[int(k[0])]=k
            elif '/exchangeInfo' in url:exchangeinfo=next((s for s in payload['symbols'] if s['symbol']=='BTCUSDT'),None)
        elif rec['kind'] in ('market','public'):
            event=payload.get('data',payload);kind=event.get('e');counts[kind]+=1
            if 'E' in event:latencies.append(rec['receipt_utc_ns']/1e6-event['E'])
            if kind=='depthUpdate':depth(event,rec['receipt_utc_ns'])
            elif kind=='aggTrade':
                if lastagg is not None and event['a']!=lastagg+1:counts['aggregate_id_gaps_or_reordering']+=1
                lastagg=event['a'];agg.append(event)
            elif kind=='kline' and event['k']['x']:klines[event['k']['t']]=event['k']
    candles=defaultdict(list)
    for event in agg:candles[event['T']//60000*60000].append(event)
    checks=[]
    for minute,events in sorted(candles.items()):
        full=minute>=min((x['T'] for x in agg),default=0) and minute+60000<=max((x['T'] for x in agg),default=0)
        events=sorted(events,key=lambda x:(x['T'],x['a']));prices=[Decimal(e['p']) for e in events]
        result=dict(open=str(prices[0]),high=str(max(prices)),low=str(min(prices)),close=str(prices[-1]),base_volume=str(sum(Decimal(e['q']) for e in events)))
        ref=restklines.get(minute)
        comparison=None
        if ref is not None:
            comparison=dict(ohlc_match=[Decimal(result[k])==Decimal(ref[i]) for k,i in [('open',1),('high',2),('low',3),('close',4)]],
                            base_volume_difference=str(Decimal(result['base_volume'])-Decimal(ref[5])))
        checks.append(dict(minute_utc_ms=minute,complete_capture_window=full,aggtrade_events=len(events),reconstructed=result,exchange_rest_comparison=comparison))
    out.mkdir(parents=True,exist_ok=False)
    summary=dict(venue=manifest['venue'],instrument=manifest['instrument'],capture_manifest=manifest,
        counts=dict(counts),last_book_update=last,book_currently_synchronized=sync,
        quality_events=quality,top20_sample_count=len(bookstates),
        latency_ms=dict(min=min(latencies),max=max(latencies),mean=sum(latencies)/len(latencies)) if latencies else None,
        exchange_symbol_metadata=exchangeinfo,candle_checks=checks,
        verdict='engineering_sample_only_not_training_ready',
        limitations=['Finite snapshot depth; unchanged levels outside snapshot unknown.',
                    'aggTrade aggregation and insurance/ADL exclusions prevent certification of every execution.',
                    'No reconnect/resnapshot daemon; any sequence gap invalidates book until fresh bootstrap.',
                    'Five-minute capture provides no training split,1440-minute synchronized context or forward forecasts.',
                    'Receipt latency includes local clock skew; exchange and local times retained separately.'])
    (out/'quality.json').write_text(json.dumps(summary,indent=2))
    (out/'top20-samples.json').write_text(json.dumps(bookstates,indent=2))
    print(json.dumps({k:summary[k] for k in ['counts','book_currently_synchronized','top20_sample_count','verdict']},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('rawdir',type=Path);p.add_argument('out',type=Path);a=p.parse_args();validate(a.rawdir,a.out)
