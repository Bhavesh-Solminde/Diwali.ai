"""One-pass August causal contexts joined to complete event windows.

Keep all accepted rows; do not select origins using target returns. Clock-flagged
trade-hour contents conservatively exclude intersecting input histories/targets.
"""
import argparse
import json
import time
from collections import Counter
from pathlib import Path

import numpy as np

from .candle_tape import CandleTape, MINUTE, SECOND, SCALE, released
from .event_replay import DTYPE as BOOK
from .trade_events import DTYPE as TRADE
from .event_shards import read_events
from .event_join_cohort import hour_ns, source_release, join_selection, HOUR
from .validate_archive import file_hash, save


def intersects(first, stop, intervals):
    return any(first < b and stop > a for a,b in intervals)


def clock_exclusions(source, hours):
    intervals=[]
    for h in hours:
        p=h['files']['trades']
        if not p['clock_bad']:
            continue
        path=source/h['UTC_hour']/p['file']
        if file_hash(path) != p['sha256']:
            raise ValueError('Changed clock-flagged source')
        rows=read_events(path,TRADE)
        at=hour_ns(h['UTC_hour'])
        lo=min(at,int(rows['trade_ns'].min())//MINUTE*MINUTE) if len(rows) else at
        hi=max(at+HOUR,(int(rows['trade_ns'].max())//MINUTE+1)*MINUTE) if len(rows) else at+HOUR
        intervals.append((lo,hi))
    return intervals


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    sr=json.loads((a.source/'report.json').read_text())
    if sr['state'] != 'complete':
        raise ValueError('Incomplete source extraction')
    first,stop=hour_ns('2026-08-01T00'),hour_ns('2026-09-01T00')
    if sr['protocol']['stop_exclusive'] != '2026-09-01T00:00:00+00:00':
        raise ValueError('This bounded builder requires the frozen August source end')
    exclusions=clock_exclusions(a.source,sr['hours'])
    a.output.mkdir(parents=True,exist_ok=False)
    out=a.output/'candles';out.mkdir()
    wo=a.output/'windows';wo.mkdir()
    began=time.time();tape=CandleTape()
    previous=None;watermarks={'orderbook':-1,'trades':-1}
    pending=np.empty(0,dtype=TRADE);pending_at=np.empty(0,np.int64)
    contexts=[];masks=[];metadata=[];ledger=[];reject=Counter();counts=[];provenance={}
    total_origins=0;source_rows=0
    protocol={'source_report_sha256':file_hash(a.source/'report.json'),
              'origins':['2026-08-01','2026-08-31'],'freeze_second':15,'history_minutes':1440,
              'recent_event_seconds':60,'targets':15,'clock_trade_exclusion_intervals_ns':exclusions,
              'context_policy':'At least99percent valid, latest candle valid; explicit masks',
              'target_policy':'No bad/missing or clock-exclusion target; month-end horizon purge',
              'no_target_outcome_origin_selection':True,'reserved_final_denied':True,
              'code_hashes':{n:file_hash(Path(__file__).with_name(n)) for n in ['event_month_cohort.py','candle_tape.py','event_windows.py','event_join_cohort.py']}}
    save(a.output/'protocol.json',protocol)
    for hour in sr['hours']:
        at=hour_ns(hour['UTC_hour'])
        if at>=stop:
            break
        current={'entry':hour,'stamp':at,'before':watermarks.copy(),'rows':{}}
        for kind,dtype in [('orderbook',BOOK),('trades',TRADE)]:
            part=hour['files'][kind];path=a.source/hour['UTC_hour']/part['file']
            if file_hash(path) != part['sha256']:
                raise ValueError('Changed event shard')
            rows=read_events(path,dtype);current['rows'][kind]=rows
            times=source_release(rows,kind,watermarks[kind],part['clock_bad'])
            if len(times):watermarks[kind]=int(times[-1])
            if part['clock_bad']:current['bad_clock']=True
            provenance[str(path)]=part['sha256']
        trades=current['rows']['trades'];source_rows+=len(trades)
        times=released(trades,current['before']['trades'])
        if len(pending):
            trades=np.concatenate([pending,trades]);times=np.r_[pending_at,times]
        cursor=0;paired=previous is not None and at-previous['stamp']==HOUR
        if paired:
            b=np.concatenate([previous['rows']['orderbook'],current['rows']['orderbook']])
            t=np.concatenate([previous['rows']['trades'],current['rows']['trades']])
        for minute in range(60):
            cutoff=at+minute*MINUTE+15*SECOND
            end=int(np.searchsorted(times,cutoff,side='left'))
            for row,available in zip(trades[cursor:end],times[cursor:end]):
                tape.ingest(row,int(available))
            cursor=end
            if not first<=cutoff<stop:
                continue
            total_origins+=1
            context_start=cutoff//MINUTE*MINUTE-1440*MINUTE
            if intersects(context_start,cutoff,exclusions):
                reject['clock_trade_hour_intersects_input_history']+=1;continue
            if not paired:
                reject['missing_preceding_hour']+=1;continue
            if previous.get('bad_clock') or current.get('bad_clock'):
                reject['clock_flagged_recent_source_hour']+=1;continue
            before=previous['before']
            try:
                chosen=join_selection(b,t,cutoff,before['orderbook'],before['trades'])
                snapshot=tape.snapshot(cutoff,mask_context=True)
            except ValueError as error:
                reject[str(error)]+=1;continue
            index=len(metadata);name=f'{index:06d}.npz'
            np.savez_compressed(wo/name,events=chosen['events'])
            contexts.append(snapshot.pop('candles'));masks.append(snapshot.pop('candle_mask'));metadata.append(snapshot)
            counts.append(len(chosen['events']))
            ledger.append({'input_row':index,'input_cutoff_ns':cutoff,'window_start_ns':cutoff-60*SECOND,
                           'file':name,'sha256':file_hash(wo/name),'book_seed_row':chosen['book_seed_row'],
                           'book_events':chosen['book_events'],'trade_rows':chosen['trade_rows'],
                           'market_trades':chosen['market_trades'],'truncated':False,
                           'hours':[previous['entry']['UTC_hour'],hour['UTC_hour']],
                           'previous_release':before.copy()})
        pending=trades[cursor:].copy();pending_at=times[cursor:].copy()
        previous=current
        status={'state':'constructing','hour':hour['UTC_hour'],'origins_considered':total_origins,
                'joined_contexts':len(metadata),'rejections':dict(reject),'elapsed_seconds':time.time()-began}
        save(a.output/'status.json',status)
        print(hour['UTC_hour'],len(metadata),flush=True)
    for row,available in zip(pending[pending_at<stop],pending_at[pending_at<stop]):
        tape.ingest(row,int(available))
    np.save(out/'input-candles.npy',np.stack(contexts) if contexts else np.empty((0,1440,8),np.float32))
    np.save(out/'input-candle-masks.npy',np.stack(masks) if masks else np.empty((0,1440),bool))
    save(out/'input-metadata.json',metadata)
    targets=[];target_reject=Counter()
    for i,m in enumerate(metadata):
        start=m['target_start_ns'];end=start+15*MINUTE
        if end>stop:
            target_reject['month_end_boundary']+=1;continue
        if intersects(start,end,exclusions):
            target_reject['clock_trade_hour_intersects_target']+=1;continue
        bars=[tape.minutes.get(start+j*MINUTE) for j in range(15)]
        if any(b is None or not b['n'] or b['bad'] for b in bars):
            target_reject['missing_or_bad_target']+=1;continue
        closes=[b['c']/SCALE for b in bars]
        targets.append({'input_row':i,'target_start_ns':start,'closes':closes,
                        'returns_bp':[(c/m['reference']-1)*10000 for c in closes]})
    save(out/'targets.json',targets)
    common={'state':'complete','source_report_sha256':protocol['source_report_sha256'],
            'training_ready':False,'protocol_sha256':file_hash(a.output/'protocol.json')}
    cr={**common,'target_interval':['2026-08-01','2026-08-31'],'contexts':len(metadata),
        'labelled_origins':len(targets),'input_rejections':dict(reject),'target_rejections':dict(target_reject),
        'artifact_sha256':{n:file_hash(out/n) for n in ['input-candles.npy','input-candle-masks.npy','input-metadata.json','targets.json']},
        'masked_context_minutes':int(sum((~m).sum() for m in masks)),
        'limitations':['Labels use executions retained by month end; later external arrivals are unproven.',
                       'Inputs freeze at historical provider release times, not proven exchange receipt times.',
                       'Only passing book windows retained; coverage is limited and must be reported.']}
    save(out/'report.json',cr);save(wo/'windows.json',ledger)
    wr={**common,'input_contexts':len(metadata),'joined_origins':len(ledger),
        'event_rows':sum(counts),'minimum_events':min(counts,default=0),'maximum_events':max(counts,default=0),
        'rejections':dict(reject),'candle_report_sha256':file_hash(out/'report.json'),
        'ledger_sha256':file_hash(wo/'windows.json'),'future_labels_read':False,
        'note':'Window selection used input-only gates; separate targets finalized afterward.',
        'source_hashes':provenance}
    save(wo/'report.json',wr)
    if len(metadata)+sum(reject.values()) != total_origins:
        raise ValueError('Incomplete origin ledger')
    report={**common,'origins_considered':total_origins,'joined_contexts':len(metadata),
            'labelled_joined_origins':len(targets),'input_rejections':dict(reject),
            'target_rejections':dict(target_reject),'event_rows':sum(counts),
            'minimum_events':min(counts,default=0),'maximum_events':max(counts,default=0),
            'source_trade_rows':source_rows,'elapsed_seconds':time.time()-began,
            'candle_report_sha256':file_hash(out/'report.json'),'window_report_sha256':file_hash(wo/'report.json')}
    save(a.output/'report.json',report);save(a.output/'status.json',report)


if __name__=='__main__':
    main()
