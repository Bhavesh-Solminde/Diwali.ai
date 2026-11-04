"""Unscaled, input-only event features from a verified joined development cohort."""
import argparse
import json
import time
from pathlib import Path

import numpy as np

from .event_replay import DTYPE as BOOK
from .trade_events import DTYPE as TRADE
from .event_shards import read_events
from .event_windows import window
from .event_features import build, NAMES
from .validate_archive import file_hash, save


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--candles', type=Path, required=True)
    p.add_argument('--windows', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    sr = json.loads((a.source/'report.json').read_text())
    cr = json.loads((a.candles/'report.json').read_text())
    wr = json.loads((a.windows/'report.json').read_text())
    if any(r['state'] != 'complete' for r in [sr,cr,wr]):
        raise ValueError('Incomplete input preparation')
    if wr['source_report_sha256'] != file_hash(a.source/'report.json') or cr['source_report_sha256'] != wr['source_report_sha256'] or wr['candle_report_sha256'] != file_hash(a.candles/'report.json'):
        raise ValueError('Different input provenance')
    if file_hash(a.windows/'windows.json') != wr['ledger_sha256']:
        raise ValueError('Changed windows')
    for name in ['input-metadata.json','input-candles.npy','input-candle-masks.npy']:
        if file_hash(a.candles/name) != cr['artifact_sha256'][name]:
            raise ValueError('Changed candle inputs')
    metadata = json.loads((a.candles/'input-metadata.json').read_text())
    windows = json.loads((a.windows/'windows.json').read_text())
    # Labels are deliberately never opened here.
    hours = {h['UTC_hour']:h for h in sr['hours']}
    a.output.mkdir(parents=True,exist_ok=False)
    began = time.time()
    pair = None
    counts, ledger = [], []
    for item in windows:
        if tuple(item['hours']) != pair:
            pair = tuple(item['hours'])
            arrays = {}
            for kind, dtype in [('orderbook',BOOK),('trades',TRADE)]:
                pieces=[]
                for hour in pair:
                    part=hours[hour]['files'][kind];path=a.source/hour/part['file']
                    if part['clock_bad'] or file_hash(path) != part['sha256']:
                        raise ValueError('Changed or clock-invalid event source')
                    pieces.append(read_events(path,dtype))
                arrays[kind]=np.concatenate(pieces)
        b,t=arrays['orderbook'],arrays['trades']
        cutoff,start=item['input_cutoff_ns'],item['window_start_ns']
        previous=item['previous_release']
        selection=window(b,t,start,cutoff,book_previous_release=previous['orderbook'],trade_previous_release=previous['trades'])
        path=a.windows/item['file']
        if file_hash(path) != item['sha256']:
            raise ValueError('Changed source indices')
        with np.load(path) as stored:
            np.testing.assert_array_equal(selection['events'],stored['events'])
        if selection['book_seed_row'] != item['book_seed_row']:
            raise ValueError('Changed seed')
        value=build(b,t,selection,start,cutoff)
        m=metadata[item['input_row']]
        if m['input_cutoff_ns'] != cutoff:
            raise ValueError('Misaligned candle freeze')
        reference_offset=(m['reference']/value['anchor']-1)*10000
        name=f"{item['input_row']:06d}.npz"
        np.savez_compressed(a.output/name,events=value['features'],seed=value['seed_features'],
                            time_groups=value['time_groups'],reference_from_seed_bp=np.float64(reference_offset))
        n=len(value['features']);counts.append(n)
        ledger.append({'input_row':item['input_row'],'file':name,'sha256':file_hash(a.output/name),
                       'event_rows':n,'input_cutoff_ns':cutoff,'truncated':False})
        save(a.output/'status.json',{'state':'preparing_input_features','origins_done':len(ledger),'origins_total':len(windows)})
    save(a.output/'inputs.json',ledger)
    report={'state':'complete','origins':len(ledger),'event_rows':sum(counts),'feature_count':len(NAMES),'feature_names':NAMES,
            'minimum_events':min(counts,default=0),'maximum_events':max(counts,default=0),
            'future_labels_read':False,'normalization_fitted':False,'training_started':False,'training_ready':False,
            'join_report_sha256':file_hash(a.windows/'report.json'),'candle_report_sha256':file_hash(a.candles/'report.json'),
            'source_report_sha256':file_hash(a.source/'report.json'),'ledger_sha256':file_hash(a.output/'inputs.json'),
            'code_hashes':{p.name:file_hash(p) for p in [Path(__file__),Path(__file__).with_name('event_features.py'),Path(__file__).with_name('event_windows.py')]},
            'elapsed_seconds':time.time()-began,
            'limitations':['Unscaled input-only development features; target reconciliation and fit-only transforms remain separate.',
                           'Reference-to-seed coordinate is retained explicitly for the later training input contract.',
                           'No event truncation; same-time groups do not prove cross-feed order.']}
    save(a.output/'report.json',report)
    save(a.output/'status.json',{'state':'complete','origins':len(ledger),'event_rows':sum(counts)})


if __name__ == '__main__':
    main()
