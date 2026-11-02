"""Experimental autoregressive OHLC rollout, without future observations."""
import hashlib
import numpy as np
import torch
from ..market_data.build_pilot import WARMUP
from ..market_data.trade_alignment import transform


def candle_features(ohlc,volume,quote,count,minute_ms):
    o,h,l,c=map(float,ohlc)
    if min(o,h,l,c)<=0 or h<max(o,c) or l>min(o,c):raise ValueError('Invalid generated candle')
    angle=(minute_ms//60000%1440)/1440*2*np.pi
    return np.asarray([np.log(c/o),np.log(h/o),np.log(l/o),np.log1p(volume),
        np.log1p(quote),np.log1p(count),np.sin(angle),np.cos(angle)],dtype=np.float32)


def rollout(data,model,row,steps=15):
    if not 1<=steps<=15:raise ValueError('Horizon must be 1 to 15')
    ci,b,e=map(int,(row[2],row[3],row[4]));target=int(row[1])
    candles=np.array(data.candles[ci-1440:ci],copy=True)
    last=np.array(data.raw[ci-1],dtype=float,copy=True)
    book=np.array(data.book[b:e]['x'],copy=True)
    trades=np.array(data.trades[b:e]['x'][:,:4],dtype=np.float64,copy=True)
    last_minute=WARMUP+(ci-1)*60000
    results=[];bridges=[];feedback=[];input_hashes=[]
    def append(ohlc,minute):
        nonlocal candles,last,last_minute
        # Only non-price inputs are carried forward; no future volume/count read.
        feature=candle_features(ohlc,last[4],last[5],last[6],minute)
        candles=np.concatenate((candles[1:],feature[None]),axis=0)
        last=np.asarray([*ohlc,*last[4:]],dtype=float);last_minute=minute
    model.eval()
    for step in range(steps):
        anchor=float(last[3]);arrays=[candles,book,transform(trades,anchor)];normalized=[]
        for values,key in zip(arrays,('candles','book','trades')):
            s=data.scalers[key];normalized.append(((values-np.asarray(s['mean']))/np.asarray(s['std'])).astype(np.float32).ravel())
        x=np.concatenate(normalized)
        if not np.isfinite(x).all():raise ValueError('Invalid recursive input')
        input_hashes.append(hashlib.sha256(x.tobytes()).hexdigest())
        with torch.inference_mode():bp=model(torch.from_numpy(x[None])).cpu().numpy()[0]
        predicted=anchor*(1+bp.astype(float)/10000)
        minute=target+step*60000
        if not np.isfinite(predicted).all():raise ValueError('Nonfinite forecast')
        # Initial next-full-minute task has an unobserved in-progress minute.
        # Preserve consecutive context explicitly with a labelled flat-price bridge.
        while last_minute+60000<minute:
            flat=[float(last[3])]*4;bridges.append({'time':last_minute+60000,'ohlc':flat,'source':'flat_price_bridge_not_observed'})
            append(flat,last_minute+60000)
        results.append({'step':step+1,'time':minute,'ohlc':predicted.tolist()})
        append(predicted,minute)
        feedback.append({'step':step+1,'last_context_time':last_minute,
            'last_context_ohlc':last[:4].tolist(),'context_length':len(candles)})
    return {'candles':results,'bridges':bridges,'feedback':feedback,'input_sha256_by_step':input_hashes,
        'assumptions':['Book/trade observations stay fixed at original snapshot; no future messages are loaded.',
            'Volume, quote volume and execution count carry forward from last input candle.',
            'Unobserved in-progress minute uses a flat-price bridge before first forecast feedback.',
            'Steps 2–15 use a different inference lead/context from training; errors can compound.'],
        'future_actuals_used':False,'uncertainty_calibrated_for_15_steps':False}
