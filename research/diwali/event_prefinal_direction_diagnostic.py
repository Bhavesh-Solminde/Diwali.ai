"""Frozen final-build weights on September 1–14 only; never reserved-test rows."""
import argparse
import json
from pathlib import Path

import numpy as np
import torch

from . import event_direction_diagnostic as diagnostic
from .event_data_exact import ExactEventData
from .event_evaluation import eligible_origins
from .event_model import EventModel
from .event_train import infer, probabilities
from ..market_data.validate_archive import file_hash, save


def main():
    p = argparse.ArgumentParser(); p.add_argument('--run', type=Path, required=True)
    p.add_argument('--cohort', type=Path, required=True); p.add_argument('--features', type=Path, required=True)
    p.add_argument('--content-audit', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        raise ValueError('Do not overwrite a completed diagnostic')
    data = ExactEventData(a.cohort, a.features, a.content_audit)
    if ((data.cutoffs < np.datetime64('2026-09-01', 'ns').astype(np.int64)) |
        (data.cutoffs >= np.datetime64('2026-09-15', 'ns').astype(np.int64))).any():
        raise ValueError('Only prefinal September 1–14 inputs allowed')
    protocol = json.loads((a.run/'run-protocol.json').read_text())
    for name, sha in protocol['source_hashes'].items():
        if file_hash(Path(__file__).with_name(name)) != sha:
            raise ValueError('Frozen training source changed')
    report = json.loads((a.run/'report.json').read_text()); cal = json.loads((a.run/'calibration.json').read_text())
    sha = file_hash(a.run/'weights.pt')
    if sha != report['selection']['weights_sha256'] or sha != cal['weights_sha256']:
        raise ValueError('Frozen checkpoint/calibration identity differs')
    transform = json.loads((a.run/'fit-transforms.json').read_text())
    if transform['source_hashes']['september_selection_calibration'] != data.hashes:
        raise ValueError('Different prefinal inputs')
    model = EventModel('attention' if protocol['candidate'] == 'event_attention' else 'temporal_conv',
                       width=protocol['neural_width'], block=protocol['event_block_groups'])
    model.load_state_dict(torch.load(a.run/'weights.pt', weights_only=True, map_location='cpu'))
    torch.set_num_threads(4); result = {}
    for name in ['select', 'calibrate']:
        keep, counts = eligible_origins(data.cutoffs, data.starts, 'final', name)
        ids = np.flatnonzero(keep)
        if len(ids) != report['cohorts'][name]['retained']:
            raise ValueError('Partition count differs from final build')
        logits = infer(model, data, ids, transform, 'cpu', protocol['batch_size'])
        raw = probabilities(logits); calibrated = probabilities(logits, cal['temperatures'])
        y = data.y[ids] >= 13
        days = np.asarray([str(np.datetime64(int(v), 'ns'))[:10] for v in data.cutoffs[ids]])
        result[name] = {'origin_counts': counts, 'raw': diagnostic.directional_view(y, raw[:, :, 13:].sum(-1)),
                        'calibrated': diagnostic.directional_view(y, calibrated[:, :, 13:].sum(-1)),
                        'daily': {day: {mode: [{'horizon': h+1, **diagnostic.binary_metrics(y[days == day, h], value[days == day, h, 13:].sum(-1))} for h in range(15)]
                                        for mode, value in [('raw', raw), ('calibrated', calibrated)]} for day in sorted(set(days))}}
        print(name, len(ids), 'final raw/calibrated AUC', result[name]['raw'][-1]['roc_auc'], result[name]['calibrated'][-1]['roc_auc'], flush=True)
    save(a.output, {'state': 'complete', 'model': 'diwali1.4 frozen final build', 'new_training_runs': 0,
                    'reserved_september_data_read': False, 'weights_sha256': sha, 'data_hashes': data.hashes,
                    'mapping_audit': diagnostic.mapping_audit(data), 'temperatures': cal['temperatures'],
                    'partitions': result,
                    'source_sha256': file_hash(Path(__file__)), 'metric_source_sha256': file_hash(Path(diagnostic.__file__)),
                    'scope': 'Same actual final checkpoint, previously used selection/calibration dates only. Selection chose weights; calibration chose temperatures. Neither partition is independent performance confirmation.'})


if __name__ == '__main__':
    main()
