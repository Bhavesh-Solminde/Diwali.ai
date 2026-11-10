"""Finalize unpublished source metadata and audit the recovered cohort contents."""
from collections import Counter
import csv
from datetime import datetime, timezone
from decimal import Decimal
import io
import json
from pathlib import Path
import zipfile

import numpy as np

from .august_candlefeed_day import finalize_metadata
from ..market_data.event_cohort_audit import combine_bar
from ..market_data.validate_archive import file_hash, save


def final_metadata(source, cohort):
    """Correct inherited source-summary fields without changing any selected input/label bytes."""
    sr = json.loads((source/'report.json').read_text())
    protocol = json.loads((cohort/'protocol.json').read_text())
    cr = json.loads((cohort/'candles/report.json').read_text())
    wr = json.loads((cohort/'windows/report.json').read_text())
    report = json.loads((cohort/'report.json').read_text())
    if any(x['state'] != 'complete' for x in [sr, cr, wr, report]):
        raise ValueError('Preparation must finish before metadata finalization/audit')
    old = file_hash(source/'report.json')
    if (cohort/'source-metadata-finalization.json').exists():
        if protocol['source_report_sha256'] != old:
            raise ValueError('Changed finalized source')
        return
    for record in [protocol, cr, wr, report]:
        if record['source_report_sha256'] != old:
            raise ValueError('Cohort/source provenance disagrees before finalization')
    for name, sha in cr['artifact_sha256'].items():
        if file_hash(cohort/'candles'/name) != sha:
            raise ValueError('Changed prepared input or target data')
    (source/'report.before-metadata-finalization.json').write_bytes((source/'report.json').read_bytes())
    sr = finalize_metadata(sr, source)
    sr['parent_extraction_elapsed_seconds'] = sr.pop('elapsed_seconds')
    sr['metadata_finalizer_sha256'] = file_hash(Path(__file__))
    save(source/'report.json', sr)
    new = file_hash(source/'report.json')
    protocol['original_preparation_source_report_sha256'] = old
    protocol['source_report_sha256'] = new
    save(cohort/'protocol.json', protocol)
    protocol_hash = file_hash(cohort/'protocol.json')
    for record in [cr, wr, report]:
        record['source_report_sha256'] = new
        record['protocol_sha256'] = protocol_hash
    save(cohort/'candles/report.json', cr)
    wr['candle_report_sha256'] = file_hash(cohort/'candles/report.json')
    save(cohort/'windows/report.json', wr)
    report['candle_report_sha256'] = wr['candle_report_sha256']
    report['window_report_sha256'] = file_hash(cohort/'windows/report.json')
    save(cohort/'report.json', report)
    save(cohort/'status.json', report)
    save(cohort/'source-metadata-finalization.json', {
        'reason':'Inherited parent byte totals and quality bindings were finalized for the new derived source. No input selection, replay bytes, target data or model artifact changed.',
        'original_source_report_sha256':old, 'final_source_report_sha256':new,
        'unchanged_candle_input_and_target_hashes':cr['artifact_sha256'],
        'unchanged_window_ledger_sha256':wr['ledger_sha256']})


def main():
    source = Path('data/btc-perp/event-shards-august-candlefeed-recovered-v1')
    cohort = Path('data/btc-perp/august-recovered-v1')
    parent = Path('data/btc-perp/event-month-cohort-august-v1')
    final_metadata(source, cohort)
    sr = json.loads((source/'report.json').read_text())
    cr = json.loads((cohort/'candles/report.json').read_text())
    wr = json.loads((cohort/'windows/report.json').read_text())
    if cr['source_report_sha256'] != file_hash(source/'report.json') or wr['candle_report_sha256'] != file_hash(cohort/'candles/report.json'):
        raise ValueError('Finalized source binding mismatch')
    for name, sha in cr['artifact_sha256'].items():
        if file_hash(cohort/'candles'/name) != sha:
            raise ValueError('Changed frozen candle inputs or labels')
    metadata = json.loads((cohort/'candles/input-metadata.json').read_text())
    targets = json.loads((cohort/'candles/targets.json').read_text())
    old_meta = json.loads((parent/'candles/input-metadata.json').read_text())
    old_targets = json.loads((parent/'candles/targets.json').read_text())
    old = {old_meta[r['input_row']]['input_cutoff_ns']:r for r in old_targets}
    new = {metadata[r['input_row']]['input_cutoff_ns']:r for r in targets}
    if len(new) != len(targets) or len(old) != len(old_targets):
        raise ValueError('Duplicate labelled origins')
    gained = new.keys()-old.keys()
    lost = old.keys()-new.keys()
    # Explicit references preserve every original example; the original dataset is never edited.
    # This is a research index, not a silently merged feature tensor or released training split.
    combined = [{'input_cutoff_ns':at, 'cohort':'original', 'input_row':old[at]['input_row']} for at in old]
    combined += [{'input_cutoff_ns':at, 'cohort':'recovered', 'input_row':new[at]['input_row']} for at in gained]
    combined.sort(key=lambda r:r['input_cutoff_ns'])
    if len({r['input_cutoff_ns'] for r in combined}) != len(old)+len(gained):
        raise ValueError('Combined research index contains duplicate origins')
    save(cohort/'combined-origin-index.json', {
        'training_ready':False,
        'policy':'Keep original inputs at every originally accepted origin; add only newly eligible recovered origins. Retain explicit source-version references. Matched training preparation remains a separate experiment.',
        'sources':{'original':str(parent), 'recovered':str(cohort)},
        'source_report_sha256':{'original':file_hash(parent/'report.json'), 'recovered':file_hash(cohort/'report.json')},
        'origins':combined})
    bars = {}
    checked_files = 0
    for entry in sr['hours']:
        folder = source/entry['UTC_hour']
        for kind, part in entry['files'].items():
            if file_hash(folder/part['file']) != part['sha256']:
                raise ValueError('Changed source shard')
            checked_files += 1
            if kind == 'orderbook' and entry['UTC_hour'].startswith('2026-08-01T'):
                if file_hash(folder/part['quality_file']) != part['quality_sha256']:
                    raise ValueError('Changed independent replay audit')
        audit = json.loads((folder/'trades-audit.json').read_text())
        for bar in audit['candles']:
            stamp = bar['minute_ms']*10**6
            bars[stamp] = combine_bar(bars.get(stamp), bar)
    checked = 0
    for row in targets:
        m = metadata[row['input_row']]
        if row['target_start_ns'] != m['target_start_ns'] or len(row['closes']) != 15:
            raise ValueError('Misaligned/incomplete target')
        for horizon, close in enumerate(row['closes']):
            b = bars[row['target_start_ns']+horizon*60*10**9]
            if b['bad'] or not b['count'] or float(Decimal(b['close'])) != close:
                raise ValueError('Target differs from independent native execution aggregate')
            if abs((close/m['reference']-1)*10000-row['returns_bp'][horizon]) > 1e-9:
                raise ValueError('Return/reference mismatch')
            checked += 1
    ledger = json.loads((cohort/'windows/windows.json').read_text())
    if file_hash(cohort/'windows/windows.json') != wr['ledger_sha256']:
        raise ValueError('Changed window ledger')
    for row in ledger:
        if file_hash(cohort/'windows'/row['file']) != row['sha256']:
            raise ValueError('Changed frozen window indices')
    reference = Path('data/btc-perp/august-book-recovery-v1/august-klines.zip')
    expected = reference.with_suffix(reference.suffix+'.CHECKSUM').read_text().split()[0]
    if file_hash(reference) != expected:
        raise ValueError('Official reference checksum mismatch')
    with zipfile.ZipFile(reference) as archive:
        candles = list(csv.DictReader(io.TextIOWrapper(archive.open(archive.namelist()[0]))))
    official = {int(r['open_time'])*10**6:r for r in candles}
    reference_checks = 0
    reference_mismatches = 0
    for cutoff in gained:
        row = new[cutoff]
        for horizon, close in enumerate(row['closes']):
            at = row['target_start_ns']+horizon*60*10**9
            ref = official[at];native = bars[at]
            reference_mismatches += int(float(ref['close']) != close or
                Decimal(native['volume']) != Decimal(ref['volume']) or native['count'] != int(ref['count']))
            reference_checks += 1
    opens = np.array([int(r['open_time'])*10**6 for r in candles],np.int64)
    closes = np.array([float(r['close']) for r in candles])
    changes = np.r_[np.nan,np.diff(np.log(closes))]
    rms = np.full(len(candles),np.nan)
    for j in range(61,len(candles)):
        rms[j] = np.sqrt(np.mean(changes[j-60:j]**2))*10000
    thresholds = np.quantile(rms[np.isfinite(rms)],[.25,.5,.75])
    quarters = np.searchsorted(thresholds,rms)
    def distribution(origins):
        ids = np.array([(at-15*10**9-opens[0])//(60*10**9) for at in origins],int)
        ids = ids[np.isfinite(rms[ids])]
        return np.bincount(quarters[ids],minlength=4).tolist()
    day = lambda at:datetime.fromtimestamp(at/1e9,timezone.utc).strftime('%Y-%m-%d')
    result = {
        'state':'recovered_cohort_audited', 'scope':'Only August 1 books were reseeded. Original August sources otherwise retained.',
        'audit_code_sha256':file_hash(Path(__file__)),
        'independent_snapshot_sha256':sr['protocol']['independent_snapshot_sha256'],
        'independent_snapshots_used':288, 'snapshot_price_level_rows':576000,
        'account_access':{'authenticated_plan':'free', 'authorized_august_days':['2026-08-01'],
                          'other_august_days_plan_restricted':30, 'july31_http_status':403,
                          'required_archive_entitlement':'Pro or separately authorized provider export'},
        'source_files_hash_verified':checked_files, 'frozen_windows_hash_verified':len(ledger),
        'original_labelled_examples':len(old), 'recovered_version_labelled_examples':len(new),
        'newly_eligible_origins':len(gained), 'original_origins_absent_in_recovered_version':len(lost),
        'unique_original_plus_newly_recovered_examples':len(combined),
        'combined_research_index_sha256':file_hash(cohort/'combined-origin-index.json'),
        'combined_index_has_duplicate_origins':False, 'combined_index_training_ready':False,
        'net_change':len(new)-len(old), 'unchanged_original_dataset_labelled_examples':len(old),
        'original_by_day':dict(Counter(map(day,old))), 'recovered_by_day':dict(Counter(map(day,new))),
        'gained_by_day':dict(Counter(map(day,gained))), 'lost_by_day':dict(Counter(map(day,lost))),
        'gained_by_utc_hour':dict(sorted(Counter(datetime.fromtimestamp(at/1e9,timezone.utc).hour for at in gained).items())),
        'gained_prior_hour_volatility_quartiles':distribution(gained),
        'old_prior_hour_volatility_quartiles':distribution(old),
        'recovered_prior_hour_volatility_quartiles':distribution(new),
        'native_target_coordinates_checked':checked, 'native_target_mismatches':0,
        'new_target_coordinates_checked_against_official_archive':reference_checks,
        'official_close_volume_count_mismatches':reference_mismatches,
        'input_rejections':json.loads((cohort/'report.json').read_text())['input_rejections'],
        'target_rejections':cr['target_rejections'],
        'source_report_sha256':file_hash(source/'report.json'),
        'cohort_report_sha256':file_hash(cohort/'report.json'),
        'training_started':False, 'current_forward_models_modified':False,
        'limits':['Partial recovery with a Free CandleFeed account; other August dates require entitlement.',
                  'Historical cross-provider clocks are not proven original live availability.',
                  'Some previously accepted windows fail the reseeded stream at snapshot bootstrap transitions. Preserve both versions; do not silently discard or union their inputs.',
                  'Additional data is not evidence of improved model accuracy.']}
    save(cohort/'recovery-audit.json',result)
    save(Path('results/diwali1.5/august-candlefeed-recovery.json'),result)
    print({k:result[k] for k in ['original_labelled_examples','recovered_version_labelled_examples',
                               'newly_eligible_origins','original_origins_absent_in_recovered_version',
                               'native_target_mismatches','official_close_volume_count_mismatches']},flush=True)


if __name__ == '__main__':
    main()
