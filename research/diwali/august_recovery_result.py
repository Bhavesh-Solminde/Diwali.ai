"""Reconcile the predeclared sample after the bounded independent snapshot replay."""
import argparse
import json
from pathlib import Path

import numpy as np

from ..market_data.event_replay import DTYPE as BOOK
from ..market_data.event_shards import read_events
from ..market_data.event_windows import window
from ..market_data.trade_events import DTYPE as TRADE
from ..market_data.validate_archive import file_hash, save

HOUR = 3600*10**9


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    root = args.root
    fixed_path = root/'fixed-sample.json'
    sample = json.loads(fixed_path.read_text())
    replay = root/'independent-snapshot-buffered-replay-v2'
    report = json.loads((replay/'report.json').read_text())
    protocol = json.loads((replay/'protocol.json').read_text())
    if protocol['sample_sha256'] != file_hash(fixed_path):
        raise ValueError('Bounded sample changed')
    gap_count = sum(h['counts'].get('sequence_gaps',0) for h in report['hours'])
    invalid_count = sum(h['counts'].get('invalid_events',0) for h in report['hours'])
    if gap_count or invalid_count:
        raise ValueError('Independent seed did not establish a continuous valid update chain')
    rows = []
    for item in sample['strata']:
        cutoff = item['cutoff_ns']
        entry = {'stratum':item['stratum'], 'fixed_cutoff_ns':cutoff,
                 'recovered_and_quality_accepted':False}
        if cutoff is None:
            entry['status'] = 'empty_predeclared_stratum'
        elif item['stratum'].startswith('2026-08-01'):
            hour = int(item['stratum'][-2:])
            sources = [replay/f'{h:02d}-sample-events.parquet' for h in (hour-1,hour) if h>=0]
            book = np.concatenate([read_events(p,BOOK) for p in sources])
            entry.update(snapshot_exists=True, snapshot_receipt_ns=protocol['snapshot_receipt_ns'],
                         native_chain_without_break=True, matched_venue_contract='Binance USD-M BTCUSDT perpetual')
            try:
                # Book gate runs before trade gates; remaining gates are reached only if the seed passes.
                window(book, np.empty(0,TRADE), cutoff-60*10**9, cutoff)
            except ValueError as exc:
                entry.update(status='existing_book_gate_failed', first_remaining_failure=str(exc),
                             subsequent_gates_reached=False,
                             diagnosis='Independent snapshot arrives after the required pre-window time'
                                       if protocol['snapshot_receipt_ns']>=cutoff-60*10**9
                                       else 'Native sequence connects but top20 leaves the verified snapshot bounds')
            else:
                raise ValueError('Book recovered: run the full unchanged gate pipeline before accepting an example')
        else:
            day=int(item['stratum'][8:10])
            probe=root/f'tardis-aug{day:02d}-minute0.txt'
            error=json.loads(probe.read_text())
            if error.get('code')!=10:
                raise ValueError('Unexpected source access response')
            entry.update(status='independent_snapshot_access_required', snapshot_exists=None,
                         native_chain_without_break=None, subsequent_gates_reached=False)
        rows.append(entry)
    sample_report=json.loads((root/'sample-report.json').read_text())
    q=sample_report['coverage']
    retained=q['retained_volatility_quartiles']
    totals=q['potential_volatility_quartiles']
    final={'state':'bounded_recovery_investigation_complete', 'fixed_strata':20,
           'fixed_sample_rule':sample['protocol']['sample'],
           'fixed_sample_protocol_sha256':sample['protocol_sha256'],
           'sampled_rejected_origins':sum(r['fixed_cutoff_ns'] is not None for r in rows),
           'empty_strata':sum(r['status']=='empty_predeclared_stratum' for r in rows),
           'independent_snapshot_windows_tested':sum(r['status']=='existing_book_gate_failed' for r in rows),
           'source_access_unresolved':sum(r['status']=='independent_snapshot_access_required' for r in rows),
           'recovered_quality_accepted':0,'rows':rows,
           'continuous_native_updates_replayed':sum(h['counts'].get('accepted_updates',0) for h in report['hours']),
           'native_sequence_gaps':gap_count,'invalid_events':invalid_count,
           'coverage':{**q,'retained_share_by_volatility_quartile':[n/sum(retained) for n in retained],
                       'retention_rate_within_volatility_quartile':[a/b for a,b in zip(retained,totals)]},
           'binance_bookDepth_schema':['timestamp','percentage','depth','notional'],
           'binance_bookDepth_compatible_with_native_snapshot_splice':False,
           'source_references':[
               'https://docs.tardis.dev/historical-data-details/binance-futures',
               'https://docs.tardis.dev/api/http-api-reference',
               'https://data.binance.vision/?prefix=data/futures/um/daily/bookDepth/BTCUSDT/'],
           'artifact_hashes':{str(p.relative_to(root)):file_hash(p) for p in [
               fixed_path,root/'protocol.json',root/'sample-report.json',replay/'protocol.json',
               replay/'report.json',root/'august-klines.zip',root/'binance-bookDepth-aug01.zip',
               *sorted(root.glob('tardis-aug*-minute0.txt'))]},
           'next_training_dataset_version':'august-recovered-v1 reserved until examples pass every original gate',
           'next_training_condition':'Paired original and attention fits on the identical expanded chronological origins after validated recovery',
           'current_forward_models_modified':False}
    save(root/'recovery-result.json',final)
    # Publish aggregate records only. No historical snapshot or individual reconstructed window is included.
    aggregate={k:v for k,v in final.items() if k not in ('rows','artifact_hashes')}
    aggregate['artifact_manifest_sha256']=file_hash(root/'recovery-result.json')
    aggregate['coverage']['fixed_rejected_sample_quartiles_suppressed']='Four groups each have fewer than ten sample origins'
    aggregate['coverage'].pop('fixed_rejected_sample_quartiles',None)
    save(Path('results/diwali1.5/august-recovery-investigation.json'),aggregate)
    print({k:final[k] for k in ('sampled_rejected_origins','independent_snapshot_windows_tested',
                              'source_access_unresolved','recovered_quality_accepted','continuous_native_updates_replayed')})


if __name__=='__main__':
    main()
