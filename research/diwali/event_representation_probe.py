"""Input-only structural probe; does not change frozen study settings or weights."""
import argparse
import json
from pathlib import Path

import numpy as np
import torch

from .event_model import EventModel
from .event_data import EventData
from ..market_data.validate_archive import file_hash,save


def main():
    p=argparse.ArgumentParser();p.add_argument('--cohort',type=Path,required=True);p.add_argument('--features',type=Path,required=True);p.add_argument('--content-audit',type=Path,required=True);p.add_argument('--study',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    data=EventData(a.cohort,a.features,a.content_audit);j=int(data.partition('A','fit')[0][0]);raw=data.raw(j)[0]
    where=int(np.flatnonzero((raw[:,81]>0)&(raw[:,82]==0))[0]);torch.set_num_threads(2);results=[]
    for candidate,mode in [('event_temporal_conv','temporal_conv'),('event_attention','attention')]:
        root=a.study/f'A-{candidate}-seed17';r=json.loads((root/'report.json').read_text());settings=json.loads((root/'run-protocol.json').read_text());transforms=json.loads((root/'fit-transforms.json').read_text())
        if file_hash(root/'weights.pt')!=r['selection']['weights_sha256'] or settings['source_hashes']['event_model.py']!=file_hash(Path(__file__).with_name('event_model.py')):raise ValueError('Changed fitted model')
        model=EventModel(mode);model.load_state_dict(torch.load(root/'weights.pt',map_location='cpu',weights_only=True));model.eval()
        args,_=data.batch(np.array([j]),transforms,'cpu');event,mask,candles,seed,groups,cm,reference=args;single=event[:,where:where+1].clone();predictions=[]
        with torch.inference_mode():
            for n in [1,2,16]:
                x=single.repeat(1,n,1);valid=torch.ones(1,n,dtype=torch.bool);same_time=torch.zeros(1,n,dtype=torch.long)
                predictions.append(model(x,valid,candles,seed,same_time,cm,reference).softmax(-1).numpy())
        differences=[float(np.abs(x-predictions[0]).max()) for x in predictions[1:]]
        results.append({'candidate':candidate,'weights_sha256':r['selection']['weights_sha256'],
                        'same_time_identical_fill_counts':[1,2,16],'maximum_probability_changes':differences,
                        'count_information_unidentifiable_in_this_case':max(differences)<1e-6})
    report={'state':'complete','probe':'Repeat an otherwise identical market-fill feature vector in one availability-time group; hold all other inputs fixed.',
            'models':results,'target_outcomes_used_in_probe':False,'loader_validates_existing_development_targets':True,'synthetic_counterexample':True,
            'mechanism':'Normalized set pooling averages away multiplicity when every vector in a group is identical. Individual rows enter projection but cardinality is not guaranteed to survive.',
            'implication':'This is a remaining representation limitation, not proof of its impact on natural forecast errors.',
            'next_bounded_design':'After frozen1.4 comparison, test explicit group counts/size sums or sum-plus-mean pooling while retaining same-time permutation invariance.',
            'frozen_study_changed':False,'probe_source_sha256':file_hash(Path(__file__)),'model_source_sha256':file_hash(Path(__file__).with_name('event_model.py'))}
    save(a.output,report);print(json.dumps(report,indent=2))


if __name__=='__main__':main()
