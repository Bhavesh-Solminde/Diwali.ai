import pytest
from research.diwali.audit_candidate import verify_commit


def test_candidate_identity_and_pre_target_chronology_are_bound():
    request={'snapshot_utc_ns':100_000_000_000,'snapshot_monotonic_ns':1000,'target_start_ns':120_000_000_000,'target_end_ns':180_000_000_000}
    record={'model_id':'diwali1.1',**request,'ready_utc_ns':100_001_000_000,'ready_monotonic_ns':1001000};row={'receipt_utc_ns':100_002_000_000,'receipt_monotonic_ns':2001000}
    verify_commit(request,record,row,request['snapshot_utc_ns'],'diwali1.1')
    with pytest.raises(ValueError,match='Wrong model'):verify_commit(request,record,row,0,'diwali0.9')
    with pytest.raises(ValueError,match='predates follower'):verify_commit(request,record,row,request['snapshot_utc_ns']+1,'diwali1.1')
    row['receipt_utc_ns']=request['target_start_ns']
    with pytest.raises(ValueError,match='before target'):verify_commit(request,record,row,0,'diwali1.1')
