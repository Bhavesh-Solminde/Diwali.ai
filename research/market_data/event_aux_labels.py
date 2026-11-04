"""Separate short-horizon availability-price labels; never input features.

An endpoint uses the last market execution released strictly before it, at most
two seconds old. This differs deliberately from future full-candle close labels.
"""
import argparse
import json
from pathlib import Path

import numpy as np

from .candle_tape import released,SECOND,SCALE
from .trade_events import DTYPE
from .event_shards import read_events
from .event_join_cohort import hour_ns,HOUR
from .event_month_cohort import intersects
from .validate_archive import file_hash,save

HORIZONS=[5,15,30,60]


def endpoint_price(rows,times,endpoint,last_market=None):
    end=int(np.searchsorted(times,endpoint,side='left'))
    candidates=np.flatnonzero((~rows['bad'][:end].astype(bool))&(~rows['nonmarket'][:end].astype(bool)))
    if len(candidates):
        i=int(candidates[-1]);last_market=(int(times[i]),int(rows['price'][i]))
    if last_market is None or endpoint-last_market[0]>2*SECOND:
        return None
    return last_market[1]/SCALE


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--cohort',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    sr=json.loads((a.source/'report.json').read_text());cr=json.loads((a.cohort/'candles/report.json').read_text());protocol=json.loads((a.cohort/'protocol.json').read_text())
    if sr['state']!='complete' or cr['state']!='complete' or cr.get('target_interval')!=['2026-08-01','2026-08-31']:raise ValueError('Only completed August development cohorts permitted')
    if cr['source_report_sha256']!=file_hash(a.source/'report.json'):raise ValueError('Source differs')
    meta=a.cohort/'candles/input-metadata.json'
    if file_hash(meta)!=cr['artifact_sha256']['input-metadata.json']:raise ValueError('Changed frozen origins')
    origins=json.loads(meta.read_text());queries={};result={i:{'input_row':i,'input_cutoff_ns':m['input_cutoff_ns'],'horizons':{}} for i,m in enumerate(origins)}
    for i,m in enumerate(origins):
        at=m['input_cutoff_ns'];queries.setdefault(at//HOUR*HOUR,[]).append((at,i,0))
        for h in HORIZONS:
            end=at+h*SECOND;queries.setdefault(end//HOUR*HOUR,[]).append((end,i,h))
    pending=np.empty(0,dtype=DTYPE);pending_at=np.empty(0,np.int64);watermark=-1;bad_count=0;last_market=None;origin_bad={};sourcehashes={}
    for hour in sr['hours']:
        at=hour_ns(hour['UTC_hour']);part=hour['files']['trades'];path=a.source/hour['UTC_hour']/part['file']
        if file_hash(path)!=part['sha256']:raise ValueError('Changed trade source')
        sourcehashes[str(path)]=part['sha256'];rows=read_events(path,DTYPE);times=released(rows,watermark)
        if len(times):watermark=int(times[-1])
        if len(pending):rows=np.concatenate([pending,rows]);times=np.r_[pending_at,times]
        counts=np.r_[0,np.cumsum(rows['bad'].astype(np.int64))]
        for endpoint,i,h in sorted(queries.get(at,[])):
            end=int(np.searchsorted(times,endpoint,side='left'));count=bad_count+int(counts[end]);m=origins[i]
            if h==0:origin_bad[i]=count;continue
            reason=None;price=endpoint_price(rows,times,endpoint,last_market)
            if intersects(m['input_cutoff_ns'],endpoint,protocol['clock_trade_exclusion_intervals_ns']):reason='clock_flagged_trade_period'
            elif count!=origin_bad.get(i,-1):reason='invalid_trade_marker_in_horizon'
            elif price is None:reason='no_fresh_available_market_execution'
            result[i]['horizons'][str(h)]={'valid':reason is None,'reason':reason,'price':price if reason is None else None,
                                         'return_bp':(price/m['reference']-1)*10000 if reason is None else None}
        end=int(np.searchsorted(times,at+HOUR,side='left'))
        market=np.flatnonzero((~rows['bad'][:end].astype(bool))&(~rows['nonmarket'][:end].astype(bool)))
        if len(market):
            i=int(market[-1]);last_market=(int(times[i]),int(rows['price'][i]))
        bad_count+=int(counts[end]);pending=rows[end:].copy();pending_at=times[end:].copy()
    a.output.mkdir(parents=True,exist_ok=False);save(a.output/'labels.json',list(result.values()))
    counts={str(h):sum(v['horizons'].get(str(h),{}).get('valid',False) for v in result.values()) for h in HORIZONS}
    report={'state':'complete','origins':len(origins),'horizons_seconds_after_freeze':HORIZONS,'valid_endpoint_counts':counts,
            'definition':'Latest market execution released strictly before endpoint, at most2seconds old; relative to the original frozen reference.',
            'primary_task_unchanged':True,'not_the_same_as_candle_close':True,'used_as_input':False,
            'label_sha256':file_hash(a.output/'labels.json'),'source_report_sha256':file_hash(a.source/'report.json'),
            'cohort_sha256':file_hash(a.cohort/'report.json'),'code_sha256':file_hash(Path(__file__)),
            'limitations':['Auxiliary availability-price labels include trade-price bid/ask noise, not true latent value.',
                           'No claim of exchange-original receipt authenticity.','Signal lifetime still requires matched chronological predictive scoring.']}
    save(a.output/'report.json',report);print(json.dumps(counts))


if __name__=='__main__':main()
