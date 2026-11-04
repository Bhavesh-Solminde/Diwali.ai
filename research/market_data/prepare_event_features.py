"""Prepare unscaled fit-only event features from verified raw row windows."""
import argparse,json
from pathlib import Path
import numpy as np
from .event_replay import DTYPE as BOOK
from .trade_events import DTYPE as TRADE
from .event_windows import window
from .event_features import build,NAMES
from .validate_archive import file_hash,save


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    root=Path('data/btc-perp/event-window-preflight-20261104-v1');br=Path('data/btc-perp/event-replay-preflight-20261104-v3');tr=Path('data/btc-perp/trade-events-preflight-20261104-v1');out=args.output;out.mkdir(parents=True,exist_ok=False)
    bh={r['hour']:r for r in json.loads((br/'report.json').read_text())['hours']};th={r['hour']:r for r in json.loads((tr/'report.json').read_text())['hours']}
    windows=json.loads((root/'windows.json').read_text());ledger=[];raw_count=0;distinct_hours=sorted({r['hour'] for r in windows})
    for hour in distinct_hours:
        if file_hash(br/(hour+'-events.bin'))!=bh[hour]['event_sha256'] or file_hash(tr/(hour+'-events.bin'))!=th[hour]['event_sha256']:raise ValueError('Changed raw event inputs')
        b=np.memmap(br/(hour+'-events.bin'),dtype=BOOK,mode='r');t=np.memmap(tr/(hour+'-events.bin'),dtype=TRADE,mode='r')
        for r in [r for r in windows if r['hour']==hour]:
            path=root/r['file']
            if file_hash(path)!=r['sha256']:raise ValueError('Changed window')
            selected=window(b,t,r['start_ns'],r['snapshot_ns']);np.testing.assert_array_equal(selected['events'],np.load(path));assert selected['book_seed_row']==r['seed_row']
            value=build(b,t,selected,r['start_ns'],r['snapshot_ns']);x=value['features'];raw_count+=len(x);name=Path(r['file']).stem
            np.savez(out/(name+'.npz'),features=x,seed_features=value['seed_features'],time_groups=value['time_groups'])
            ledger.append({'rows':len(x),'columns':x.shape[1],'finite':bool(np.isfinite(x).all()),'nonmarket_markers':int(x[:,NAMES.index('nonmarket_marker')].sum()),'future_outcomes_used':False,'truncated':False})
    report={'state':'complete','windows':len(ledger),'event_rows':raw_count,'feature_count':len(NAMES),'names':NAMES,'unscaled':True,'training_started':False,'training_ready':False,
        'source_hashes':{str(p):file_hash(p) for p in [Path(__file__),Path(__file__).with_name('event_features.py'),Path(__file__).with_name('event_windows.py'),root/'report.json',br/'report.json',tr/'report.json']},
        'counts':{'minimum_rows':min(r['rows'] for r in ledger),'maximum_rows':max(r['rows'] for r in ledger),'all_finite':all(r['finite'] for r in ledger),'nonmarket_markers':sum(r['nonmarket_markers'] for r in ledger)},
        'limitations':['Four fit-only hours,32 inputs, no targets.','Top20 entry/exit is a visibility change, not an identified cancellation/refill.','Trade records do not consume same-time book updates as confirmed prior context.','No fitted normalization; fitting later must exclude validation/calibration/final periods.','No full-size dataset or trained model yet.']}
    save(out/'report.json',report);public=Path('results/event-feature-preflight');public.mkdir(exist_ok=True);save(public/'report.json',report);print(json.dumps({k:report[k] for k in ['windows','event_rows','feature_count','counts']}))


if __name__=='__main__':main()
