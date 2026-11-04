"""Compare matched, fully matured forecasts with nonoverlapping target sets."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from .audit_anchored import check
from .net_direction import net_metrics
from .path import chain_losses
from ..market_data.validate_archive import save


def committed(root,audit,cutoff):
    records={}
    for name,prefix in audit['follower_prefixes'].items():
        data=(root/name).read_bytes()[:prefix['bytes']]
        if hashlib.sha256(data).hexdigest()!=prefix['sha256']:raise ValueError('Changed audited prefix')
        for line in data.splitlines():
            row=json.loads(line)
            if row['kind']=='forecast_saved' and row['receipt_utc_ns']<=cutoff:
                file=row['payload']['file'];raw=(root/'predictions'/file).read_bytes()
                if hashlib.sha256(raw).hexdigest()!=row['payload']['sha256']:raise ValueError('Changed prediction')
                record=json.loads(raw);key=record['input_sha256']
                if key in records:raise ValueError('Duplicate origin')
                records[key]=(file,record)
    outcomes={}
    for p in (root/'outcomes').glob('*.json'):
        row=json.loads(p.read_text())
        if row['scored_utc_ns']<=cutoff:outcomes.setdefault(row['forecast_file'],{})[row['horizon']]=row
    complete={}
    for key,(file,r) in records.items():
        labels=outcomes.get(file,{})
        if len(labels)==15:complete[key]=(r,np.asarray([labels[h]['actual_bin'] for h in range(1,16)]))
    return records,complete


def compare(left,right):
    roots=[left,right];runs=[Path('data/models/diwali0.9'),Path('data/models/diwali1.2')]
    protocols=[json.loads((p/'follower-protocol.json').read_text()) for p in roots]
    if protocols[0]['source_capture']!=protocols[1]['source_capture']:raise ValueError('Receivers differ')
    audits=[check(p,r) for p,r in zip(roots,runs)];cutoff=min(a['audited_through_utc_ns'] for a in audits);groups=[committed(p,a,cutoff) for p,a in zip(roots,audits)]
    keys=sorted(set(groups[0][1])&set(groups[1][1]));result={'state':'matched_prospective_smoke_only','matched_complete_origins':len(keys),'audited_cutoff_utc_ns':cutoff,
        'follower_stopped':[a['capture_complete'] for a in audits],'committed_counts':[len(g[0]) for g in groups],'complete_counts':[len(g[1]) for g in groups],
        'same_receiver_same_frozen_inputs':True,'minimum_spacing_seconds':[p['spacing_seconds'] for p in protocols],'only_fully_matured15_close_paths_scored':True,'models':{},
        'scope':'One small session with nonoverlapping target candle sets; not independent days, perfect probabilities, entry efficacy or training/selection evidence.'}
    for key in keys:
        a,ya=groups[0][1][key];b,yb=groups[1][1][key];np.testing.assert_array_equal(ya,yb)
        if a['target_start_ns']!=b['target_start_ns'] or a['prediction']['reference']!=b['prediction']['reference']:raise ValueError('Reference or target differs')
    if keys:
        y=np.stack([groups[0][1][key][1] for key in keys]);rows=np.arange(len(y))[:,None];hs=np.arange(15)[None]
        for root,g in zip(runs,groups):
            forecasts=[g[1][key][0]['prediction'] for key in keys];p=np.asarray([f['bin_probabilities'] for f in forecasts]);a=np.asarray([f['initial'] for f in forecasts]);t=np.asarray([f['transitions'] for f in forecasts])
            result['models'][root.name]={'final_direction':net_metrics(y[:,-1],p[:,-1]),'mean15_range_log_loss':float(-np.log(np.maximum(p[rows,hs,y],1e-15)).mean()),'joint_log_loss':float(chain_losses(a,t,y).mean())}
        result['always_half_final_binary_log_loss']=float(np.log(2))
    save(right/'matched-candidate-comparison.json',result);return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('left',type=Path);p.add_argument('right',type=Path);a=p.parse_args();print(json.dumps(compare(a.left,a.right),indent=2))
