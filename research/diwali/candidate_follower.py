"""Issue frozen candidate forecasts from a running receiver's immutable freezes, without another feed."""
import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import torch

from .path import PathModel,forecast,chain_losses
from .fan import direction
from .prospective import ForwardStore,live_input,exclusive_json
from ..market_data.frozen_inputs import write_snapshot,prediction_record
from ..market_data.validate_archive import file_hash,save


class Predictor:
    def __init__(self,run):
        from .refined import RefinedJoint
        from .flow import FlowJoint
        self.run=run;r=json.loads((run/'report.json').read_text());self.model_id=r['model'];self.mode=r['selected_mode'];self.info=r['models'][self.mode]
        if self.model_id not in ['diwali0.9','diwali1.1']:raise ValueError('Unsupported candidate')
        prep=Path('data/models/diwali0.5/preprocessing.json');self.prep=json.loads(prep.read_text());scalers=Path('data/btc-perp/aligned-button-pilot-202610-v1/scalers.json')
        if file_hash(scalers)!=self.prep['aligned_scaler_sha256']:raise ValueError('Changed live scalers')
        self.scalers=json.loads(scalers.read_text());checkpoint=run/f'{self.mode}-17.pt'
        if file_hash(checkpoint)!=self.info['checkpoint_sha256']:raise ValueError('Changed checkpoint')
        definition='refined.py' if self.model_id=='diwali0.9' else 'flow.py'
        if file_hash(Path('research/diwali')/definition)!=r['protocol']['model_source_sha256']:raise ValueError('Changed candidate source')
        if self.model_id=='diwali0.9':model=RefinedJoint(self.mode,checkpoint,r['protocol']['parents'],self.info['residual_temperatures'])
        else:model=FlowJoint(checkpoint,r['protocol']['parent'],self.info['residual_temperatures'],self.mode)
        self.model=model.eval();torch.set_num_threads(4)
        names=['refined.py','flow.py','directional.py','path.py','fan.py','model.py','probability.py','coupled.py','prospective.py','candidate_follower.py','net_direction.py']
        self.provenance={'model':self.model_id,'mode':self.mode,'checkpoint_sha256':file_hash(checkpoint),'report_sha256':file_hash(run/'report.json'),
            'preprocessing_sha256':file_hash(prep),'sources':{name:file_hash(Path('research/diwali')/name) for name in names}}

    def predict(self,request):
        x,meta=live_input(request,self.scalers,self.prep);a,t,p,_=forecast(self.model,x[None],self.info['temperatures'],'cpu')
        from .net_direction import direction_summary
        return {'bin_probabilities':p[0].tolist(),'direction_probabilities':direction(p[0]).tolist(),'overall_direction':direction_summary(p[0]),'initial':a[0].tolist(),'transitions':t[0].tolist(),**meta,
            'target_close_ns':[request['target_start_ns']+(h+1)*60_000_000_000 for h in range(15)],'provenance':self.provenance,
            'scope':'Joint15 closes and final displacement probabilities from frozen received inputs; no orders placed.'}


def complete_lines(path,offset):
    with path.open('rb') as f:f.seek(offset);data=f.read()
    end=data.rfind(b'\n')+1
    return [json.loads(line) for line in data[:end].splitlines()],offset+end


def joint_scores(store):
    groups={}
    for row in store.outcomes:groups.setdefault(row['forecast_file'],{})[row['horizon']]=row
    results=[]
    for name,rows in groups.items():
        if len(rows)!=15:continue
        record=json.loads((store.root/'predictions'/name).read_text());p=record['prediction'];y=np.array([[rows[h]['actual_bin'] for h in range(1,16)]])
        loss=chain_losses(np.asarray(p['initial'])[None],np.asarray(p['transitions'])[None],y)[0]
        results.append({'forecast_file':name,'joint_log_loss':float(loss)})
    save(store.root/'joint-status.json',{'complete_paths':len(results),'mean_joint_log_loss':float(np.mean([r['joint_log_loss'] for r in results])) if results else None,
        'scope':'Small correlated prospective smoke sample; not enough for calibration/efficacy claims.'})


def follow(source,run,output,issue_seconds):
    source=source.resolve();source_status=json.loads((source/'status.json').read_text())
    remaining=source_status['start_utc_ns']/1e9+3600-time.time()
    # Keep the final16min targets plus1min label margin inside the receiver's budget.
    issue_seconds=min(issue_seconds,int(remaining-17*60))
    if source_status['state']=='stopped' or issue_seconds<60:raise ValueError('Receiver has insufficient live time for a new fully maturing forecast')
    predictor=Predictor(run);model_id=predictor.model_id;store=ForwardStore(output,run);store.predictor=predictor;offsets={};end=time.monotonic()+issue_seconds;stop=end+17*60
    save(output/'follower-protocol.json',{'model':model_id,'source_capture':str(source),'issue_seconds':issue_seconds,'maximum_label_drain_seconds':17*60,
        'started_utc_ns':store.started,'only_snapshots_at_or_after_start':True,'new_network_connections':False,'orders_placed':False,'provenance':predictor.provenance})
    try:
        store.status('following_source')
        while time.monotonic()<stop:
            for path in sorted(source.glob('events-*.jsonl')):
                rows,offset=complete_lines(path,offsets.get(path.name,0));offsets[path.name]=offset
                for row in rows:
                    if row['kind']=='input_snapshot' and row['payload']['snapshot_utc_ns']>=store.started and time.monotonic()<end:
                        try:
                            meta=row['payload'];data=(source/'frozen-inputs'/meta['snapshot_file']).read_bytes()
                            if hashlib.sha256(data).hexdigest()!=meta['sha256']:raise ValueError('Changed source freeze')
                            request=json.loads(data)
                            if store.inputs.freeze(request['snapshot_utc_ns'],request['snapshot_monotonic_ns'])!=request:raise ValueError('Source freeze differs from actual receipts')
                            if time.time_ns()>=request['target_start_ns']:raise ValueError('Reader missed target deadline')
                            stored=write_snapshot(output/'frozen-inputs',request);store.save('input_snapshot',stored,source_capture=str(source),source_file=path.name)
                            p=predictor.predict(request);record=prediction_record(request,p,model_id,time.time_ns(),time.monotonic_ns())
                            name=f"{request['snapshot_utc_ns']}-{model_id}.json";digest=exclusive_json(output/'predictions'/name,record)
                            if time.time_ns()>=request['target_start_ns']:raise ValueError('Follower commit missed target deadline')
                            store.save('forecast_saved',{'file':name,'sha256':digest,'input_sha256':record['input_sha256'],'target_start_ns':record['target_start_ns']})
                            store.forecasts+=1;store.snapshot_count+=1;store.pending[name]={'record':record,'done':set()}
                        except ValueError as exc:
                            store.forward_rejections[str(exc)]+=1;store.save('forward_rejected',{'reason':str(exc)})
                    # Preserve receiver receipt times; do not relabel these as follower arrivals.
                    store.inputs.ingest(row)
            store.score_matured();joint_scores(store)
            save(output/'source-offsets.json',offsets)
            if time.monotonic()>=end and not store.pending:break
            if (source/'manifest.json').exists():
                store.save('source_stopped',{'pending':len(store.pending)});break
            time.sleep(.5)
    finally:
        store.score_matured();joint_scores(store);store.finish()
        manifest=json.loads((output/'manifest.json').read_text());manifest.update({'forward_follower':True,'source_capture':str(source),
            'source_receipt_times_retained':True,'pending_paths_at_stop':len(store.pending),'limitations':['Metadata/forecast journal follows the separately preserved native receiver; not an independent second receiver.','Small correlated sample; no calibration or trading guarantee.']});save(output/'manifest.json',manifest)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--run',type=Path,default=Path('data/models/diwali1.1'));p.add_argument('--output',type=Path,required=True);p.add_argument('--issue-seconds',type=int,default=600);a=p.parse_args()
    if a.issue_seconds<=0:raise ValueError('Positive forecast duration required')
    follow(a.source,a.run,a.output,a.issue_seconds)
