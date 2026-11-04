import numpy as np
import pytest
from research.market_data.candle_tape import CandleTape,MINUTE,SECOND,released
from research.market_data.trade_events import DTYPE


def trade(receipt,execution,ident,price):
    r=np.zeros(1,dtype=DTYPE);r['receipt_ns']=receipt;r['event_ns']=execution;r['trade_ns']=execution;r['trade_id']=ident;r['price']=int(price*1e8);r['quantity']=100000000;return r[0]


def test_late_execution_does_not_rewrite_an_already_frozen_snapshot():
    tape=CandleTape();cut=2*MINUTE+15*SECOND
    tape.ingest(trade(MINUTE+SECOND,MINUTE+SECOND,1,100),MINUTE+SECOND)
    tape.ingest(trade(cut-SECOND,cut-SECOND,2,101),cut-SECOND)
    original=tape.snapshot(cut,history=1);before=original['candles'].copy()
    # An old execution arriving after this freeze may update later snapshots only.
    tape.ingest(trade(cut+SECOND,MINUTE+2*SECOND,3,90),cut+SECOND)
    np.testing.assert_array_equal(original['candles'],before)
    assert tape.minutes[MINUTE]['l']==9000000000 and original['last_candle_close']==100
    with pytest.raises(ValueError,match='after input freeze'):tape.snapshot(cut,history=1)


def test_completed_second_reference_future_block_and_trade_gap():
    rows=np.array([trade(10,100,1,100),trade(20,20,2,101)],dtype=DTYPE)
    np.testing.assert_array_equal(released(rows),[100,100])
    t=CandleTape();t.ingest(trade(MINUTE+SECOND,MINUTE+SECOND,1,100),MINUTE+SECOND)
    t.ingest(trade(2*MINUTE+14*SECOND,2*MINUTE+14*SECOND,3,101),2*MINUTE+14*SECOND)
    assert t.minutes[2*MINUTE]['bad']
    assert t.minutes[MINUTE]['bad'] # missing IDs can span the preceding minute too


def test_missing_context_is_masked_not_invented_or_silently_accepted():
    t=CandleTape()
    for i in range(101):t.ingest(trade(i*MINUTE+SECOND,i*MINUTE+SECOND,i+1,100+i/100),i*MINUTE+SECOND)
    cutoff=101*MINUTE+15*SECOND;t.ingest(trade(cutoff-SECOND,cutoff-SECOND,102,101),cutoff-SECOND)
    t.minutes[50*MINUTE]['bad']=True
    with pytest.raises(ValueError,match='Invalid completed'):t.snapshot(cutoff,history=100)
    s=t.snapshot(cutoff,history=100,mask_context=True)
    assert s['candle_mask'].sum()==99 and not s['candles'][49].any()
    t.minutes[51*MINUTE]['bad']=True
    with pytest.raises(ValueError,match='99percent'):t.snapshot(cutoff,history=100,mask_context=True)
