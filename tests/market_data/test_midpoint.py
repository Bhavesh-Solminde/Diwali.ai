import json,subprocess
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from research.market_data.midpoint import DTYPE,compile_midpoint,validate_hour,window_features
from research.market_data.build_pilot import compile_features,feature_dtype
from research.diwali.prospective import book_features
from research.market_data.midpoint_windows import summaries


def test_old_book_shape_can_hide_absolute_price_movement():
    def levels(scale):return {'bids':[[scale*(100-i),1] for i in range(20)],'asks':[[scale*(101+i),1] for i in range(20)],'top20_within_snapshot_bounds':True}
    np.testing.assert_allclose(book_features(levels(1)),book_features(levels(2)),atol=1e-10)
    a=window_features(np.full(60,100.5),100);b=window_features(np.full(60,201.),100);assert not np.array_equal(a,b)


def test_window_has_no_future_midpoints_and_never_upgrades_exclusions():
    m=np.arange(100,160,dtype=float);x=window_features(m,100);np.testing.assert_allclose(x[0],[0,0]);assert x[-1,0]==5900
    with pytest.raises(ValueError):window_features(np.zeros(60),100)
    a=np.zeros(3600,dtype=DTYPE);b=np.zeros(3600,dtype=feature_dtype('book'));a['mid']=100;a['valid']=1
    validate_hour(a,b,clock_bad=True);assert not a['valid'].any()
    a['receipt_ns'][0]=1
    with pytest.raises(ValueError,match='receipt_ns'):validate_hour(a,b)


def test_summary_uses_latest_level_and_only_observed_window_change():
    m=np.arange(100,160,dtype=float);x=window_features(m,100);summary=summaries(x[None])[0]
    np.testing.assert_allclose(summary,[5900,np.log(159/100)*10000],rtol=1e-6)
    with pytest.raises(ValueError):summaries(np.zeros((60,2)))


def test_native_midpoint_replay_matches_original_metadata_and_cutoffs(tmp_path):
    hour=1793448000000000000
    schema=pa.schema([(n,t) for n,t in [('received_time',pa.int64()),('event_time',pa.int64()),('transaction_time',pa.int64()),('symbol',pa.string()),('event_type',pa.string()),('first_update_id',pa.int64()),('final_update_id',pa.int64()),('prev_final_update_id',pa.int64()),('last_update_id',pa.int64()),('side',pa.string()),('price',pa.string()),('quantity',pa.string()),('order_count',pa.int64())]])
    rows=[]
    for offset,seq,bid in [(100000000,100,100),(2200000000,200,150)]:
        for side,prices in [('bid',[bid-i for i in range(20)]),('ask',[bid+1+i for i in range(20)])]:
            for price in prices:rows.append(dict(received_time=hour+offset,event_time=(hour+offset)//1000000,transaction_time=None,symbol='BTCUSDT',event_type='snapshot',first_update_id=None,final_update_id=seq,prev_final_update_id=None,last_update_id=seq,side=side,price=str(price),quantity='1',order_count=None))
        update=hour+offset+100000000
        rows.append(dict(received_time=update,event_time=update//1000000,transaction_time=None,symbol='BTCUSDT',event_type='update',first_update_id=seq+1,final_update_id=seq+1,prev_final_update_id=seq,last_update_id=None,side='bid',price=str(bid),quantity='2',order_count=None))
    source=tmp_path/'source.parquet';pq.write_table(pa.Table.from_pylist(rows,schema=schema),source,row_group_size=7);mid=compile_midpoint(tmp_path);old=compile_features(tmp_path);a=tmp_path/'mid.bin';b=tmp_path/'old.bin'
    for command,path in [([str(mid)],a),([str(old),'book'],b)]:
        result=subprocess.run(command,input=f'{hour}\t{source}\t{path}\n',text=True,capture_output=True,check=True);assert json.loads(result.stdout)['ok']
    values=np.fromfile(a,dtype=DTYPE);parent=np.fromfile(b,dtype=feature_dtype('book'));validate_hour(values,parent)
    assert values['mid'][1]==100.5 and values['mid'][3]==150.5
    assert not values['valid'][5] and values['mid'][5]==0
