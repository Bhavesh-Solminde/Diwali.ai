"""Local Diwali 1.4 selection replay: predict first, reveal actual closes separately."""
import argparse
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
import uuid

import numpy as np
import torch

from .event_data import EDGES, normalize
from .event_data_exact import ExactEventData, exact_one_second
from .event_final_gate import check_release, resolve
from .event_model import EventModel
from .event_train import probabilities
from ..market_data.validate_archive import file_hash

ROOT = Path(__file__).resolve().parents[2]


def inference_input(data, index, transforms):
    """Prepare inputs without accessing target labels or actual future prices."""
    event, groups, candles, mask, seed, ref = data.raw(index)
    if transforms['representation'] == 'one_second':
        event = exact_one_second(event, data.exact_elapsed(index))
        groups = np.arange(60, dtype=np.int64)
    stats = transforms['moments']
    event = normalize(event, stats['event'])
    candles = normalize(candles, stats['candle']); candles[~mask] = 0
    arrays = [event[None], np.ones((1, len(event)), bool), candles[None],
              normalize(seed, stats['seed'])[None], groups[None], mask[None],
              normalize(ref, stats['reference'])[None]]
    return tuple(torch.from_numpy(x) for x in arrays)


def forecast_payload(p, reference, target_ms):
    p = np.asarray(p, np.float64)
    if p.shape != (15, 26) or not np.isfinite(p).all() or (p < 0).any():
        raise ValueError('Invalid model probabilities')
    np.testing.assert_allclose(p.sum(-1), 1, atol=1e-8, rtol=0)
    edges = [None, *EDGES.tolist(), None]
    return [{'horizon': h+1, 'close_ms': target_ms+(h+1)*60000,
             'up': float(row[13:].sum()), 'down_or_unchanged': float(row[:13].sum()),
             'ranges': [{'lower_price': None if edges[k] is None else reference*(1+edges[k]/10000),
                         'upper_price': None if edges[k+1] is None else reference*(1+edges[k+1]/10000),
                         'lower_inclusive': k == 16, 'upper_inclusive': k != 15,
                         'probability': float(value)} for k, value in enumerate(row)]}
            for h, row in enumerate(p)]


class Engine:
    def __init__(self, run, release, cohort, features, audit):
        self.run = run; self.lock = threading.RLock(); self.requests = {}
        record = check_release(release)
        if resolve(release, record['artifacts']['selected_model']).resolve() != (run/'weights.pt').resolve():
            raise ValueError('UI run differs from released weights')
        self.data = ExactEventData(cohort, features, audit)
        demo = json.loads((run/'historical-demo.json').read_text())
        if demo['state'] != 'selection_demo_prepared' or demo['data_hashes'] != self.data.hashes:
            raise ValueError('Changed or mismatched historical demo')
        self.cases = demo['cases']
        targets = {r['input_row']: r['closes'] for r in json.loads((cohort/'candles/targets.json').read_text())}
        for case in self.cases:
            j = case['data_index']; i = int(self.data.ids[j]); meta = self.data.metadata[i]
            if case['input_row'] != i or case['snapshot_ms'] != int(self.data.cutoffs[j])//10**6 or case['reference'] != meta['reference']:
                raise ValueError('Historical case identity differs')
            if not 1788220800000 <= case['snapshot_ms'] < 1788825600000:
                raise ValueError('UI examples must be September 1–7 selection dates')
            np.testing.assert_array_equal(case['actual_closes'], targets[i])
            expected_last = case['snapshot_ms']//60000*60000-60000
            if [b['time'] for b in case['past']] != list(range(expected_last-39*60000, expected_last+60000, 60000)):
                raise ValueError('Displayed past includes an unavailable or missing candle')
            chart_features = []
            for b in case['past']:
                o, hi, lo, cl = b['ohlc']
                if not 0 < lo <= min(o, cl) <= max(o, cl) <= hi:
                    raise ValueError('Invalid displayed input candle')
                chart_features.append(np.log(np.array([cl, hi, lo])/o))
            np.testing.assert_allclose(np.asarray(chart_features, np.float32), self.data.candles[i, -40:, :3], atol=2e-7, rtol=0)
        self.transforms = json.loads((run/'fit-transforms.json').read_text())
        if self.transforms['source_hashes']['september_selection_calibration'] != self.data.hashes:
            raise ValueError('UI data differ from final-build preprocessing')
        self.calibration = json.loads((run/'calibration.json').read_text())
        protocol = json.loads((run/'run-protocol.json').read_text())
        self.model = EventModel('attention' if protocol['candidate'] == 'event_attention' else 'temporal_conv',
                                width=protocol['neural_width'], block=protocol['event_block_groups'])
        self.model.load_state_dict(torch.load(run/'weights.pt', map_location='cpu', weights_only=True))
        self.model.eval(); torch.set_num_threads(4)
        self.weights_sha256 = file_hash(run/'weights.pt')

    def case(self, index):
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(self.cases):
            raise ValueError('Choose an available historical example')
        c = self.cases[index]
        return {k: copy.deepcopy(c[k]) for k in ['snapshot_ms', 'target_ms', 'reference', 'past']}

    def predict(self, index):
        with self.lock:
            case = self.case(index); started = time.perf_counter()
            args = inference_input(self.data, self.cases[index]['data_index'], self.transforms)
            with torch.inference_mode():
                logits = self.model(*args).numpy()
            p = probabilities(logits, self.calibration['temperatures'])[0]
            token = uuid.uuid4().hex
            result = {'token': token, 'case_id': index, 'fan': forecast_payload(p, case['reference'], case['target_ms']),
                      'calculation_ms': 1000*(time.perf_counter()-started),
                      'weights_sha256': self.weights_sha256, 'future_actuals_used': False,
                      'scope': 'Earlier selection example; 15 direct close distributions, no intraminute path or entry probability.'}
            self.requests[token] = (index, copy.deepcopy(result))
            if len(self.requests) > 1000:
                del self.requests[next(iter(self.requests))]
            return result

    def reveal(self, token):
        with self.lock:
            if token not in self.requests:
                raise ValueError('Predict first, then reveal that prediction')
            index, prediction = self.requests[token]; c = self.cases[index]
            actual = [{'close_ms': c['target_ms']+(h+1)*60000, 'close': value}
                      for h, value in enumerate(c['actual_closes'])]
            return {'case_id': index, 'actual_closes': actual, 'prediction_unchanged': True}


def dashboard_report():
    dev = json.loads((ROOT/'results/diwali1.4/development-report.json').read_text())
    rows = []
    for name in dev['decision']['mean_development_transfer_log_loss']:
        ms = [r['partitions']['score'] for r in dev['neural_runs'] if r['candidate'] == name]
        rows.append({'name': name, 'range_error': float(np.mean([m['mean15_bin_log_loss'] for m in ms])),
                     'direction_error': float(np.mean([m['final_direction_log_loss'] for m in ms])),
                     'direction_accuracy': float(np.mean([m['final_direction_accuracy'] for m in ms]))})
    for name in dev['baselines']['A']['models']:
        ms = [fold['models'][name]['partitions']['score'] for fold in dev['baselines'].values()]
        rows.append({'name': name, 'range_error': float(np.mean([m['mean15_bin_log_loss'] for m in ms])),
                     'direction_error': float(np.mean([m['final_direction_log_loss'] for m in ms])),
                     'direction_accuracy': float(np.mean([m['final_direction_accuracy'] for m in ms]))})
    path = ROOT/'data/btc-perp/diwali14-final-evaluation-v1/status.json'
    status = json.loads(path.read_text()) if path.exists() else {'state': 'not_started'}
    final = ROOT/'data/evaluations/diwali1.4-reserved-v1/report.json'
    return {'development': rows, 'selected_family': dev['decision']['selected_family'],
            'neural_runs_complete': len(dev['neural_runs']), 'final_test_status': status,
            'final_test': json.loads(final.read_text()) if final.exists() else None}


def main():
    p = argparse.ArgumentParser(); p.add_argument('--port', type=int, default=8754)
    p.add_argument('--run', type=Path, default=ROOT/'data/models/diwali1.4-final-v1')
    p.add_argument('--release', type=Path, default=ROOT/'data/evaluations/diwali1.4-final-release-v1.json')
    a = p.parse_args()
    engine = Engine(a.run, a.release, ROOT/'data/btc-perp/event-month-cohort-september-selection-v1',
                    ROOT/'data/btc-perp/event-inputs-september-selection-fast-v1',
                    ROOT/'results/event-joined-cohort/september-selection-audit.json')

    class Handler(BaseHTTPRequestHandler):
        def send(self, content, kind='application/json', status=200):
            b = json.dumps(content, allow_nan=False).encode() if kind == 'application/json' else content.encode()
            self.send_response(status); self.send_header('Content-Type', kind)
            self.send_header('Cache-Control', 'no-store'); self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)

        def do_GET(self):
            from urllib.parse import urlparse, parse_qs
            u = urlparse(self.path)
            try:
                if u.path == '/':
                    return self.send(Path(__file__).with_name('event_dashboard.html').read_text(), 'text/html; charset=utf-8')
                if u.path == '/dashboard.js':
                    return self.send(Path(__file__).with_name('event_dashboard.js').read_text(), 'text/javascript; charset=utf-8')
                if u.path == '/api/report':
                    return self.send(dashboard_report())
                if u.path == '/api/case':
                    return self.send(engine.case(int(parse_qs(u.query).get('id', ['0'])[0])))
                return self.send({'error': 'Not found'}, status=404)
            except Exception as error:
                self.send({'error': str(error)}, status=400)

        def do_POST(self):
            try:
                n = int(self.headers.get('Content-Length', '0'))
                if not 0 < n < 4096:
                    raise ValueError('Invalid request size')
                body = json.loads(self.rfile.read(n))
                if self.path == '/api/predict':
                    return self.send(engine.predict(body['case_id']))
                if self.path == '/api/reveal':
                    return self.send(engine.reveal(body['token']))
                return self.send({'error': 'Not found'}, status=404)
            except Exception as error:
                self.send({'error': str(error)}, status=400)

        def log_message(self, *args):
            pass

    print(f'Diwali 1.4 http://127.0.0.1:{a.port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', a.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
