"""Run the retained control and frozen benchmarks on the same input."""
import json

import joblib
import numpy as np
import torch

from .comparison15 import ROOT, cache_batch
from .event_baselines import summary
from .event_data import normalize
from .event_data_exact import exact_one_second
from .event_lifetime import sigmoid
from .event_model import EventModel
from .event_train import probabilities
from ..market_data.validate_archive import file_hash


class Predictor:
    def __init__(self, root=ROOT):
        self.selected = root/'results/diwali1.5/selected-artifact.json'
        selected = json.loads(self.selected.read_text())
        model_path = root/selected['model_directory']
        self.binary_path = root/'data/models/diwali1.5-final-binary-v1'
        baseline = root/'data/models/diwali1.4-final-baselines-v1'
        self.binary_report = json.loads((self.binary_path/'report.json').read_text())
        baseline_report = json.loads((baseline/'report.json').read_text())
        if (selected['selected_configuration'] != 'A_original'
                or self.binary_report['state'] != 'fitted_calibrated_and_reload_verified'
                or self.binary_report['volatility_baseline_report_sha256'] != file_hash(baseline/'report.json')):
            raise ValueError('Expected the retained control and matched final comparators')
        self.artifacts = {}
        for directory, hashes in [
            (model_path, selected['artifacts']),
            (self.binary_path, self.binary_report['artifact_hashes']),
            (baseline, {name: baseline_report['artifact_hashes'][name]
                        for name in ('fit-transforms.json', 'histograms.npz', 'calibration.json')})
        ]:
            for name, expected in hashes.items():
                if file_hash(directory/name) != expected:
                    raise ValueError(f'Changed forecast artifact: {name}')
                self.artifacts[str((directory/name).relative_to(root))] = expected
        for path in (self.selected, baseline/'report.json', self.binary_path/'report.json'):
            self.artifacts[str(path.relative_to(root))] = file_hash(path)
        torch.set_num_threads(4)
        self.model = EventModel().eval()
        self.model.load_state_dict(torch.load(model_path/'weights.pt', map_location='cpu', weights_only=True))
        self.transforms = json.loads((model_path/'fit-transforms.json').read_text())['moments']
        self.temps = json.loads((model_path/'calibration.json').read_text())['temperatures']
        self.binary_transform = json.loads((self.binary_path/'fit-transforms.json').read_text())
        self.binary_temps = np.array(json.loads((self.binary_path/'calibration.json').read_text())['temperatures'])
        self.heads = [joblib.load(self.binary_path/f'horizon-{h:02d}.joblib') for h in range(1, 16)]
        self.thresholds = json.loads((baseline/'fit-transforms.json').read_text())['volatility_thresholds']
        with np.load(baseline/'histograms.npz') as archive:
            self.hist = archive['volatility_histograms']
        self.hist_temps = baseline_report['models']['fit_volatility_histogram']['temperatures']

    def predict(self, raw, elapsed):
        events, _, candles, mask, seed, reference = raw
        arrays = {'seconds': exact_one_second(events, elapsed)[None],
                  'candles': candles[None], 'candle_masks': mask[None],
                  'seeds': seed[None], 'references': reference[None],
                  'labels': np.zeros((1, 15), dtype=np.int64)}
        args, _ = cache_batch(arrays, [0], self.transforms, 'cpu')
        with torch.inference_mode():
            logits = self.model(*args).numpy()
        features, vol = summary(raw)
        x = normalize(features[None], self.binary_transform)
        binary_logits = np.array([head.decision_function(x)[0] for head in self.heads])
        histogram = self.hist[np.searchsorted(self.thresholds, vol)]
        return {
            'control_raw': probabilities(logits)[0],
            'control': probabilities(logits, self.temps)[0],
            'volatility_raw': histogram,
            'volatility': probabilities(np.log(histogram[None]), self.hist_temps)[0],
            'binary_raw': sigmoid(binary_logits),
            'binary': sigmoid(binary_logits/self.binary_temps),
            'half': np.full(15, .5)}
