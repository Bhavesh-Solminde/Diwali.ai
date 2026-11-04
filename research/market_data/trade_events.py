"""Preserve every retained trade/placeholder with original sequence and integer units."""
import argparse,json,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import pyarrow as pa
from .build_pilot import feature_dtype,START
from .validate_archive import file_hash,save,raw_path,hour_ns,decoded,HARD_CLOCK

FIELDS=['receipt_ns','event_ns','trade_ns','trade_id','price','quantity','buyer_maker','bad','nonmarket']
DTYPE=np.dtype([(n,'<i8') for n in FIELDS])


def compile_trades(output):
    here=Path(__file__).parent;build=output/'build';build.mkdir()
    (build/'archive_scan.cpp').write_bytes((here/'archive_scan.cpp').read_bytes())
    source=(here/'feature_scan.cpp').read_text();entry='int main(int argc,char** argv)'
    if source.count(entry)!=1:raise ValueError('Changed feature entry')
    (build/'feature_scan.cpp').write_text(source.replace(entry,'int feature_scanner_entry(int argc,char** argv)'))
    (build/'trade_event_scan.cpp').write_bytes((here/'trade_event_scan.cpp').read_bytes())
    lib=Path(pa.get_library_dirs()[0]);binary=build/'trade-event-scan'
    subprocess.run(['clang++','-std=c++20','-O3',str(build/'trade_event_scan.cpp'),'-I'+pa.get_include(),str(sorted(lib.glob('libarrow.[0-9]*.dylib'))[0]),str(sorted(lib.glob('libparquet.[0-9]*.dylib'))[0]),'-Wl,-rpath,'+str(lib),'-o',str(binary)],check=True,capture_output=True,text=True)
    return binary.resolve()


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=False);began=time.time()
    root=Path('data/btc-perp/cryptohftdata-monthly');manifest=root/'manifest.json';records=json.loads(manifest.read_text());selected=[(d,h) for d in ['2026-10-05','2026-10-12'] for h in ['00','12']]
    sources={n:file_hash(Path(__file__).parent/n) for n in ['trade_events.py','trade_event_scan.cpp','feature_scan.cpp','archive_scan.cpp']}
    protocol={'hours':selected,'source_hashes':sources,'archive_manifest_sha256':file_hash(manifest),'integer_scale':100000000,'buyer_maker_means':'seller was aggressor','retain_nonmarket_and_bad_markers':True,'training_started':False};save(out/'protocol.json',protocol)
    binary=compile_trades(out);oldpath=Path('data/btc-perp/pilot-features-202610/trades-seconds.bin');expected=json.loads((oldpath.parent/'trades-extraction.json').read_text())['sha256']
    if file_hash(oldpath)!=expected:raise ValueError('Changed original trades')
    old=np.memmap(oldpath,dtype=feature_dtype('trades'),mode='r');ledger=[]
    for day,hour in selected:
        key=f'binance_futures/{day}/{hour}/BTCUSDT_trades.parquet';at=hour_ns(key);warm_at=at-3600*10**9;stamp=datetime.fromtimestamp(warm_at/1e9,timezone.utc);warm=f'binance_futures/{stamp:%Y-%m-%d}/{stamp:%H}/BTCUSDT_trades.parquet';pair=[]
        for k in [warm,key]:
            r=next(r for r in records if r['remote_file']==k);path=raw_path(root,r)
            if file_hash(path)!=r['sha256']:raise ValueError('Changed raw trades')
            bits=k.split('/');q=json.loads((Path('data/btc-perp/validation-v2-20261102/hours')/bits[1]/bits[2]/(bits[3]+'.quality.json')).read_text())
            if not q.get('ok') or q['manifest_sha256']!=r['sha256'] or any(q['counts'].get(x,0) for x in HARD_CLOCK+('backward_receipt_rows',)):raise ValueError('Unsuitable trade sample')
            pair.append((r,path))
        name=day+'T'+hour;seconds=out/(name+'-seconds.bin');events=out/(name+'-events.bin');ws=out/'warm-seconds.bin';we=out/'warm-events.bin'
        with decoded(pair[0][1],out) as a,decoded(pair[1][1],out) as b:
            lines=f'{warm_at}\t{a.resolve()}\t{ws.resolve()}\t{we.resolve()}\n{at}\t{b.resolve()}\t{seconds.resolve()}\t{events.resolve()}\n'
            result=subprocess.run([str(binary)],input=lines,text=True,capture_output=True,check=True)
        audit=json.loads(result.stdout.splitlines()[-1]);ws.unlink();we.unlink();data=np.memmap(events,dtype=DTYPE,mode='r');grid=np.fromfile(seconds,dtype=feature_dtype('trades'));i=(at-START*10**6)//10**9
        if len(grid)!=3600 or grid.tobytes()!=old[i:i+3600].tobytes():raise ValueError('Trade seconds parity failed')
        if len(data)!=pair[1][0]['rows'] or len(data)!=audit['counts']['rows'] or (np.diff(data['trade_id'])!=1).any() or data['bad'].any():raise ValueError('Trade row/sequence preflight failed')
        market=~data['nonmarket'].astype(bool)
        if (data['price'][market]<=0).any() or (data['quantity'][market]<=0).any():raise ValueError('Invalid market trade')
        ledger.append({'hour':name,'source_sha256':pair[1][0]['sha256'],'warmup_source_sha256':pair[0][0]['sha256'],'rows':len(data),'market_trades':int(market.sum()),'nonmarket_markers':int((~market).sum()),'bad_rows':int(data['bad'].sum()),'original_grid_rows_byte_equal':3600,'event_sha256':file_hash(events)})
        save(out/'status.json',{'state':'extracting','hours_done':len(ledger)});print(name,len(data),flush=True)
    save(out/'report.json',{'state':'complete','protocol':protocol,'parent_seconds_sha256':expected,'hours':ledger,'elapsed_seconds':time.time()-began,'training_ready':False,'limitations':['Four fit-only hours; not whole-month continuity.','Retained provider times do not prove original exchange receipt times.','Nonmarket placeholders remain markers, never market fills.','No cross-stream causal order or hidden order identity inferred.']});save(out/'status.json',{'state':'complete','hours_done':4})


if __name__=='__main__':main()
