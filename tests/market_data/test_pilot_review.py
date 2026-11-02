import numpy as np
from research.market_data.review_pilot import context_failures, metrics, baseline_predictions
from research.market_data.build_pilot import feature_dtype


def test_bad_minute_expires_after_full_context_window():
    valid=np.ones(1500,bool);valid[10]=False
    assert context_failures(valid,1450).tolist()==[10]
    assert context_failures(valid,1451).tolist()==[]


def test_direction_score_counts_flat_predictions_separately():
    actual=np.array([[0,2,-1,1],[0,1,-2,-1],[0,0,0,0.]])
    result=metrics(np.zeros_like(actual),actual)
    assert result['close_direction_accuracy']==1/3
    assert result['balanced_direction_accuracy']==1/3


def test_rule_forecasts_cannot_read_target_candle():
    raw=np.array([[100,102,98,101,1,1,1],[101,104,100,103,1,1,1],[103,200,1,150,1,1,1.]])
    indices=np.array([[0,2,0,60]])
    book=np.zeros(60,dtype=feature_dtype('book'))
    trades=np.zeros(60,dtype=feature_dtype('trades'))
    first=baseline_predictions(raw,indices,book,trades,1)
    raw[2]=999
    second=baseline_predictions(raw,indices,book,trades,1)
    for k in first:
        np.testing.assert_equal(first[k],second[k])
        assert first[k][0,1]>=max(first[k][0,0],first[k][0,3])
        assert first[k][0,2]<=min(first[k][0,0],first[k][0,3])
