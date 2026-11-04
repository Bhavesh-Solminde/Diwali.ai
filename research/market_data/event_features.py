"""Ordered price-aligned features; boundary visibility is not cancellation identity."""
import numpy as np

LEVEL_NAMES=[f'{side}_{i}_{field}' for i in range(1,21) for side in ['bid','ask'] for field in ['price_from_seed_bp','log_quantity']]
EXTRA_NAMES=['book_event','trade_event','nonmarket_marker','log_group_gap_seconds','elapsed_seconds',
    'mid_from_seed_bp','spread_bp','imbalance20','log_book_gap_seconds',
    'log_bid_matched_increase','log_bid_matched_decrease','log_ask_matched_increase','log_ask_matched_decrease',
    'log_bid_entering_visible','log_bid_leaving_visible','log_ask_entering_visible','log_ask_leaving_visible',
    'bid_price_overlap_fraction','ask_price_overlap_fraction','trade_price_from_seed_bp','signed_log_trade_quantity','signed_log_trade_notional','log_trade_gap_seconds']
NAMES=LEVEL_NAMES+EXTRA_NAMES
SCALE=100000000


def price_changes(previous,current):
    """Compare prices present in both top20s; keep entry/exit visibility separate."""
    a={int(p):int(q) for p,q in previous};b={int(p):int(q) for p,q in current};common=a.keys()&b.keys()
    increase=sum(max(b[p]-a[p],0) for p in common)/SCALE;decrease=sum(max(a[p]-b[p],0) for p in common)/SCALE
    entering=sum(b[p] for p in b.keys()-a.keys())/SCALE;leaving=sum(a[p] for p in a.keys()-b.keys())/SCALE
    return np.array([np.log1p(increase),np.log1p(decrease),np.log1p(entering),np.log1p(leaving),len(common)/20],np.float64)


def level_state(levels,anchor):
    a=np.asarray(levels,np.int64)
    if a.shape!=(20,4) or (a<=0).any() or anchor<=0:raise ValueError('Invalid top20/anchor')
    result=np.empty((20,4),np.float64);result[:,0]=(a[:,0]/SCALE/anchor-1)*10000;result[:,2]=(a[:,2]/SCALE/anchor-1)*10000
    result[:,1]=np.log1p(a[:,1]/SCALE);result[:,3]=np.log1p(a[:,3]/SCALE)
    return result.ravel()


def build(book,trades,selection,start,cutoff):
    seed=book[selection['book_seed_row']];previous=seed['levels'].copy();anchor=(int(previous[0,0])+int(previous[0,2]))/(2*SCALE)
    if not seed['valid'] or max(int(seed['receipt_ns']),int(seed['event_ns']))>=start:raise ValueError('Unavailable seed')
    index=selection['events'];x=np.zeros((len(index),len(NAMES)),np.float32);seed_x=level_state(previous,anchor).astype(np.float32)
    last_book=start;last_trade=start;last_group=start;group_time=start
    for i,row in enumerate(index):
        at=int(row['available_ns']);src=int(row['source_row']);z=x[i,80:]
        if not start<=at<cutoff:raise ValueError('Event outside input window')
        if i and at<int(index[i-1]['available_ns']):raise ValueError('Unordered event indices')
        if i==0 or at!=group_time:last_group=group_time;group_time=at
        z[3]=np.log1p((at-last_group)/1e9);z[4]=(at-start)/1e9
        if row['kind']==0:
            b=book[src]
            if not b['valid'] or max(int(b['receipt_ns']),int(b['event_ns']))>at:raise ValueError('Invalid/unavailable book event')
            current=b['levels'];x[i,:80]=level_state(current,anchor);z[0]=1;mid=(int(current[0,0])+int(current[0,2]))/(2*SCALE)
            z[5]=(mid/anchor-1)*10000;z[6]=(int(current[0,2])-int(current[0,0]))/SCALE/mid*10000
            bq=sum(map(int,current[:,1]));aq=sum(map(int,current[:,3]));z[7]=(bq-aq)/(bq+aq);z[8]=np.log1p((at-last_book)/1e9)
            bid=price_changes(previous[:,:2],current[:,:2]);ask=price_changes(previous[:,2:],current[:,2:])
            z[9:13]=[bid[0],bid[1],ask[0],ask[1]];z[13:17]=[bid[2],bid[3],ask[2],ask[3]];z[17:19]=[bid[4],ask[4]]
            previous=current.copy();last_book=at
        elif row['kind']==1:
            t=trades[src]
            if t['bad'] or max(int(t['receipt_ns']),int(t['event_ns']),int(t['trade_ns']))>at:raise ValueError('Invalid/unavailable trade')
            z[1]=1;z[2]=int(t['nonmarket']);z[22]=np.log1p((at-last_trade)/1e9);last_trade=at
            if not t['nonmarket']:
                price=int(t['price'])/SCALE;qty=int(t['quantity'])/SCALE
                if price<=0 or qty<=0:raise ValueError('Invalid fill')
                sign=-1 if t['buyer_maker'] else 1;z[19]=(price/anchor-1)*10000;z[20]=sign*np.log1p(qty);z[21]=sign*np.log1p(price*qty)
        else:raise ValueError('Unknown event kind')
    if not np.isfinite(x).all():raise ValueError('Nonfinite features')
    return {'features':x,'seed_features':seed_x,'anchor':anchor,'time_groups':index['time_group'].copy(),
        'feature_names':NAMES,'truncated':False,'future_outcomes_used':False,
        'scope':'Book state after atomic own-stream batches; trade coordinates use fixed pre-window seed. No within-group cross-stream order claim.'}
