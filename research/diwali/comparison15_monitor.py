"""Operational monitoring for the fixed live comparison, without performance scores."""
import argparse
import json
from pathlib import Path
import time

from .comparison15 import ROOT
from ..market_data.validate_archive import file_hash, save


def snapshot(root):
    status = json.loads((root/'status.json').read_text())
    now = time.time_ns()
    result = {'state': status['state'], 'checked_utc_ns': now,
              'last_health_utc_ns': status['updated_utc_ns'],
              'health_age_seconds': (now-status['updated_utc_ns'])/1e9,
              'source_counts': status['counts'],
              'issued_forecasts': len(list((root/'committed').glob('*.json'))),
              'skipped_slots': len(list((root/'skipped').glob('*.json'))),
              'verified_outcomes': 0, 'rejected_outcomes': 0, 'alerts': []}
    if result['health_age_seconds'] > 180:
        result['alerts'].append('No operational heartbeat in over 180 seconds')
    if status['counts'].get('clock_steps'):
        result['alerts'].append('Native recorder clock step detected')
    release = root/'release.json'
    if release.exists():
        protocol = json.loads(release.read_text())
        result.update(release_sha256=file_hash(release), start_utc=protocol['start_utc'],
                      stop_exclusive_utc=protocol['stop_exclusive_utc'])
        for name,sha in protocol['artifacts'].items():
            if file_hash(ROOT/name) != sha:
                result['alerts'].append('Frozen artifact changed: '+name)
        for proof_path in (root/'committed').glob('*.json'):
            proof = json.loads(proof_path.read_text())
            path = root/'forecasts'/proof_path.name
            forecast = json.loads(path.read_text())
            if (proof['forecast_sha256'] != file_hash(path)
                    or forecast['release_sha256'] != result['release_sha256']
                    or forecast['last_input_receipt_utc_ns'] >= forecast['cutoff_ns']
                    or proof['committed_utc_ns'] >= forecast['target_start_ns']):
                result['alerts'].append('Forecast timing or identity failed: '+proof_path.name)
    for path in (root/'outcomes').glob('*.json'):
        outcome = json.loads(path.read_text())
        if outcome['state'] == 'matured':
            result['verified_outcomes'] += 1
        else:
            result['rejected_outcomes'] += 1
    result['pending_outcomes'] = result['issued_forecasts']-result['verified_outcomes']-result['rejected_outcomes']
    manifest = root/'manifest.json'
    if manifest.exists():
        result['capture_finished'] = True
        ended = json.loads(manifest.read_text())
        if ended.get('failure'):
            result['alerts'].append(ended['failure'])
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    path = args.source/'operational-monitor.json'
    while True:
        try:
            result = snapshot(args.source)
        except Exception as exc:
            result = {'state': 'monitor_failed', 'alerts': [str(exc)]}
            save(path, result)
            raise
        save(path, result)
        if result.get('capture_finished'):
            break
        time.sleep(60)


if __name__ == '__main__':
    main()
