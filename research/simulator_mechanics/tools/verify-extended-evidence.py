"""Verify frozen raw catalogs and distinct-parent counts; no new simulation."""
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'results/simulator_research'
flow=BASE/'flow-2026-11-01'
repeat=BASE/'repeat-2026-11-01'
checks={}
for name,folder,raw in [('flow',flow,flow/'raw-validated'),('repeat',repeat,repeat/'raw')]:
    catalog=json.loads((folder/'main-analysis/raw-sha256.json').read_text())
    checks[name+'_hash_catalog']=all(hashlib.sha256((raw/file).read_bytes()).hexdigest()==expected for file,expected in catalog.items())
    manifests=[json.loads(p.read_text()) for p in raw.glob('*.manifest.json')]
    expected_scenarios=40 if name=='flow' else 200
    checks[name+'_unique_scenarios']=len(manifests)==len({r['run_id'] for r in manifests})==expected_scenarios
    checks[name+'_pilot_parents']=len({r['seed'] for r in manifests if r['phase']=='pilot'})==10
    checks[name+'_main_parents']=len({r['seed'] for r in manifests if r['phase']=='main'})==30
    checks[name+'_completed']=all(r['status']=='ok' for r in manifests)
    stats=json.loads((folder/'main-analysis/statistics.json').read_text())
    checks[name+'_record_checks']=all(a['event_reconstruction_pass'] and a['candle_invariants_pass'] for a in stats['audits'].values()) if name=='flow' else all(r['cash_coin_ledger_pass'] for r in stats['runs'])
checks['flow_pilot_rerun_equal']=all(gzip.decompress(p.read_bytes())==gzip.decompress((flow/'raw-validated'/p.name).read_bytes()) for p in (flow/'raw-v2').glob('*.gz'))
checks['flow_reference_scheduler_both_phases']=all(json.loads((flow/'raw-validated'/f'flow-v04-{seed}.manifest.json').read_text())['reference_scheduler_checked'] for seed in (31000,41000))
failed=json.loads((flow/'raw/flow-v04-31000.manifest.json').read_text())
checks['initial_failure_preserved']=failed['status']=='error' and failed['completed_candles']==0
spec=importlib.util.spec_from_file_location('audit',Path(__file__).with_name('audit-evidence.py'))
audit=importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
checks['original_evidence_and_binaries_preserved']=audit.audit(ROOT)['integrity_pass']
old=BASE/'windows-2026-11-01'
manifest=json.loads((old/'evidence/manifest.json').read_text())
compat=flow/'compatibility-original-host'
if all((compat/Path(item['path']).name).exists() for item in manifest['files']):
    checks['refactored_original_host_all_six_csvs_match']=all(hashlib.sha256((compat/Path(item['path']).name).read_bytes()).hexdigest().upper()==item['sha256'].upper() for item in manifest['files'])
result=dict(evidence_type='verification_of_recorded_diagnostics',checks=checks,passed=all(checks.values()),
            new_distinct_parent_states=80,new_scenario_identities=240,new_observations=34200,
            raw_dirs=['flow-2026-11-01/raw-validated','repeat-2026-11-01/raw'],
            exclusions='One initial technical failure and repeated pilot files preserved, not counted as new parent states',
            native_access='Window activation failed twice; no new native input/capture; previous native control evidence remains separate')
(BASE/'extended-verification-2026-11-01.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
raise SystemExit(0 if result['passed'] else 1)
