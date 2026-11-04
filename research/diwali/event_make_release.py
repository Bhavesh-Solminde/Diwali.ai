"""Freeze a deliberate final-test release after all earlier stages complete."""
import argparse
import json
import os
from pathlib import Path

from .event_final_gate import check_release
from ..market_data.validate_archive import file_hash


def main():
    p=argparse.ArgumentParser();p.add_argument('--model',type=Path,required=True);p.add_argument('--baselines',type=Path,required=True);p.add_argument('--development-report',type=Path,required=True);p.add_argument('--preflight-report',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    report=json.loads((a.model/'report.json').read_text())
    if report.get('state')!='fitted_selected_calibrated_without_final_evaluation':raise ValueError('Final model build incomplete')
    files={'run_protocol':a.model/'run-protocol.json','selected_model':a.model/'weights.pt','fit_transforms':a.model/'fit-transforms.json',
           'calibration':a.model/'calibration.json','development_selection':a.development_report}
    source_names=['event_final_gate.py','event_final_score.py','event_final_preflight.py','event_make_release.py','event_model.py','event_data.py','event_data_exact.py',
                  'event_final_data.py','event_train.py','event_evaluation.py','event_baselines.py','event_protocol.py','event_final_train.py','event_final_baselines.py']
    source_paths=[Path(__file__).with_name(n).resolve() for n in source_names]
    source_paths += [(Path(__file__).parents[1]/'market_data'/n).resolve() for n in ['event_shards_final.py','event_shards.py','event_replay.py','event_scan.cpp','trade_events.py','trade_event_scan.cpp','archive_scan.cpp','feature_scan.cpp','candle_tape.py','event_month_cohort.py','event_month_audit.py','event_prepare_fast.py','event_prepare_joined.py','event_features_fast.py','event_features.py','event_windows.py','event_join_cohort.py']]
    baseline=a.baselines/'report.json'
    record={'stage':'final_evaluation','model':'diwali1.4','final_period':['2026-09-15','2026-09-29'],
            'artifacts':{n:{'path':str(f.resolve()),'sha256':file_hash(f)} for n,f in files.items()},
            'baseline_report':{'path':str(baseline.resolve()),'sha256':file_hash(baseline)},
            'preflight_report':{'path':str(a.preflight_report.resolve()),'sha256':file_hash(a.preflight_report)},
            'source_hashes':{str(f):file_hash(f) for f in source_paths},
            'scoring_rule':'Report all eligible origins, primary mean15-bin log loss, per-horizon/direction/probability/daily metrics and paired baselines; no post-score tuning.',
            'consumption':'One shared registry entry across model versions; consumed before final labels load. A failure remains recorded, never silently retried.'}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as stream:
        json.dump(record,stream,indent=2);stream.flush();os.fsync(stream.fileno())
    # An invalid release remains inspectable but can never pass the scoring gate.
    check_release(a.output)
    print(json.dumps({'state':'release_verified','release_sha256':file_hash(a.output),'final_evaluated':False}))


if __name__=='__main__':main()
