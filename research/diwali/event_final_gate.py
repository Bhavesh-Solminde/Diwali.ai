"""Artifact-bound, one-use final scoring guard shared across model versions."""
import json
import os
import time
from pathlib import Path

from .event_evaluation import verify_release,interval
from .event_final_train import selected_family
from .event_protocol import protocol
from ..market_data.validate_archive import file_hash,save

REGISTRY_NAME='btc-perp-2026-09-15-through-2026-09-29.json'


def resolve(release,record):
    path=Path(record['path'])
    return path if path.is_absolute() else Path(release).parent/path


def check_release(path):
    path=Path(path);r=verify_release(path)
    own=Path(__file__).resolve();score=own.with_name('event_final_score.py')
    frozen={Path(k).resolve() if Path(k).is_absolute() else (path.parent/k).resolve():v for k,v in r['source_hashes'].items()}
    if own not in frozen or score not in frozen:raise ValueError('Final guard and scorer sources must be frozen')
    artifacts=r['artifacts'];settings=json.loads(resolve(path,artifacts['run_protocol']).read_text());cal=json.loads(resolve(path,artifacts['calibration']).read_text());development=json.loads(resolve(path,artifacts['development_selection']).read_text())
    chosen=selected_family(development,protocol())
    if settings.get('candidate')!=chosen or settings.get('seed')!=17:raise ValueError('Final model differs from frozen development decision')
    if settings.get('development_report_sha256')!=artifacts['development_selection']['sha256']:raise ValueError('Different development selection artifact')
    transforms=json.loads(resolve(path,artifacts['fit_transforms']).read_text());fit_start,fit_stop=interval('final','fit')
    if not fit_start<=transforms['fit_cutoff_min_ns']<=transforms['fit_cutoff_max_ns']<fit_stop:raise ValueError('Transforms were fitted outside final-fit dates')
    expected_representation='one_second' if chosen.startswith('one_second') else 'events'
    if transforms['representation']!=expected_representation:raise ValueError('Final model and transform representations differ')
    weights_hash=artifacts['selected_model']['sha256']
    if cal['weights_sha256']!=weights_hash:raise ValueError('Calibration belongs to different weights')
    for name,sha in settings['source_hashes'].items():
        if file_hash(own.with_name(name))!=sha:raise ValueError('Selected model implementation changed since fitting')
    baseline=r.get('baseline_report')
    if not baseline or file_hash(resolve(path,baseline))!=baseline['sha256']:raise ValueError('Final baseline report must be frozen')
    bp=resolve(path,baseline);br=json.loads(bp.read_text())
    if br.get('state')!='baselines_fitted_without_final_evaluation':raise ValueError('Final baselines are incomplete')
    required_baselines={'fit-transforms.json','histograms.npz','calibration.json','flow_logistic/weights.pt','flow_logistic/selection.json'}|{f'flow_boosted_trees/horizon-{h:02d}.joblib' for h in range(1,16)}
    if set(br['artifact_hashes'])!=required_baselines:raise ValueError('Missing final baseline artifacts')
    if br['data_hashes']!=transforms['source_hashes']:raise ValueError('Baselines and final model use different input cohorts')
    for name,sha in br['artifact_hashes'].items():
        target=(bp.parent/name).resolve()
        if not target.is_relative_to(bp.parent.resolve()) or file_hash(target)!=sha:raise ValueError('Changed final baseline artifact')
    # Baseline source hashes are frozen in their own protocol as well.
    bprotocol=json.loads((bp.parent/'run-protocol.json').read_text())
    if not bprotocol['source_hashes']:raise ValueError('Baseline sources must be frozen')
    for name,sha in bprotocol['source_hashes'].items():
        if file_hash(own.with_name(name))!=sha:raise ValueError('Final baseline implementation changed')
    preflight=r.get('preflight_report')
    if not preflight or file_hash(resolve(path,preflight))!=preflight['sha256']:raise ValueError('A frozen nonfinal inference preflight is required')
    pr=json.loads(resolve(path,preflight).read_text())
    if pr.get('state')!='preflight_passed':raise ValueError('Nonfinal inference preflight did not pass')
    for name in ['selected_model','fit_transforms','calibration']:
        if pr['artifact_hashes'][name]!=artifacts[name]['sha256']:raise ValueError('Preflight belongs to different model artifacts')
    if pr['artifact_hashes']['baseline_report']!=baseline['sha256']:raise ValueError('Preflight belongs to different baselines')
    if not pr['source_hashes']:raise ValueError('Preflight implementation must be frozen')
    for name,sha in pr['source_hashes'].items():
        if file_hash(own.with_name(name))!=sha:raise ValueError('Preflight/evaluation implementation changed')
    return r


def claim(path,registry=Path('data/evaluation-consumption')):
    path=Path(path);check_release(path);registry=Path(registry);registry.mkdir(parents=True,exist_ok=True);target=registry/REGISTRY_NAME
    record={'state':'claimed_before_loading_labels_for_scoring','release_sha256':file_hash(path),'started_ns':time.time_ns(),'pid':os.getpid(),
            'period':['2026-09-15','2026-09-29'],'scope':'This interval is consumed for subsequent model versions too; no new-path retry.'}
    try:fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError:raise ValueError('Reserved interval already claimed; do not repeat final evaluation or tune against it')
    with os.fdopen(fd,'w') as stream:
        json.dump(record,stream,indent=2);stream.flush();os.fsync(stream.fileno())
    return target


def finish(path,release,state,report=None,error=None):
    path=Path(path);record=json.loads(path.read_text())
    if record['release_sha256']!=file_hash(Path(release)) or record['pid']!=os.getpid():raise ValueError('Final scoring claim belongs to another execution')
    record.update({'state':state,'finished_ns':time.time_ns()})
    if report is not None:record['report_sha256']=file_hash(Path(report))
    if error is not None:record['error']=str(error)
    save(path,record)
