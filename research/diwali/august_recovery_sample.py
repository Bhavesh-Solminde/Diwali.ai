"""Select the fixed August rejection sample and describe coverage before recovery."""
import argparse
import csv
import io
import json
from pathlib import Path
import zipfile

import numpy as np
import pyarrow.parquet as pq

from ..market_data.event_join_cohort import hour_ns
from ..market_data.event_month_cohort import intersects
from ..market_data.event_replay import DTYPE as BOOK
from ..market_data.event_shards import read_events
from ..market_data.event_windows import release_times
from ..market_data.validate_archive import file_hash, save

MINUTE = 60*10**9
HOUR = 60*MINUTE
DAYS = (1, 8, 15, 22, 29)
HOURS = (0, 6, 12, 18)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    root = Path('data/btc-perp')
    shards = root/'event-shards-snapshot-seeded-august-v2'
    cohort = root/'event-month-cohort-august-v1'
    report = json.loads((shards/'report.json').read_text())
    protocol = json.loads((cohort/'protocol.json').read_text())
    sample_protocol = json.loads((args.output/'protocol.json').read_text())
    targets = {f'2026-08-{d:02d}T{h:02d}' for d in DAYS for h in HOURS}
    exclusions = protocol['clock_trade_exclusion_intervals_ns']
    selected = []
    previous = None
    watermark = -1
    for item in report['hours']:
        stamp = hour_ns(item['UTC_hour'])
        part = item['files']['orderbook']
        path = shards/item['UTC_hour']/part['file']
        # A release prefix ends at the maximum clock reached in all earlier rows.
        clocks = pq.read_table(path, columns=['receipt_ns', 'event_ns'])
        receipt = clocks['receipt_ns'].to_numpy()
        event = clocks['event_ns'].to_numpy()
        before = watermark
        if len(receipt):
            watermark = max(watermark, int(receipt.max()), int(event.max()))
        if item['UTC_hour'] in targets:
            pair = previous is not None and stamp-previous['stamp'] == HOUR
            options = []
            if pair:
                prior = previous['item']
                pp = shards/prior['UTC_hour']/prior['files']['orderbook']['file']
                if file_hash(path) != part['sha256'] or file_hash(pp) != prior['files']['orderbook']['sha256']:
                    raise ValueError('Changed source shard')
                book = np.concatenate([read_events(pp, BOOK), read_events(path, BOOK)])
                available = release_times(book['receipt_ns'], book['event_ns'], previous['before'])
                clock_bad = any(h['files'][kind]['clock_bad'] for h in (prior, item) for kind in ('trades','orderbook'))
                for minute in range(60):
                    cutoff = stamp+minute*MINUTE+15*10**9
                    if intersects(cutoff//MINUTE*MINUTE-1440*MINUTE, cutoff, exclusions) or clock_bad:
                        continue
                    seed = int(np.searchsorted(available, cutoff-MINUTE, side='left'))-1
                    if seed < 0 or not book['valid'][seed]:
                        options.append(cutoff)
                del book
            audit = json.loads((shards/item['UTC_hour']/'orderbook-audit.json').read_text())
            selected.append({'stratum': item['UTC_hour'],
                             'cutoff_ns': options[0] if options else None,
                             'eligible_missing_seed_origins_in_stratum': len(options),
                             'original_first_failed_gate': 'No valid pre-window book seed' if options else None,
                             'hour_book_audit': {k:v for k,v in audit['counts'].items()
                                if k in ('snapshots','sequence_gaps','invalid_events','orphan_updates',
                                         'empty_or_crossed_events','top20_outside_snapshot_bounds_seconds')}})
            save(args.output/'sample-progress.json', {'strata_checked':len(selected), 'strata':selected})
        previous = {'stamp':stamp, 'item':item, 'before':before}
        if item['UTC_hour'] >= max(targets):
            break
    if len(selected) != 20:
        raise ValueError('Fixed strata missing from replay')
    save(args.output/'fixed-sample.json', {'protocol':sample_protocol, 'strata':selected,
                                         'protocol_sha256':file_hash(args.output/'protocol.json')})
    archive = args.output/'august-klines.zip'
    checksum = (args.output/'august-klines.zip.CHECKSUM').read_text().split()[0]
    if file_hash(archive) != checksum:
        raise ValueError('Official candle archive checksum failed')
    with zipfile.ZipFile(archive) as z:
        reader = csv.DictReader(io.TextIOWrapper(z.open(z.namelist()[0])))
        candles = list(reader)
    opens = np.array([int(r['open_time'])*10**6 for r in candles],np.int64)
    closes = np.array([float(r['close']) for r in candles])
    if len(candles) != 44640 or not np.all(np.diff(opens)==MINUTE):
        raise ValueError('Official August candle coverage differs')
    changes = np.r_[np.nan, np.diff(np.log(closes))]
    rms = np.full(len(candles),np.nan)
    # Each forecast at second15 uses 60 prior closed returns.
    for j in range(61,len(candles)):
        rms[j] = np.sqrt(np.mean(changes[j-60:j]**2))*10000
    thresholds = np.quantile(rms[np.isfinite(rms)],[.25,.5,.75])
    metadata = json.loads((cohort/'candles/input-metadata.json').read_text())
    labelled = json.loads((cohort/'candles/targets.json').read_text())
    keep = np.array([(metadata[r['input_row']]['input_cutoff_ns']-15*10**9-opens[0])//MINUTE for r in labelled],int)
    assigned = np.searchsorted(thresholds,rms)
    valid = np.isfinite(rms)
    count = lambda ids: [int(np.sum(assigned[np.asarray(ids)]==k)) for k in range(4)]
    chosen = [s['cutoff_ns'] for s in selected if s['cutoff_ns'] is not None]
    ci = np.array([(t-15*10**9-opens[0])//MINUTE for t in chosen],int)
    quality = json.loads((cohort/'report.json').read_text())
    result = {'state':'fixed_sample_selected','strata':selected,'nonempty_strata':len(chosen),
              'empty_predetermined_strata':len(selected)-len(chosen),
              'coverage':{'potential_volatility_quartiles':count(np.flatnonzero(valid)),
                          'retained_volatility_quartiles':count(keep[valid[keep]]),
                          'fixed_rejected_sample_quartiles':count(ci[valid[ci]]),
                          'volatility_thresholds_bp':thresholds.tolist(),
                          'retained_by_day':{f'2026-08-{d:02d}':sum(metadata[r['input_row']]['input_cutoff_ns']//(24*HOUR)==hour_ns(f'2026-08-{d:02d}T00')//(24*HOUR) for r in labelled) for d in range(1,32)},
                          'retained_by_utc_hour':np.bincount((opens[keep]//HOUR)%24,minlength=24).tolist(),
                          'original_quality_retention':quality['labelled_joined_origins']/quality['origins_considered']},
              'official_candles_usage':'Coverage diagnosis only. No repaired candle supplied to model inputs.',
              'snapshot_recovery_results':'Pending source and native-sequence checks',
              'source_hashes':{str(p):file_hash(p) for p in (archive,shards/'report.json',cohort/'report.json')}}
    save(args.output/'sample-report.json',result)
    print('Fixed sample',len(chosen),'of20strata; coverage',result['coverage'],flush=True)


if __name__ == '__main__':
    main()
