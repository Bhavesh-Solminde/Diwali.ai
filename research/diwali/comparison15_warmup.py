"""Verify three full native inputs after a 24-hour collection warmup."""
import argparse
import json
from pathlib import Path
import time

import numpy as np

from .comparison15_live_inputs import MINUTE, SECOND, NativeInputs
from .comparison15_predict import Predictor
from ..market_data.validate_archive import file_hash, save


def verify(source, cutoffs):
    predictor = Predictor()
    inputs = NativeInputs()
    windows = []
    for path in sorted(source.glob('events-*.jsonl')):
        with path.open() as file:
            for line in file:
                if not line.endswith('\n'):
                    break
                row = json.loads(line)
                at = row['receipt_utc_ns']
                while len(windows) < len(cutoffs) and at >= cutoffs[len(windows)]:
                    cutoff = cutoffs[len(windows)]
                    try:
                        raw, elapsed, _ = inputs.freeze(cutoff)
                    except ValueError as exc:
                        windows.append({'cutoff_ns': cutoff, 'passed': False, 'reason': str(exc)})
                        continue
                    prediction = predictor.predict(raw, elapsed)
                    for values in prediction.values():
                        if not np.isfinite(values).all() or (values < 0).any() or (values > 1).any():
                            raise ValueError('Invalid warmup prediction probabilities')
                        if values.ndim == 2:
                            np.testing.assert_allclose(values.sum(-1), 1, rtol=0, atol=1e-12)
                    windows.append({'cutoff_ns': cutoff, 'passed': True,
                                    'valid_candles': int(raw[3].sum()), 'event_rows': len(elapsed)})
                if len(windows) == len(cutoffs):
                    return windows, predictor.artifacts
                if (row.get('clock_step_ns') or at >= cutoffs[0]-120*SECOND
                        or row['kind'] not in ('depth', 'book', 'rest')):
                    inputs.ingest(row)
    raise ValueError('Capture ended before the prespecified warmup checks')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Warmup verification already attempted')
    status = args.source/'status.json'
    start = json.loads(status.read_text())['start_utc_ns']
    first = (start//MINUTE+1442)*MINUTE+15*SECOND
    cutoffs = [first + i*MINUTE for i in range(3)]
    try:
        while time.time_ns() < cutoffs[-1]+30*SECOND:
            if (args.source/'manifest.json').exists():
                raise ValueError('Recorder stopped before warmup finished')
            current = json.loads(status.read_text())
            if time.time_ns()-current['updated_utc_ns'] > 180*SECOND:
                raise ValueError('Recorder health updates stopped')
            time.sleep(30)
        windows, artifacts = verify(args.source, cutoffs)
        save(args.output, {'state': 'warmup_verified' if all(w['passed'] for w in windows) else 'warmup_failed',
                           'windows': windows, 'artifacts': artifacts,
                           'capture_protocol_sha256': file_hash(args.source/'capture-protocol.json'),
                           'forecasts_issued': 0})
    except Exception as exc:
        save(args.output, {'state': 'warmup_failed', 'reason': str(exc), 'forecasts_issued': 0})
        raise


if __name__ == '__main__':
    main()
