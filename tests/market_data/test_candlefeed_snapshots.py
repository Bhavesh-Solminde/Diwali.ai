import hashlib

import pytest

from research.market_data.candlefeed_snapshots import download_file


def test_resume_preserves_verified_bytes_and_refuses_mismatched_existing_file(tmp_path, monkeypatch):
    original = b'preserve these source bytes'
    path = tmp_path/'snapshot.parquet'
    path.write_bytes(original)
    record = {'name':path.name, 'size':len(original), 'sha256':hashlib.sha256(original).hexdigest()}
    assert download_file(record, tmp_path) == 'already_verified'
    record['sha256'] = '0'*64
    with pytest.raises(ValueError, match='preserve'):
        download_file(record, tmp_path)
    assert path.read_bytes() == original


@pytest.mark.parametrize('name', ['../snapshot.parquet', 'depth/00.parquet'])
def test_snapshot_only_download_rejects_unexpected_paths(tmp_path, name):
    with pytest.raises(ValueError, match='Only snapshot'):
        download_file({'name':name}, tmp_path)
