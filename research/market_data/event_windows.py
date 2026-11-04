"""Lossless row-reference windows; no resampling, labels or invented cross-feed order."""
import numpy as np

INDEX_DTYPE=np.dtype([('available_ns','<i8'),('kind','u1'),('source_row','<i8'),('time_group','<i8')])


def release_times(receipt,event):
    receipt=np.asarray(receipt,np.int64);event=np.asarray(event,np.int64)
    if receipt.ndim!=1 or receipt.shape!=event.shape or (receipt<=0).any() or (event<=0).any() or (np.diff(receipt)<0).any():raise ValueError('Invalid source ordering/clocks')
    # A later row cannot leap over an earlier not-yet-available book transition.
    return np.maximum.accumulate(np.maximum(receipt,event))


def window(book,trades,start,cutoff,max_stale_ns=10**9):
    if start>=cutoff or max_stale_ns<=0:raise ValueError('Invalid window')
    bt=release_times(book['receipt_ns'],book['event_ns'])
    tt=release_times(trades['receipt_ns'],np.maximum(trades['event_ns'],trades['trade_ns']))
    seed=int(np.searchsorted(bt,start,side='left'))-1
    if seed<0 or not book['valid'][seed]:raise ValueError('No valid pre-window book seed')
    bi=np.flatnonzero((bt>=start)&(bt<cutoff));ti=np.flatnonzero((tt>=start)&(tt<cutoff))
    if not book['valid'][bi].all() or trades['bad'][ti].any():raise ValueError('Gap/invalid marker inside window')
    accepted=np.flatnonzero((bt<cutoff)&book['accepted_update'].astype(bool))
    before=accepted[bt[accepted]<start]
    if not len(before):raise ValueError('No accepted pre-window book update')
    stamps=np.r_[bt[before[-1]],bt[accepted[(bt[accepted]>=start)]],cutoff]
    if (np.diff(stamps)>max_stale_ns).any():raise ValueError('Stale book coverage')
    merged=np.zeros(len(bi)+len(ti),dtype=INDEX_DTYPE)
    merged['available_ns']=np.r_[bt[bi],tt[ti]];merged['kind']=np.r_[np.zeros(len(bi),np.uint8),np.ones(len(ti),np.uint8)];merged['source_row']=np.r_[bi,ti]
    # Deterministic serialization inside a timestamp group is NOT causal order.
    merged=merged[np.lexsort((merged['source_row'],merged['kind'],merged['available_ns']))]
    if len(merged):merged['time_group']=np.r_[0,np.cumsum(np.diff(merged['available_ns'])!=0)]
    return {'book_seed_row':seed,'events':merged,'book_events':len(bi),'trade_rows':len(ti),
        'market_trades':int((~trades['nonmarket'][ti].astype(bool)).sum()),'truncated':False,
        'tie_policy':'Group equal availability; source kind/row only serializes ties, does not prove cross-stream causality.'}
