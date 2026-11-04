"""Bounded source-resolution audit; aggregate statistics, not training examples."""
import argparse,json,time
from pathlib import Path
import numpy as np
import pyarrow.compute as pc
import pyarrow as pa
import pyarrow.parquet as pq
from .validate_archive import file_hash,raw_path,decoded,hour_ns,save,HARD_CLOCK


def event_starts(keys,previous=None):
    keys=np.asarray(keys,dtype=np.int64)
    if keys.ndim!=2 or keys.shape[1]!=3:raise ValueError('Expected receipt,event,final sequence identity')
    if not len(keys):return np.zeros(0,bool),previous
    mask=np.ones(len(keys),bool);mask[1:]=np.any(keys[1:]!=keys[:-1],axis=1)
    if previous is not None:mask[0]=not np.array_equal(keys[0],previous)
    return mask,keys[-1].copy()


def summary(values):
    x=np.asarray(values)
    return {'count':len(x),'minimum':float(x.min()) if len(x) else None,'median':float(np.median(x)) if len(x) else None,
        'p90':float(np.quantile(x,.9)) if len(x) else None,'p99':float(np.quantile(x,.99)) if len(x) else None,'maximum':float(x.max()) if len(x) else None}


def market_mask(batch):
    price=pc.cast(batch.column('price'),'float64');quantity=pc.cast(batch.column('quantity'),'float64');typ=batch.column('order_type')
    # Match the archive validator: NA is nonmarket only for the zero placeholder.
    placeholder=pc.and_(pc.and_(pc.equal(price,0),pc.equal(quantity,0)),pc.equal(typ,'NA'))
    special=pc.is_in(typ,value_set=pa.array(['INSURANCE_FUND','ADL']))
    return pc.and_(pc.and_(pc.greater(price,0),pc.greater(quantity,0)),pc.invert(pc.or_(placeholder,special)))


def scan(path,kind,start):
    counts=np.zeros(3600,np.int64);events=[];previous=None;rows=0;snapshots=0;zero_rows=0;outside=0;nonmarket=0;exchange=[];last_id=None;gaps=duplicates=0
    columns=['received_time','event_time','event_type','final_update_id','quantity'] if kind=='orderbook' else ['received_time','event_time','trade_time','trade_id','price','quantity','order_type','is_buyer_maker']
    for batch in pq.ParquetFile(path,page_checksum_verification=True).iter_batches(batch_size=65536,columns=columns):
        rows+=len(batch)
        if kind=='orderbook':
            updates=pc.equal(batch.column('event_type'),'update');snapshots+=int(pc.sum(pc.cast(pc.equal(batch.column('event_type'),'snapshot'),'int64')).as_py() or 0)
            b=batch.filter(updates)
            if not len(b):continue
            keys=np.column_stack([b.column(k).to_numpy(zero_copy_only=False) for k in ['received_time','event_time','final_update_id']]);mask,previous=event_starts(keys,previous);r=keys[mask,0];events.extend(r.tolist());exchange.extend((keys[mask,1]*10**6).tolist())
            zero_rows+=int(pc.sum(pc.cast(pc.equal(pc.cast(b.column('quantity'),'float64'),0),'int64')).as_py() or 0)
        else:
            b=batch.filter(market_mask(batch));nonmarket+=len(batch)-len(b)
            r=b.column('received_time').to_numpy(zero_copy_only=False);events.extend(r.tolist());exchange.extend((b.column('trade_time').to_numpy(zero_copy_only=False)*10**6).tolist())
            ids=batch.column('trade_id').to_numpy(zero_copy_only=False)
            if len(ids):
                seq=np.diff(np.r_[last_id,ids] if last_id is not None else ids);gaps+=int((seq>1).sum());duplicates+=int((seq<=0).sum());last_id=int(ids[-1])
        seconds=(r-start)//10**9;good=(seconds>=0)&(seconds<3600);outside+=int((~good).sum());np.add.at(counts,seconds[good],1)
    a=np.array(events,np.int64);e=np.array(exchange,np.int64);diff=np.diff(a)
    return {'raw_rows':rows,'snapshot_level_rows_excluded_from_delta_statistics':snapshots,'events_or_market_trades':len(a),'out_of_hour_events':outside,
        'per_received_second':summary(counts),'seconds_with_multiple_events':int((counts>1).sum()),'receipt_gap_ms':summary(diff/1e6),
        'zero_receipt_gap_count':int((diff==0).sum()),'backward_receipt_gap_count':int((diff<0).sum()),
        'receipt_minus_exchange_ms':summary((a-e)/1e6),'delta_zero_quantity_rows':zero_rows,
        'nonmarket_rows_excluded':nonmarket,'trade_id_gap_events':gaps,'trade_id_nonincreasing_events':duplicates,
        'event_resolution_scope':'Provider-emitted L2 update batches, not individual exchange orders' if kind=='orderbook' else 'Provider-retained market trade rows, not private order intentions'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=False);began=time.time()
    root=Path('data/btc-perp/cryptohftdata-monthly');manifest=root/'manifest.json';records=json.loads(manifest.read_text())
    hours=[(day,hour) for day in ['2026-10-05','2026-10-12'] for hour in ['00','12']]
    protocol={'hours':hours,'selection':'Fixed fit-period days and hours, no outcome or volatility-based choice','source_sha256':file_hash(Path(__file__)),'archive_manifest_sha256':file_hash(manifest),'training_started':False,'overwrite_existing_inputs':False}
    save(out/'protocol.json',protocol);results=[]
    for day,hour in hours:
        for kind in ['orderbook','trades']:
            key=f'binance_futures/{day}/{hour}/BTCUSDT_{kind}.parquet';matches=[r for r in records if r['remote_file']==key]
            if len(matches)!=1:raise ValueError('Missing/duplicate source inventory')
            record=matches[0];path=raw_path(root,record)
            if file_hash(path)!=record['sha256']:raise ValueError('Changed raw input')
            quality=json.loads((Path('data/btc-perp/validation-v2-20261102/hours')/day/hour/(key.split('/')[-1]+'.quality.json')).read_text())
            if quality['manifest_sha256']!=record['sha256']:raise ValueError('Quality provenance differs')
            with decoded(path,out) as plain:value=scan(plain,kind,hour_ns(key))
            if value['raw_rows']!=record['rows']:raise ValueError('Raw row total differs')
            if kind=='orderbook' and value['events_or_market_trades']!=quality['counts'].get('accepted_updates',0):raise ValueError('Diagnostic updates differ from accepted replay updates; sample requires further investigation')
            results.append({'UTC_hour':day+'T'+hour,'kind':kind,'source_sha256':record['sha256'],'quality_ok':quality.get('ok'),
                'prior_replay_accepted_updates':quality['counts'].get('accepted_updates') if kind=='orderbook' else None,
                'quality_clock_flags':{k:quality['counts'].get(k,0) for k in HARD_CLOCK+('backward_receipt_rows',)},**value})
            save(out/'status.json',{'state':'scanning','files_done':len(results),'files_total':8,'elapsed_seconds':time.time()-began});print(day,hour,kind,flush=True)
    save(out/'report.json',{'state':'complete','protocol':protocol,'hours':4,'files':8,'results':results,'elapsed_seconds':time.time()-began,
        'training_ready':False,'limitations':['Resolution diagnostic only; not a new event-book replay or proof of original receipt times.','L2 updates can batch many exchange changes; zero quantity does not identify cancellation versus execution.','No joins between book/trades, no hidden orders, no target labels inspected.','A four-hour fit-only sample does not establish month-wide continuity or forecast usefulness.']})
    save(out/'status.json',{'state':'complete','files_done':8,'elapsed_seconds':time.time()-began})


if __name__=='__main__':main()
