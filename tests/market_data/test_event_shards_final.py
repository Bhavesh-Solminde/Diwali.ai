from datetime import datetime,timezone
import pytest
from research.market_data import event_shards_final


def test_final_replay_guard_requires_release_and_one_exact_interval(monkeypatch):
    calls=[]
    monkeypatch.setattr(event_shards_final,'check_release',lambda path:calls.append(path))
    def at(day):return datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
    event_shards_final.final_interval(at('2026-09-14'),at('2026-09-30'),'verified-release')
    assert calls==['verified-release']
    with pytest.raises(ValueError,match='Only the frozen'):
        event_shards_final.final_interval(at('2026-09-14'),at('2026-10-01'),'verified-release')


def test_missing_or_invalid_release_cannot_prepare_final_data(monkeypatch):
    def denied(path):raise ValueError('release not verified')
    monkeypatch.setattr(event_shards_final,'check_release',denied)
    with pytest.raises(ValueError,match='release not verified'):
        event_shards_final.final_interval(datetime(2026,9,14,tzinfo=timezone.utc),datetime(2026,9,30,tzinfo=timezone.utc),'missing')
