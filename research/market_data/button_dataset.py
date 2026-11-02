"""Versioned next-full-minute button dataset; historical candle availability is ASSUMED."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import numpy as np
from .build_pilot import (START,STOP,WARMUP,feature_dtype,fit_scaler,trade_values,
                          references,make_candles,compile_features,extract)
from .freeze_pilot import SPLITS,timestamp
from .review_pilot import utc
from .validate_archive import save,file_hash

PHASES=(0,15,30,45)
GRACES=(1000,5000,30000,60000)


def context_end(snapshot_ms,grace_ms):
    # Candle at [end-60s,end) is eligible under the explicit finalization assumption.
    return (snapshot_ms-grace_ms-1)//60000*60000


def select(targets,phase_seconds,grace_ms,content_valid,book,trades):
    kept=[];rejected=Counter();bad=np.r_[0,np.cumsum(~content_valid)]
    for target in targets:
        snapshot=target-60000+phase_seconds*1000
        end=context_end(snapshot,grace_ms)
        ci=(end-WARMUP)//60000
        se=(snapshot-START)//1000;sb=se-60
        if ci<1440 or sb<0 or se>len(book):
            rejected['outside_history']+=1;continue
        if bad[ci]!=bad[ci-1440]:
            rejected['unrecovered_candle_context']+=1;continue
        b,t=book[sb:se],trades[sb:se]
        if not b['valid'].all() or not t['valid'].all():
            rejected['invalid_book_or_trade_seconds']+=1;continue
        cutoff=snapshot*10**6
        if any(np.max(r[name])>=cutoff for r in (b,t) for name in ('receipt_ns','event_ns')):
            rejected['future_book_or_trade_message']+=1;continue
        if not np.isfinite(b['x']).all() or not np.isfinite(t['x']).all():
            rejected['nonfinite_inputs']+=1;continue
        if end>snapshot or snapshot>=target:raise ValueError('Noncausal input/target boundary')
        kept.append([snapshot,target,ci,sb,se])
    return np.asarray(kept,dtype=np.int64).reshape(-1,5),dict(rejected)


def build(features,audit,recovery,output,archive):
    output.mkdir(parents=True,exist_ok=True)
    import fcntl
    lock=(output/'.build.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    content=np.load(features/'candle-valid.npy').copy()
    recovered=json.loads((recovery/'recovery-manifest.json').read_text())
    if recovered['state']!='content_recovery_complete':raise ValueError('Recovery has unfinished days')
    for row in recovered['minutes']:
        if row['content_recovery_accepted']:content[(row['minute_ms']-WARMUP)//60000]=True
    refs=references(audit)
    _,candles,raw,_,_=make_candles(refs,{}, {})
    for kind in ('book','trades'):
        expected=json.loads((features/f'{kind}-extraction.json').read_text())['sha256']
        if file_hash(features/f'{kind}-seconds.bin')!=expected:raise ValueError('Source feature hash changed')
    # Refresh only trade features for the corrected non-market filter and max(E,T)
    # cutoff. Book replay is unchanged; reuse its independently hashed bytes.
    refreshed=output/'corrected-trades';refreshed.mkdir(exist_ok=True)
    records=json.loads((archive/'manifest.json').read_text())
    jobs=sorted([r for r in records if '_trades.' in r['remote_file'] and
        '2026-09-30'<=r['remote_file'].split('/')[1]<'2026-11-01'],key=lambda r:r['remote_file'])
    here=Path(__file__).resolve().parent
    trade_fingerprint=hashlib.sha256(''.join(file_hash(p) for p in [here/'feature_scan.cpp',
        here/'archive_scan.cpp',archive/'manifest.json']).encode()).hexdigest()
    binary=compile_features(refreshed)
    extract(archive,audit,refreshed,binary,'trades',jobs,trade_fingerprint)
    book=np.memmap(features/'book-seconds.bin',mode='r',dtype=feature_dtype('book'))
    trades=np.memmap(refreshed/'trades-seconds.bin',mode='r',dtype=feature_dtype('trades'))
    np.save(output/'candle-features.npy',candles);np.save(output/'candle-raw.npy',raw)
    np.save(output/'candle-content-valid.npy',content)
    # No invented receipt time array is produced for official historical repairs.
    counts={};primary_fit=None;daily={};target_hashes={}
    for split,(lo,hi) in SPLITS.items():
        targets=[int(t) for t in np.arange(timestamp(lo),timestamp(hi),60000) if int(t) in refs]
        target_hashes[split]=hashlib.sha256(json.dumps(targets).encode()).hexdigest()
        counts[split]={}
        for phase in PHASES:
            for grace in GRACES:
                key=f'phase{phase}-grace{grace}'
                indices,exclusions=select(targets,phase,grace,content,book,trades)
                if len(indices) and ((indices[:,1]+60000>timestamp(hi)).any() or (indices[:,1]<timestamp(lo)).any()):
                    raise ValueError('Target outside partition')
                truth=raw[(indices[:,1]-WARMUP)//60000].copy()
                if len(truth) and (not np.isfinite(truth).all() or (truth[:,:4]<=0).any()):raise ValueError('Invalid target')
                np.save(output/f'{split}-{key}-indices.npy',indices)
                np.save(output/f'{split}-{key}-targets.npy',truth)
                by_day=dict(sorted(Counter(utc(int(t))[:10] for t in indices[:,1]).items()))
                counts[split][key]={'eligible':len(indices),'excluded':exclusions,'days_represented':len(by_day)}
                daily[f'{split}:{key}']=by_day
                if split=='fit' and phase==15 and grace==1000:primary_fit=indices
        save(output/'progress.json',{'state':'building','partition_completed':split,'training_started':False})
    if primary_fit is not None and len(primary_fit):
        save(output/'scalers.json',{'fit_partition_only':True,'primary':'phase15-grace1000',
            'candles':fit_scaler((candles[r[2]-1440:r[2]] for r in primary_fit),8),
            'book':fit_scaler((book[r[3]:r[4]]['x'] for r in primary_fit),87),
            'trades':fit_scaler((trade_values(trades[r[3]:r[4]],raw[r[2]-1,3]) for r in primary_fit),8),
            'weighting':'eligible primary fitting windows; no calibration/development/test values'})
    source_manifest=json.loads((features/'dataset-manifest.json').read_text())
    result={'state':'historical_button_dataset_complete','training_started':False,
        'historical_candle_availability':'ASSUMED close time + grace; not measured receipt time',
        'verified_leakage_free_live_test':False,'original_dataset_changed':False,
        'target':'next full calendar minute after input snapshot; reject results ready at/after target start',
        'input_index_columns':['snapshot_ms','target_minute_ms','candle_end_exclusive_index','second_begin','second_end_exclusive'],
        'context_candles':1440,'book_trade_seconds':60,'phases_seconds':list(PHASES),
        'assumed_candle_finalization_grace_ms':list(GRACES),'primary':'phase15-grace1000',
        'partition_counts':counts,'daily_coverage':daily,'content_invalid_minutes_remaining':int((~content).sum()),
        'target_calendar_hashes':target_hashes,
        'book_source':str((features/'book-seconds.bin').resolve()),
        'trade_source':str((refreshed/'trades-seconds.bin').resolve()),
        'trade_feature_fingerprint':trade_fingerprint,'source_feature_fingerprint':source_manifest['fingerprint'],
        'recovery_fingerprint':recovered['fingerprint'],
        'limitations':['Official recovered trade/candle content has no original receipt clock.',
            'Grace settings are assumptions/sensitivity cases, not guaranteed finalization delays.',
            'Book/trade receipt validity is relative to the historical provider, not our Mac.',
            'Four snapshots per target are correlated; split/group and evaluate by target/day.',
            'Next-full-minute target changes lead time versus original minute-open experiment.',
            'No test outcomes were scored or used to select dates or phases.']}
    paths=[Path(__file__),features/'dataset-manifest.json',recovery/'recovery-manifest.json',
           refreshed/'trades-extraction.json']
    result['fingerprint']=hashlib.sha256(''.join(file_hash(p) for p in paths).encode()).hexdigest()
    result['artifact_sha256']={p.name:file_hash(p) for p in sorted(output.glob('*.npy'))}
    if (output/'scalers.json').exists():result['artifact_sha256']['scalers.json']=file_hash(output/'scalers.json')
    save(output/'dataset-manifest.json',result)
    save(output/'progress.json',{'state':result['state'],'training_started':False})
    print(json.dumps({k:v for k,v in result.items() if k not in ('daily_coverage','artifact_sha256')},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('features','audit','recovery','output'):p.add_argument(name,type=Path)
    p.add_argument('--archive',type=Path,required=True)
    a=p.parse_args();build(a.features,a.audit,a.recovery,a.output,a.archive)
