from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest

from research.diwali import comparison15_forward as forward


def test_late_write_has_no_commit_marker(tmp_path, monkeypatch):
    store = forward.Forward(tmp_path/'capture', SimpleNamespace())
    cutoff = 15*forward.SECOND
    target = forward.MINUTE
    store.release_hash = 'release'
    forecast = {name+suffix: np.full((15, 26), 1/26)
                for name in forward.MODELS for suffix in ('', '_raw')}
    forecast['half'] = np.full(15, .5)
    data = (np.zeros(1),)
    monkeypatch.setattr(store, 'check_input', lambda at, cutoff: (
        data, np.zeros(1), {'target_start_ns': target, 'reference': 100}, forecast))
    with (tmp_path/'journal').open('wb') as store.file:
        with patch.object(forward.time, 'time_ns', side_effect=[cutoff, target]):
            with pytest.raises(ValueError, match='finish writing'):
                store.issue(cutoff, cutoff)
    assert (store.root/'forecasts'/f'{cutoff}.json').exists()
    assert not (store.root/'committed'/f'{cutoff}.json').exists()
    assert not store.pending


def test_independent_targets_reject_a_mismatched_execution_count():
    bars = [[i*60000, '1', '1', '1', '1', '1', (i+1)*60000-1, '1', 2] for i in range(15)]
    tape = {i*forward.MINUTE: {'bad': False, 'c': forward.SCALE, 'v': forward.SCALE, 'n': 2}
            for i in range(15)}
    assert forward.reconcile(bars, tape, 0) == [1.]*15
    tape[0]['n'] = 1
    with pytest.raises(ValueError, match='disagrees'):
        forward.reconcile(bars, tape, 0)


def test_hour_compression_preserves_bytes(tmp_path):
    import gzip
    path = tmp_path/'events-test.jsonl'
    contents = b'{"event":"test"}\n'
    path.write_bytes(contents)
    record = forward.compress_hour(path)
    assert not path.exists()
    archive = path.with_suffix('.jsonl.gz')
    assert gzip.decompress(archive.read_bytes()) == contents
    assert forward.file_hash(archive) == record['gzip_sha256']
