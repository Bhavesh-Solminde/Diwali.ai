"""Actual-receipt input freezes for next-full-minute forecasts; does not run a model."""
import asyncio
from collections import deque
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import time
from .collect import Store
from .validate_archive import save

MINUTE=60_000_000_000


def target_after(snapshot_ns):
    return (snapshot_ns//MINUTE+1)*MINUTE


def ready_before_target(ready_ns,target_ns):
    return ready_ns<target_ns


class FrozenInputs:
    def __init__(self):
        self.candles={};self.book=None;self.book_history=deque();self.trades=deque();self.market_since=None
        self.gap_since=None;self.clock_fault=False;self.server_probe=None

    def ingest(self,row):
        kind,p=row['kind'],row['payload'];at=row['receipt_utc_ns'];mono=row['receipt_monotonic_ns']
        if row.get('clock_step_ns'):
            self.clock_fault=True
        if kind=='connection' and p.get('stream')=='market':
            self.market_since=at;self.gap_since=at;self.trades.clear()
        if kind=='connection_error':
            if p.get('stream')=='depth':self.book=None;self.book_history.clear()
            if p.get('stream')=='market':self.market_since=None;self.trades.clear()
        if kind=='book_invalidated':self.book=None;self.book_history.clear()
        if kind=='trade_gap_or_reorder':self.gap_since=at
        if kind=='book':
            self.book={'available_ns':at,'source_receipt_ns':row['source_receipt_utc_ns'],
                'exchange_event_ms':row.get('exchange_event_ms'),'connection':row['connection'],
                'snapshot_id':row['snapshot_id'],'levels':p}
            self.book_history.append(self.book)
        if kind=='market' and p.get('e')=='aggTrade':
            if p['T']*10**6>at or p['E']*10**6>at:self.gap_since=at
            self.trades.append({'available_ns':at,'receipt_monotonic_ns':mono,'payload':p})
        if kind=='market' and p.get('e')=='kline' and p['k'].get('x'):
            k=p['k']
            self.candles[k['t']]={'open_ms':k['t'],'close_ms':k['T'],'values':
                [k['o'],k['h'],k['l'],k['c'],k['v'],k['q'],k['n']],
                'available_ns':at,'source':'received_closed_websocket_kline'}
        if kind=='rest' and row.get('path')=='/fapi/v1/time':
            self.server_probe=(p['serverTime'],mono)
        if kind=='rest' and '/klines?' in row.get('path','') and self.server_probe:
            # A conservative server-clock lower bound at receipt, avoiding treating
            # the still-open REST row as finalized using the Mac's clock alone.
            server_lower=self.server_probe[0]+max(0,mono-self.server_probe[1])//10**6
            for k in p:
                if k[6]>=server_lower:continue
                old=self.candles.get(k[0])
                values=[k[1],k[2],k[3],k[4],k[5],k[7],k[8]]
                if old and old['values']==values:continue
                self.candles[k[0]]={'open_ms':k[0],'close_ms':k[6],'values':values,
                    'available_ns':at,'source':'received_closed_rest_kline'}
        while self.trades and self.trades[0]['available_ns']<at-120*10**9:self.trades.popleft()
        while self.book_history and self.book_history[0]['available_ns']<at-120*10**9:self.book_history.popleft()
        if len(self.candles)>1600:
            for key in sorted(self.candles)[:-1600]:del self.candles[key]

    def freeze(self,at,mono):
        if self.clock_fault:raise ValueError('clock_step_requires_new_capture')
        if self.market_since is None or at-self.market_since<60*10**9:
            raise ValueError('need_60_seconds_continuous_trade_capture')
        if self.gap_since is not None and at-self.gap_since<60*10**9:
            raise ValueError('recent_trade_gap')
        b=self.book
        if not b or not 0<=at-b['available_ns']<=10**9 or b['available_ns']>=at:
            raise ValueError('book_unavailable_stale_or_not_before_freeze')
        if b['exchange_event_ms'] is None or b['exchange_event_ms']*10**6>=at:
            raise ValueError('book_exchange_time_not_before_freeze')
        if b['source_receipt_ns']>=at:raise ValueError('future_book_source')
        if min(len(b['levels']['bids']),len(b['levels']['asks']))<20:raise ValueError('insufficient_top20')
        if not b['levels'].get('top20_within_snapshot_bounds',False):raise ValueError('top20_outside_verified_snapshot_bounds')
        available=[k for k,v in self.candles.items() if v['available_ns']<at and (v['close_ms']+1)*10**6<=at]
        if not available:raise ValueError('no_received_closed_candles')
        last=max(available);keys=list(range(last-1439*60000,last+1,60000))
        if any(k not in self.candles or self.candles[k]['available_ns']>=at for k in keys):
            raise ValueError('incomplete_received_1440_candle_history')
        if at-(last+60000)*10**6>120*10**9:raise ValueError('candle_history_too_stale')
        candles=[self.candles[k] for k in keys]
        for c in candles:
            o,h,l,cl,v,q,n=map(Decimal,map(str,c['values']))
            if min(o,h,l,cl)<=0 or min(v,q,n)<0 or h<max(o,cl) or l>min(o,cl):raise ValueError('invalid_received_candle')
        second_end=at//10**9*10**9;second_start=second_end-60*10**9
        history=list(self.book_history);cursor=0;previous=None;book_seconds=[]
        for grid in range(second_start,second_end,10**9):
            while cursor<len(history) and history[cursor]['available_ns']<=grid:
                previous=history[cursor];cursor+=1
            if previous is None or grid-previous['available_ns']>10**9:
                raise ValueError('incomplete_fresh_60_second_book_history')
            if previous['exchange_event_ms'] is None or previous['exchange_event_ms']*10**6>grid:
                raise ValueError('future_book_history_event')
            if previous['source_receipt_ns']>grid or min(len(previous['levels']['bids']),len(previous['levels']['asks']))<20 or not previous['levels'].get('top20_within_snapshot_bounds',False):
                raise ValueError('unavailable_book_history')
            book_seconds.append({'grid_utc_ns':grid,'book':previous})
        trades=[r for r in self.trades if second_start<=r['available_ns']<second_end]
        if any(r['payload']['T']*10**6>=at or r['payload']['E']*10**6>=at for r in trades):
            raise ValueError('future_trade_event')
        result={'snapshot_utc_ns':at,'snapshot_monotonic_ns':mono,'target_start_ns':target_after(at),
            'target_end_ns':target_after(at)+MINUTE,'candles':candles,'book':b,
            'book_seconds':book_seconds,'book_trade_window_ns':[second_start,second_end],'trades':trades,
            'availability_policy':'actual recorded receipt; no synthetic historical timestamps',
            'prediction_generated':False,'training_ready':False,
            'limitations':['Aggregate trades are not complete individual executions.',
                'Single-recorder finite top20 view; no complete or hidden liquidity claim.',
                'Capture chronology and labels still require quality review before training.']}
        # Roundtrip breaks all references to mutable caches. Updates arriving later
        # cannot alter a frozen request that is waiting for model calculation.
        return json.loads(json.dumps(result,separators=(',',':')))


def write_snapshot(root,snapshot):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    data=json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()
    digest=hashlib.sha256(data).hexdigest()
    path=root/f"{snapshot['snapshot_utc_ns']}-{digest[:12]}.json"
    # Exclusive create: never overwrite an existing request.
    with path.open('xb') as f:f.write(data)
    return {'snapshot_file':path.name,'sha256':digest,'snapshot_utc_ns':snapshot['snapshot_utc_ns'],
        'target_start_ns':snapshot['target_start_ns'],'prediction_generated':False}


class SnapshotStore(Store):
    def __init__(self,root):
        super().__init__(root);self.inputs=FrozenInputs();self.snapshot_count=0;self.rejections={}
    def save(self,kind,payload,**extra):
        row=super().save(kind,payload,**extra);self.inputs.ingest(row);return row
    async def snapshots(self,every):
        while True:
            await asyncio.sleep(every)
            at,mono=time.time_ns(),time.monotonic_ns()
            try:
                request=self.inputs.freeze(at,mono)
                stored=write_snapshot(self.root/'frozen-inputs',request)
                super().save('input_snapshot',stored)
                self.snapshot_count+=1
            except ValueError as exc:
                reason=str(exc);self.rejections[reason]=self.rejections.get(reason,0)+1
                super().save('input_snapshot_rejected',{'reason':reason,'snapshot_utc_ns':at})
            save(self.root/'snapshot-status.json',{'snapshots_saved':self.snapshot_count,
                'rejections':self.rejections,'prediction_generated':False,'orders_placed':False})


def prediction_record(request, prediction, model_id, ready_utc_ns, ready_monotonic_ns):
    """Future model/UI integration must use this guard; never backdate a result."""
    if ready_utc_ns<request['snapshot_utc_ns'] or ready_monotonic_ns<request['snapshot_monotonic_ns']:
        raise ValueError('prediction_ready_time_precedes_input_freeze')
    if not ready_before_target(ready_utc_ns,request['target_start_ns']):
        raise ValueError('prediction_ready_at_or_after_target_start')
    encoded=json.dumps(request,sort_keys=True,separators=(',',':')).encode()
    return {'input_sha256':hashlib.sha256(encoded).hexdigest(),'model_id':model_id,
        'snapshot_utc_ns':request['snapshot_utc_ns'],'ready_utc_ns':ready_utc_ns,
        'ready_monotonic_ns':ready_monotonic_ns,'target_start_ns':request['target_start_ns'],
        'target_end_ns':request['target_end_ns'],'prediction':json.loads(json.dumps(prediction)),
        'calculation_seconds':(ready_monotonic_ns-request['snapshot_monotonic_ns'])/1e9}
