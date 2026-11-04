"""Incremental candles from available trades; never use finalized future input bars."""
import math
import numpy as np

SECOND=10**9
MINUTE=60*SECOND
SCALE=10**8


class CandleTape:
    def __init__(self):
        self.minutes={};self.last_available=-1;self.last_id=-1;self.previous_trade_ns=None;self.flow_second=-1;self.flow_quantity=0;self.flow_notional=0;self.flow_last_available=-1
    def ingest(self,row,available_ns):
        at=int(available_ns);receipt=int(row['receipt_ns']);event=max(int(row['event_ns']),int(row['trade_ns']))
        if at<max(receipt,event) or at<self.last_available:raise ValueError('Future/backward trade availability')
        self.last_available=at;minute=int(row['trade_ns'])//MINUTE*MINUTE;bad=bool(row['bad'])
        ident=int(row['trade_id'])
        if self.last_id>=0 and ident!=self.last_id+1:
            bad=True
            lo=min(self.previous_trade_ns,int(row['trade_ns']))//MINUTE*MINUTE;hi=max(self.previous_trade_ns,int(row['trade_ns']))//MINUTE*MINUTE
            if hi-lo>120*MINUTE:raise ValueError('Unbounded trade gap span')
            for touched in range(lo,hi+MINUTE,MINUTE):
                self.minutes.setdefault(touched,{'bad':True,'n':0})['bad']=True
        self.last_id=ident
        self.previous_trade_ns=int(row['trade_ns'])
        bar=self.minutes.get(minute)
        if bad:
            if bar is None:self.minutes[minute]={'bad':True,'n':0}
            else:bar['bad']=True
            return
        if row['nonmarket']:return
        price=int(row['price']);quantity=int(row['quantity'])
        if price<=0 or quantity<=0:raise ValueError('Invalid market fill')
        if bar is None:
            bar={'bad':False,'n':0,'first':ident,'last':ident,'o':price,'h':price,'l':price,'c':price,'v':0,'q':0};self.minutes[minute]=bar
        if not bar['n'] and bar['bad']:return
        if ident<bar['first']:bar['first']=ident;bar['o']=price
        if ident>=bar['last']:bar['last']=ident;bar['c']=price
        bar['h']=max(bar['h'],price);bar['l']=min(bar['l'],price);bar['v']+=quantity;bar['q']+=price*quantity;bar['n']+=1
        sec=at//SECOND
        if sec!=self.flow_second:self.flow_second=sec;self.flow_quantity=0;self.flow_notional=0
        self.flow_quantity+=quantity;self.flow_notional+=price*quantity
        self.flow_last_available=at
    def snapshot(self,cutoff_ns,history=1440,mask_context=False):
        at=int(cutoff_ns)
        if at<=self.last_available:raise ValueError('Trade at/after input freeze')
        if self.flow_second<0 or self.flow_quantity<=0 or at-(self.flow_second+1)*SECOND<0 or at-self.flow_last_available>2*SECOND:raise ValueError('No fresh completed-second reference')
        last=at//MINUTE*MINUTE-MINUTE;times=last-np.arange(history-1,-1,-1,dtype=np.int64)*MINUTE
        bars=[self.minutes.get(int(t)) for t in times]
        valid=np.array([b is not None and b['n']>0 and not b['bad'] for b in bars],bool)
        if not mask_context:
            if any(b is None or not b['n'] for b in bars):raise ValueError('Missing completed candle')
            if not valid.all():raise ValueError('Invalid completed candle')
        if mask_context and (valid.mean()<.99 or not valid[-1]):raise ValueError('Insufficient99percent context or missing latest candle')
        x=np.array([[math.log(b['c']/b['o']),math.log(b['h']/b['o']),math.log(b['l']/b['o']),math.log1p(b['v']/SCALE),math.log1p(b['q']/SCALE**2),math.log1p(b['n']),math.sin(2*math.pi*((t//MINUTE)%1440)/1440),math.cos(2*math.pi*((t//MINUTE)%1440)/1440)] if ok else [0.]*8 for t,b,ok in zip(times,bars,valid)],np.float32)
        reference=self.flow_notional/self.flow_quantity/SCALE
        return {'candles':x,'candle_mask':valid,'last_candle_start_ns':int(last),'last_candle_close':bars[-1]['c']/SCALE,'reference':reference,'reference_second':self.flow_second,'input_cutoff_ns':at,'target_start_ns':(at//MINUTE+1)*MINUTE}


def released(rows,previous_release=-1):
    if not len(rows):return np.empty(0,np.int64)
    times=np.maximum(np.maximum(rows['receipt_ns'],rows['event_ns']),rows['trade_ns'])
    return np.maximum.accumulate(np.maximum(times,previous_release))
