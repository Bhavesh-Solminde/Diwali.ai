"""Audit a bounded prefix of forward records against its original source receipts."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from .prospective import Predictor
from .fan import range_labels,direction
from ..market_data.frozen_inputs import FrozenInputs
from ..market_data.validate_archive import save


def verify_outcome(outcome,record,candles):
    h=int(outcome['horizon'])-1
    if not 0<=h<15:raise ValueError('Invalid outcome horizon')
    start=record['target_start_ns']//10**6+h*60000
    if start!=outcome['target_start_ms']:raise ValueError('Changed outcome target')
    candle=candles.get(start)
    if not candle or candle['available_ns']>outcome['scored_utc_ns'] or (candle['close_ms']+1)*10**6>outcome['scored_utc_ns']:
        raise ValueError('Outcome before actual candle received/closed')
    if candle['available_ns']!=outcome['actual_available_ns'] or candle['source']!=outcome['actual_source']:raise ValueError('Changed outcome provenance')
    close=float(candle['values'][3]);ret=(close/record['prediction']['reference']-1)*10000;b=int(range_labels(ret));y=0 if ret<=-2 else 2 if ret>=2 else 1
    if close!=outcome['actual_close'] or b!=outcome['actual_bin'] or y!=outcome['actual_class']:raise ValueError('Changed actual label')
    p=np.asarray(record['prediction']['bin_probabilities'])[h]
    np.testing.assert_allclose(ret,outcome['actual_return_bp'],atol=1e-9)
    np.testing.assert_allclose(-np.log(max(p[b],1e-15)),outcome['bin_log_loss'],atol=1e-9)
    np.testing.assert_allclose(-np.log(max(direction(p)[y],1e-15)),outcome['direction_log_loss'],atol=1e-9)
    if bool(direction(p).argmax()==y)!=outcome['direction_correct']:raise ValueError('Changed directional scoring')


def check(root,run):
    model=Predictor(run);replay=FrozenInputs();snapshots={};forecasts={};prefixes={};records=[]
    complete=(root/'manifest.json').exists()
    expected=json.loads((root/'manifest.json').read_text())['raw_sha256'] if complete else None
    for f in sorted(root.glob('events-*.jsonl')):
        # Copy once. A live writer may continue; never call this a completed full scan.
        data=f.read_bytes();end=data.rfind(b'\n')+1;prefix=data[:end]
        if complete and (end!=len(data) or hashlib.sha256(data).hexdigest()!=expected.get(f.name)):
            raise ValueError('Completed capture raw manifest mismatch')
        prefixes[f.name]={'bytes':len(prefix),'sha256':hashlib.sha256(prefix).hexdigest(),'ignored_partial_tail_bytes':len(data)-end}
        records.extend(json.loads(line) for line in prefix.splitlines())
    if complete and set(expected)!=set(prefixes):raise ValueError('Completed capture raw file set mismatch')
    last=max((r['receipt_utc_ns'] for r in records),default=0)
    outcomes=sorted([json.loads(p.read_text()) for p in (root/'outcomes').glob('*.json')],key=lambda r:r['scored_utc_ns'])
    outcomes=[r for r in outcomes if r['scored_utc_ns']<=last];cursor=0;checked_outcomes=0;maximum=0;leads=[]
    keys=[(r['forecast_file'],r['horizon']) for r in outcomes]
    if len(keys)!=len(set(keys)):raise ValueError('Duplicate outcome horizon')
    for row in records:
        while cursor<len(outcomes) and outcomes[cursor]['scored_utc_ns']<row['receipt_utc_ns']:
            outcome=outcomes[cursor];key=outcome['forecast_file']
            if key not in forecasts:raise ValueError('Outcome has no previously committed forecast')
            verify_outcome(outcome,forecasts[key],replay.candles);cursor+=1;checked_outcomes+=1
        if row['kind']=='input_snapshot':
            meta=row['payload'];data=(root/'frozen-inputs'/meta['snapshot_file']).read_bytes();digest=hashlib.sha256(data).hexdigest()
            if digest!=meta['sha256']:raise ValueError('Changed input bytes')
            request=json.loads(data)
            if replay.freeze(request['snapshot_utc_ns'],request['snapshot_monotonic_ns'])!=request:raise ValueError('Input differs from actual then-received source messages')
            snapshots[digest]=request
        if row['kind']=='forecast_saved':
            meta=row['payload'];data=(root/'predictions'/meta['file']).read_bytes()
            if hashlib.sha256(data).hexdigest()!=meta['sha256']:raise ValueError('Changed forecast bytes')
            record=json.loads(data);request=snapshots[record['input_sha256']]
            if not request['snapshot_utc_ns']<=record['ready_utc_ns']<row['receipt_utc_ns']<record['target_start_ns']:
                raise ValueError('Forecast not committed after freeze and before target start')
            if record['ready_monotonic_ns']<request['snapshot_monotonic_ns']:raise ValueError('Invalid monotonic computation chronology')
            if record['prediction']['provenance']!=model.provenance:raise ValueError('Changed model/report/source provenance')
            expected=model.predict(request);actual=record['prediction'];diff=float(np.abs(np.asarray(expected['bin_probabilities'])-actual['bin_probabilities']).max())
            if diff>1e-7 or expected['target_close_ns']!=actual['target_close_ns'] or expected['reference']!=actual['reference']:raise ValueError('Forecast differs from saved input/model')
            maximum=max(maximum,diff);leads.append((record['target_start_ns']-row['receipt_utc_ns'])/1e9);forecasts[meta['file']]=record
        replay.ingest(row)
    result={'state':'bounded_forward_prefix_verified','capture_complete':complete,'completed_raw_manifest_verified':complete,
        'source_prefixes':prefixes,'source_records':len(records),'input_snapshots_replayed':len(snapshots),'pre_target_forecasts_recomputed':len(forecasts),
        'matured_outcomes_verified':checked_outcomes,'max_recomputed_probability_difference':maximum,'minimum_committed_lead_seconds':min(leads) if leads else None,
        'scope':'Source receipt replay, immutable input/forecast bytes, frozen model recomputation and then-available outcome scoring. Not a calibration or profitability proof.',
        'training_ready':False}
    save(root/'forward-prefix-audit.json',result);return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('capture',type=Path);p.add_argument('--run',type=Path,default=Path('data/models/diwali0.5'));a=p.parse_args()
    print(json.dumps(check(a.capture,a.run),indent=2))
