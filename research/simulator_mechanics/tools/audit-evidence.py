"""Read-only integrity audit of transferred simulator evidence (stdlib only)."""
import csv
import hashlib
import json
from pathlib import Path


def audit(root):
    evidence = root / 'results/simulator_research/windows-2026-11-01'
    manifest = json.loads((evidence / 'evidence/manifest.json').read_text())
    checks = []
    for item in manifest['files']:
        file = evidence / item['path']
        checks.append({'path': item['path'], 'matches':
                       hashlib.sha256(file.read_bytes()).hexdigest().upper() == item['sha256'].upper()})
    builds = []
    for item in manifest['builds']:
        file = root / 'Krafer Agent Trader Sim' / item['archive'].removesuffix('.zip') / item['entry']
        builds.append({'path': str(file.relative_to(root)), 'matches':
                       file.exists() and hashlib.sha256(file.read_bytes()).hexdigest().upper() == item['sha256'].upper()})
    versions = {}
    for version in ('04', '05'):
        def rows(kind):
            with (evidence / f'evidence/original-host/{kind}-v{version}.csv').open(newline='') as f:
                return list(csv.DictReader(f))
        runs, candles = rows('runs'), rows('candles')
        ids = {r['run_id'] for r in runs}
        counts = {i: 0 for i in ids}
        for row in candles:
            counts[row['run_id']] += 1
        versions[version] = {
            'scenarios': len(runs), 'unique_scenarios': len(ids),
            'parents': len({r['parent_id'] for r in runs}),
            'main_parents': len({r['parent_id'] for r in runs if r['phase'] == 'main'}),
            'candle_rows': len(candles),
            'all_status_ok': all(r['status'] == 'ok' for r in runs),
            'all_fingerprints_matched': all(r['matched_baseline'] == 'True' for r in runs),
            'all_scenarios_have_35_observations': all(n == 35 for n in counts.values()),
        }
    return {'evidence_type': 'audit_of_existing_files_no_new_simulation',
            'csv_hash_checks': checks, 'extracted_build_checks': builds, 'versions': versions,
            'integrity_pass': all(x['matches'] for x in checks + builds) and all(
                v['scenarios'] == v['unique_scenarios'] and v['all_status_ok'] and
                v['all_fingerprints_matched'] and v['all_scenarios_have_35_observations']
                for v in versions.values())}


if __name__ == '__main__':
    result = audit(Path(__file__).resolve().parents[3])
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['integrity_pass'] else 1)
