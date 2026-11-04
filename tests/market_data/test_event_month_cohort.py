import pytest
from research.market_data.event_month_cohort import intersects,period_bounds


def test_clock_exclusions_are_half_open_and_cannot_overlap_context_or_target():
    bad=[(100,200)]
    assert not intersects(0,100,bad)
    assert not intersects(200,300,bad)
    assert intersects(99,101,bad)
    assert intersects(199,201,bad)
    assert intersects(50,250,bad)


def test_only_frozen_nonfinal_periods_can_be_constructed():
    assert period_bounds('august')[2]==['2026-08-01','2026-08-31']
    assert period_bounds('september-selection')[1]=='2026-09-15T00'
    with pytest.raises(ValueError,match='reserved final preparation denied'):period_bounds('final')
