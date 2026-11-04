import hashlib,json
import numpy as np
import pytest
import research.diwali.compare_candidates as comparison


def setup_capture(root):
    root.mkdir();(root/'predictions').mkdir();(root/'outcomes').mkdir();(root/'follower-protocol.json').write_text(json.dumps({'source_capture':'one-native-receiver'}));rows=[];p=np.full((15,26),1/26)
    for key in ['complete','partial']:
        record={'input_sha256':key,'target_start_ns':1000,'prediction':{'reference':100.,'bin_probabilities':p.tolist(),'initial':p[0].tolist(),'transitions':np.broadcast_to(p[1:,None,:],(14,26,26)).tolist()}}
        raw=json.dumps(record).encode();file=key+'.json';(root/'predictions'/file).write_bytes(raw);rows.append({'kind':'forecast_saved','receipt_utc_ns':100,'payload':{'file':file,'sha256':hashlib.sha256(raw).hexdigest()}})
        for h in range(1,16 if key=='complete' else 15):(root/'outcomes'/f'{key}-{h}.json').write_text(json.dumps({'forecast_file':file,'horizon':h,'actual_bin':13,'scored_utc_ns':900}))
    data=b''.join(json.dumps(r).encode()+b'\n' for r in rows);file='events-test.jsonl';(root/file).write_bytes(data)
    return {'audited_through_utc_ns':999,'capture_complete':False,'follower_prefixes':{file:{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}}}


def test_comparison_never_scores_partial15_target_paths(tmp_path,monkeypatch):
    left=tmp_path/'left';right=tmp_path/'right';a=setup_capture(left);b=setup_capture(right);monkeypatch.setattr(comparison,'check',lambda root,run:a if root==left else b)
    r=comparison.compare(left,right);assert r['committed_counts']==[2,2] and r['complete_counts']==[1,1] and r['matched_complete_origins']==1
    assert r['models']['diwali1.1']['final_direction']['examples']==1


def test_changed_audited_forecast_is_rejected(tmp_path,monkeypatch):
    left=tmp_path/'left';right=tmp_path/'right';a=setup_capture(left);b=setup_capture(right);monkeypatch.setattr(comparison,'check',lambda root,run:a if root==left else b)
    (right/'predictions'/'complete.json').write_text('{}')
    with pytest.raises(ValueError,match='Changed prediction'):comparison.compare(left,right)
