"""Available-trade candle contexts and separately stored future endpoint labels."""
import argparse,json,math,time
from collections import Counter
from datetime import datetime,timezone,timedelta
from pathlib import Path
import numpy as np
from .event_shards import read_events
from .trade_events import DTYPE
from .candle_tape import CandleTape,released,MINUTE,SECOND,SCALE
from .validate_archive import file_hash,save


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--target-day',required=True);p.add_argument('--mask-context',action='store_true');a=p.parse_args();source=a.source;out=a.output;out.mkdir(parents=True,exist_ok=False);began=time.time()
    report=json.loads((source/'report.json').read_text())
    if report['state']!='complete':raise ValueError('Source extraction incomplete')
    day=datetime.fromisoformat(a.target_day).replace(tzinfo=timezone.utc);first=int(day.timestamp())*SECOND;stop=first+1440*MINUTE
    if not '2026-08-01'<=a.target_day<='2026-08-31':raise ValueError('This development builder denies other target dates')
    tape=CandleTape();pending=np.empty(0,dtype=DTYPE);pending_at=np.empty(0,np.int64);watermark=-1;contexts=[];masks=[];metadata=[];reject=Counter();source_rows=0;source_hashes={};hours_processed=0
    for hour in report['hours']:
        stamp=datetime.strptime(hour['UTC_hour'],'%Y-%m-%dT%H').replace(tzinfo=timezone.utc);at=int(stamp.timestamp())*SECOND
        if at>=stop:break
        part=hour['files']['trades'];path=source/hour['UTC_hour']/part['file']
        if file_hash(path)!=part['sha256']:raise ValueError('Changed trade shard')
        if part['clock_bad']:raise ValueError('Clock-flagged hour needs explicit exclusion support')
        rows=read_events(path,DTYPE);times=released(rows,watermark);watermark=int(times[-1]) if len(times) else watermark;source_rows+=len(rows);source_hashes[str(path)]=part['sha256'];hours_processed+=1
        if len(pending):rows=np.concatenate([pending,rows]);times=np.r_[pending_at,times]
        cursor=0
        for minute in range(60):
            cutoff=at+minute*MINUTE+15*SECOND;end=int(np.searchsorted(times,cutoff,side='left'))
            for row,available in zip(rows[cursor:end],times[cursor:end]):tape.ingest(row,int(available))
            cursor=end
            if first<=cutoff<stop:
                try:s=tape.snapshot(cutoff,mask_context=a.mask_context)
                except ValueError as error:reject[str(error)]+=1;continue
                contexts.append(s.pop('candles'));masks.append(s.pop('candle_mask'));metadata.append(s)
        pending=rows[cursor:].copy();pending_at=times[cursor:].copy()
        save(out/'status.json',{'state':'reconstructing','hours_done':hours_processed,'contexts':len(contexts),'rejections':dict(reject)});print(hour['UTC_hour'],len(contexts),flush=True)
    # Finish only rows whose release remains inside the retained source period.
    eligible=pending_at<stop
    for row,available in zip(pending[eligible],pending_at[eligible]):tape.ingest(row,int(available))
    np.save(out/'input-candles.npy',np.stack(contexts) if contexts else np.empty((0,1440,8),np.float32));np.save(out/'input-candle-masks.npy',np.stack(masks) if masks else np.empty((0,1440),bool));save(out/'input-metadata.json',metadata)
    target_rows=[];target_reject=Counter()
    for i,m in enumerate(metadata):
        start=m['target_start_ns'];starts=start+np.arange(15,dtype=np.int64)*MINUTE
        if start+15*MINUTE>stop:target_reject['end_boundary']+=1;continue
        bars=[tape.minutes.get(int(t)) for t in starts]
        if any(b is None or not b['n'] or b['bad'] for b in bars):target_reject['missing_or_bad_target']+=1;continue
        close=[b['c']/SCALE for b in bars];target_rows.append({'input_row':i,'target_start_ns':start,'closes':close,'returns_bp':[(c/m['reference']-1)*10000 for c in close]})
    save(out/'targets.json',target_rows)
    result={'state':'complete','target_day':a.target_day,'source_report_sha256':file_hash(source/'report.json'),'source_rows':source_rows,'hours_processed':hours_processed,'contexts':len(contexts),'input_rejections':dict(reject),'labelled_origins':len(target_rows),'target_rejections':dict(target_reject),'source_hashes':source_hashes,
        'artifact_sha256':{n:file_hash(out/n) for n in ['input-candles.npy','input-candle-masks.npy','input-metadata.json','targets.json']},'context_policy':'At least99percent valid minute contexts, latest complete candle valid; invalid contexts zero with explicit mask' if a.mask_context else 'Strict all1440 complete candles valid','masked_context_minutes':int(sum((~m).sum() for m in masks)),'code_hashes':{str(p):file_hash(p) for p in [Path(__file__),Path(__file__).with_name('candle_tape.py')]},'elapsed_seconds':time.time()-began,'training_ready':False,
        'limitations':['Candles reconstructed only from trades released before each cutoff; not finalized historical inputs.','Separate labels use executions retained by source end; later arrivals outside retained range are not proven absent.','Book-event window eligibility is not joined yet.','Development day only; no reserved final labels accessed.','Input scalers and target cohort purges for rolling folds remain unimplemented.']}
    save(out/'report.json',result);save(out/'status.json',{'state':'complete','contexts':len(contexts),'labelled_origins':len(target_rows)})


if __name__=='__main__':main()
