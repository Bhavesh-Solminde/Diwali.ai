"""Fit the fixed direction comparator for the retained Diwali 1.5 candidate."""
import argparse
import json
from pathlib import Path
import warnings

import joblib
import numpy as np
import sklearn
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from threadpoolctl import threadpool_limits

from .comparison15 import ROOT
from .comparison15_train import score_direction
from .event_baselines import summary
from .event_data import Moments, normalize
from .event_data_exact import ExactEventData
from .event_final_data import FinalBuildData
from .event_lifetime import sigmoid
from ..market_data.validate_archive import file_hash, save


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    output = parser.parse_args().output
    baseline = ROOT/'data/models/diwali1.4-final-baselines-v1'
    baseline_report = json.loads((baseline/'report.json').read_text())
    data_root = ROOT/'data/btc-perp'
    audit_root = ROOT/'results/event-joined-cohort'
    data = FinalBuildData(
        ExactEventData(data_root/'event-month-cohort-august-v1',
                       data_root/'event-inputs-august-fast-v1', audit_root/'august-month-audit.json'),
        ExactEventData(data_root/'event-month-cohort-september-selection-v1',
                       data_root/'event-inputs-september-selection-fast-v1',
                       audit_root/'september-selection-audit.json'))
    if data.hashes != baseline_report['data_hashes']:
        raise ValueError('Direction and volatility comparators must use the same source cohorts')
    fit, fit_counts = data.partition('final', 'fit')
    cal, cal_counts = data.partition('final', 'calibrate')
    if len(fit) != 5391 or len(cal) != 1476:
        raise ValueError('Frozen fit or calibration cohort changed')
    output.mkdir(parents=True, exist_ok=False)
    provenance = {
        'fit_origins': len(fit), 'calibration_origins': len(cal),
        'data_hashes': data.hashes, 'fit_counts': fit_counts, 'calibration_counts': cal_counts,
        'source_sha256': file_hash(Path(__file__)),
        'bounded_binary_source_sha256': file_hash(Path(__file__).with_name('comparison15_train.py')),
        'volatility_baseline_report_sha256': file_hash(baseline/'report.json'),
        'sklearn_version': sklearn.__version__, 'reserved_september_data_read': False}
    save(output/'protocol.json', provenance)
    fit_features = np.stack([summary(data.raw(j))[0] for j in fit])
    cal_features = np.stack([summary(data.raw(j))[0] for j in cal])
    moments = Moments(447)
    moments.add(fit_features)
    transform = moments.record()
    transform_path = baseline/'fit-transforms.json'
    if file_hash(transform_path) != baseline_report['artifact_hashes'][transform_path.name]:
        raise ValueError('Volatility baseline transform identity changed')
    if transform != json.loads(transform_path.read_text())['summary']:
        raise ValueError('Fit-only summary differs from the existing baseline')
    save(output/'fit-transforms.json', transform)
    x_fit = normalize(fit_features, transform)
    x_cal = normalize(cal_features, transform)
    y_fit, y_cal = data.y[fit] >= 13, data.y[cal] >= 13
    grid = np.geomspace(.5, 4., 49)
    logits = []
    temperatures = []
    iterations = []
    with threadpool_limits(limits=4), warnings.catch_warnings():
        warnings.simplefilter('error', ConvergenceWarning)
        for h in range(15):
            head = LogisticRegression(C=1., solver='lbfgs', max_iter=1000, random_state=17)
            head.fit(x_fit, y_fit[:, h])
            path = output/f'horizon-{h+1:02d}.joblib'
            joblib.dump(head, path)
            z = head.decision_function(x_cal)
            np.testing.assert_array_equal(joblib.load(path).decision_function(x_cal), z)
            losses = [-np.log(np.maximum(np.where(y_cal[:, h], p, 1-p), 1e-15)).mean()
                      for p in (sigmoid(z/t) for t in grid)]
            temperatures.append(float(grid[np.argmin(losses)]))
            iterations.append(int(head.n_iter_[0]))
            logits.append(z)
            print('Verified direction head', h+1, flush=True)
    z = np.stack(logits, axis=1)
    save(output/'calibration.json', {'temperatures': temperatures, 'origins': len(cal)})
    save(output/'report.json', {
        'state': 'fitted_calibrated_and_reload_verified', **provenance,
        'iterations': iterations, 'raw_calibration_diagnostic': score_direction(y_cal, sigmoid(z)),
        'adjusted_calibration_diagnostic': score_direction(y_cal, sigmoid(z/np.asarray(temperatures))),
        'artifact_hashes': {p.name: file_hash(p) for p in sorted(output.iterdir())},
        'scope': 'Development calibration only. Fresh forecasts have not been issued.'})


if __name__ == '__main__':
    main()
