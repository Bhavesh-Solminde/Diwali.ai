"""Exercise frozen model and baselines on selection inputs before final release."""
import argparse
import json
from pathlib import Path

import numpy as np
import torch

from .event_data_exact import ExactEventData
from .event_model import EventModel
from .event_train import infer,probabilities
from .event_final_score import baseline_predictions
from ..market_data.validate_archive import file_hash,save


def main():
    p=argparse.ArgumentParser();p.add_argument('--model',type=Path,required=True);p.add_argument('--baselines',type=Path,required=True);p.add_argument('--cohort',type=Path,required=True);p.add_argument('--features',type=Path,required=True);p.add_argument('--content-audit',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=json.loads((a.model/'report.json').read_text());settings=json.loads((a.model/'run-protocol.json').read_text());br=json.loads((a.baselines/'report.json').read_text())
    if r['state']!='fitted_selected_calibrated_without_final_evaluation' or br['state']!='baselines_fitted_without_final_evaluation':raise ValueError('Final artifacts are not complete')
    weights=a.model/'weights.pt';transforms_path=a.model/'fit-transforms.json';calpath=a.model/'calibration.json'
    if file_hash(weights)!=r['selection']['weights_sha256']:raise ValueError('Changed model weights')
    for name,sha in br['artifact_hashes'].items():
        if file_hash(a.baselines/name)!=sha:raise ValueError('Changed baseline artifact')
    data=ExactEventData(a.cohort,a.features,a.content_audit);ids,_=data.partition('final','select')
    if len(ids)<10:raise ValueError('Insufficient nonfinal inputs for preflight')
    ids=ids[np.linspace(0,len(ids)-1,10,dtype=int)]
    model=EventModel('attention' if settings['candidate']=='event_attention' else 'temporal_conv',width=settings['neural_width'],block=settings['event_block_groups'])
    model.load_state_dict(torch.load(weights,map_location='cpu',weights_only=True));transforms=json.loads(transforms_path.read_text());cal=json.loads(calpath.read_text());torch.set_num_threads(4)
    cpu=probabilities(infer(model,data,ids,transforms,'cpu',settings['batch_size']),cal['temperatures']);maximum=None
    if torch.backends.mps.is_available():
        model.to('mps');mps=probabilities(infer(model,data,ids,transforms,'mps',settings['batch_size']),cal['temperatures']);maximum=float(np.abs(cpu-mps).max())
        if maximum>1e-5:raise ValueError('CPU/MPS final inference differs materially')
    predictions={'diwali1.4':cpu};predictions.update(baseline_predictions(data,ids,Path.cwd(),{'baseline_report':{'path':str((a.baselines/'report.json').resolve())}}));checks={}
    for name,prob in predictions.items():
        error=float(np.abs(prob.sum(-1)-1).max())
        if prob.shape!=(10,15,26) or not np.isfinite(prob).all() or (prob<0).any() or error>1e-10:raise ValueError('Invalid preflight probability distributions')
        checks[name]={'shape':list(prob.shape),'all_finite':True,'maximum_probability_sum_error':error}
    source_names=['event_final_preflight.py','event_final_gate.py','event_final_score.py','event_model.py','event_data.py','event_data_exact.py','event_baselines.py','event_train.py']
    report={'state':'preflight_passed','selection_origins_checked':10,'checks':checks,'maximum_cpu_mps_probability_difference':maximum,
            'artifact_hashes':{'selected_model':file_hash(weights),'fit_transforms':file_hash(transforms_path),'calibration':file_hash(calpath),'baseline_report':file_hash(a.baselines/'report.json')},
            'source_hashes':{n:file_hash(Path(__file__).with_name(n)) for n in source_names},
            'reserved_final_labels_loaded':False,'existing_selection_labels_loaded_for_loader_validation':True,'target_outcomes_used_in_preflight':False,
            'scope':'Engineering inference on already used selection inputs; no performance score or final-test access.'}
    save(a.output,report);print(json.dumps({'state':report['state'],'models_checked':list(checks)}))


if __name__=='__main__':main()
