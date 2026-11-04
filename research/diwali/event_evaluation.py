"""Chronological development partitions and deliberately released final scoring.

This gate is an accidental-access guard, not an OS security boundary. Raw final
data preparation remains separately denied by event_shards.allowed().
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from ..market_data.validate_archive import file_hash

SECOND = 10**9
MINUTE = 60*SECOND
FOLDS = {
    'A': {'fit': ('08-01','08-10'), 'select': ('08-11','08-13'), 'calibrate': ('08-14','08-15'), 'score': ('08-16','08-18')},
    'B': {'fit': ('08-01','08-18'), 'select': ('08-19','08-21'), 'calibrate': ('08-22','08-23'), 'score': ('08-24','08-26')},
    'C': {'fit': ('08-01','08-23'), 'select': ('08-24','08-26'), 'calibrate': ('08-27','08-28'), 'score': ('08-29','08-31')},
    'final': {'fit': ('08-01','08-31'), 'select': ('09-01','09-07'), 'calibrate': ('09-08','09-14'), 'score': ('09-15','09-29')},
}


def interval(fold, partition):
    first, last = FOLDS[fold][partition]
    begin = datetime.fromisoformat('2026-'+first).replace(tzinfo=timezone.utc)
    end = datetime.fromisoformat('2026-'+last).replace(tzinfo=timezone.utc)+timedelta(days=1)
    return int(begin.timestamp())*SECOND, int(end.timestamp())*SECOND


def eligible_origins(cutoffs, target_starts, fold, partition, *, final_release=None):
    """Select by frozen dates and purge all targets extending beyond the split."""
    if fold == 'final' and partition == 'score':
        if final_release is None:
            raise ValueError('Reserved final evaluation has not been deliberately released')
        verify_release(final_release)
    cutoffs = np.asarray(cutoffs, np.int64)
    targets = np.asarray(target_starts, np.int64)
    if cutoffs.ndim != 1 or targets.shape != cutoffs.shape:
        raise ValueError('Invalid origin times')
    if (targets != (cutoffs//MINUTE+1)*MINUTE).any():
        raise ValueError('Targets must start at the next full calendar minute')
    begin, end = interval(fold, partition)
    inside = (cutoffs >= begin) & (cutoffs < end)
    keep = inside & (targets+15*MINUTE <= end)
    return keep, {'inside_partition': int(inside.sum()), 'retained': int(keep.sum()),
                  'purged_target_overlap': int((inside & ~keep).sum()),
                  'outside_partition': int((~inside).sum())}


def horizon_seconds(cutoff, target_start):
    if target_start != (cutoff//MINUTE+1)*MINUTE:
        raise ValueError('Different target timing contract')
    return (target_start+np.arange(1,16,dtype=np.int64)*MINUTE-cutoff)/SECOND


def verify_release(path):
    """Bind final access to already selected/calibrated artifacts and source hashes.

    A future runner must create this record only after all earlier stages finish,
    then log its first final evaluation. It cannot tune models through this gate.
    """
    path = Path(path)
    record = json.loads(path.read_text())
    if record.get('stage') != 'final_evaluation' or record.get('final_period') != ['2026-09-15','2026-09-29']:
        raise ValueError('Invalid final release scope')
    required = {'run_protocol', 'selected_model', 'fit_transforms', 'calibration', 'development_selection'}
    artifacts = record.get('artifacts', {})
    if set(artifacts) != required:
        raise ValueError('Final release requires frozen training/selection/calibration artifacts')
    for value in artifacts.values():
        p = Path(value['path'])
        if not p.is_absolute():
            p = path.parent/p
        if file_hash(p) != value['sha256']:
            raise ValueError('Final release artifact has changed')
    sources = record.get('source_hashes', {})
    if not sources:
        raise ValueError('Final release requires source hashes')
    for name, sha in sources.items():
        p = Path(name)
        if not p.is_absolute():
            p = path.parent/p
        if file_hash(p) != sha:
            raise ValueError('Final evaluation source changed')
    return record
