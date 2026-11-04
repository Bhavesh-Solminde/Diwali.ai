"""Recover absolute book midpoints without changing any existing model inputs."""
import argparse,json,subprocess,time
from pathlib import Path
import numpy as np
import pyarrow as pa
from .build_pilot import feature_dtype,START
from .validate_archive import file_hash,save,raw_path,hour_ns,decoded,HARD_CLOCK

DTYPE=np.dtype([(k,'<i8') for k in ['time_ns','receipt_ns','event_ns','sequence','age_ns','valid']]+[('mid','<f8')])


def compile_midpoint(output):
    here=Path(__file__).parent;lib=Path(pa.get_library_dirs()[0]);binary=output/'midpoint-scan'
    subprocess.run(['clang++','-std=c++20','-O3',str(here/'midpoint_scan.cpp'),'-I'+pa.get_include(),str(sorted(lib.glob('libarrow.[0-9]*.dylib'))[0]),str(sorted(lib.glob('libparquet.[0-9]*.dylib'))[0]),'-Wl,-rpath,'+str(lib),'-o',str(binary)],check=True,capture_output=True,text=True)
    return binary.resolve()


def validate_hour(values,parent,clock_bad=False):
    if len(values)!=3600 or len(parent)!=3600:raise ValueError('Incomplete midpoint hour')
    if clock_bad:values['valid']=0
    for key in ['time_ns','receipt_ns','event_ns','sequence','age_ns','valid']:
        if not np.array_equal(values[key],parent[key]):raise ValueError('Midpoint replay differs from parent '+key)
    good=values['valid'].astype(bool)
    if not np.isfinite(values['mid']).all() or (values['mid'][good]<=0).any():raise ValueError('Invalid midpoint')
    return values


def window_features(midpoints,anchor):
    m=np.asarray(midpoints,float)
    if m.shape[-1]!=60 or not np.isfinite(m).all() or (m<=0).any() or not np.isfinite(anchor) or anchor<=0:raise ValueError('Invalid midpoint window or candle anchor')
    offset=(m/anchor-1)*10000;change=np.concatenate([np.zeros_like(m[...,:1]),np.diff(np.log(m),axis=-1)*10000],axis=-1)
    return np.stack([offset,change],-1).astype(np.float32)


def prepare(output,hours):
    output.mkdir(parents=True,exist_ok=False);began=time.time();archive=Path('data/btc-perp/cryptohftdata-monthly');audit=Path('data/btc-perp/validation-v2-20261102');book=Path('data/btc-perp/pilot-features-202610/book-seconds.bin')
    expected=json.loads((book.parent/'book-extraction.json').read_text())['sha256']
    if file_hash(book)!=expected:raise ValueError('Changed parent book features')
    manifest=archive/'manifest.json';records=sorted([r for r in json.loads(manifest.read_text()) if '/2026-10-' in r['remote_file'] and '_orderbook.' in r['remote_file']],key=lambda r:r['remote_file'])
    if len(records)!=744 or not 1<=hours<=744:raise ValueError('Invalid October inventory or hour count')
    here=Path(__file__).parent;protocol={'hours':hours,'full_october':hours==744,'parent_book_sha256':expected,'archive_manifest_sha256':file_hash(manifest),'sources':{n:file_hash(here/n) for n in ['midpoint.py','midpoint_scan.cpp','archive_scan.cpp']},'preserve_existing_exclusions':True,'feature_contract':'same receipt-grid metadata and validity as parent; midpoint adds absolute location, no hidden orders or future messages'};save(output/'protocol.json',protocol)
    binary=compile_midpoint(output);parent=np.memmap(book,dtype=feature_dtype('book'),mode='r');process=subprocess.Popen([str(binary)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True);temporary=output/'hour.bin';target=output/'midpoints.part';ledger=[]
    try:
        with target.open('wb') as stream:
            for i,record in enumerate(records[:hours]):
                path=raw_path(archive,record)
                if file_hash(path)!=record['sha256']:raise ValueError('Changed raw archive')
                key=record['remote_file'].split('/');quality=json.loads((audit/'hours'/key[1]/key[2]/(key[3]+'.quality.json')).read_text())
                if not quality.get('ok') or quality['manifest_sha256']!=record['sha256']:raise ValueError('Unvalidated raw hour')
                at=hour_ns(record['remote_file']);start=(at-START*10**6)//10**9
                with decoded(path,output) as plain:
                    process.stdin.write(f'{at}\t{plain.resolve()}\t{temporary.resolve()}\n');process.stdin.flush();line=process.stdout.readline()
                    if not line:raise ValueError('Midpoint scanner stopped')
                    result=json.loads(line)
                if not result.get('ok') or result['counts']['rows']!=record['rows']:raise ValueError('Replay row count differs')
                values=np.fromfile(temporary,dtype=DTYPE);bad=any(quality['counts'].get(k,0) for k in HARD_CLOCK+('backward_receipt_rows',));validate_hour(values,parent[start:start+3600],bad);values.tofile(stream);temporary.unlink();ledger.append({'hour':i,'source_sha256':record['sha256'],'valid_seconds':int(values['valid'].sum()),'parent_metadata_equal':True})
                save(output/'status.json',{'state':'extracting','hours_done':i+1,'hours_total':hours,'elapsed_seconds':time.time()-began});print(i+1,hours,flush=True)
        process.stdin.close();process.wait(timeout=30)
        if process.returncode:raise ValueError('Scanner exited unsuccessfully')
        target.replace(output/'midpoints.bin');save(output/'report.json',{'state':'complete','hours':hours,'full_october':hours==744,'seconds':hours*3600,'valid_seconds':sum(v['valid_seconds'] for v in ledger),'all_parent_metadata_equal':True,'sha256':file_hash(output/'midpoints.bin'),'elapsed_seconds':time.time()-began,'hours_ledger':ledger,'training_started':False});save(output/'status.json',{'state':'complete','hours_done':hours,'elapsed_seconds':time.time()-began})
    except Exception as exc:
        save(output/'status.json',{'state':'failed','reason':str(exc),'hours_done':len(ledger)});raise
    finally:
        if process.poll() is None:process.terminate();process.wait(timeout=30)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--hours',type=int,default=2);a=p.parse_args();prepare(a.output,a.hours)
