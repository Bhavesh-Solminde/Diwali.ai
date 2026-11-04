import pytest
from research.diwali.audit_anchored import verify_spacing


def test_fifteen_minute_target_windows_cannot_overlap():
    verify_spacing([1,900_000_000_001,1_800_000_000_001],900)
    for times in [[1,900_000_000_000],[1,1]]:
        with pytest.raises(ValueError,match='Overlapping'):verify_spacing(times,900)
    with pytest.raises(ValueError):verify_spacing([1,2],1)
