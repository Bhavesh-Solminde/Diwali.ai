"""Explicit artifact-authorized preparation of the fixed reserved interval.

Reuse the frozen lossless replayer. This wrapper replaces only its development
date guard, with one exact final interval and a verified final release.
"""
import argparse
import json
import sys
from datetime import datetime,timezone
from pathlib import Path

from . import event_shards
from .validate_archive import file_hash,save
from ..diwali.event_final_gate import check_release


def final_interval(start,stop,release):
    check_release(release)
    if start!=datetime(2026,9,14,tzinfo=timezone.utc) or stop!=datetime(2026,9,30,tzinfo=timezone.utc):raise ValueError('Only the frozen final preparation interval is allowed')


def main():
    p=argparse.ArgumentParser();p.add_argument('--release',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--resume',action='store_true');a=p.parse_args()
    check_release(a.release);authorization={'release_sha256':file_hash(a.release),'wrapper_sha256':file_hash(Path(__file__)),'original_replayer_sha256':file_hash(Path(event_shards.__file__)),
                                         'start':'2026-09-14','stop_exclusive':'2026-09-30','purpose':'Final quality/context preparation after all model artifacts frozen; no forecast performance scoring.'}
    sidecar=a.output.parent/(a.output.name+'.final-authorization.json');sidecar.parent.mkdir(parents=True,exist_ok=True)
    if sidecar.exists():
        if not a.resume or json.loads(sidecar.read_text())!=authorization:raise ValueError('Final preparation authorization differs')
    else:save(sidecar,authorization)
    original_args=sys.argv;original_guard=event_shards.allowed
    try:
        event_shards.allowed=lambda start,stop:final_interval(start,stop,a.release)
        sys.argv=[original_args[0],'--start','2026-09-14','--days','16','--output',str(a.output)]+(['--resume'] if a.resume else [])
        event_shards.main()
    finally:
        event_shards.allowed=original_guard;sys.argv=original_args


if __name__=='__main__':main()
