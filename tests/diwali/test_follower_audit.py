import hashlib
import json

import pytest

from research.diwali.audit_follower import read_prefix,verify_commit


def chronology():
    request={'snapshot_utc_ns':100_000_000_000,'snapshot_monotonic_ns':1000,'target_start_ns':120_000_000_000,'target_end_ns':180_000_000_000}
    record={'model_id':'diwali0.6',**request,'ready_utc_ns':100_001_000_000,'ready_monotonic_ns':1001000}
    row={'receipt_utc_ns':100_002_000_000,'receipt_monotonic_ns':2001000}
    return request,record,row


def test_real_commit_order_and_startup_are_required():
    request,record,row=chronology();verify_commit(request,record,row,request['snapshot_utc_ns'])
    with pytest.raises(ValueError,match='predates follower'):verify_commit(request,record,row,request['snapshot_utc_ns']+1)
    row['receipt_utc_ns']=request['target_start_ns']
    with pytest.raises(ValueError,match='before target'):verify_commit(request,record,row,0)


def test_utc_jump_cannot_disguise_invalid_prediction_timing():
    request,record,row=chronology();record['ready_utc_ns']+=1_000_000_000;row['receipt_utc_ns']+=1_000_000_000
    with pytest.raises(ValueError,match='Clock step'):verify_commit(request,record,row,0)


def test_stopped_journal_cannot_hide_an_incomplete_appended_tail(tmp_path):
    raw=tmp_path/'events-test.jsonl';raw.write_bytes(b'{"test":1}\n');(tmp_path/'manifest.json').write_text(json.dumps({'raw_sha256':{raw.name:hashlib.sha256(raw.read_bytes()).hexdigest()}}))
    assert read_prefix(tmp_path)[2]
    with raw.open('ab') as f:f.write(b'{"partial":')
    with pytest.raises(ValueError,match='manifest mismatch'):read_prefix(tmp_path)
