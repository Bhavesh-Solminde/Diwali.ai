"""Resumable hourly lossless event storage. Reserved final dates are denied."""
import argparse,json,subprocess,hashlib,shutil,time
from datetime import datetime,timedelta,timezone
from pathlib import Path
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from .event_replay import DTYPE as BOOK,compile_events,validate_events
from .trade_events import DTYPE as TRADE,compile_trades
from .validate_archive import file_hash,save,raw_path,decoded,HARD_CLOCK


def allowed(start,stop):
    if start.tzinfo is None or stop.tzinfo is None or start>=stop:raise ValueError('Invalid UTC interval')
    if start<datetime(2026,7,31,tzinfo=timezone.utc) or stop>datetime(2026,9,15,tzinfo=timezone.utc):raise ValueError('Outside development preparation range; final period denied')


def initializing_hour(start,quality_root,maximum_hours=7*24):
    for offset in range(1,maximum_hours+1):
        stamp=start-timedelta(hours=offset);path=quality_root/f'{stamp:%Y-%m-%d}'/f'{stamp:%H}'/'BTCUSDT_orderbook.parquet.quality.json'
        if not path.exists():continue
        q=json.loads(path.read_text())
        if q.get('ok') and q.get('valid_end') and q['counts'].get('snapshots',0)>0:return stamp
    raise ValueError('No initializing snapshot in bounded warmup search')


def store_events(path,rows):
    columns={}
    for name in rows.dtype.names:
        values=np.ascontiguousarray(rows[name])
        if name=='levels':columns[name]=pa.FixedSizeListArray.from_arrays(pa.array(values.reshape(-1),type=pa.int64()),80)
        else:columns[name]=pa.array(values,type=pa.int64())
    temp=path.with_suffix('.part');pq.write_table(pa.table(columns),temp,compression='zstd',compression_level=3,row_group_size=65536,write_page_checksum=True)
    actual=read_events(temp,rows.dtype)
    if actual.tobytes()!=rows.tobytes():raise ValueError('Lossless storage roundtrip failed')
    temp.replace(path)


def read_events(path,dtype):
    table=pq.read_table(path,page_checksum_verification=True);result=np.empty(len(table),dtype=dtype)
    if table.column_names!=list(dtype.names):raise ValueError('Changed stored schema')
    for name in dtype.names:
        column=table[name].combine_chunks()
        result[name]=column.values.to_numpy(zero_copy_only=False).reshape(-1,20,4) if name=='levels' else column.to_numpy(zero_copy_only=False)
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--start',required=True);p.add_argument('--days',type=int,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--resume',action='store_true');a=p.parse_args()
    start=datetime.fromisoformat(a.start).replace(tzinfo=timezone.utc);stop=start+timedelta(days=a.days);allowed(start,stop)
    out=a.output;out.mkdir(parents=True,exist_ok=a.resume);scratch=out/'scratch';scratch.mkdir(exist_ok=True);began=time.time();root=Path('data/btc-perp/cryptohftdata-monthly');manifest=root/'manifest.json';records={r['remote_file']:r for r in json.loads(manifest.read_text())}
    warm_start=initializing_hour(start,Path('data/btc-perp/validation-v2-20261102/hours'))
    names=['event_shards.py','event_replay.py','event_scan.cpp','trade_events.py','trade_event_scan.cpp','feature_scan.cpp','archive_scan.cpp']
    protocol={'start':start.isoformat(),'stop_exclusive':stop.isoformat(),'warmup_start':warm_start.isoformat(),'warmup_policy':'Latest preceding quality-verified snapshot-bearing hour within7days; replay all following hours continuously','source_hashes':{n:file_hash(Path(__file__).with_name(n)) for n in names},'archive_manifest_sha256':file_hash(manifest),'all_rows_retained':True,'lossless':True,'final_period_denied':True,'training_started':False}
    if (out/'protocol.json').exists():
        if json.loads((out/'protocol.json').read_text())!=protocol:raise ValueError('Resume contract differs')
    else:save(out/'protocol.json',protocol)
    # Recompile only in a new private build folder; interrupted builds stay intact.
    build=out/('build-'+str(time.time_ns()));build.mkdir();bb=build/'book';tt=build/'trades';bb.mkdir();tt.mkdir();binaries={'orderbook':compile_events(bb),'trades':compile_trades(tt)}
    processes={k:subprocess.Popen([str(v)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for k,v in binaries.items()};ledgers=[];compressed=uncompressed=0
    hours=[warm_start+timedelta(hours=i) for i in range(int((stop-warm_start).total_seconds()//3600))]
    try:
        for number,stamp in enumerate(hours):
            if shutil.disk_usage(out).free<30*1024**3:raise ValueError('30GiB disk reserve reached')
            name=f'{stamp:%Y-%m-%dT%H}';h=int(stamp.timestamp())*10**9;is_warm=stamp<start;hourdir=out/name;hourdir.mkdir(exist_ok=True);items={};existing=None
            if (hourdir/'manifest.json').exists():
                existing=json.loads((hourdir/'manifest.json').read_text())
                for part in existing['files'].values():
                    if file_hash(hourdir/part['file'])!=part['sha256']:raise ValueError('Changed completed shard')
            for kind,dtype in [('orderbook',BOOK),('trades',TRADE)]:
                key=f'binance_futures/{stamp:%Y-%m-%d}/{stamp:%H}/BTCUSDT_{kind}.parquet';record=records[key];path=raw_path(root,record)
                if file_hash(path)!=record['sha256']:raise ValueError('Changed raw source')
                qualitypath=Path('data/btc-perp/validation-v2-20261102/hours')/f'{stamp:%Y-%m-%d}'/f'{stamp:%H}'/f'BTCUSDT_{kind}.parquet.quality.json';quality=json.loads(qualitypath.read_text())
                if not quality.get('ok') or quality['manifest_sha256']!=record['sha256']:raise ValueError('Unvalidated source hour')
                seconds=scratch/(kind+'-seconds.bin');events=scratch/(kind+'-events.bin');process=processes[kind]
                with decoded(path,scratch) as plain:
                    process.stdin.write(f'{h}\t{plain.resolve()}\t{seconds.resolve()}\t{events.resolve()}\n');process.stdin.flush();line=process.stdout.readline()
                if not line:raise ValueError('Replay process stopped')
                audit=json.loads(line);save(hourdir/(kind+'-audit.json'),audit)
                rows=np.memmap(events,dtype=dtype,mode='r')
                if not audit.get('ok') or audit['counts']['rows']!=record['rows']:raise ValueError('Replay row total differs')
                if kind=='orderbook':validate_events(rows,audit['counts'])
                elif len(rows)!=record['rows']:raise ValueError('Trade row total differs')
                binary_hash=file_hash(events);size=events.stat().st_size;target=hourdir/(kind+'-events.parquet')
                if existing:
                    if binary_hash!=existing['files'][kind]['decoded_binary_sha256']:raise ValueError('Resume replay state differs')
                else:store_events(target,rows)
                compressed+=target.stat().st_size;uncompressed+=size
                clock_bad=any(quality['counts'].get(x,0) for x in HARD_CLOCK+('backward_receipt_rows',))
                items[kind]={'file':target.name,'sha256':file_hash(target),'decoded_binary_sha256':binary_hash,'source_sha256':record['sha256'],'quality_sha256':file_hash(qualitypath),'rows':len(rows),'uncompressed_bytes':size,'stored_bytes':target.stat().st_size,'clock_bad':clock_bad}
                del rows;events.unlink();seconds.unlink()
            entry={'UTC_hour':name,'warmup_only':is_warm,'files':items,'model_input_ready':False};save(hourdir/'manifest.json',entry);ledgers.append(entry)
            save(out/'status.json',{'state':'extracting','hours_done':number+1,'hours_total':len(hours),'elapsed_seconds':time.time()-began,'compressed_bytes':compressed,'uncompressed_bytes':uncompressed});print(name,number+1,len(hours),flush=True)
        save(out/'report.json',{'state':'complete','protocol':protocol,'hours_including_warmup':len(ledgers),'hours':ledgers,'elapsed_seconds':time.time()-began,'compressed_bytes':compressed,'uncompressed_bytes':uncompressed,'training_ready':False,'limitations':['Raw event shards only; context/target cohorts and normalization not yet fitted.','Clock-bad records remain marked, not silently used.','Provider original timing is unproven.','Warmup source is replayed for continuity, not a training target.']});save(out/'status.json',{'state':'complete','hours_done':len(ledgers),'hours_total':len(hours),'compressed_bytes':compressed,'uncompressed_bytes':uncompressed})
    except Exception as error:
        save(out/'status.json',{'state':'failed','hours_done':len(ledgers),'reason':str(error),'resume_allowed':True});raise
    finally:
        for process in processes.values():
            if process.poll() is None:process.stdin.close();process.wait(timeout=30)


if __name__=='__main__':main()
