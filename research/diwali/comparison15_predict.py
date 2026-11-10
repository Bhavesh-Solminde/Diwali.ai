"""Run the retained control and frozen benchmarks on the same input."""
import json

import joblib
import numpy as np
import torch

from .comparison15 import ROOT, CandleAttentionModel, cache_batch, source_hashes
from .event_baselines import summary
from .event_data import normalize
from .event_data_exact import exact_one_second
from .event_lifetime import sigmoid
from .event_model import EventModel
from .event_train import probabilities
from ..market_data.validate_archive import file_hash


class Predictor:
    def __init__(self, root=ROOT, *, attention=None, include_binary=True):
        self.selected = root/'results/diwali1.5/selected-artifact.json'
        selected = json.loads(self.selected.read_text())
        model_path = root/selected['model_directory']
        self.binary_path = root/'data/models/diwali1.5-final-binary-v1'
        baseline = root/'data/models/diwali1.4-final-baselines-v1'
        baseline_report = json.loads((baseline/'report.json').read_text())
        if selected['selected_configuration'] != 'A_original':
            raise ValueError('Expected the retained control and matched final comparators')
        self.artifacts = {}
        manifests = [
            (model_path, selected['artifacts']),
            (baseline, {name: baseline_report['artifact_hashes'][name]
                        for name in ('fit-transforms.json', 'histograms.npz', 'calibration.json')})
        ]
        reports = [self.selected, baseline/'report.json']
        self.heads = []
        if include_binary:
            path = self.binary_path/'report.json'
            binary_report = json.loads(path.read_text())
            if (binary_report['state'] != 'fitted_calibrated_and_reload_verified'
                    or binary_report['volatility_baseline_report_sha256'] != file_hash(baseline/'report.json')):
                raise ValueError('Expected matched binary comparator')
            manifests.append((self.binary_path, binary_report['artifact_hashes']))
            reports.append(path)
        self.attention = None
        if attention is not None:
            path = attention/'report.json'
            challenger = json.loads(path.read_text())
            if (challenger['state'] != 'fitted_calibrated_reload_verified'
                    or challenger['configuration'] != 'C_attention_lower_lr'
                    or challenger['data_hashes'] != baseline_report['data_hashes']
                    or challenger['source_hashes'] != source_hashes()
                    or challenger['artifact_hashes']['fit-transforms.json'] != selected['artifacts']['fit-transforms.json']):
                raise ValueError('Expected the declared attention challenger and matched transforms')
            manifests.append((attention, challenger['artifact_hashes']))
            reports.append(path)
        for directory, hashes in manifests:
            for name, expected in hashes.items():
                if file_hash(directory/name) != expected:
                    raise ValueError(f'Changed forecast artifact: {name}')
                self.artifacts[str((directory/name).relative_to(root))] = expected
        for path in reports:
            self.artifacts[str(path.relative_to(root))] = file_hash(path)
        torch.set_num_threads(4)
        self.model = EventModel().eval()
        self.model.load_state_dict(torch.load(model_path/'weights.pt', map_location='cpu', weights_only=True))
        self.transforms = json.loads((model_path/'fit-transforms.json').read_text())['moments']
        self.temps = json.loads((model_path/'calibration.json').read_text())['temperatures']
        if include_binary:
            self.binary_transform = json.loads((self.binary_path/'fit-transforms.json').read_text())
            self.binary_temps = np.array(json.loads((self.binary_path/'calibration.json').read_text())['temperatures'])
            self.heads = [joblib.load(self.binary_path/f'horizon-{h:02d}.joblib') for h in range(1, 16)]
        if attention is not None:
            self.attention = CandleAttentionModel().eval()
            self.attention.load_state_dict(torch.load(attention/'weights.pt', map_location='cpu', weights_only=True))
            self.attention_temps = json.loads((attention/'calibration.json').read_text())['temperatures']
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
            attention_logits = self.attention(*args).numpy() if self.attention is not None else None
        features, vol = summary(raw)
        histogram = self.hist[np.searchsorted(self.thresholds, vol)]
        result = {
            'control_raw': probabilities(logits)[0],
            'control': probabilities(logits, self.temps)[0],
            'volatility_raw': histogram,
            'volatility': probabilities(np.log(histogram[None]), self.hist_temps)[0],
            'half': np.full(15, .5)}
        if self.heads:
            x = normalize(features[None], self.binary_transform)
            binary_logits = np.array([head.decision_function(x)[0] for head in self.heads])
            result.update(binary_raw=sigmoid(binary_logits), binary=sigmoid(binary_logits/self.binary_temps))
        if attention_logits is not None:
            result.update(attention_raw=probabilities(attention_logits)[0],
                          attention=probabilities(attention_logits, self.attention_temps)[0])
        return result
