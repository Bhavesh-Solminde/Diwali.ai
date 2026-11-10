"""Publish aggregate evidence while suppressing small reliability groups too."""
import argparse
import json
from pathlib import Path

from ..market_data.validate_archive import file_hash, save


def aggregate_only(value):
    if isinstance(value, dict):
        for key in ('origins', 'count'):
            if isinstance(value.get(key), int) and value[key] < 10:
                return {key: value[key], 'metrics_suppressed': 'Fewer than ten origins; metrics stay private.'}
        return {k: aggregate_only(v) for k, v in value.items()}
    if isinstance(value, list):
        return [aggregate_only(v) for v in value]
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--study', type=Path, required=True)
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = json.loads((args.study/'report.json').read_text())
    audit = json.loads(args.audit.read_text())
    if (report['state'] != 'development_complete' or audit['state'] != 'complete'
            or audit['runs_verified'] != 39
            or audit['study_report_sha256'] != file_hash(args.study/'report.json')):
        raise ValueError('Completed, matching audited study required')
    args.output.mkdir(parents=True, exist_ok=True)
    save(args.output/'development-report.json', aggregate_only(report))
    save(args.output/'development-progress.json', {
        'state': 'development_complete', 'completed_runs': 39, 'planned_runs': 39,
        'completed_report': 'development-report.json', 'artifact_audit': args.audit.name,
        'report_sha256': file_hash(args.output/'development-report.json'),
        'scope': 'Aggregate development evidence; private inputs, forecasts and fitted artifacts are excluded.'})


if __name__ == '__main__':
    main()
