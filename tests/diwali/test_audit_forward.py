import numpy as np
import pytest
import json
import hashlib

from research.diwali.audit_forward import verify_outcome,check
from research.diwali.fan import range_labels,direction


def evidence():
    start=1_800_000_000_000;ref=100.;close=100.01;p=np.ones((15,26))/26
    record={'target_start_ns':start*10**6,'prediction':{'reference':ref,'bin_probabilities':p.tolist()}}
    ret=(close/ref-1)*10000;b=int(range_labels(ret));candles={start:{'available_ns':(start+61000)*10**6,'close_ms':start+59999,'source':'received','values':[100,101,99,close]}}
    outcome={'horizon':1,'target_start_ms':start,'scored_utc_ns':(start+62000)*10**6,'actual_available_ns':candles[start]['available_ns'],
        'actual_source':'received','actual_close':close,'actual_return_bp':ret,'actual_bin':b,'actual_class':1,'bin_log_loss':float(-np.log(p[0,b])),
        'direction_log_loss':float(-np.log(direction(p[0])[1])),'direction_correct':False}
    return outcome,record,candles


def test_forward_audit_accepts_exact_source_and_rejects_changed_label():
    outcome,record,candles=evidence();verify_outcome(outcome,record,candles)
    outcome['actual_class']=2
    with pytest.raises(ValueError,match='Changed actual label'):verify_outcome(outcome,record,candles)


def test_forward_audit_rejects_labels_scored_before_receipt():
    outcome,record,candles=evidence();outcome['scored_utc_ns']=outcome['actual_available_ns']-1
    with pytest.raises(ValueError,match='before actual candle received'):verify_outcome(outcome,record,candles)


def test_completed_capture_manifest_detects_extra_raw_bytes(tmp_path,monkeypatch):
    monkeypatch.setattr('research.diwali.audit_forward.Predictor',lambda run:None)
    raw=tmp_path/'events-test.jsonl';raw.write_text(json.dumps({'kind':'noop','payload':{},'receipt_utc_ns':1,'receipt_monotonic_ns':1})+'\n')
    (tmp_path/'manifest.json').write_text(json.dumps({'raw_sha256':{raw.name:hashlib.sha256(raw.read_bytes()).hexdigest()}}))
    assert check(tmp_path,tmp_path)['completed_raw_manifest_verified']
    with raw.open('a') as f:f.write('\n')
    with pytest.raises(ValueError,match='raw manifest mismatch'):check(tmp_path,tmp_path)
