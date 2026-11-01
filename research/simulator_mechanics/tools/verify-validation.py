"""Evidence/seed/ledger verification for the bounded validation study."""
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
R=ROOT/'results/simulator_research/validation-2026-11-01'
catalog=json.loads((R/'analysis-final/raw-sha256.json').read_text())
checks={'raw_hashes':all(hashlib.sha256((R/p).read_bytes()).hexdigest()==h for p,h in catalog.items())}
v04=json.loads((R/'analysis-final/v04-statistics.json').read_text())
v05=json.loads((R/'analysis-final/v05-statistics.json').read_text())
for profile in ('standard','sparse','maker30'):
    f=v04[profile];r=v05['profiles'][profile]
    checks['v04_'+profile+'_budget']=f['attempted_parents']==f['completed_parents']==60 and not f['failures']
    checks['v04_'+profile+'_exclusions']=f['origins']+sum(f['exclusions'].values())==28200
    checks['v05_'+profile+'_budget']=r['parents']==40 and r['attempts']==360 and r['status_counts']=={'ok':360}
    checks['v05_'+profile+'_pairs']=all(c['attempted_pairs']==c['complete_pairs']==40 for c in r['contrasts'].values())
checks['v05_all_ledgers']=all(r.get('ledger_pass') for r in v05['runs'])
seeds04={json.loads(p.read_text())['seed'] for p in (R/'v04').glob('*.manifest.json')}
seeds05={json.loads(p.read_text())['seed'] for p in (R/'v05').glob('*.manifest.json')}
checks['fresh_independent_seeds']=len(seeds04)==180 and len(seeds05)==120 and not seeds04&seeds05 and min(seeds04)>42029
with gzip.open(R/'analysis-final/confirmatory-origins.jsonl.gz','rt') as f:origins=[json.loads(line) for line in f]
checks['unique_confirmatory_origins']=len({(r['run_id'],r['candle']) for r in origins})==len(origins)==sum(s['origins'] for s in v04.values())
audit=json.loads((R/'baseline-audit.json').read_text())
checks['reviewer_baseline_figures']=audit['origins']==10168 and all(abs(audit['rules'][r]['accuracy']*100-v)<.00006 for r,v in
    [('up',49.5771),('down',48.9477),('momentum',42.8698),('reversal',54.3371),('book',56.7172)])
capture=R/'real-data-raw';m=json.loads((capture/'manifest.json').read_text())
checks['public_raw_preserved']=hashlib.sha256((capture/'raw.jsonl.gz').read_bytes()).hexdigest()==m['raw_sha256']
checks['public_no_orders_or_credentials']=not m['orders_placed'] and not m['credentials_used']
quality=json.loads((R/'real-data-quality-final/quality.json').read_text())
checks['public_sample_sequence']=quality['book_currently_synchronized'] and not quality['counts'].get('sequence_gaps',0)
spec=importlib.util.spec_from_file_location('audit',Path(__file__).with_name('audit-evidence.py'))
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
checks['original_binaries_and_csvs_preserved']=module.audit(ROOT)['integrity_pass']
native={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((R/'native-v05').glob('*.jpg'))}
checks['native_evidence_archived']=len(native)==15 and (R/'native-v05/observations.json').exists()
result=dict(checks=checks,passed=all(checks.values()),raw_files_checked=len(catalog),native_image_hashes=native,
            new_v04_parents=180,new_v05_parents=120,new_scenario_identities=1260,new_observations=163080,
            main_analysis='analysis-final',old_analysis_retained='analysis',model_training_started=False,
            interpretation='Separate original-DLL host confirmation, native behavioral evidence and bounded real public-data engineering sample')
(R/'verification.json').write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k!='native_image_hashes'},indent=2))
raise SystemExit(0 if result['passed'] else 1)
