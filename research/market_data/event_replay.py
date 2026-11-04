"""Exact top20 states after every retained L2 batch, with old-grid parity checks."""
import argparse,json,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import pyarrow as pa
from .build_pilot import feature_dtype,START
from .validate_archive import file_hash,save,raw_path,hour_ns,decoded,HARD_CLOCK

METADATA=['receipt_ns','event_ns','available_ns','sequence','source_update_id','snapshot','accepted_update','valid','ordinal']
DTYPE=np.dtype([(n,'<i8') for n in METADATA]+[('levels','<i8',(20,4))])


def compile_events(output):
    here=Path(__file__).parent;generated=output/'build';generated.mkdir()
    source=(here/'archive_scan.cpp').read_text()
    needle='  virtual void on_tick(I, bool) {}'
    if source.count(needle)!=1 or source.count('    event_open=false;')!=1:raise ValueError('Frozen replay hook location changed')
    source=source.replace(needle,needle+'\n  virtual void on_book_event() {}').replace('    event_open=false;','    on_book_event();\n    event_open=false;')
    (generated/'archive_scan.cpp').write_text(source)
    feature=(here/'feature_scan.cpp').read_text()
    entry='int main(int argc,char** argv)'
    if feature.count(entry)!=1:raise ValueError('Feature entry point changed')
    (generated/'feature_scan.cpp').write_text(feature.replace(entry,'int feature_scanner_entry(int argc,char** argv)'))
    (generated/'event_scan.cpp').write_bytes((here/'event_scan.cpp').read_bytes())
    lib=Path(pa.get_library_dirs()[0]);binary=generated/'event-scan'
    subprocess.run(['clang++','-std=c++20','-O3',str(generated/'event_scan.cpp'),'-I'+pa.get_include(),str(sorted(lib.glob('libarrow.[0-9]*.dylib'))[0]),str(sorted(lib.glob('libparquet.[0-9]*.dylib'))[0]),'-Wl,-rpath,'+str(lib),'-o',str(binary)],check=True,capture_output=True,text=True)
    return binary.resolve()


def validate_events(rows,counts):
    if len(rows)!=counts.get('events',0) or int(rows['accepted_update'].sum())!=counts.get('accepted_updates',0):raise ValueError('Event emission count mismatch')
    np.testing.assert_array_equal(rows['ordinal'],np.arange(len(rows)))
    np.testing.assert_array_equal(rows['available_ns'],np.maximum(rows['receipt_ns'],rows['event_ns']))
    good=rows['valid'].astype(bool);levels=rows['levels'][good]
    if len(levels):
        if (levels<=0).any() or (np.diff(levels[:,:,0],axis=1)>=0).any() or (np.diff(levels[:,:,2],axis=1)<=0).any() or (levels[:,0,0]>=levels[:,0,2]).any():raise ValueError('Invalid emitted top20')
    if rows['levels'][~good].any():raise ValueError('Invalid states must carry zero levels')


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=False);began=time.time()
    root=Path('data/btc-perp/cryptohftdata-monthly');manifest=root/'manifest.json';records=json.loads(manifest.read_text());selected=[(d,h) for d in ['2026-10-05','2026-10-12'] for h in ['00','12']]
    protocol={'hours':selected,'selection':'Same fixed fit-only resolution-audit hours; no labels','sources':{n:file_hash(Path(__file__).parent/n) for n in ['event_replay.py','event_scan.cpp','archive_scan.cpp','feature_scan.cpp']},'archive_manifest_sha256':file_hash(manifest),'top20_scale':100000000,'dtype_bytes':DTYPE.itemsize,'batch_atomic':True,'training_started':False}
    save(out/'protocol.json',protocol);binary=compile_events(out);ledger=[]
    parent=np.memmap('data/btc-perp/pilot-features-202610/book-seconds.bin',dtype=feature_dtype('book'),mode='r')
    expected=json.loads(Path('data/btc-perp/pilot-features-202610/book-extraction.json').read_text())['sha256']
    if file_hash(Path('data/btc-perp/pilot-features-202610/book-seconds.bin'))!=expected:raise ValueError('Changed original seconds')
    # Replay the preceding hour too: even an invalid first grid can carry age
    # metadata from the previous update. Never relax byte parity for that case.
    for day,hour in selected:
        key=f'binance_futures/{day}/{hour}/BTCUSDT_orderbook.parquet';r=next(r for r in records if r['remote_file']==key);path=raw_path(root,r)
        if file_hash(path)!=r['sha256']:raise ValueError('Changed raw input')
        quality=json.loads((Path('data/btc-perp/validation-v2-20261102/hours')/day/hour/'BTCUSDT_orderbook.parquet.quality.json').read_text())
        if not quality.get('ok') or quality['manifest_sha256']!=r['sha256'] or any(quality['counts'].get(k,0) for k in HARD_CLOCK+('backward_receipt_rows',)):raise ValueError('Unsuitable sample clock/quality')
        name=day+'T'+hour;seconds=out/(name+'-seconds.bin');events=out/(name+'-events.bin');at=hour_ns(key)
        warm_at=at-3600*10**9;stamp=datetime.fromtimestamp(warm_at/1e9,timezone.utc);warm_key=f'binance_futures/{stamp:%Y-%m-%d}/{stamp:%H}/BTCUSDT_orderbook.parquet'
        warm_record=next(r for r in records if r['remote_file']==warm_key);warm_path=raw_path(root,warm_record)
        if file_hash(warm_path)!=warm_record['sha256']:raise ValueError('Changed warmup input')
        warm_seconds=out/'warmup-seconds.bin';warm_events=out/'warmup-events.bin'
        with decoded(warm_path,out) as warm_plain,decoded(path,out) as plain:
            lines=f'{warm_at}\t{warm_plain.resolve()}\t{warm_seconds.resolve()}\t{warm_events.resolve()}\n{at}\t{plain.resolve()}\t{seconds.resolve()}\t{events.resolve()}\n'
            run=subprocess.run([str(binary)],input=lines,text=True,capture_output=True,check=True)
        audits=[json.loads(s) for s in run.stdout.splitlines()];audit=audits[-1]
        if len(audits)!=2 or audits[0]['counts'].get('snapshots',0)<1:raise ValueError('Warmup lacks an initializing snapshot')
        warm_seconds.unlink();warm_events.unlink()
        values=np.fromfile(seconds,dtype=feature_dtype('book'));start=(at-START*10**6)//10**9
        # Compare every state/feature including rejected grids, not just row totals.
        original=parent[start:start+3600]
        if len(values)!=3600 or values.tobytes()!=original.tobytes():raise ValueError('Observer changed historical replay bytes')
        emitted=np.memmap(events,dtype=DTYPE,mode='r');validate_events(emitted,audit['counts'])
        ledger.append({'hour':name,'source_sha256':r['sha256'],'warmup_source_sha256':warm_record['sha256'],'events':len(emitted),'accepted_updates':int(emitted['accepted_update'].sum()),'valid_states':int(emitted['valid'].sum()),'old_grid_rows_byte_equal':3600,'event_sha256':file_hash(events),'seconds_sha256':file_hash(seconds)})
        save(out/'status.json',{'state':'extracting','hours_done':len(ledger),'hours_total':4});print(name,len(emitted),flush=True)
    save(out/'report.json',{'state':'complete','protocol':protocol,'parent_seconds_sha256':expected,'hours':ledger,'elapsed_seconds':time.time()-began,'training_ready':False,'limitations':['Top20 per provider batch; raw deeper levels remain in source archive.','No trade merge or new model windows yet.','Provider receipt authenticity remains uncertain.','Atomic batch order does not reveal individual orders or hidden liquidity.','Four sampled hour pairs do not prove whole-month continuity.']})
    save(out/'status.json',{'state':'complete','hours_done':4})


if __name__=='__main__':main()
