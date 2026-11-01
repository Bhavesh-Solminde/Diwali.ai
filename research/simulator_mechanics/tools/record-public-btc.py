"""Bounded public Binance USD-M BTCUSDT engineering recorder. No credentials/orders."""
import argparse
import asyncio
import gzip
import hashlib
import json
import time
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from websockets.asyncio.client import connect


async def record(output, seconds):
    output.mkdir(parents=True,exist_ok=False)
    counts=Counter();errors=[];start=time.time_ns();stop=time.monotonic()+seconds
    stream=gzip.open(output/'raw.jsonl.gz','wt',encoding='utf-8')
    first_depth=asyncio.Event()
    def save(kind,payload,**extra):
        counts[kind]+=1
        stream.write(json.dumps(dict(kind=kind,receipt_utc_ns=time.time_ns(),receipt_monotonic_ns=time.monotonic_ns(),payload=payload,**extra))+'\n')
        stream.flush()
    async def rest(path):
        url='https://fapi.binance.com'+path
        sent=time.time_ns()
        try:
            def fetch():
                with urllib.request.urlopen(url,timeout=12) as r:return json.load(r)
            data=await asyncio.to_thread(fetch)
            save('rest',data,url=url,request_utc_ns=sent)
            return data
        except Exception as e:
            errors.append(dict(url=url,error=type(e).__name__,detail=str(e)))
            save('rest_error',str(e),url=url,request_utc_ns=sent)
    async def socket(label,url):
        try:
            async with connect(url,open_timeout=12,ping_interval=20,ping_timeout=20,max_size=4*1024*1024) as ws:
                save('connection',dict(label=label,url=url))
                while time.monotonic()<stop:
                    try:
                        msg=await asyncio.wait_for(ws.recv(),timeout=min(15,max(.1,stop-time.monotonic())))
                    except asyncio.TimeoutError:
                        if time.monotonic()>=stop:break
                        save('silence',dict(label=label));continue
                    obj=json.loads(msg);save(label,obj)
                    payload=obj.get('data',obj)
                    if payload.get('e')=='depthUpdate':first_depth.set()
        except Exception as e:
            errors.append(dict(connection=label,error=type(e).__name__,detail=str(e)))
            save('connection_error',dict(label=label,error=type(e).__name__,detail=str(e)))
    async def snapshots():
        await rest('/fapi/v1/time')
        await rest('/fapi/v1/exchangeInfo?symbol=BTCUSDT')
        await rest('/fapi/v1/klines?symbol=BTCUSDT&interval=1m&limit=1500')
        try:
            await asyncio.wait_for(first_depth.wait(),timeout=20)
            await rest('/fapi/v1/depth?symbol=BTCUSDT&limit=1000')
        except asyncio.TimeoutError:
            errors.append(dict(error='NoDepthForSnapshot',detail='No depth event within20s'))
    try:
        await asyncio.gather(socket('public','wss://fstream.binance.com/public/stream?streams=btcusdt@depth@100ms'),
            socket('market','wss://fstream.binance.com/market/stream?streams=btcusdt@aggTrade/btcusdt@kline_1m'),snapshots())
        await rest('/fapi/v1/klines?symbol=BTCUSDT&interval=1m&limit=10')
    finally:
        stream.close()
        manifest=dict(venue='Binance USD-M futures',instrument='BTCUSDT perpetual',scope='bounded_engineering_capture_not_training_dataset',
            requested_seconds=seconds,start_utc_ns=start,end_utc_ns=time.time_ns(),counts=dict(counts),errors=errors,
            complete_ordered_execution_feed=False,reason='aggTrade excludes insurance/ADL trades and is aggregated; exact all-trade coverage not certified',
            reconnect_policy='No silent reconnection. A connection failure terminates that stream and is retained; gaps invalidate derived book segments.',
            credentials_used=False,orders_placed=False,raw_sha256=hashlib.sha256((output/'raw.jsonl.gz').read_bytes()).hexdigest())
        (output/'manifest.json').write_text(json.dumps(manifest,indent=2))
        print(json.dumps(manifest,indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);p.add_argument('--seconds',type=int,default=300)
    a=p.parse_args()
    if not 1<=a.seconds<=300:raise ValueError('bounded capture must be1..300seconds')
    asyncio.run(record(a.output,a.seconds))
