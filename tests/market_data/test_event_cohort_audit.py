from research.market_data.event_cohort_audit import combine_bar


def bar(first, last, price, bad=False, count=1):
    return {'first_id':first,'last_id':last,'open':str(price),'close':str(price),
            'high':str(price),'low':str(price),'count':count,'bad':bad,'volume':'0.1','quote_volume':'10.0'}


def test_native_aggregate_merge_uses_trade_ids_and_keeps_zero_count_gap_marker():
    a=combine_bar(bar(20,30,100),bar(10,15,99))
    assert a['open']=='99' and a['close']=='100' and a['count']==2
    assert a['high']=='100' and a['low']=='99' and a['volume']=='0.2'
    gap=bar(0,0,0,bad=True,count=0)
    assert combine_bar(a,gap)['bad']
    assert combine_bar(gap,a)['bad']
