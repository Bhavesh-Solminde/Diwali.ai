"""Vectorized equivalent of the independently retained event feature reference."""
import numpy as np
from .event_features import NAMES, SCALE, level_state


def changes(previous,current):
    n=len(current)
    if not n:return np.empty((0,5))
    low=min(int(previous[:,:,0].min()),int(current[:,:,0].min()))
    span=max(int(previous[:,:,0].max()),int(current[:,:,0].max()))-low+1
    if span*n>np.iinfo(np.int64).max or max(int(previous[:,:,1].max()),int(current[:,:,1].max()))>np.iinfo(np.int64).max//20:
        raise ValueError('Integer coordinate/sum bound exceeded')
    offsets=np.arange(n,dtype=np.int64)[:,None]*span
    pa=previous[:,:,0]-low+offsets;pb=current[:,:,0]-low+offsets
    order=np.argsort(pa,axis=1);sorted_keys=np.take_along_axis(pa,order,axis=1).ravel()
    quantities=np.take_along_axis(previous[:,:,1],order,axis=1).ravel()
    at=np.searchsorted(sorted_keys,pb.ravel());safe=np.minimum(at,len(sorted_keys)-1)
    common=(at<len(sorted_keys))&(sorted_keys[safe]==pb.ravel())
    prior=np.where(common,quantities[safe],0).reshape(n,20);common=common.reshape(n,20)
    qty=current[:,:,1];diff=qty-prior
    inc=np.where(common,np.maximum(diff,0),0).sum(1)/SCALE
    dec=np.where(common,np.maximum(-diff,0),0).sum(1)/SCALE
    entering=np.where(~common,qty,0).sum(1)/SCALE
    leaving=(previous[:,:,1].sum(1)-prior.sum(1))/SCALE
    return np.stack([np.log1p(inc),np.log1p(dec),np.log1p(entering),np.log1p(leaving),common.sum(1)/20],1)


def build(book,trades,selection,start,cutoff):
    seed=book[selection['book_seed_row']];previous=seed['levels'];anchor=(int(previous[0,0])+int(previous[0,2]))/(2*SCALE)
    if not seed['valid'] or max(int(seed['receipt_ns']),int(seed['event_ns']))>=start:raise ValueError('Unavailable seed')
    index=selection['events'];x=np.zeros((len(index),len(NAMES)),np.float32);times=index['available_ns']
    if ((times<start)|(times>=cutoff)).any() or (np.diff(times)<0).any():raise ValueError('Event outside/unordered input window')
    group_first=np.r_[True,np.diff(times)!=0] if len(times) else np.empty(0,bool)
    at=times[group_first];gaps=np.log1p((at-np.r_[start,at[:-1]])/1e9) if len(at) else np.empty(0)
    if len(index):x[:,83]=np.repeat(gaps,np.diff(np.r_[np.flatnonzero(group_first),len(index)]));x[:,84]=(times-start)/1e9
    bi=np.flatnonzero(index['kind']==0);ti=np.flatnonzero(index['kind']==1)
    if len(bi)+len(ti)!=len(index):raise ValueError('Unknown event kind')
    if len(bi):
        b=book[index['source_row'][bi]];levels=b['levels']
        if not b['valid'].all() or (np.maximum(b['receipt_ns'],b['event_ns'])>times[bi]).any() or (levels<=0).any():raise ValueError('Invalid/unavailable book event')
        state=np.empty(levels.shape,np.float64)
        state[:,:,0]=(levels[:,:,0]/SCALE/anchor-1)*10000;state[:,:,2]=(levels[:,:,2]/SCALE/anchor-1)*10000
        state[:,:,1]=np.log1p(levels[:,:,1]/SCALE);state[:,:,3]=np.log1p(levels[:,:,3]/SCALE)
        x[bi,:80]=state.reshape(-1,80);x[bi,80]=1
        mid=(levels[:,0,0]+levels[:,0,2])/(2*SCALE)
        x[bi,85]=(mid/anchor-1)*10000;x[bi,86]=(levels[:,0,2]-levels[:,0,0])/SCALE/mid*10000
        if levels[:,:,1::2].max()>np.iinfo(np.int64).max//40:raise ValueError('Depth sum bound exceeded')
        bq=levels[:,:,1].sum(1);aq=levels[:,:,3].sum(1);x[bi,87]=(bq-aq)/(bq+aq)
        x[bi,88]=np.log1p((times[bi]-np.r_[start,times[bi][:-1]])/1e9)
        prev=np.concatenate([previous[None],levels[:-1]])
        bid=changes(prev[:,:,:2],levels[:,:,:2]);ask=changes(prev[:,:,2:],levels[:,:,2:])
        x[bi,89:93]=np.stack([bid[:,0],bid[:,1],ask[:,0],ask[:,1]],1)
        x[bi,93:97]=np.stack([bid[:,2],bid[:,3],ask[:,2],ask[:,3]],1)
        x[bi,97:99]=np.stack([bid[:,4],ask[:,4]],1)
    if len(ti):
        t=trades[index['source_row'][ti]]
        if t['bad'].any() or (np.maximum(np.maximum(t['receipt_ns'],t['event_ns']),t['trade_ns'])>times[ti]).any():raise ValueError('Invalid/unavailable trade')
        x[ti,81]=1;x[ti,82]=t['nonmarket'];x[ti,102]=np.log1p((times[ti]-np.r_[start,times[ti][:-1]])/1e9)
        market=~t['nonmarket'].astype(bool);where=ti[market];fills=t[market]
        price=fills['price']/SCALE;qty=fills['quantity']/SCALE
        if (price<=0).any() or (qty<=0).any():raise ValueError('Invalid fill')
        sign=np.where(fills['buyer_maker'],-1,1)
        x[where,99]=(price/anchor-1)*10000;x[where,100]=sign*np.log1p(qty);x[where,101]=sign*np.log1p(price*qty)
    if not np.isfinite(x).all():raise ValueError('Nonfinite features')
    return {'features':x,'seed_features':level_state(previous,anchor).astype(np.float32),'anchor':anchor,
            'time_groups':index['time_group'].copy(),'feature_names':NAMES,'truncated':False,'future_outcomes_used':False,
            'scope':'Vectorized reference feature dictionary, unchanged cutoff and source-row semantics.'}
