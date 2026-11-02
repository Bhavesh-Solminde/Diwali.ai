"""Common additive trade features: deliberately exclude execution/message counts."""
import argparse
import asyncio
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import time
import urllib.request
import numpy as np
from websockets.asyncio.client import connect
from .build_pilot import feature_dtype,fit_scaler
from .validate_archive import file_hash,save

NAMES=['log1p_buy_btc','log1p_sell_btc','log1p_buy_usdt','log1p_sell_usdt','vwap_vs_candle_close_bp']


def additive(rows):
    """Rows are (price, quantity, buyer_is_maker); invariant to splitting same-side/price fills."""
    total=[Decimal(0) for _ in range(4)]
    for price,qty,maker in rows:
        p,q=Decimal(str(price)),Decimal(str(qty))
        if not p.is_finite() or not q.is_finite() or p<=0 or q<=0 or not isinstance(maker,bool):
            raise ValueError('Invalid trade input')
        side=int(maker);total[side]+=q;total[side+2]+=p*q
    return total


def transform(values,anchor):
    a=np.asarray(values,dtype=np.float64)
    if a.shape[-1]!=4 or not np.isfinite(a).all() or (a<0).any() or anchor<=0:
        raise ValueError('Invalid common trade features')
    qty=a[...,0]+a[...,1];notional=a[...,2]+a[...,3]
    vwap=np.divide(notional,qty,out=np.zeros_like(qty),where=qty>0)
    offset=np.where(qty>0,(vwap/anchor-1)*10000,0)
    return np.concatenate([np.log1p(a),offset[...,None]],axis=-1)


def live_features(request,anchor):
    start,end=request['book_trade_window_ns'];values=np.zeros((60,4),np.float64)
    for r in request['trades']:
        at=r['available_ns'];p=r['payload']
        if not start<=at<end or max(p['E'],p['T'])*10**6>=request['snapshot_utc_ns']:
            raise ValueError('Out-of-window/future trade')
        # q includes all reported market volume; nq explicitly excludes RPI.
        values[(at-start)//10**9]+=np.asarray(additive([(p['p'],p['q'],p['m'])]),np.float64)
    return transform(values,anchor)


def prepare(dataset,output):
    output.mkdir(parents=True,exist_ok=True)
    m=json.loads((dataset/'dataset-manifest.json').read_text())
    for name,sha in m['artifact_sha256'].items():
        if file_hash(dataset/name)!=sha:raise ValueError('Frozen dataset artifact changed')
    source=Path(m['trade_source']);expected=json.loads((source.parent/'trades-extraction.json').read_text())['sha256']
    if file_hash(source)!=expected:raise ValueError('Trade source changed')
    trades=np.memmap(source,mode='r',dtype=feature_dtype('trades'))
    raw=np.load(dataset/'candle-raw.npy');indices=np.load(dataset/'fit-phase15-grace1000-indices.npy')
    scaler=fit_scaler((transform(trades[r[3]:r[4]]['x'][:,:4],raw[r[2]-1,3]) for r in indices),5)
    old=json.loads((dataset/'scalers.json').read_text())
    save(output/'scalers.json',{'candles':old['candles'],'book':old['book'],'trades':scaler,
        'fit_partition_only':True,'source':'fit primary windows only','trade_names':NAMES})
    contract={'state':'aligned_features_prepared','parent_dataset_fingerprint':m['fingerprint'],
        'parent_dataset':str(dataset.resolve()),'trade_names':NAMES,'trade_width':5,
        'removed':['individual_execution_count','buy_execution_count','sell_execution_count','aggregate_message_count'],
        'quantity_field_live':'q (not nq)','bucketing':'60 complete local receipt-second buckets before freeze',
        'common_transform':'trade_alignment.transform, using latest input candle close as anchor',
        'fit_origin_hash':file_hash(dataset/'fit-phase15-grace1000-indices.npy'),
        'scaler_sha256':file_hash(output/'scalers.json'),'code_sha256':file_hash(Path(__file__)),
        'limitations':['Receipt-time grouping/latency can differ between recorders and aggregate/individual delivery.',
            'Matching complete execution groups demonstrates additive definitions, not identical cross-recorder seconds.',
            'Historical candle availability remains assumed.'], 'neural_training_started':False}
    save(output/'alignment-contract.json',contract)
    return contract


def probe_gate(matched,bundled,total,mismatches,errors):
    return matched>=100 and bundled>=10 and total>0 and matched/total>=.95 and not mismatches and not errors


async def probe(output,seconds):
    output.mkdir(parents=True,exist_ok=False);groups={};fills={};errors=[];receipts=[];began=time.monotonic()
    async def ws():
        async with connect('wss://fstream.binance.com/market/stream?streams=btcusdt@aggTrade',open_timeout=12) as stream:
            while True:
                row=json.loads(await stream.recv())['data'];at=time.time_ns()
                if row.get('e')!='aggTrade':continue
                groups[row['a']]=row;receipts.append({'kind':'aggregate','receipt_ns':at,'payload':row})
    async def poll():
        while True:
            def fetch():
                with urllib.request.urlopen('https://fapi.binance.com/fapi/v1/trades?symbol=BTCUSDT&limit=1000',timeout=12) as r:return json.load(r)
            try:
                rows=await asyncio.to_thread(fetch);at=time.time_ns()
                receipts.append({'kind':'individual_rest','receipt_ns':at,'payload':rows})
                for row in rows:
                    if row['id'] in fills and fills[row['id']]!=row:raise ValueError('Conflicting REST trade ID')
                    fills[row['id']]=row
            except Exception as exc:errors.append(type(exc).__name__)
            await asyncio.sleep(2)
    tasks=[asyncio.create_task(ws()),asyncio.create_task(poll())]
    await asyncio.sleep(seconds)
    for task in tasks:task.cancel()
    results=await asyncio.gather(*tasks,return_exceptions=True)
    for r in results:
        if isinstance(r,Exception) and not isinstance(r,asyncio.CancelledError):errors.append(repr(r))
    matched=0;missing=0;mismatches=[];bundled=0;execution_count=0;rpi_different=0
    for a,g in groups.items():
        ids=range(g['f'],g['l']+1)
        if len(ids)>10000 or any(i not in fills for i in ids):missing+=1;continue
        rows=[fills[i] for i in ids]
        expected=additive([(r['price'],r['qty'],r['isBuyerMaker']) for r in rows])
        actual=additive([(g['p'],g['q'],g['m'])])
        if actual!=expected:mismatches.append(a);continue
        matched+=1;execution_count+=len(rows);bundled+=len(rows)>1
        rpi_different+=g.get('nq',g['q'])!=g['q']
    raw=output/'raw-messages.json';save(raw,receipts)
    summary={'state':'pass' if probe_gate(matched,bundled,len(groups),mismatches,errors) else 'needs_review',
        'acceptance':'at least 100 complete groups, 10 bundled, 95% complete coverage; zero mismatches/errors',
        'duration_seconds':round(time.monotonic()-began,2),'aggregate_messages':len(groups),
        'individual_ids_observed':len(fills),'complete_groups_matched':matched,'bundled_groups_matched':bundled,
        'matched_executions':execution_count,'incomplete_groups_excluded':missing,'mismatching_group_count':len(mismatches),
        'groups_q_differs_from_nq':rpi_different,'errors':errors,'raw_sha256':file_hash(raw),
        'comparison':'exact Decimal buy/sell quantity and notional, same native execution-ID groups',
        'not_proven':'Identical receipt-time buckets across recorders; historical arrival authenticity'}
    save(output/'probe-summary.json',summary);print(json.dumps(summary,indent=2));return summary

if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='action',required=True)
    a=sub.add_parser('prepare');a.add_argument('dataset',type=Path);a.add_argument('output',type=Path)
    b=sub.add_parser('probe');b.add_argument('output',type=Path);b.add_argument('--seconds',type=int,default=90)
    args=p.parse_args()
    if args.action=='probe':asyncio.run(probe(args.output,args.seconds))
    else:print(json.dumps(prepare(args.dataset,args.output),indent=2))
