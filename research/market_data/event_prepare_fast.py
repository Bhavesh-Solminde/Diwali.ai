"""Use the common verified preparer with explicit vectorized implementation provenance."""
import json
from pathlib import Path
import sys
from . import event_prepare_joined as reference
from .event_features_fast import build
from .validate_archive import file_hash,save


def main():
    # Replace only numerical feature construction. Provenance/window checks and
    # atomic output paths are the same. Never modify an active preparer's source.
    reference.build=build
    reference.main()
    args=sys.argv
    out=Path(args[args.index('--output')+1])
    report=json.loads((out/'report.json').read_text())
    report['feature_implementation']='event_features_fast.build; vectorized reference semantics'
    report['code_hashes'].update({p.name:file_hash(p) for p in [Path(__file__),Path(__file__).with_name('event_features_fast.py')]})
    save(out/'report.json',report)


if __name__=='__main__':main()
