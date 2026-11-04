"""Verify follower forecasts against the separately retained native receipt journal."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from .candidate_follower import Predictor
from .audit_forward import verify_outcome
from .path import chain_losses
from ..market_data.frozen_inputs import FrozenInputs
from ..market_data.validate_archive import save


def read_prefix(root):
    complete=(root/'manifest.json').exists();expected=json.loads((root/'manifest.json').read_text())['raw_sha256'] if complete else None
    records=[];prefixes={}
    for path in sorted(root.glob('events-*.jsonl')):
        full=path.read_bytes();end=full.rfind(b'\n')+1;data=full[:end];digest=hashlib.sha256(data).hexdigest()
        if complete and (end!=len(full) or digest!=expected.get(path.name)):raise ValueError('Completed journal manifest mismatch')
        prefixes[path.name]={'bytes':end,'sha256':digest};records.extend(json.loads(line) for line in data.splitlines())
    if complete and set(expected)!=set(prefixes):raise ValueError('Completed journal file set mismatch')
    return records,prefixes,complete


def verify_commit(request,record,row,start,expected_model_id):
    if record['model_id']!=expected_model_id or request['snapshot_utc_ns']<start:raise ValueError('Wrong model or snapshot predates follower startup')
    if record['target_start_ns']!=request['target_start_ns'] or record['target_end_ns']!=request['target_end_ns']:raise ValueError('Changed target times')
    if record['snapshot_utc_ns']!=request['snapshot_utc_ns']:raise ValueError('Changed freeze time')
    if not request['snapshot_utc_ns']<=record['ready_utc_ns']<row['receipt_utc_ns']<record['target_start_ns']:raise ValueError('Forecast not committed before target')
    if not request['snapshot_monotonic_ns']<=record['ready_monotonic_ns']<=row['receipt_monotonic_ns']:raise ValueError('Invalid monotonic computation order')
    elapsed=record['ready_utc_ns']-request['snapshot_utc_ns'];mono=record['ready_monotonic_ns']-request['snapshot_monotonic_ns']
    if row.get('clock_step_ns') or abs(elapsed-mono)>100_000_000:raise ValueError('Clock step during forecast')


def check(root,run):
    protocol=json.loads((root/'follower-protocol.json').read_text());source=Path(protocol['source_capture']);native,prefixes,source_complete=read_prefix(source);own,ownprefixes,complete=read_prefix(root)
    # A live follower can append a forecast while the auditor is copying the
    # receiver prefix. Audit one common chronological boundary, not mixed moments.
    last=max((r['receipt_utc_ns'] for r in native),default=0);later_rows=sum(r['receipt_utc_ns']>last for r in own)
    own=[r for r in own if r['receipt_utc_ns']<=last]
    model=Predictor(run);replay=FrozenInputs();snapshots={}
    for row in native:
        if row['kind']=='input_snapshot':
            meta=row['payload'];data=(source/'frozen-inputs'/meta['snapshot_file']).read_bytes();digest=hashlib.sha256(data).hexdigest()
            if digest!=meta['sha256']:raise ValueError('Changed native freeze')
            request=json.loads(data)
            if replay.freeze(request['snapshot_utc_ns'],request['snapshot_monotonic_ns'])!=request:raise ValueError('Native freeze differs from then-received rows')
            snapshots[digest]=request
        replay.ingest(row)
    forecasts={};maximum=0;leads=[];copied={}
    for row in own:
        meta=row['payload']
        if row['kind']=='input_snapshot':
            data=(root/'frozen-inputs'/meta['snapshot_file']).read_bytes();digest=hashlib.sha256(data).hexdigest()
            if digest!=meta['sha256'] or digest not in snapshots or json.loads(data)!=snapshots[digest]:raise ValueError('Follower input not identical to verified native freeze')
            copied[digest]=snapshots[digest]
        if row['kind']=='forecast_saved':
            data=(root/'predictions'/meta['file']).read_bytes()
            if hashlib.sha256(data).hexdigest()!=meta['sha256']:raise ValueError('Changed follower forecast')
            record=json.loads(data);request=copied[record['input_sha256']];verify_commit(request,record,row,protocol['started_utc_ns'],model.provenance['model'])
            if meta['input_sha256']!=record['input_sha256'] or meta['target_start_ns']!=record['target_start_ns']:raise ValueError('Changed forecast journal linkage')
            if record['prediction']['provenance']!=model.provenance:raise ValueError('Changed frozen model/source')
            expected=model.predict(request);actual=record['prediction']
            for key in ['bin_probabilities','direction_probabilities','initial','transitions']:
                d=float(np.abs(np.asarray(expected[key])-actual[key]).max());maximum=max(maximum,d)
                if d>1e-7:raise ValueError('Changed forecast computation')
            if expected['reference']!=actual['reference'] or expected['target_close_ns']!=actual['target_close_ns']:raise ValueError('Changed reference/horizon')
            if expected['overall_direction']!=actual['overall_direction']:raise ValueError('Changed coherent final-direction claim')
            forecasts[meta['file']]=record;leads.append((record['target_start_ns']-row['receipt_utc_ns'])/1e9)
    outcomes=sorted([json.loads(p.read_text()) for p in (root/'outcomes').glob('*.json')],key=lambda r:r['scored_utc_ns']);pending=[r for r in outcomes if r['scored_utc_ns']<=last]
    if len({(r['forecast_file'],r['horizon']) for r in outcomes})!=len(outcomes):raise ValueError('Duplicate outcome horizon')
    replay=FrozenInputs();cursor=0;verified={}
    for row in native:
        while cursor<len(pending) and pending[cursor]['scored_utc_ns']<row['receipt_utc_ns']:
            actual=pending[cursor];name=actual['forecast_file'];verify_outcome(actual,forecasts[name],replay.candles);verified.setdefault(name,{})[actual['horizon']]=actual;cursor+=1
        replay.ingest(row)
    joint=[]
    for name,rows in verified.items():
        if len(rows)!=15:continue
        p=forecasts[name]['prediction'];y=np.asarray([[rows[h]['actual_bin'] for h in range(1,16)]]);joint.append(float(chain_losses(np.asarray(p['initial'])[None],np.asarray(p['transitions'])[None],y)[0]))
    result={'state':'follower_source_prefix_verified','model':model.provenance['model'],'capture_complete':complete,'source_capture_complete':source_complete,
        'source_prefixes':prefixes,'follower_prefixes':ownprefixes,'follower_rows_beyond_source_prefix':later_rows,'native_freezes_replayed':len(snapshots),'forecasts_recomputed':len(forecasts),
        'matured_outcomes_verified':cursor,'outcomes_beyond_source_prefix':len(outcomes)-cursor,'complete_joint_paths_verified':len(joint),'joint_log_loss':float(np.mean(joint)) if joint else None,
        'audited_through_utc_ns':last,'max_recomputed_probability_difference':maximum,'minimum_pre_target_commit_seconds':min(leads) if leads else None,
        'scope':'Actual receiver source replay and model/forecast/outcome chronology; small correlated sample, no accuracy/calibration guarantee.','training_ready':False}
    save(root/'follower-source-audit.json',result);return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('capture',type=Path);p.add_argument('--run',type=Path,default=Path('data/models/diwali1.1'));a=p.parse_args();print(json.dumps(check(a.capture,a.run),indent=2))
