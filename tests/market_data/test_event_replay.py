import json,subprocess
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from research.market_data.event_replay import DTYPE,compile_events,validate_events


def test_event_metadata_and_invalid_level_guards():
    rows=np.zeros(1,dtype=DTYPE);rows['receipt_ns']=10;rows['event_ns']=20;rows['available_ns']=20
    validate_events(rows,{'events':1})
    rows['available_ns']=10
    with pytest.raises(AssertionError):validate_events(rows,{'events':1})
    rows['available_ns']=20;rows['levels'][0,0,0]=1
    with pytest.raises(ValueError,match='Invalid states'):validate_events(rows,{'events':1})


def test_native_batches_atomic_future_clock_explicit_gap_rejected(tmp_path):
    at=1791158400000000000
    types={'received_time':pa.int64(),'event_time':pa.int64(),'transaction_time':pa.int64(),'symbol':pa.string(),'event_type':pa.string(),'first_update_id':pa.int64(),'final_update_id':pa.int64(),'prev_final_update_id':pa.int64(),'last_update_id':pa.int64(),'side':pa.string(),'price':pa.string(),'quantity':pa.string(),'order_count':pa.int64()}
    def row(side,price,qty,receipt,event,kind='update',first=101,final=101,previous=100):
        return dict(received_time=at+receipt,event_time=(at+event)//10**6,transaction_time=None,symbol='BTCUSDT',event_type=kind,first_update_id=first,final_update_id=final,prev_final_update_id=previous,last_update_id=100 if kind=='snapshot' else None,side=side,price=str(price),quantity=str(qty),order_count=None)
    rows=[row(side,price,1,100000000,100000000,'snapshot',100,100,99) for side,prices in [('bid',range(100,80,-1)),('ask',range(101,121))] for price in prices]
    # Two rows form ONE batch. Its exchange time is later than receipt time.
    rows.extend([row('bid',100,2,200000000,500000000),row('ask',101,3,200000000,500000000)])
    rows.append(row('bid',100,4,600000000,600000000,first=900,final=900,previous=899))
    path=tmp_path/'source.parquet';pq.write_table(pa.Table.from_pylist(rows,schema=pa.schema(types)),path,row_group_size=7)
    binary=compile_events(tmp_path);seconds=tmp_path/'seconds.bin';events=tmp_path/'events.bin'
    run=subprocess.run([str(binary)],input=f'{at}\t{path}\t{seconds}\t{events}\n',text=True,capture_output=True,check=True)
    audit=json.loads(run.stdout);a=np.fromfile(events,dtype=DTYPE);validate_events(a,audit['counts'])
    assert len(a)==3 and a['accepted_update'].tolist()==[0,1,0] and a['valid'].tolist()==[0,1,0]
    assert a[1]['available_ns']==at+500000000 and a[1]['receipt_ns']==at+200000000
    assert a[1]['levels'][0].tolist()==[10000000000,200000000,10100000000,300000000]
    assert audit['counts']['sequence_gaps']==1
