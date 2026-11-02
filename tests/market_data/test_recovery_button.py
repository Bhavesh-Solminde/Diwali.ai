from decimal import Decimal
import hashlib
import json
import numpy as np
import pytest
from research.market_data.recover_candles import aggregate,agrees,market_execution
from research.market_data.button_dataset import context_end,select
from research.market_data.build_pilot import START,WARMUP,feature_dtype
from research.market_data.frozen_inputs import FrozenInputs,target_after,ready_before_target,write_snapshot,MINUTE


def test_official_reconstruction_and_duplicate_guard():
    rows=[['2','102','2','204','1001','false'],['1','100','1','100','1000','true']]
    a=aggregate(rows)
    assert a==dict(open=Decimal(100),high=Decimal(102),low=Decimal(100),close=Decimal(102),volume=Decimal(3),quote_volume=Decimal(304),count=2)
    assert agrees(a,a)
    with pytest.raises(ValueError):aggregate(rows+rows[:1])
    assert not market_execution({'order_type':'INSURANCE_FUND','price':'100','quantity':'1'})
    assert not market_execution({'order_type':'ADL','price':'100','quantity':'1'})
    assert market_execution({'order_type':'MARKET','price':'100','quantity':'1'})


def test_button_context_and_target_cutoffs():
    target=START+120000; snapshot=target-60000+15000
    assert context_end(snapshot,1000)==target-60000
    assert context_end(target-60000,1000)==target-120000
    assert context_end(snapshot,15000)==target-120000  # Equality is not strictly before freeze.
    ci=(context_end(snapshot,1000)-WARMUP)//60000
    v=np.ones(ci+1,bool)
    book=np.zeros(200,dtype=feature_dtype('book'));trades=np.zeros(200,dtype=feature_dtype('trades'))
    for r in (book,trades):r['valid']=1;r['receipt_ns']=START*10**6+np.arange(200)*10**9;r['event_ns']=r['receipt_ns']
    a,reject=select([target],15,1000,v,book,trades)
    assert a.tolist()==[[snapshot,target,ci,15,75]] and not reject
    trades['receipt_ns'][74]=snapshot*10**6
    assert select([target],15,1000,v,book,trades)[1]=={'future_book_or_trade_message':1}
    v[ci-1440]=False
    assert select([target],15,1000,v,book,trades)[1]=={'unrecovered_candle_context':1}


def freeze_fixture():
    at=START*10**6+90*10**9;mono=10**12
    s=FrozenInputs();s.market_since=at-70*10**9;s.gap_since=s.market_since
    s.book={'available_ns':at-100_000_000,'source_receipt_ns':at-200_000_000,
        'exchange_event_ms':(at-300_000_000)//10**6,'connection':1,'snapshot_id':1,
        'levels':{'top20_within_snapshot_bounds':True,'bids':[['99','1']]*20,'asks':[['101','1']]*20,'update_id':2}}
    import copy
    for sec in range(-61,0):
        old=copy.deepcopy(s.book);old['available_ns']=at//10**9*10**9+sec*10**9
        old['source_receipt_ns']=old['available_ns']-1000;old['exchange_event_ms']=(old['available_ns']-1000000)//10**6
        s.book_history.append(old)
    last=(at//MINUTE-1)*60000
    for i in range(1440):
        k=last-i*60000;s.candles[k]={'open_ms':k,'close_ms':k+59999,'values':['100','102','99','101','1','100',1],
            'available_ns':at-10**9,'source':'test_received'}
    return s,at,mono


def test_frozen_requests_are_immutable_and_deadline_explicit(tmp_path):
    s,at,mono=freeze_fixture();snapshot=s.freeze(at,mono)
    assert snapshot['target_start_ns']==target_after(at) and target_after(at)>at
    assert target_after(START*10**6)==START*10**6+MINUTE
    assert ready_before_target(at,snapshot['target_start_ns'])
    assert not ready_before_target(snapshot['target_start_ns'],snapshot['target_start_ns'])
    saved=write_snapshot(tmp_path,snapshot);p=tmp_path/saved['snapshot_file'];before=p.read_bytes()
    s.book['levels']['bids'][0][0]='1'
    assert snapshot['book']['levels']['bids'][0][0]=='99'
    assert hashlib.sha256(before).hexdigest()==saved['sha256']
    with pytest.raises(FileExistsError):write_snapshot(tmp_path,snapshot)
    assert p.read_bytes()==before


def test_live_freeze_rejects_future_clock_gap_and_incomplete_history():
    s,at,mono=freeze_fixture();s.book['available_ns']=at
    with pytest.raises(ValueError,match='not_before'):s.freeze(at,mono)
    s,at,mono=freeze_fixture();s.clock_fault=True
    with pytest.raises(ValueError,match='clock_step'):s.freeze(at,mono)
    s,at,mono=freeze_fixture();s.gap_since=at-10**9
    with pytest.raises(ValueError,match='recent_trade_gap'):s.freeze(at,mono)
    s,at,mono=freeze_fixture();del s.candles[min(s.candles)]
    with pytest.raises(ValueError,match='1440'):s.freeze(at,mono)


def test_rest_candle_finalization_uses_server_lower_bound_not_fast_local_clock():
    s=FrozenInputs();at=START*10**6+60*10**9
    def row(kind,payload,**extra):return dict(kind=kind,payload=payload,receipt_utc_ns=at,receipt_monotonic_ns=1000,**extra)
    s.ingest(row('rest',{'serverTime':START+59900},path='/fapi/v1/time'))
    k=[START,'100','102','99','101','1',START+59999,'100',1]
    s.ingest(row('rest',[k],path='/fapi/v1/klines?symbol=BTCUSDT'))
    assert not s.candles  # Mac thinks minute ended, but server lower bound does not.
    s.ingest(row('rest',{'serverTime':START+60001},path='/fapi/v1/time'))
    s.ingest(row('rest',[k],path='/fapi/v1/klines?symbol=BTCUSDT'))
    assert s.candles[START]['available_ns']==at


def test_native_trade_features_include_trade_time_in_future_guard(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq
    import subprocess
    from research.market_data.build_pilot import compile_features
    hour=START*10**6
    schema=pa.schema([(k,t) for k,t in [('received_time',pa.int64()),('event_time',pa.int64()),
        ('symbol',pa.string()),('trade_id',pa.int64()),('price',pa.string()),('quantity',pa.string()),
        ('trade_time',pa.int64()),('is_buyer_maker',pa.bool_()),('order_type',pa.string())]])
    row=dict(received_time=hour+1_100_000_000,event_time=START+1000,symbol='BTCUSDT',trade_id=1,
             price='100',quantity='1',trade_time=START+5000,is_buyer_maker=False,order_type='MARKET')
    source=tmp_path/'future.parquet';pq.write_table(pa.Table.from_pylist([row],schema=schema),source)
    binary=compile_features(tmp_path);dest=tmp_path/'trade.bin'
    subprocess.run([str(binary),'trades'],input=f'{hour}\t{source}\t{dest}\n',text=True,capture_output=True,check=True)
    seconds=np.fromfile(dest,dtype=feature_dtype('trades'))
    assert seconds[1]['event_ns']==hour+5_000_000_000


def test_prediction_result_cannot_be_backdated_or_claim_an_already_started_target():
    from research.market_data.frozen_inputs import prediction_record
    s,at,mono=freeze_fixture();request=s.freeze(at,mono)
    result=prediction_record(request,{'close':101},'test-only',at+10**9,mono+10**9)
    assert result['calculation_seconds']==1
    with pytest.raises(ValueError,match='precedes'):
        prediction_record(request,{},'test-only',at-1,mono+1)
    with pytest.raises(ValueError,match='at_or_after'):
        prediction_record(request,{},'test-only',request['target_start_ns'],mono+60*10**9)
