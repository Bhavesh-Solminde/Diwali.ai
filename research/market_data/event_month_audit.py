"""Independent native close reconciliation and frozen split coverage for August."""
import argparse
import json
from pathlib import Path
from decimal import Decimal

import numpy as np

from .event_cohort_audit import combine_bar
from .validate_archive import file_hash,save
from ..diwali.event_evaluation import eligible_origins


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--cohort',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--final-release',type=Path);a=p.parse_args()
    sr=json.loads((a.source/'report.json').read_text());r=json.loads((a.cohort/'report.json').read_text());cr=json.loads((a.cohort/'candles/report.json').read_text());wr=json.loads((a.cohort/'windows/report.json').read_text())
    if any(x['state']!='complete' for x in [sr,r,cr,wr]):raise ValueError('Incomplete cohort')
    reserved=cr.get('target_interval')==['2026-09-15','2026-09-29']
    if reserved and a.final_release is not None:
        from ..diwali.event_final_gate import check_release
        check_release(a.final_release)
    elif cr.get('target_interval') not in [['2026-08-01','2026-08-31'],['2026-09-01','2026-09-14']]:raise ValueError('Reserved final audit access denied')
    if r['source_report_sha256']!=file_hash(a.source/'report.json'):raise ValueError('Changed source provenance')
    for part in ['candles','windows']:
        if r[('candle' if part=='candles' else 'window')+'_report_sha256']!=file_hash(a.cohort/part/'report.json'):raise ValueError('Changed cohort report')
    for name,sha in cr['artifact_sha256'].items():
        if file_hash(a.cohort/'candles'/name)!=sha:raise ValueError('Changed context/target file')
    if file_hash(a.cohort/'windows/windows.json')!=wr['ledger_sha256']:raise ValueError('Changed window ledger')
    metadata=json.loads((a.cohort/'candles/input-metadata.json').read_text());targets=json.loads((a.cohort/'candles/targets.json').read_text());windows=json.loads((a.cohort/'windows/windows.json').read_text())
    if len(windows)!=len(metadata) or len({x['input_cutoff_ns'] for x in metadata})!=len(metadata):raise ValueError('Incomplete/duplicate inputs')
    for i,w in enumerate(windows):
        if w['input_row']!=i or w['input_cutoff_ns']!=metadata[i]['input_cutoff_ns'] or file_hash(a.cohort/'windows'/w['file'])!=w['sha256']:raise ValueError('Misaligned/changed window')
    bars={}
    for hour in sr['hours']:
        part=hour['files']['trades'];path=a.source/hour['UTC_hour']/part['file']
        if file_hash(path)!=part['sha256']:raise ValueError('Changed trade source')
        for bar in json.loads((a.source/hour['UTC_hour']/'trades-audit.json').read_text())['candles']:
            stamp=bar['minute_ms']*1000000;bars[stamp]=combine_bar(bars.get(stamp),bar)
    checked=0;max_difference=0.
    for row in targets:
        if len(row['closes'])!=15 or len(row['returns_bp'])!=15:raise ValueError('Incomplete targets')
        m=metadata[row['input_row']]
        if row['target_start_ns']!=m['target_start_ns']:raise ValueError('Misaligned target')
        for i,(close,ret) in enumerate(zip(row['closes'],row['returns_bp'])):
            b=bars[row['target_start_ns']+i*60*10**9]
            if not b['count'] or b['bad']:raise ValueError('Native aggregate rejects retained target')
            difference=abs(float(Decimal(b['close']))-close);max_difference=max(max_difference,difference)
            if difference or abs((close/m['reference']-1)*10000-ret)>1e-9:raise ValueError('Target close/reference mismatch')
            checked+=1
    cutoffs=np.array([metadata[t['input_row']]['input_cutoff_ns'] for t in targets],np.int64);starts=np.array([t['target_start_ns'] for t in targets],np.int64)
    folds={}
    fold_names=['A','B','C'] if cr['target_interval'][0]=='2026-08-01' else ['final']
    partitions=['score'] if reserved else (['fit','select','calibrate','score'] if fold_names[0]=='A' else ['select','calibrate'])
    for fold in fold_names:
        folds[fold]={}
        for partition in partitions:
            keep,counts=eligible_origins(cutoffs,starts,fold,partition,final_release=a.final_release);folds[fold][partition]=counts
    days={}
    for t in targets:
        day=str(np.datetime64(metadata[t['input_row']]['input_cutoff_ns'],'ns'))[:10];days[day]=days.get(day,0)+1
    report={'state':'complete','scope':'Development/selection content and cohort audit, not forecasting performance','target_interval':cr['target_interval'],
            'cohort_sha256':file_hash(a.cohort/'report.json'),'source_report_sha256':file_hash(a.source/'report.json'),
            'audit_source_sha256':file_hash(Path(__file__)),'joined_contexts':len(metadata),'labelled_origins':len(targets),
            'native_target_coordinates_checked':checked,'maximum_close_difference':max_difference,
            'input_rejections':r['input_rejections'],'target_rejections':r['target_rejections'],
            'event_rows':r['event_rows'],'minimum_events':r['minimum_events'],'maximum_events':r['maximum_events'],
            'folds':folds,'labelled_origins_by_day':days,'content_gate_passed':True,'full_training_readiness':False,
            'limitations':['Historical provider timing is an assumption; original exchange authenticity is not certified.',
                           'Native aggregation checks a separate candle implementation using the same paid raw source.',
                           'Month-end target arrivals beyond retained data remain unproven; no outside data were invented.',
                           'Limited quality-approved book coverage restricts the research population; all rejections remain explicit.',
                           'Fit-only transforms, executable training settings and matched baselines must be verified separately.']}
    save(a.output,report);print(json.dumps({k:report[k] for k in ['joined_contexts','labelled_origins','native_target_coordinates_checked','maximum_close_difference','folds']},indent=2))


if __name__=='__main__':main()
