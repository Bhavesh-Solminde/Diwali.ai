"""Verify recorded frozen request bytes, direct provenance and strict time boundaries."""
import argparse
import hashlib
import json
from pathlib import Path
from .quality import audit
from .frozen_inputs import FrozenInputs,MINUTE,target_after
from .validate_archive import save


def check(root):
    quality=audit(root)
    replay=FrozenInputs();checked=[]
    for f in sorted(root.glob('events-*.jsonl')):
        for line in f.open():
            row=json.loads(line)
            if row['kind']=='input_snapshot':
                meta=row['payload'];path=root/'frozen-inputs'/meta['snapshot_file'];data=path.read_bytes()
                if hashlib.sha256(data).hexdigest()!=meta['sha256']:raise ValueError('Frozen request hash mismatch')
                request=json.loads(data);at=request['snapshot_utc_ns']
                expected=replay.freeze(at,request['snapshot_monotonic_ns'])
                if request!=expected:raise ValueError('Request differs from then-received source messages')
                if request['target_start_ns']!=target_after(at) or request['target_end_ns']!=target_after(at)+MINUTE:
                    raise ValueError('Target not next full minute')
                if len(request['candles'])!=1440 or len(request['book_seconds'])!=60:raise ValueError('Incomplete context')
                for c in request['candles']:
                    if c['available_ns']>=at or (c['close_ms']+1)*10**6>at:raise ValueError('Future candle input')
                for r in request['trades']:
                    if r['available_ns']>=at or max(r['payload']['T'],r['payload']['E'])*10**6>=at:
                        raise ValueError('Future trade input')
                for r in request['book_seconds']:
                    b=r['book'];grid=r['grid_utc_ns']
                    if grid>=at or max(b['available_ns'],b['source_receipt_ns'],b['exchange_event_ms']*10**6)>grid:
                        raise ValueError('Future book input')
                    if not b['levels']['top20_within_snapshot_bounds']:raise ValueError('Unverified book range')
                checked.append({'snapshot_utc_ns':at,'target_start_ns':request['target_start_ns'],
                    'sha256':meta['sha256'],'source_replay_identical':True})
            replay.ingest(row)
    result={'state':'frozen_requests_verified' if checked else 'no_eligible_frozen_requests',
        'quality':quality,'requests_verified':len(checked),'requests':checked,
        'neural_predictions_generated':0,'model_performance_tested':False,'training_ready':False,
        'scope':'Finite live input/provenance smoke check; not sustained coverage or model accuracy'}
    save(root/'frozen-input-audit.json',result);return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('capture',type=Path)
    print(json.dumps(check(p.parse_args().capture),indent=2))
