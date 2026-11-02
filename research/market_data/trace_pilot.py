"""Bounded independent Python checks of raw archive candles and book features."""
import argparse
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq
from .build_pilot import START,WARMUP,feature_dtype,references
from .review_pilot import utc,candle_reason
from .validate_archive import raw_path,decoded,file_hash,save


def trace(root,features,audit,out):
    records={r['remote_file']:r for r in json.loads((root/'manifest.json').read_text())}
    valid=np.load(features/'candle-valid.npy')
    official=references(audit)
    source=json.loads((features/'source-candles.json').read_text())
    idx=np.load(features/'fit-delay0-indices.npy')
    chosen={}
    for i in np.flatnonzero(~valid):
        ms=int(WARMUP+i*60000);reason=candle_reason(official.get(ms),source.get(str(ms)))
        chosen.setdefault(reason,ms)
    chosen['retained_final_context']=int(idx[0,0]-60000)
    review=json.loads((out/'coverage-review.json').read_text())
    late=next(t for t in review['selected_traces'] if t['reason']=='late_context')
    from datetime import datetime
    chosen['late_final_context']=int(datetime.fromisoformat(late['origin_utc']).timestamp()*1000)-60000
    candle_checks=[]
    for reason,ms in chosen.items():
        rows=[];evidence=[]
        # Include adjacent arrival hours: late events need not be in event-time hour.
        center=ms//3600000*3600000
        for h in (center-3600000,center,center+3600000):
            stamp=utc(h);key=f'binance_futures/{stamp[:10]}/{stamp[11:13]}/BTCUSDT_trades.parquet'
            if key not in records:continue
            r=records[key];p=raw_path(root,r)
            if file_hash(p)!=r['sha256']:raise ValueError('Raw hash differs')
            evidence.append({'remote_file':key,'sha256':r['sha256']})
            with decoded(p,out) as plain:
                for batch in pq.ParquetFile(plain).iter_batches():
                    t=batch.column(batch.schema.get_field_index('trade_time')).to_numpy()
                    mask=(t>=ms)&(t<ms+60000)
                    if mask.any():rows.extend(batch.filter(mask).to_pylist())
        execution=[r for r in rows if not (r.get('order_type')=='NA' and Decimal(r['price'])==0 and Decimal(r['quantity'])==0)]
        execution.sort(key=lambda r:r['trade_id'])
        # Deliberately no deduplication/interpolation of provider rows.
        recon=None
        if execution:
            prices=[Decimal(r['price']) for r in execution];qty=[Decimal(r['quantity']) for r in execution]
            recon={'open':prices[0],'high':max(prices),'low':min(prices),'close':prices[-1],
                   'volume':sum(qty),'quote_volume':sum(p*q for p,q in zip(prices,qty)), 'count':len(execution)}
        truth=official.get(ms)
        matches=recon is not None and truth is not None and all(recon[k]==truth[k] for k in ('open','high','low','close','volume','count')) and abs(recon['quote_volume']-truth['quote_volume'])<=Decimal('.01')
        candle_checks.append({'case':reason,'minute_utc':utc(ms),'raw_execution_rows':len(execution),
            'matches_official_reference':bool(matches),'source_bad_flag':source.get(str(ms),{}).get('bad'),
            'max_receipt_minus_next_open_ms':(max(r['received_time'] for r in execution)-(ms+60000)*10**6)/1e6 if execution else None,
            'source_files':evidence})
    # Independent Decimal replay to a specific native sequence. Only one early
    # within-hour retained sample is needed for this bounded implementation check.
    candidates=[r for r in idx if r[0]//60000%60 in (1,2,3)]
    row=candidates[0] if candidates else idx[0]
    book=np.memmap(features/'book-seconds.bin',mode='r',dtype=feature_dtype('book'))
    sample=book[int(row[3]-1)];target=int(sample['sequence'])
    ms=int(sample['time_ns']//10**6);stamp=utc(ms);key=f'binance_futures/{stamp[:10]}/{stamp[11:13]}/BTCUSDT_orderbook.parquet'
    record=records[key];p=raw_path(root,record)
    if file_hash(p)!=record['sha256']:raise ValueError('Raw book hash differs')
    bids={};asks={};previous=None;event=[];last=None;max_receipt=0;max_event=0;events=0
    def apply(group):
        nonlocal last,max_receipt,max_event,events
        head=group[0];snap=head['event_type']=='snapshot'
        u=head['last_update_id'] if snap else head['final_update_id']
        if snap:bids.clear();asks.clear()
        elif last is not None and u<=last:return
        elif last is not None and head['prev_final_update_id']!=last and not (head['first_update_id']<=last<=u):
            raise ValueError('Independent replay sequence gap')
        for r in group:
            side=bids if r['side']=='bid' else asks
            price,qty=Decimal(r['price']),Decimal(r['quantity'])
            if qty:side[price]=qty
            else:side.pop(price,None)
        last=u;events+=1;max_receipt=max(r['received_time'] for r in group);max_event=head['event_time']
    done=False
    with decoded(p,out) as plain:
        for batch in pq.ParquetFile(plain).iter_batches():
            for r in batch.to_pylist():
                keyevent=(r['event_type'],r['event_time'],r['final_update_id'],r['last_update_id'])
                if event and keyevent!=previous:
                    apply(event);event=[]
                    if last==target:done=True;break
                event.append(r);previous=keyevent
            if done:break
        if not done and event:apply(event)
    if last!=target:raise ValueError('Target sequence not reached')
    b=sorted(bids,reverse=True)[:20];a=sorted(asks)[:20];mid=float((b[0]+a[0])/2)
    expected=[]
    for bp,ap in zip(b,a):expected += [(float(bp)/mid-1)*10000,np.log1p(float(bids[bp])),(float(ap)/mid-1)*10000,np.log1p(float(asks[ap]))]
    np.testing.assert_allclose(sample['x'][:80],expected,atol=2e-5,rtol=2e-5)
    if int(sample['receipt_ns'])!=max_receipt or int(sample['event_ns'])!=max_event*10**6:raise ValueError('Source clock mismatch')
    save(out/'raw-trace-review.json',{'scope':'five candle cases, one independent native-sequence book replay; not archive-wide certification',
        'candle_checks':candle_checks,'book_check':{'origin_utc':utc(int(row[0])),'grid_utc':utc(ms),'sequence':target,
        'independent_replay_events':events,'top20_price_quantity_features_match':True,'source_clocks_match':True,
        'remote_file':record['remote_file'],'sha256':record['sha256']}})
    print('Raw trace checks complete')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('archive','features','audit','output'):p.add_argument(name,type=Path)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True);trace(a.archive,a.features,a.audit,a.output)
