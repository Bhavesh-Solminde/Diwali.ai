"""Public read-only forward evidence: actual-receipt freezes and immutable forecasts."""
import argparse
import asyncio
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import time

import numpy as np
import torch

from .fan import FanModel,range_labels,direction
from .probability import probabilities
from ..market_data.frozen_inputs import SnapshotStore,write_snapshot,prediction_record
from ..market_data.collect import rest,retry,depth_session,market_session,housekeeping
from ..market_data.trade_alignment import additive,transform
from ..market_data.validate_archive import save,file_hash


def book_features(levels):
    bids=np.asarray(levels['bids'][:20],float);asks=np.asarray(levels['asks'][:20],float)
    if bids.shape!=(20,2) or asks.shape!=(20,2) or not np.isfinite(bids).all() or not np.isfinite(asks).all():raise ValueError('Invalid top20')
    if (bids<=0).any() or (asks<=0).any() or not (np.diff(bids[:,0])<0).all() or not (np.diff(asks[:,0])>0).all() or bids[0,0]>=asks[0,0]:raise ValueError('Unsorted/crossed book')
    if not levels.get('top20_within_snapshot_bounds'):raise ValueError('Unbounded top20')
    mid=(bids[0,0]+asks[0,0])/2;v=[]
    for b,a in zip(bids,asks):v.extend([(b[0]-mid)/mid*10000,np.log1p(b[1]),(a[0]-mid)/mid*10000,np.log1p(a[1])])
    bq=bids[:,1];aq=asks[:,1];imb=lambda n:float((bq[:n].sum()-aq[:n].sum())/(bq[:n].sum()+aq[:n].sum()))
    micro=(asks[0,0]*bq[0]+bids[0,0]*aq[0])/(bq[0]+aq[0])
    v.extend([(asks[0,0]-bids[0,0])/mid*10000,imb(1),imb(5),imb(20),np.log1p(bq.sum()),np.log1p(aq.sum()),(micro-mid)/mid*10000])
    return np.asarray(v,np.float32)


def live_input(request,scalers,prep):
    at=int(request['snapshot_utc_ns']);candles=request['candles'];books=request['book_seconds'];start,end=map(int,request['book_trade_window_ns'])
    if len(candles)!=1440 or len(books)!=60 or end-start!=60*10**9 or end>at:raise ValueError('Invalid live history shape')
    if (candles[-1]['close_ms']+1)*10**6 != (at//60_000_000_000)*60_000_000_000:raise ValueError('Latest completed candle unavailable')
    cf=[];previous=None
    for candle in candles:
        if candle['available_ns']>=at or (candle['close_ms']+1)*10**6>at:raise ValueError('Future/unreceived candle')
        if previous is not None and candle['open_ms']!=previous+60000:raise ValueError('Candle gap')
        previous=candle['open_ms'];o,h,l,c,v,q,n=map(float,candle['values'])
        if not np.isfinite([o,h,l,c,v,q,n]).all() or min(o,h,l,c)<=0 or min(v,q,n)<0 or h<max(o,c) or l>min(o,c):raise ValueError('Invalid candle')
        angle=(candle['open_ms']//60000%1440)/1440*2*np.pi
        cf.append([np.log(c/o),np.log(h/o),np.log(l/o),np.log1p(v),np.log1p(q),np.log1p(n),np.sin(angle),np.cos(angle)])
    bf=[]
    for i,row in enumerate(books):
        grid=start+i*10**9;b=row['book']
        if row['grid_utc_ns']!=grid or b['available_ns']>grid or b['source_receipt_ns']>grid or b['exchange_event_ms']*10**6>grid or grid-b['available_ns']>10**9:raise ValueError('Future/stale book')
        bf.append(book_features(b['levels']))
    bucket=[[] for _ in range(60)];latest=np.zeros(60,np.int64)
    for r in request['trades']:
        received=int(r['available_ns']);p=r['payload']
        if not start<=received<end or max(p['E'],p['T'])*10**6>=at:raise ValueError('Future/out-of-window execution')
        j=(received-start)//10**9;bucket[j].append((p['p'],p['q'],p['m']));latest[j]=max(latest[j],received)
    # Match archived float32 additive storage before the common nonlinear transform.
    values=np.asarray([additive(rows) for rows in bucket],np.float32).astype(np.float64)
    nonempty=np.flatnonzero(values[:,:2].sum(1)>0)
    if not len(nonempty):raise ValueError('No observed execution reference')
    j=nonempty[-1];age=(at-int(latest[j]))/1e9
    if age>2:raise ValueError('Observed execution reference older than2s')
    reference=values[j,2:].sum()/values[j,:2].sum();anchor=float(candles[-1]['values'][3])
    arrays=[np.asarray(cf,np.float32),np.asarray(bf,np.float32),transform(values,anchor)]
    pieces=[]
    for a,key in zip(arrays,['candles','book','trades']):
        s=scalers[key];pieces.append(((a-np.asarray(s['mean']))/np.asarray(s['std'])).astype(np.float32).ravel())
    delta=((reference/anchor-1)*10000-prep['delta_mean'])/prep['delta_std']
    x=np.concatenate(pieces+[np.asarray([delta],np.float32)])
    if not np.isfinite(x).all():raise ValueError('Nonfinite live input')
    return x,{'reference':float(reference),'reference_age_seconds':float(age),'last_candle_source':candles[-1]['source']}


class Predictor:
    def __init__(self,run):
        self.run=run;self.report=json.loads((run/'report.json').read_text());mode=self.report['selected_mode'];self.info=self.report['models'][mode]
        self.prep=json.loads((run/'preprocessing.json').read_text());aligned=Path('data/btc-perp/aligned-button-pilot-202610-v1/scalers.json')
        if file_hash(aligned)!=self.prep['aligned_scaler_sha256']:raise ValueError('Changed live scaler')
        self.scalers=json.loads(aligned.read_text());path=run/f'{mode}-17.pt'
        if file_hash(path)!=self.info['checkpoint_sha256']:raise ValueError('Changed live checkpoint')
        state=torch.load(path,map_location='cpu',weights_only=True);self.model=FanModel();self.model.load_state_dict(state['state_dict']);self.model.eval();torch.set_num_threads(4)
        self.provenance={'model':'diwali0.5','mode':mode,'checkpoint_sha256':file_hash(path),'report_sha256':file_hash(run/'report.json'),'source_sha256':file_hash(Path(__file__))}

    def predict(self,request):
        x,metadata=live_input(request,self.scalers,self.prep)
        with torch.inference_mode():z,c=self.model(torch.from_numpy(x[None]));z=z.numpy()[0]
        p=np.array([probabilities(z[h],self.info['temperatures'][h]) for h in range(15)])
        return {'bin_probabilities':p.tolist(),'direction_probabilities':direction(p).tolist(),**metadata,
                'target_close_ns':[request['target_start_ns']+(h+1)*60_000_000_000 for h in range(15)],
                'scope':'15 marginal future closes; no orders placed','provenance':self.provenance}


def exclusive_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);data=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    with path.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    return hashlib.sha256(data).hexdigest()


class ForwardStore(SnapshotStore):
    def __init__(self,root,run):
        super().__init__(root);self.run=run;self.predictor=None;self.pending={};self.outcomes=[];self.forecasts=0;self.forward_rejections=Counter()

    def score_matured(self):
        now=time.time_ns()
        for key,item in list(self.pending.items()):
            record=item['record'];p=np.asarray(record['prediction']['bin_probabilities']);ref=record['prediction']['reference']
            for h in range(15):
                if h in item['done']:continue
                start=record['target_start_ns']//10**6+h*60000;candle=self.inputs.candles.get(start)
                if not candle or candle['available_ns']>now or (candle['close_ms']+1)*10**6>now:continue
                ret=(float(candle['values'][3])/ref-1)*10000;b=int(range_labels(ret));y=0 if ret<=-2 else 2 if ret>=2 else 1
                result={'forecast_file':key,'horizon':h+1,'target_start_ms':start,'actual_close':float(candle['values'][3]),'actual_return_bp':float(ret),
                    'actual_bin':b,'actual_class':y,'actual_available_ns':candle['available_ns'],'actual_source':candle['source'],
                    'scored_utc_ns':now,'bin_log_loss':float(-np.log(max(p[h,b],1e-15))),
                    'direction_log_loss':float(-np.log(max(direction(p[h])[y],1e-15))),
                    'direction_correct':bool(direction(p[h]).argmax()==y)}
                exclusive_json(self.root/'outcomes'/f'{Path(key).stem}-h{h+1}.json',result)
                self.outcomes.append(result);item['done'].add(h)
            if len(item['done'])==15:del self.pending[key]
        summary={}
        for h in range(1,16):
            rows=[r for r in self.outcomes if r['horizon']==h]
            if rows:summary[str(h)]={'n':len(rows),'bin_log_loss':float(np.mean([r['bin_log_loss'] for r in rows])),
                'direction_log_loss':float(np.mean([r['direction_log_loss'] for r in rows])),'direction_accuracy':float(np.mean([r['direction_correct'] for r in rows]))}
        save(self.root/'forward-status.json',{'forecasts_saved_before_target':self.forecasts,'pending_forecasts':len(self.pending),'matured_horizons':summary,
             'rejections':dict(self.forward_rejections),'model_ready':self.predictor is not None,'orders_placed':False,'updated_utc_ns':now,
             'limitations':'Small prospective sample, correlated overlapping horizons; no perfect/calibrated-market guarantee.'})

    async def snapshots(self):
        while True:
            now=time.time();next_phase=(int(now)//60)*60+15
            if next_phase<=now:next_phase+=60
            await asyncio.sleep(max(0,next_phase-now));at=time.time_ns();mono=time.monotonic_ns()
            try:
                request=self.inputs.freeze(at,mono);stored=write_snapshot(self.root/'frozen-inputs',request);self.save('input_snapshot',stored);self.snapshot_count+=1
                if self.predictor is None:
                    if not (self.run/'report.json').exists():raise ValueError('model_not_ready_yet')
                    self.predictor=Predictor(self.run)
                forecast=self.predictor.predict(request);record=prediction_record(request,forecast,'diwali0.5',time.time_ns(),time.monotonic_ns())
                name=f'{at}-diwali0.5.json';digest=exclusive_json(self.root/'predictions'/name,record)
                if time.time_ns()>=request['target_start_ns']:raise ValueError('forecast_commit_missed_target_deadline')
                self.save('forecast_saved',{'file':name,'sha256':digest,'input_sha256':record['input_sha256'],'target_start_ns':record['target_start_ns']})
                self.forecasts+=1;self.pending[name]={'record':record,'done':set()}
            except ValueError as exc:
                self.forward_rejections[str(exc)]+=1;self.save('forward_rejected',{'reason':str(exc),'snapshot_utc_ns':at})
            self.score_matured()


async def capture(root,run,seconds):
    store=ForwardStore(root,run);tasks=[]
    try:
        metadata=await rest(store,'/fapi/v1/exchangeInfo');symbol=next(s for s in metadata['symbols'] if s['symbol']=='BTCUSDT')
        if symbol['contractType']!='PERPETUAL' or symbol['status']!='TRADING':raise ValueError('Unexpected instrument/status')
        tasks=[asyncio.create_task(retry(store,'depth',depth_session)),asyncio.create_task(retry(store,'market',market_session)),
               asyncio.create_task(housekeeping(store)),asyncio.create_task(store.snapshots())]
        store.status('recording')
        # A failed recorder must not silently leave a healthy-looking session.
        done,_=await asyncio.wait(tasks,timeout=seconds,return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            error=task.exception()
            if error is not None:
                store.save('forward_capture_failed',{'error_type':type(error).__name__,'reason':str(error)})
                raise error
            raise RuntimeError('Forward recording task ended unexpectedly')
    finally:
        for task in tasks:task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True);store.score_matured();store.finish()


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,default=Path('data/models/diwali0.5'));p.add_argument('--output',type=Path,required=True);p.add_argument('--seconds',type=int,default=3600);a=p.parse_args()
    if a.seconds<=0:raise ValueError('Positive duration required')
    asyncio.run(capture(a.output,a.run,a.seconds))


if __name__=='__main__':main()
