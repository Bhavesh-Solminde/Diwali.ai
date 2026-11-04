"""Join causal candle contexts to complete raw event windows, without reading labels.

The saved row references address the preceding and current hourly shards joined
in that order. Source watermarks are carried from the start of the replay: an
hour boundary must not make a blocked earlier event available sooner.
"""
import argparse
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .event_replay import DTYPE as BOOK
from .trade_events import DTYPE as TRADE
from .event_shards import read_events
from .event_windows import release_times, window
from .validate_archive import file_hash, save

SECOND = 10**9
HOUR = 3600 * SECOND


def hour_ns(name):
    return int(datetime.strptime(name, '%Y-%m-%dT%H').replace(tzinfo=timezone.utc).timestamp()) * SECOND


def join_selection(book, trades, cutoff, book_watermark=-1, trade_watermark=-1):
    return window(book, trades, cutoff-60*SECOND, cutoff,
                  book_previous_release=book_watermark,
                  trade_previous_release=trade_watermark)


def source_release(rows, kind, previous, clock_bad=False):
    event = rows['event_ns'] if kind == 'orderbook' else np.maximum(rows['event_ns'], rows['trade_ns'])
    if clock_bad:
        # An excluded hour still carries any future-clock ordering barrier.
        return np.maximum.accumulate(np.maximum(np.maximum(rows['receipt_ns'], event), previous))
    return release_times(rows['receipt_ns'], event, previous)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--candles', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source, candles, out = args.source, args.candles, args.output
    sr = json.loads((source/'report.json').read_text())
    cr = json.loads((candles/'report.json').read_text())
    if sr['state'] != 'complete' or cr['state'] != 'complete':
        raise ValueError('Source preparation is incomplete')
    if cr['source_report_sha256'] != file_hash(source/'report.json'):
        raise ValueError('Candle contexts belong to a different source replay')
    # Intentionally do not open targets.json or any future price labels.
    for name in ['input-metadata.json', 'input-candles.npy', 'input-candle-masks.npy']:
        if file_hash(candles/name) != cr['artifact_sha256'][name]:
            raise ValueError('Changed candle input artifact')
    metadata = json.loads((candles/'input-metadata.json').read_text())
    cutoffs = [m['input_cutoff_ns'] for m in metadata]
    if cutoffs != sorted(set(cutoffs)):
        raise ValueError('Duplicate or unordered input freezes')
    if any(not hour_ns('2026-08-01T00') <= at < hour_ns('2026-09-01T00') for at in cutoffs):
        raise ValueError('Only August development origins are permitted')
    out.mkdir(parents=True, exist_ok=False)
    began = time.time()
    by_hour = {}
    for i, m in enumerate(metadata):
        by_hour.setdefault(m['input_cutoff_ns']//HOUR*HOUR, []).append((i, m))
    watermarks = {'orderbook': -1, 'trades': -1}
    previous = None
    ledger, rejected, counts, provenance = [], Counter(), [], {}
    stop = max(by_hour, default=-HOUR) + HOUR
    for entry in sr['hours']:
        stamp = hour_ns(entry['UTC_hour'])
        if stamp >= stop:
            break
        current = {'entry': entry, 'stamp': stamp, 'before': watermarks.copy(), 'rows': {}}
        for kind, dtype in [('orderbook', BOOK), ('trades', TRADE)]:
            part = entry['files'][kind]
            path = source/entry['UTC_hour']/part['file']
            if file_hash(path) != part['sha256']:
                raise ValueError('Changed event shard')
            rows = read_events(path, dtype)
            current['rows'][kind] = rows
            # Clock-invalid hours remain explicit exclusions, not repaired clocks.
            if part['clock_bad']:
                current.setdefault('bad_clock', True)
            released = source_release(rows, kind, watermarks[kind], part['clock_bad'])
            if len(released):
                watermarks[kind] = int(released[-1])
            provenance[str(path)] = part['sha256']
        origins = by_hour.get(stamp, [])
        if origins:
            if previous is None or stamp-previous['stamp'] != HOUR:
                rejected['missing_preceding_hour'] += len(origins)
            elif previous.get('bad_clock') or current.get('bad_clock'):
                rejected['clock_flagged_source_hour'] += len(origins)
            else:
                b = np.concatenate([previous['rows']['orderbook'], current['rows']['orderbook']])
                t = np.concatenate([previous['rows']['trades'], current['rows']['trades']])
                before = previous['before']
                for input_row, m in origins:
                    at = m['input_cutoff_ns']
                    try:
                        chosen = join_selection(b, t, at, before['orderbook'], before['trades'])
                    except ValueError as error:
                        rejected[str(error)] += 1
                        continue
                    name = f'{input_row:06d}.npz'
                    np.savez_compressed(out/name, events=chosen['events'])
                    n = len(chosen['events'])
                    ledger.append({'input_row': input_row, 'input_cutoff_ns': at,
                                   'window_start_ns': at-60*SECOND, 'file': name,
                                   'sha256': file_hash(out/name), 'book_seed_row': chosen['book_seed_row'],
                                   'book_events': chosen['book_events'], 'trade_rows': chosen['trade_rows'],
                                   'market_trades': chosen['market_trades'], 'truncated': False,
                                   'hours': [previous['entry']['UTC_hour'], entry['UTC_hour']],
                                   'previous_release': before.copy()})
                    counts.append(n)
        previous = current
        save(out/'status.json', {'state': 'joining', 'hour': entry['UTC_hour'],
                               'joined_origins': len(ledger), 'rejections': dict(rejected)})
        if origins:
            print(entry['UTC_hour'], len(ledger), dict(rejected), flush=True)
    save(out/'windows.json', ledger)
    result = {'state': 'complete', 'input_contexts': len(metadata), 'joined_origins': len(ledger),
              'rejections': dict(rejected), 'event_rows': int(sum(counts)),
              'minimum_events': min(counts, default=0), 'maximum_events': max(counts, default=0),
              'all_rows_retained_in_accepted_windows': True, 'future_labels_read': False,
              'source_report_sha256': file_hash(source/'report.json'),
              'candle_report_sha256': file_hash(candles/'report.json'),
              'source_hashes': provenance, 'ledger_sha256': file_hash(out/'windows.json'),
              'code_hashes': {p.name: file_hash(p) for p in [Path(__file__), Path(__file__).with_name('event_windows.py')]},
              'elapsed_seconds': time.time()-began, 'training_ready': False,
              'limitations': ['Input-only join; label validity/reconciliation and split purges remain separate.',
                              'Explicitly masked older candles remain missing information.',
                              'Provider timestamps do not prove original exchange receipt timing.',
                              'Cross-hour watermarks preserve ordering; equal-time groups do not prove cross-feed causal order.',
                              'Fit-only transforms and training protocol remain required.']}
    if len(ledger)+sum(rejected.values()) != len(metadata):
        raise ValueError('Not every input context has a join decision')
    save(out/'report.json', result)
    save(out/'status.json', {'state': 'complete', 'joined_origins': len(ledger), 'rejections': dict(rejected)})


if __name__ == '__main__':
    main()
