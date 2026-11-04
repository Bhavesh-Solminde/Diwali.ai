"""Unchanged neural study settings, with exact timestamp control preprocessing."""
import argparse
from pathlib import Path
import torch

from .event_data_exact import ExactEventData
from .event_protocol import protocol
from .event_train import train
from ..market_data.validate_archive import file_hash,save


def main():
    p=argparse.ArgumentParser();p.add_argument('--cohort',type=Path,required=True);p.add_argument('--features',type=Path,required=True);p.add_argument('--content-audit',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--fold',choices=['A','B','C'],required=True);p.add_argument('--candidate',choices=['one_second_temporal_conv'],required=True);p.add_argument('--seed',type=int,choices=[17,29],required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);settings=protocol()
    settings.update({'active_fold':a.fold,'active_candidate':a.candidate,'active_seed':a.seed,
                     'implementation_amendment':'Exact integer timestamps determine second buckets. Earlier failed float32-binning control remains preserved and excluded.',
                     'source_hashes':{n:file_hash(Path(__file__).with_name(n)) for n in ['event_train_exact.py','event_data_exact.py','event_train.py','event_data.py','event_model.py','event_protocol.py','event_evaluation.py']}})
    save(a.output/'run-protocol.json',settings);data=ExactEventData(a.cohort,a.features,a.content_audit);indices={};counts={}
    for name in ['fit','select','calibrate','score']:
        indices[name],counts[name]=data.partition(a.fold,name)
        if len(indices[name])<settings['minimum_partition_origins'][name]:raise ValueError('Insufficient frozen partition')
    save(a.output/'cohorts.json',{'source_hashes':data.hashes,'partitions':counts})
    transforms=data.fit_transforms(indices['fit'],'one_second');save(a.output/'fit-transforms.json',transforms)
    torch.set_num_threads(4);device='mps' if torch.backends.mps.is_available() else 'cpu'
    train(data,a.fold,a.candidate,a.seed,a.output,transforms,indices,settings,device)


if __name__=='__main__':main()
