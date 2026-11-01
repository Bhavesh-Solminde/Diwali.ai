"""Frozen profile validation and conservative touch-entry bounds; no training."""
import argparse
import gzip
import hashlib
import importlib.util
import json
from collections import Counter, deque
from pathlib import Path
import numpy as np

spec=importlib.util.spec_from_file_location('baseline',Path(__file__).with_name('audit-baselines.py'))
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)


def read(path):
    with gzip.open(path,'rt') as f:return [json.loads(line) for line in f]


def bp(a,b):return 10000*(a/b-1)
def sign(x):return 1 if x>1 else -1 if x< -1 else 0


def interval(a,alpha=.05):
    if not a:return dict(n=0)
    a=np.array(a,dtype=float);rng=np.random.default_rng(617)
    z=a[rng.integers(0,len(a),(10000,len(a)))].mean(axis=1)
    return dict(n=len(a),mean=float(a.mean()),sd=float(a.std(ddof=1)) if len(a)>1 else None,
                alpha=alpha,ci=list(map(float,np.quantile(z,[alpha/2,1-alpha/2]))))


def weighted_quant(hist,q):
    n=sum(hist.values());i=(n-1)*q;lo=int(i);hi=int(np.ceil(i));at=0;v0=v1=None
    for value,count in sorted(hist.items()):
        if count<=0:continue
        if v0 is None and at+count>lo:v0=value
        if at+count>hi:v1=value;break
        at+=count
    return v0+(v1-v0)*(i-lo)


def barrier(rows,start,stop,level,side):
    for c in range(start,stop+1):
        r=rows[c]
        fav=side*bp(r['high' if side==1 else 'low'],level)>=10
        adv=-side*bp(r['low' if side==1 else 'high'],level)>=10
        if fav or adv:return 'ambiguous' if fav and adv else 'win' if fav else 'loss'
    return 'timeout'


def entry(rows,c,level,side):
    touch=next((i for i in range(c+1,c+16) if rows[i]['low']<=level<=rows[i]['high']),None)
    if touch is None:return dict(triggered=False,outcome='untriggered',complete_bar_outcome='untriggered')
    r=rows[touch]
    # Either barrier in the trigger candle might precede touch; never award a win.
    unsafe=bp(r['high'],level)>=10 or bp(r['low'],level)<=-10
    outcome='ambiguous' if unsafe else barrier(rows,touch+1,touch+30,level,side)
    return dict(triggered=True,trigger_candle=touch,trigger_delay=touch-c,outcome=outcome,
                complete_bar_outcome=barrier(rows,touch+1,touch+30,level,side),
                execution_status='OHLC_range_touch_proxy_not_passive_fill')


def match_events(events):
    strong=sorted([e for e in events if e['strength']=='strong'],key=lambda e:e['run_id'])
    weak=[e for e in events if e['strength']=='weak'];used=set();pairs=[]
    for a in strong:
        candidates=[]
        for i,b in enumerate(weak):
            if i in used or a['side']!=b['side'] or a['profile']!=b['profile']:continue
            vr=a['volatility_bp']/b['volatility_bp'] if b['volatility_bp'] else None
            dd=abs(a['distance_bp']-b['distance_bp']);vd=abs(a['volume_ratio']-b['volume_ratio'])
            if vr is None or not .8<=vr<=1.25 or dd>2 or vd>.25:continue
            score=(dd/2)**2+(np.log(vr)/np.log(1.25))**2+(vd/.25)**2
            candidates.append((score,b['run_id'],i,b))
        if candidates:
            _,_,i,b=min(candidates,key=lambda x:(x[0],x[1]));used.add(i)
            pairs.append(dict(strong=a,weak=b,distance_delta=a['distance_bp']-b['distance_bp'],
                log_volatility_ratio=float(np.log(a['volatility_bp']/b['volatility_bp'])),volume_ratio_delta=a['volume_ratio']-b['volume_ratio']))
    return pairs


def matched_summary(pairs):
    joint=[p for p in pairs if p['strong']['triggered'] and p['weak']['triggered']]
    graph={}
    def find(x):
        graph.setdefault(x,x)
        if graph[x]!=x:graph[x]=find(graph[x])
        return graph[x]
    for p in joint:
        a=find(p['strong']['run_id']);b=find(p['weak']['run_id']);graph[a]=b
    groups={}
    for p in joint:
        key=find(p['strong']['run_id']);groups.setdefault(key,[]).append(p)
    def bounds(p):
        a,b=p['strong']['outcome'],p['weak']['outcome']
        return int(a=='win')-int(b in ('win','ambiguous')),int(a in ('win','ambiguous'))-int(b=='win')
    out=dict(pairs=len(pairs),both_triggered=len(joint),parent_components=len(groups),
        mean_abs_distance_delta=float(np.mean([abs(p['distance_delta']) for p in pairs])) if pairs else None,
        mean_abs_log_volatility_ratio=float(np.mean([abs(p['log_volatility_ratio']) for p in pairs])) if pairs else None,
        mean_abs_volume_ratio_delta=float(np.mean([abs(p['volume_ratio_delta']) for p in pairs])) if pairs else None)
    if joint:
        out['success_difference_bounds']=[float(np.mean([bounds(p)[i] for p in joint])) for i in (0,1)]
        if len(groups)>=10:
            clusters=list(groups.values());rng=np.random.default_rng(617);lower=[];upper=[]
            for draw in rng.integers(0,len(clusters),(10000,len(clusters))):
                selected=[p for i in draw for p in clusters[i]]
                lower.append(np.mean([bounds(p)[0] for p in selected]));upper.append(np.mean([bounds(p)[1] for p in selected]))
            out['component_bootstrap_outer95']=[float(np.quantile(lower,.025)),float(np.quantile(upper,.975))]
        else:out['uncertainty']='Fewer than10independent matching components; no reliable interval claimed'
    return out


def v04(raw,out):
    origins=[];events=[];manifest=[]
    for p in sorted(raw.glob('*.manifest.json')):
        m=json.loads(p.read_text());manifest.append(m)
        if m['status']!='ok':continue
        rows=read(raw/(m['run_id']+'.rows.jsonl.gz'));assert len(rows)==600
        ages={'bid':{},'ask':{}};history=deque();hist=Counter();used=set();exclusions=Counter()
        for c,r in enumerate(rows):
            books={'bid':dict(r['bids']),'ask':dict(r['asks'])}
            for side in ages:ages[side]={price:ages[side].get(price,0)+1 for price in books[side]}
            assert r['low']>0 and r['low']<=min(r['open'],r['close'])<=max(r['open'],r['close'])<=r['high'] and r['volume']>=0
            if 100<=c<=569:
                if not books['bid'] or not books['ask'] or not 0<r['best_bid']<r['best_ask']<2147483647:exclusions['locked_or_absent']+=1
                else:
                    bid=sum(q for p,q in books['bid'].items() if 0<=10000*(r['close']-p)/r['close']<=10)
                    ask=sum(q for p,q in books['ask'].items() if 0<=10000*(p-r['close'])/r['close']<=10)
                    if bid+ask:
                        imbalance=(bid-ask)/(bid+ask)
                        origins.append(dict(run_id=m['run_id'],profile=m['profile'],seed=m['seed'],candle=c,
                            momentum=sign(bp(r['close'],rows[c-1]['close'])),book=1 if imbalance>.2 else -1 if imbalance<-.2 else 0,
                            actual=sign(bp(rows[c+1]['close'],r['close']))))
                    else:exclusions['missing_depth']+=1
                    if c<=554 and len(used)<4 and hist:
                        q50,q90=weighted_quant(hist,.5),weighted_quant(hist,.9)
                        prev=rows[c-100:c];vol=np.std([bp(rows[i]['close'],rows[i-1]['close']) for i in range(c-99,c)],ddof=1)
                        med=float(np.median([x['volume'] for x in prev]));volume_ratio=r['volume']/med if med else 0
                        for side,direction in [('bid',1),('ask',-1)]:
                            for strength in ('strong','weak'):
                                key=(side,strength)
                                candidates=[(direction*10000*(r['close']-p)/r['close'],p,q) for p,q in books[side].items()
                                    if 0<direction*10000*(r['close']-p)/r['close']<=10 and ages[side][p]>=5 and (q>=q90 if strength=='strong' else q<=q50)]
                                if key not in used and candidates:
                                    dist,level,qty=min(candidates);used.add(key)
                                    e=dict(run_id=m['run_id'],profile=m['profile'],side=side,strength=strength,candle=c,level=level,quantity=qty,
                                           distance_bp=dist,volatility_bp=float(vol),volume_ratio=volume_ratio,persistence=ages[side][level])
                                    e.update(entry(rows,c,level,direction));events.append(e)
            quantities=[q for b in books.values() for q in b.values()];history.append(quantities);hist.update(quantities)
            if len(history)>100:hist.subtract(history.popleft())
        m['exclusions']=dict(exclusions)
    results={}
    for profile in ('standard','sparse','maker30'):
        selected=[r for r in origins if r['profile']==profile];ms=[m for m in manifest if m['profile']==profile]
        assert len({(r['run_id'],r['candle']) for r in selected})==len(selected)
        ev=[e for e in events if e['profile']==profile];pairs=match_events(ev)
        entry_summary={}
        for side in ('bid','ask'):
            for strength in ('strong','weak'):
                es=[e for e in ev if e['side']==side and e['strength']==strength];trig=[e for e in es if e['triggered']]
                counts=Counter(e['outcome'] for e in es)
                entry_summary[side+'_'+strength]=dict(signals=len(es),triggered=len(trig),untriggered=counts.get('untriggered',0),
                    outcomes=dict(counts),success_bounds=[counts.get('win',0)/len(trig),(counts.get('win',0)+counts.get('ambiguous',0))/len(trig)] if trig else None,
                    complete_bar_sensitivity=dict(Counter(e['complete_bar_outcome'] for e in trig)))
        results[profile]=dict(attempted_parents=len(ms),completed_parents=sum(m['status']=='ok' for m in ms),origins=len(selected),
            failures=[m for m in ms if m['status']!='ok'],candidate_origins=len(ms)*470,
            exclusions=dict(sum((Counter(m.get('exclusions',{})) for m in ms),Counter())),coverage=len(selected)/(len(ms)*470),
            labels=dict(Counter(r['actual'] for r in selected)),
            rules={rule:base.summary(selected,rule,1) for rule in ('up','down','pilot_majority','neutral','momentum','reversal','book')},
            book_minus_reversal=base.paired(selected),book_minus_reversal_adjusted=base.paired(selected,alpha=.05/3),
            entry=entry_summary,matched_entry=matched_summary(pairs))
    (out/'v04-statistics.json').write_text(json.dumps(results,indent=2))
    for name,data in [('confirmatory-origins',origins),('entry-signals',events)]:
        with gzip.open(out/(name+'.jsonl.gz'),'wt') as f:
            for row in data:f.write(json.dumps(row)+'\n')
    return results


def v05(raw,out):
    runs=[]
    for path in sorted(raw.glob('*.manifest.json')):
        m=json.loads(path.read_text());runs.append(m)
        rows=read(raw/(m['run_id']+'.rows.jsonl.gz'));fills=read(raw/(m['run_id']+'.fills.jsonl.gz'))
        m['fills']=fills;m['observations']=len(rows)
        if m['status']!='ok':continue
        assert m['matched_baseline'] and len(rows)==51
        side=1 if m['scenario'].startswith('buy') else -1
        for c in rows:
            fs=[f for f in fills if f['relative']<=c['relative']]
            assert c['coins']-c['initial_coins']==-side*sum(f['filled'] for f in fs)
            assert c['cash']-c['initial_cash']==side*sum(f['notional'] for f in fs)
        m['ledger_pass']=True;m['partial_orders']=sum(f['filled']<f['intended'] for f in fills)
        m['deadline_returns_bp']={str(h):bp(rows[h]['last'],rows[0]['original_arrival']) for h in (1,5,15,30,50)}
        m['negative_cash_final']=rows[-1]['negative_cash_agents'];m['negative_coins_final']=rows[-1]['negative_coin_agents']
        if fills:
            qty=sum(f['filled'] for f in fills);notional=sum(f['notional'] for f in fills)
            for f in fills:
                assert 0<f['filled']<=f['intended'] and f['integer_vwap']==f['notional']//f['filled']
            m['complete_quantity']=m['total_filled']==m['total_requested']
            m['slippage_bp']=side*bp(notional/qty,rows[0]['original_arrival'])
            m['deadline_mark50_usd']=side*(qty*rows[-1]['last']-notional)/100
            last=20 if m['scenario'].endswith('five') else 0
            m['last_fill_horizon_returns_bp']={str(h):bp(rows[last+h]['last'],rows[0]['original_arrival']) for h in (1,5,15,30)}
    result={}
    for profile in ('standard','sparse','maker30'):
        group=[r for r in runs if r['profile']==profile];contrasts={}
        for side in ('buy','sell'):
            for ratio in ('0.5','2'):
                one={r['seed']:r for r in group if r['scenario']==f'{side}_d{ratio}_one'}
                five={r['seed']:r for r in group if r['scenario']==f'{side}_d{ratio}_five'}
                pairs=[(one[s],five[s]) for s in sorted(one) if s in five and all(r['status']=='ok' and r.get('complete_quantity') for r in (one[s],five[s]))]
                assert all(a['total_requested']==b['total_requested'] and a['total_filled']==b['total_filled'] for a,b in pairs)
                contrasts[side+'_d'+ratio]=dict(attempted_pairs=len(one),complete_pairs=len(pairs),
                    missing_or_incomplete_pairs=len(one)-len(pairs),quantity=interval([a['total_filled'] for a,b in pairs]),
                    actual_ratio=interval([a['total_requested']/a['initial_depth10'] for a,b in pairs]),
                    slippage_five_minus_one=interval([b['slippage_bp']-a['slippage_bp'] for a,b in pairs]),
                    slippage_adjusted=interval([b['slippage_bp']-a['slippage_bp'] for a,b in pairs],alpha=.05/12),
                    common_deadline_return_diff={str(h):interval([b['deadline_returns_bp'][str(h)]-a['deadline_returns_bp'][str(h)] for a,b in pairs]) for h in (1,5,15,30,50)},
                    mark50_five_minus_one=interval([b['deadline_mark50_usd']-a['deadline_mark50_usd'] for a,b in pairs]))
        result[profile]=dict(attempts=len(group),parents=len({r['seed'] for r in group}),status_counts=dict(Counter(r['status'] for r in group)),
            failures=[r for r in group if r['status']!='ok'],partial_orders=sum(r.get('partial_orders',0) for r in group),contrasts=contrasts)
    (out/'v05-statistics.json').write_text(json.dumps(dict(profiles=result,runs=runs),indent=2))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    f=v04(a.root/'v04',a.output);r=v05(a.root/'v05',a.output)
    catalog={str(path.relative_to(a.root)):hashlib.sha256(path.read_bytes()).hexdigest() for sub in ('v04','v05') for path in sorted((a.root/sub).glob('*'))}
    (a.output/'raw-sha256.json').write_text(json.dumps(catalog,indent=2))
    print(json.dumps(dict(v04={k:v['book_minus_reversal_adjusted'] for k,v in f.items()},
                         v05={k:{c:x['slippage_adjusted'] for c,x in v['contrasts'].items()} for k,v in r.items()}),indent=2))
