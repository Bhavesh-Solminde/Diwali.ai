"""Prepare private, as-of historical chart cases from selection dates only."""
import argparse
import json
import math
from pathlib import Path

import numpy as np

from .event_data_exact import ExactEventData
from .event_evaluation import interval, eligible_origins
from ..market_data.candle_tape import CandleTape, MINUTE, SCALE, released
from ..market_data.event_shards import read_events
from ..market_data.trade_events import DTYPE
from ..market_data.validate_archive import file_hash, save


def past_bars(source, hours, previous_release, cutoff):
    tape = CandleTape()
    last_release = int(previous_release)
    for hour in hours:
        root = source / hour['UTC_hour']
        part = hour['files']['trades']
        path = root / part['file']
        if file_hash(path) != part['sha256']:
            raise ValueError('Changed demo trade source')
        rows = read_events(path, DTYPE)
        times = released(rows, last_release)
        if len(times):
            last_release = int(times[-1])
        for row, at in zip(rows[times < cutoff], times[times < cutoff]):
            tape.ingest(row, int(at))
    last = cutoff // MINUTE * MINUTE - MINUTE
    candles = []
    features = []
    for start in range(last - 39 * MINUTE, last + MINUTE, MINUTE):
        bar = tape.minutes.get(start)
        if bar is None or bar['bad'] or not bar['n']:
            raise ValueError('Missing or invalid as-of demo candle')
        candles.append({'time': start // 10**6,
                        'ohlc': [bar[k] / SCALE for k in ['o', 'h', 'l', 'c']]})
        features.append([math.log(bar['c']/bar['o']), math.log(bar['h']/bar['o']),
                         math.log(bar['l']/bar['o']), math.log1p(bar['v']/SCALE),
                         math.log1p(bar['q']/SCALE**2), math.log1p(bar['n']),
                         math.sin(2*math.pi*((start//MINUTE)%1440)/1440),
                         math.cos(2*math.pi*((start//MINUTE)%1440)/1440)])
    return candles, np.asarray(features, np.float32)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--cohort', type=Path, required=True)
    p.add_argument('--features', type=Path, required=True)
    p.add_argument('--content-audit', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        raise ValueError('Demo artifact already exists; do not overwrite')
    data = ExactEventData(a.cohort, a.features, a.content_audit)
    sr = json.loads((a.source/'report.json').read_text())
    cr = json.loads((a.cohort/'report.json').read_text())
    if sr['state'] != 'complete' or cr['source_report_sha256'] != file_hash(a.source/'report.json'):
        raise ValueError('Demo source differs from audited cohort')
    source_hours = {r['UTC_hour']: r for r in sr['hours']}
    start, stop = interval('final', 'select')
    keep, _ = eligible_origins(data.cutoffs, data.starts, 'final', 'select')
    candidates = [int(j) for j in np.flatnonzero(keep)
                  if data.candle_masks[int(data.ids[j]), -40:].all()]
    if len(candidates) < 10:
        raise ValueError('Insufficient selection examples')
    selected = np.asarray(candidates)[np.linspace(0, len(candidates)-1, 10, dtype=int)]
    windows = json.loads((a.cohort/'windows/windows.json').read_text())
    targets = {r['input_row']: r for r in json.loads((a.cohort/'candles/targets.json').read_text())}
    cases = []
    for j in selected:
        i = int(data.ids[j]); meta = data.metadata[i]; window = windows[i]
        cutoff = int(meta['input_cutoff_ns'])
        if not start <= cutoff < stop:
            raise ValueError('Demo origin outside selection period')
        bars, x = past_bars(a.source, [source_hours[h] for h in window['hours']],
                            window['previous_release']['trades'], cutoff)
        np.testing.assert_array_equal(x, data.candles[i, -40:])
        cases.append({'data_index': int(j), 'input_row': i, 'snapshot_ms': cutoff//10**6,
                      'target_ms': int(meta['target_start_ns'])//10**6,
                      'reference': meta['reference'], 'past': bars,
                      'actual_closes': targets[i]['closes']})
    save(a.output, {'state': 'selection_demo_prepared', 'cases': cases,
                    'data_hashes': data.hashes, 'source_report_sha256': file_hash(a.source/'report.json'),
                    'selection_policy': 'Ten evenly spaced selection origins with valid last 40 input candles; no return-value selection.',
                    'past_input_feature_parity': 'All 400 displayed as-of candles match saved model features exactly.',
                    'future_actuals_policy': 'Private actual closes served only after a matching prediction token is revealed.',
                    'scope': 'Previously used selection examples, not independent final test or live forecasts.'})
    print('Prepared ten private historical cases; all 400 as-of chart candles match input features exactly.')


if __name__ == '__main__':
    main()
