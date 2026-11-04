"""Fit-only scaling of a separate60-second midpoint context on unchanged origins."""
import argparse,json
from pathlib import Path
import numpy as np
from .midpoint import DTYPE,window_features
from .build_pilot import START,fit_scaler
from .validate_archive import save,file_hash


def summaries(windows):
    x=np.asarray(windows)
    if x.ndim!=3 or x.shape[1:]!=(60,2) or not np.isfinite(x).all():raise ValueError('Expected finite60x2 midpoint windows')
    return np.stack([x[:,-1,0],x[:,:,1].sum(1,dtype=np.float64)],1).astype(np.float32)


def prepare(source,output):
    report=json.loads((source/'report.json').read_text())
    if report['state']!='complete' or not report['full_october'] or not report['all_parent_metadata_equal']:raise ValueError('Full matching midpoint source required')
    path=source/'midpoints.bin'
    if file_hash(path)!=report['sha256']:raise ValueError('Changed midpoint source')
    output.mkdir(parents=True,exist_ok=False);rows=np.memmap(path,dtype=DTYPE,mode='r');root=Path('data/models/diwali0.5');raw_path=Path('data/btc-perp/button-pilot-202610-v1/candle-raw.npy');raw_hash=file_hash(raw_path)
    if raw_hash!=json.loads((raw_path.parent/'dataset-manifest.json').read_text())['artifact_sha256'][raw_path.name]:raise ValueError('Changed candle anchors')
    raw=np.load(raw_path);parts={};hashes={str(path):report['sha256'],str(raw_path):raw_hash}
    for part in ['fit','development','calibration','locked_test']:
        target=root/f'{part}-targets.npz';z=np.load(target);indices=z['indices'];values=[];hashes[str(target)]=file_hash(target)
        for row in indices:
            s,e=int(row[3]),int(row[4]);book=rows[s:e]
            if len(book)!=60 or not book['valid'].all() or not (book['time_ns']<int(row[0])*10**6).all() or not (book['receipt_ns']<=book['time_ns']).all() or not (book['event_ns']<=book['time_ns']).all():raise ValueError('Invalid or future midpoint input; do not drop/change cohort')
            expected=START*10**6+np.arange(s,e,dtype=np.int64)*10**9
            if not np.array_equal(book['time_ns'],expected):raise ValueError('Shifted midpoint input')
            values.append(window_features(book['mid'],float(raw[int(row[2])-1,3])))
        parts[part]=np.stack(values);np.save(output/f'{part}-indices.npy',indices)
    scaler=fit_scaler(iter(parts['fit']),2);save(output/'scaler.json',scaler)
    summary_parts={k:summaries(v) for k,v in parts.items()};summary_scaler=fit_scaler((x[None] for x in summary_parts['fit']),2);save(output/'summary-scaler.json',summary_scaler)
    for part,x in parts.items():
        standardized=((x-np.asarray(scaler['mean']))/np.asarray(scaler['std'])).astype(np.float32)
        if not np.isfinite(standardized).all():raise ValueError('Nonfinite midpoint window')
        np.save(output/f'{part}-features.npy',standardized)
        summary=((summary_parts[part]-np.asarray(summary_scaler['mean']))/np.asarray(summary_scaler['std'])).astype(np.float32)
        if not np.isfinite(summary).all():raise ValueError('Nonfinite midpoint summary')
        np.save(output/f'{part}-summary.npy',summary)
    artifacts={p.name:file_hash(p) for p in output.iterdir() if p.is_file()};save(output/'manifest.json',{'state':'complete','cohorts':{k:len(v) for k,v in parts.items()},'source_sha256':file_hash(Path(__file__)),'inputs':hashes,'source_report_sha256':file_hash(source/'report.json'),'scaling':'fit origins only, overlapping windows weighted as the unchanged training cohort','names':['midpoint_vs_last_completed_candle_close_bp','within_window_midpoint_log_change_bp'],'summary_names':['latest_midpoint_vs_last_completed_candle_close_bp','net60_second_midpoint_log_change_bp'],'first_change':'zero by definition because no previous midpoint outside the60-second window is supplied','artifacts':artifacts,'new_training_started':False,'limitations':['Same historical provider timing/authenticity assumptions remain.','No hidden liquidity or future events recovered.','New feature definition, not proof of better predictions.']})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=Path('data/btc-perp/book-midpoints-202610-v1'));p.add_argument('--output',type=Path,default=Path('data/btc-perp/midpoint-windows-202610-v1'));a=p.parse_args();prepare(a.source,a.output)
