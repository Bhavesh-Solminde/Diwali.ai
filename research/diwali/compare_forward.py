"""Matched, source-audited forward smoke comparison; does not train or tune models."""
import argparse
import json
from pathlib import Path

import numpy as np

from .audit_follower import check as audit_follower
from .audit_forward import check as audit_native
from .path import BANDS,propagate,chain_losses,path_events,event_metrics
from .fan import direction,range_metrics
from .probability import metrics
from ..market_data.validate_archive import save


def committed(root,prefixes):
    rows={}
    for filename,meta in prefixes.items():
        data=(root/filename).read_bytes()[:meta['bytes']]
        if __import__('hashlib').sha256(data).hexdigest()!=meta['sha256']:raise ValueError('Changed audited prefix')
        for line in data.splitlines():
            row=json.loads(line)
            if row['kind']=='forecast_saved':
                name=row['payload']['file'];record=json.loads((root/'predictions'/name).read_text());rows[name]=record
    return rows


def compare(root):
    run=Path('data/models/diwali0.6');audit=audit_follower(root,run);source=Path(json.loads((root/'follower-protocol.json').read_text())['source_capture']);native=audit_native(source,Path('data/models/diwali0.5'))
    own=committed(root,audit['follower_prefixes']);old={r['input_sha256']:r for r in committed(source,native['source_prefixes']).values()};outcomes={}
    for path in (root/'outcomes').glob('*.json'):
        row=json.loads(path.read_text())
        if row['scored_utc_ns']<=audit['audited_through_utc_ns']:outcomes.setdefault(row['forecast_file'],{})[row['horizon']]=row
    bases=json.loads((run/'baselines.json').read_text());cuts=np.asarray(bases['cuts']);samples=[]
    snapshot_files={__import__('hashlib').sha256(p.read_bytes()).hexdigest():p for p in (root/'frozen-inputs').glob('*.json')}
    for name,labels in outcomes.items():
        if len(labels)!=15 or name not in own:continue
        record=own[name];peer=old[record['input_sha256']];a=record['prediction'];b=peer['prediction']
        if record['target_start_ns']!=peer['target_start_ns'] or abs(a['reference']-b['reference'])>1e-8:raise ValueError('Unmatched forecast target/reference')
        request=json.loads(snapshot_files[record['input_sha256']].read_text());closes=np.asarray([c['values'][3] for c in request['candles'][-16:]],float)
        group=int(np.searchsorted(cuts,np.std(np.diff(np.log(closes)))*10000,side='right'));baseline=bases['conditional'][group]
        aa=np.asarray(baseline['initial'])[None];tt=np.asarray(baseline['transitions'])[None];pm=propagate(aa,tt)[0]
        samples.append({'y':np.asarray([labels[h]['actual_bin'] for h in range(1,16)]),'05':np.asarray(b['bin_probabilities']),'06':np.asarray(a['bin_probabilities']),
            '06_initial':np.asarray(a['initial']),'06_transitions':np.asarray(a['transitions']),'baseline':pm,'baseline_initial':aa[0],'baseline_transitions':tt[0]})
    result={'state':'matched_prospective_smoke_only','complete_forecasts':len(samples),'same_receiver_same_origins':True,'all15_targets_matured_for_reported_forecasts':True,
        'all_committed_forecasts_complete':len(samples)==audit['forecasts_recomputed'],'follower_stopped':audit['capture_complete'],
        'orders_placed':False,'scope':'Small overlapping single-session sample. Neither an independent multi-day calibration study nor training/selection data for0.7.',
        'audit':{'06_forecasts_recomputed':audit['forecasts_recomputed'],'06_outcomes_verified':audit['matured_outcomes_verified'],'native05_forecasts_recomputed':native['pre_target_forecasts_recomputed']},'models':{}}
    if samples:
        y=np.stack([s['y'] for s in samples]);rows=np.arange(len(y))[:,None];hs=np.arange(15)[None]
        for key,label in [('05','diwali0.5'),('06','diwali0.6'),('baseline','volatility_markov')]:
            p=np.stack([s[key] for s in samples]);dp=direction(p);events={}
            if key=='05':joint=-np.log(np.maximum(p[rows,hs,y],1e-15)).sum(1)
            else:joint=chain_losses(np.stack([s[key+'_initial'] for s in samples]),np.stack([s[key+'_transitions'] for s in samples]),y)
            for band,(lo,hi) in BANDS.items():
                inside=(y>=lo)&(y<=hi)
                if key=='05':mass=p[:,:,lo:hi+1].sum(2);stay=mass.prod(1);visit=1-(1-mass).prod(1)
                else:stay,visit=path_events(np.stack([s[key+'_initial'] for s in samples]),np.stack([s[key+'_transitions'] for s in samples]),lo,hi)
                events[band]={'stay':event_metrics(inside.all(1),stay),'visit':event_metrics(inside.any(1),visit)}
            yy=np.where(y<10,0,np.where(y>=16,2,1));result['models'][label]={'joint_log_loss':float(joint.mean()),'mean15_marginal_bin_log_loss':float(-np.log(np.maximum(p[rows,hs,y],1e-15)).mean()),
                'h1_direction':metrics(yy[:,0],dp[:,0]),'path_events':events}
    save(root/'matched-forward-comparison.json',result);return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('capture',type=Path);a=p.parse_args();r=compare(a.capture);print(json.dumps({'complete_forecasts':r['complete_forecasts'],'models':{k:{m:v[m] for m in ['joint_log_loss','mean15_marginal_bin_log_loss']} for k,v in r['models'].items()}},indent=2))
