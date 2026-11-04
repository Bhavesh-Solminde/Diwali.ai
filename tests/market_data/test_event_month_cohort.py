from research.market_data.event_month_cohort import intersects


def test_clock_exclusions_are_half_open_and_cannot_overlap_context_or_target():
    bad=[(100,200)]
    assert not intersects(0,100,bad)
    assert not intersects(200,300,bad)
    assert intersects(99,101,bad)
    assert intersects(199,201,bad)
    assert intersects(50,250,bad)
