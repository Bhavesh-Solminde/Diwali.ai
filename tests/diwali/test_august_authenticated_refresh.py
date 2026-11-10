from datetime import datetime

from research.diwali.august_authenticated_refresh import recovery_hours


def test_recovery_hours_include_previous_day_without_duplicates_or_empty_strata():
    sample = {'strata': [
        {'stratum': '2026-08-01T00', 'cutoff_ns': 1},
        {'stratum': '2026-08-01T01', 'cutoff_ns': 2},
        {'stratum': '2026-08-08T06', 'cutoff_ns': None},
        {'stratum': '2026-08-15T00', 'cutoff_ns': 3},
    ]}
    hours = recovery_hours(sample)
    assert hours == [
        [datetime(2026, 7, 31, 23), datetime(2026, 8, 1, 0), datetime(2026, 8, 1, 1)],
        [datetime(2026, 8, 14, 23), datetime(2026, 8, 15, 0)],
    ]
