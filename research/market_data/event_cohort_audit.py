"""Content checks for event shards and a development candle/target cohort."""
import argparse
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

from .validate_archive import file_hash, save


def combine_bar(previous, incoming):
    """Combine independent native per-file execution aggregates by trade ID."""
    b = incoming.copy()
    if previous is None:
        return b
    a = previous.copy()
    bad = bool(a['bad'] or b['bad'])
    if not a['count']:
        b['bad'] = bad
        return b
    if not b['count']:
        a['bad'] = bad
        return a
    if b['first_id'] < a['first_id']:
        a['first_id'], a['open'] = b['first_id'], b['open']
    if b['last_id'] > a['last_id']:
        a['last_id'], a['close'] = b['last_id'], b['close']
    a['high'] = str(max(Decimal(a['high']), Decimal(b['high'])))
    a['low'] = str(min(Decimal(a['low']), Decimal(b['low'])))
    for field in ['volume', 'quote_volume']:
        a[field] = str(Decimal(a[field])+Decimal(b[field]))
    a['count'] += b['count']
    a['bad'] = bad
    return a


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
        raise ValueError('Incomplete preparation')
    source_hash = file_hash(a.source/'report.json')
    if cr['source_report_sha256'] != source_hash or wr['source_report_sha256'] != source_hash or wr['candle_report_sha256'] != file_hash(a.candles/'report.json'):
        raise ValueError('Different provenance')
    for name, sha in cr['artifact_sha256'].items():
        if file_hash(a.candles/name) != sha:
            raise ValueError('Changed candle artifact')
    if file_hash(a.windows/'windows.json') != wr['ledger_sha256']:
        raise ValueError('Changed join ledger')
    inputs = json.loads((a.candles/'input-metadata.json').read_text())
    labels = json.loads((a.candles/'targets.json').read_text())
    if len({r['input_row'] for r in labels}) != len(labels):
        raise ValueError('Duplicate labels')
    # Read future contents only for this already prepared August development day.
    if not '2026-08-01' <= cr['target_day'] <= '2026-08-31':
        raise ValueError('Nondevelopment label access denied')
    target_day_end = cr['target_day']+'T24'
    bars = {}
    counters, clocks = Counter(), Counter()
    differences = 0
    target_hours = good = 0
    for h in sr['hours']:
        name = h['UTC_hour']
        for kind, part in h['files'].items():
            if file_hash(a.source/name/part['file']) != part['sha256']:
                raise ValueError('Changed compressed event shard')
            qpath = Path('data/btc-perp/validation-v2-20261102/hours')/name[:10]/name[11:]/f'BTCUSDT_{kind}.parquet.quality.json'
            if file_hash(qpath) != part['quality_sha256']:
                raise ValueError('Changed prior quality record')
            q = json.loads(qpath.read_text())
            if q['manifest_sha256'] != part['source_sha256']:
                raise ValueError('Different raw source hash')
            audit = json.loads((a.source/name/(kind+'-audit.json')).read_text())
            if audit['counts']['rows'] != q['counts']['rows']:
                raise ValueError('Native replay row count differs')
            if not h['warmup_only']:
                clocks[kind] += int(part['clock_bad'])
                if kind == 'orderbook':
                    target_hours += 1
                    counters.update(audit['counts'])
                    good += sum(audit['good_seconds_per_minute'])
                    if audit['good_seconds_per_minute'] != q['good_seconds_per_minute']:
                        raise ValueError('Book eligibility changed from prior quality scan')
                    diff = {k for k in audit['counts'].keys() | q['counts'].keys() if audit['counts'].get(k,0) != q['counts'].get(k,0)}
                    if diff-{'accepted_updates','orphan_updates','top20_outside_snapshot_bounds_seconds'}:
                        raise ValueError('Unexplained replay counter difference')
                    differences += bool(diff)
            if kind == 'trades' and name < target_day_end:
                for bar in audit['candles']:
                    stamp = bar['minute_ms']*1000000
                    bars[stamp] = combine_bar(bars.get(stamp), bar)
    checked = 0
    maximum = 0.
    for row in labels:
        if len(row['closes']) != 15 or len(row['returns_bp']) != 15:
            raise ValueError('Incomplete target path')
        m = inputs[row['input_row']]
        if row['target_start_ns'] != m['target_start_ns']:
            raise ValueError('Misaligned label origin')
        for horizon, (close, ret) in enumerate(zip(row['closes'], row['returns_bp'])):
            b = bars[row['target_start_ns']+horizon*60*10**9]
            if not b['count'] or b['bad']:
                raise ValueError('Bad retained target')
            delta = abs(float(Decimal(b['close']))-close)
            maximum = max(maximum, delta)
            if delta != 0 or abs((close/m['reference']-1)*10000-ret) > 1e-9:
                raise ValueError('Target content or reference return differs')
            checked += 1
    windows = json.loads((a.windows/'windows.json').read_text())
    for row in windows:
        if file_hash(a.windows/row['file']) != row['sha256']:
            raise ValueError('Changed window indices')
    joined = {r['input_row'] for r in windows}
    labelled = {r['input_row'] for r in labels}
    result = {'state':'complete', 'target_day':cr['target_day'],
              'hours_including_warmup':sr['hours_including_warmup'], 'nonwarmup_hours':target_hours,
              'compressed_bytes':sr['compressed_bytes'], 'decoded_bytes':sr['uncompressed_bytes'],
              'book_good_seconds':good, 'book_total_seconds':target_hours*3600,
              'book_good_fraction':good/(target_hours*3600), 'book_counters':dict(counters),
              'all_hourly_book_eligibility_counts_match_prior_scan':True,
              'cold_vs_continuous_counter_difference_hours':differences,
              'counter_difference_scope':'Only accepted/orphan classification and out-of-snapshot-bound counts; book eligibility identical.',
              'clock_flagged_hours':dict(clocks), 'candle_contexts':len(inputs),
              'joined_input_windows':len(joined), 'labelled_candle_contexts':len(labelled),
              'joined_and_labelled_origins':len(joined & labelled),
              'independent_native_target_coordinates_checked':checked, 'maximum_close_difference':maximum,
              'window_rejections':wr['rejections'], 'window_event_rows':wr['event_rows'],
              'source_report_sha256':source_hash, 'candle_report_sha256':file_hash(a.candles/'report.json'),
              'join_report_sha256':file_hash(a.windows/'report.json'), 'audit_source_sha256':file_hash(Path(__file__)),
              'training_ready':False, 'limitations':[
                  'Native aggregates independently check the Python candle implementation, not exchange authenticity.',
                  'Targets are retained executions observed by source-day end; later arrivals outside it remain unproven.',
                  'Historical provider timing remains an assumption; hidden liquidity is not observed.',
                  'One development day only; full-fold cohorts, transforms, baselines and training remain outstanding.']}
    save(a.output, result)
    print(json.dumps({k:result[k] for k in ['joined_and_labelled_origins','independent_native_target_coordinates_checked','book_good_fraction']}))


if __name__ == '__main__':
    main()
