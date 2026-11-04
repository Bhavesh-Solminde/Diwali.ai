import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from research.diwali.event_final_gate import check_release,claim,finish
from research.diwali.event_evaluation import interval
from research.diwali.event_protocol import protocol
from research.diwali.event_study import choose_family
from research.market_data.validate_archive import file_hash


def release_fixture(tmp_path):
    root=Path(__file__).resolve().parents[2]/'research/diwali'
    # The repository root is parents[2] for this tests/diwali file.
    if not root.exists():root=Path.cwd()/'research/diwali'
    def write(name,value):
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value));return p
    settings=protocol();runs=[]
    for c in settings['neural_candidates']:
        for f in settings['development_folds']:
            for s in settings['seeds']:runs.append({'candidate':c,'fold':f,'seed':s,'partitions':{'score':{'mean15_bin_log_loss':2.}}})
    development=write('development.json',{'state':'development_complete','neural_runs':runs,'decision':choose_family(runs,settings)})
    weights=tmp_path/'weights.pt';weights.write_bytes(b'own-test-placeholder')
    model_protocol=write('run-protocol.json',{'candidate':'one_second_temporal_conv','seed':17,'source_hashes':{'event_model.py':file_hash(root/'event_model.py')},'development_report_sha256':file_hash(development)})
    start,stop=interval('final','fit');data={'fit':'known-test-cohorts'}
    transform=write('fit-transforms.json',{'representation':'one_second','fit_cutoff_min_ns':start,'fit_cutoff_max_ns':stop-1,'source_hashes':data})
    calibration=write('calibration.json',{'weights_sha256':file_hash(weights)})
    names=['fit-transforms.json','histograms.npz','calibration.json','flow_logistic/weights.pt','flow_logistic/selection.json']+[f'flow_boosted_trees/horizon-{h:02d}.joblib' for h in range(1,16)]
    hashes={}
    for name in names:
        p=tmp_path/'baselines'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'own-baseline-placeholder');hashes[name]=file_hash(p)
    baseline=write('baselines/report.json',{'state':'baselines_fitted_without_final_evaluation','artifact_hashes':hashes,'data_hashes':data})
    write('baselines/run-protocol.json',{'source_hashes':{'event_baselines.py':file_hash(root/'event_baselines.py')}})
    sources={str(root/n):file_hash(root/n) for n in ['event_final_gate.py','event_final_score.py']}
    files={'run_protocol':model_protocol,'selected_model':weights,'fit_transforms':transform,'calibration':calibration,'development_selection':development}
    preflight=write('preflight.json',{'state':'preflight_passed','artifact_hashes':{'selected_model':file_hash(weights),'fit_transforms':file_hash(transform),'calibration':file_hash(calibration),'baseline_report':file_hash(baseline)},'source_hashes':{'event_final_gate.py':file_hash(root/'event_final_gate.py')}})
    return write('release.json',{'stage':'final_evaluation','final_period':['2026-09-15','2026-09-29'],
                  'artifacts':{n:{'path':str(p),'sha256':file_hash(p)} for n,p in files.items()},
                  'baseline_report':{'path':str(baseline),'sha256':file_hash(baseline)},'source_hashes':sources,
                  'preflight_report':{'path':str(preflight),'sha256':file_hash(preflight)}})


def test_atomic_one_use_claim_survives_copy_and_failure(tmp_path):
    release=release_fixture(tmp_path);check_release(release);registry=tmp_path/'registry'
    def attempt():
        try:return claim(release,registry)
        except ValueError:return None
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:attempt(),range(2)))
    tickets=[r for r in results if r is not None];assert len(tickets)==1
    finish(tickets[0],release,'failed_after_final_claim',error='test failure')
    copy=tmp_path/'copied-release.json';copy.write_bytes(release.read_bytes())
    with pytest.raises(ValueError,match='already claimed'):claim(copy,registry)


def test_changed_baseline_or_mismatched_transforms_rejected_before_consumption(tmp_path):
    release=release_fixture(tmp_path);baseline=tmp_path/'baselines/histograms.npz';baseline.write_bytes(b'changed')
    with pytest.raises(ValueError,match='baseline artifact'):claim(release,tmp_path/'registry')
    assert not (tmp_path/'registry').exists()
