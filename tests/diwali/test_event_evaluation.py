from datetime import datetime, timezone
import hashlib
import json
import numpy as np
import pytest
from research.diwali.event_evaluation import eligible_origins, horizon_seconds, MINUTE


def ns(stamp):
    return int(datetime.fromisoformat(stamp).replace(tzinfo=timezone.utc).timestamp())*10**9


def test_full15_close_targets_are_purged_at_every_partition_boundary():
    cutoffs=np.array([ns('2026-08-10T23:43:15'), ns('2026-08-10T23:44:15'), ns('2026-08-10T23:45:15'), ns('2026-08-11T00:00:15')])
    starts=(cutoffs//MINUTE+1)*MINUTE
    keep, counts=eligible_origins(cutoffs, starts, 'A','fit')
    assert keep.tolist()==[True,True,False,False]
    assert counts['purged_target_overlap']==1 and counts['outside_partition']==1


def test_actual_button_to_target_delays_are_explicit():
    at=ns('2026-08-01T10:00:15');target=ns('2026-08-01T10:01:00')
    delays=horizon_seconds(at,target)
    assert delays[0]==105 and delays[-1]==945
    with pytest.raises(ValueError,match='timing contract'):
        horizon_seconds(at,at+60*10**9)


def test_reserved_final_score_is_denied_without_completed_artifact_freeze(tmp_path):
    at=np.array([ns('2026-09-16T12:00:15')]);starts=(at//MINUTE+1)*MINUTE
    with pytest.raises(ValueError,match='deliberately released'):
        eligible_origins(at,starts,'final','score')
    p=tmp_path/'release.json';p.write_text(json.dumps({'stage':'final_evaluation','final_period':['2026-09-15','2026-09-29'],'artifacts':{}}))
    with pytest.raises(ValueError,match='requires frozen'):
        eligible_origins(at,starts,'final','score',final_release=p)


def test_release_binds_selected_artifacts_and_rejects_later_changes(tmp_path):
    names=['run_protocol','selected_model','fit_transforms','calibration','development_selection']
    files={}
    for name in names+['source.py']:
        p=tmp_path/name;p.write_text(name)
        files[name]={'path':name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    record={'stage':'final_evaluation','final_period':['2026-09-15','2026-09-29'],
            'artifacts':{n:files[n] for n in names},'source_hashes':{'source.py':files['source.py']['sha256']}}
    release=tmp_path/'release.json';release.write_text(json.dumps(record))
    at=np.array([ns('2026-09-16T12:00:15')]);starts=(at//MINUTE+1)*MINUTE
    assert eligible_origins(at,starts,'final','score',final_release=release)[0].tolist()==[True]
    (tmp_path/'selected_model').write_text('modified after selection')
    with pytest.raises(ValueError,match='artifact has changed'):
        eligible_origins(at,starts,'final','score',final_release=release)
