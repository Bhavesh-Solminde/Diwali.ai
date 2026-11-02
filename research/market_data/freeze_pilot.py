"""Freeze October pilot dates from corrected audit coverage, never prediction scores."""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path

from .validate_archive import file_hash, reconcile, save


def timestamp(day):
    return int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp()) * 1000


SPLITS = {
    'fit': ('2026-10-01', '2026-10-19'),
    'development': ('2026-10-19', '2026-10-22'),
    'calibration': ('2026-10-22', '2026-10-24'),
    'locked_test': ('2026-10-24', '2026-11-01'),
}


def freeze(audit, output):
    progress = json.loads((audit / 'progress.json').read_text())
    for kind in ('book', 'trades'):
        shard = json.loads((audit / 'shards' / f'2026-10-{kind}.json').read_text())
        if (shard['files_expected'] != 744 or shard['files_done'] != 744
                or shard['fingerprint'] != progress['fingerprint'] or shard['errors']):
            raise ValueError('Complete matching October shards required')
    output.mkdir(parents=True, exist_ok=True)
    link = output / 'reference'
    if not link.exists():
        link.symlink_to((audit / 'reference').resolve(), target_is_directory=True)
    # Reconcile only October hours, while retaining preceding independent candle context.
    # A separate view prevents partially completed other months entering the pilot report.
    view = output / 'hours'
    view.mkdir(exist_ok=True)
    for day in range(1, 32):
        name = f'2026-10-{day:02d}'
        for source in (audit / 'hours' / name).rglob('*.quality.json'):
            target = view / source.relative_to(audit / 'hours')
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                os.link(source, target)
    refs = json.loads((audit / 'reference' / 'status.json').read_text())
    reconcile(output, {'scope': 'October pilot; prior candle context only'}, refs)
    origins = json.loads((output / 'usable-origin-times.json').read_text())
    origins = [t for t in origins if timestamp('2026-10-01') <= t < timestamp('2026-11-01')]
    partitions = {}
    consumed = set()
    daily = Counter()
    for name, (start, stop) in SPLITS.items():
        lo, hi = timestamp(start), timestamp(stop)
        eligible = [t for t in origins if lo <= t and t + 60000 <= hi]
        if consumed.intersection(eligible):
            raise ValueError('Overlapping pilot targets')
        consumed.update(eligible)
        save(output / f'{name}-origins.json', eligible)
        expected = (hi - lo) // 60000
        partitions[name] = {'start_utc': start, 'end_exclusive_utc': stop,
                            'expected_origins': expected, 'candidate_origins': len(eligible),
                            'coverage_percent': round(100 * len(eligible) / expected, 3),
                            'origin_file_sha256': file_hash(output / f'{name}-origins.json')}
        for t in eligible:
            daily[datetime.fromtimestamp(t / 1000, timezone.utc).strftime('%Y-%m-%d')] += 1
    audit_report = json.loads((output / 'report.json').read_text())
    manifest = {
        'stage': 'one-month exploratory pilot', 'date_selection_basis': 'audited coverage, not model performance',
        'quality_audit_fingerprint': progress['fingerprint'], 'month': '2026-10',
        'context_completed_minutes': 1440, 'book_trade_history_seconds': 60,
        'target': 'next completed one-minute BTCUSDT perpetual candle',
        'warmup_start_utc': '2026-09-30', 'partitions': partitions,
        'daily_candidates': dict(sorted(daily.items())),
        'independent_reference_supplements': audit_report['independent_reference_supplements'],
        'training_ready': False,
        'remaining_gates': ['Causal feature construction and maximum available-time cutoffs',
                            'Target/input overlap and leakage checks on actual feature arrays',
                            'Preprocessing fit on fit partition only',
                            'Baseline protocol and hardware/training budget freeze',
                            'No reuse of inspected pilot test as later untouched main holdout'],
        'exclusions': 'Omit invalid origins without joining separated periods or manufacturing book values',
        'data_quality_statement': 'No claim of perfect data or verified hidden liquidity; strict accepted subset only',
    }
    save(output / 'pilot-manifest.json', manifest)
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('audit', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    freeze(args.audit, args.output)
