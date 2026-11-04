"""Independent raw-trade field audit and bounded causal row-index windows."""
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq
from .event_replay import DTYPE as BOOK
from .trade_events import DTYPE as TRADE
from .event_windows import window
from .validate_archive import file_hash,raw_path,decoded,hour_ns,save


def main():
    bookroot=Path('data/btc-perp/event-replay-preflight-20261104-v3');traderoot=Path('data/btc-perp/trade-events-preflight-20261104-v1');out=Path('data/btc-perp/event-window-preflight-20261104-v1');out.mkdir(parents=True,exist_ok=False)
    br=json.loads((bookroot/'report.json').read_text());tr=json.loads((traderoot/'report.json').read_text());archive=Path('data/btc-perp/cryptohftdata-monthly');records=json.loads((archive/'manifest.json').read_text());ledger=[];index=[];rejected=Counter()
    for bh,th in zip(br['hours'],tr['hours']):
        if bh['hour']!=th['hour']:raise ValueError('Mismatched event hours')
        name=bh['hour'];bp=bookroot/(name+'-events.bin');tp=traderoot/(name+'-events.bin')
        if file_hash(bp)!=bh['event_sha256'] or file_hash(tp)!=th['event_sha256']:raise ValueError('Changed event output')
        b=np.memmap(bp,dtype=BOOK,mode='r');t=np.memmap(tp,dtype=TRADE,mode='r');day,hour=name.split('T');key=f'binance_futures/{day}/{hour}/BTCUSDT_trades.parquet';record=next(r for r in records if r['remote_file']==key);raw=raw_path(archive,record)
        if file_hash(raw)!=th['source_sha256']:raise ValueError('Changed source trade bytes')
        cursor=0
        with decoded(raw,out) as plain:
            for batch in pq.ParquetFile(plain,page_checksum_verification=True).iter_batches(batch_size=65536):
                d=batch.to_pydict();part=t[cursor:cursor+len(batch)]
                for src,dst,scale in [('received_time','receipt_ns',1),('event_time','event_ns',10**6),('trade_time','trade_ns',10**6),('trade_id','trade_id',1)]:np.testing.assert_array_equal(part[dst],np.asarray(d[src],np.int64)*scale)
                for field in ['price','quantity']:
                    exact=np.fromiter((int(Decimal(v)*10**8) for v in d[field]),dtype=np.int64,count=len(batch));np.testing.assert_array_equal(part[field],exact)
                np.testing.assert_array_equal(part['buyer_maker'],[int(bool(v)) for v in d['is_buyer_maker']])
                special=np.array([kind in ['INSURANCE_FUND','ADL'] or (kind=='NA' and Decimal(p)==0 and Decimal(q)==0) for kind,p,q in zip(d['order_type'],d['price'],d['quantity'])]);np.testing.assert_array_equal(part['nonmarket'],special)
                cursor+=len(batch)
        if cursor!=len(t):raise ValueError('Independent trade row count mismatch')
        origin=hour_ns(key);count=0;counts=[]
        # Fixed input freezes only; no target outcomes or event-activity selection.
        for minute in [2,9,16,23,30,37,44,51]:
            cutoff=origin+(minute*60+15)*10**9
            try:w=window(b,t,cutoff-60*10**9,cutoff)
            except ValueError as error:rejected[str(error)]+=1;continue
            path=out/(name+f'-{minute:02d}-indices.npy');np.save(path,w['events']);count+=1;counts.append(len(w['events']))
            index.append({'hour':name,'snapshot_ns':cutoff,'start_ns':cutoff-60*10**9,'seed_row':w['book_seed_row'],'file':path.name,'sha256':file_hash(path),'book_events':w['book_events'],'trade_rows':w['trade_rows'],'market_trades':w['market_trades'],'truncated':False})
        ledger.append({'hour':name,'raw_trade_fields_exact_rows':cursor,'windows':count,'minimum_events':min(counts) if counts else None,'maximum_events':max(counts) if counts else None})
    save(out/'windows.json',index)
    save(out/'report.json',{'state':'complete','sources':{str(p):file_hash(p) for p in [Path(__file__),Path(__file__).with_name('event_windows.py'),bookroot/'report.json',traderoot/'report.json']},'hours':ledger,'windows':len(index),'rejections':dict(rejected),'retained_all_events_in_each_accepted_window':True,'cutoff':'strictly before freeze; prefix-max source availability; timestamp groups do not identify cross-feed causal order','training_ready':False,'limitations':['Four sampled fit-only hours; no sealed evaluation split yet.','Row-reference windows only, no fitted features or model.','One-second maximum accepted-update gap required.','No clipping/truncation; variable event counts need a suitable encoder.','Historical provider clock provenance remains unresolved.']})
    print(json.dumps({'windows':len(index),'rejected':dict(rejected),'independent_raw_trade_rows':sum(x['raw_trade_fields_exact_rows'] for x in ledger)}))


if __name__=='__main__':main()
