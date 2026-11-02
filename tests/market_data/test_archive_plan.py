from datetime import date
from collections import Counter

from research.market_data.archive_sample import build_jobs
from research.market_data.archive_sample import inspect_file
import pyarrow as pa
import pyarrow.parquet as pq


def test_year_partition_has_exact_coverage_without_duplicates():
    jobs = build_jobs(date(2025, 11, 1), 365)
    assert len(jobs) == len(set(jobs)) == 17520
    assert min(j[0] for j in jobs) == date(2025, 11, 1)
    assert max(j[0] for j in jobs) == date(2026, 10, 31)
    assert set(Counter(j[0] for j in jobs).values()) == {48}
    assert len({str(j[0])[:7] for j in jobs[:12]}) == 12
    counts = Counter(str(j[0])[:7] for j in jobs)
    assert counts['2026-02'] == 28 * 48
    assert counts['2026-10'] == 31 * 48


def test_single_hour_is_bounded_to_matching_book_and_trades():
    jobs = build_jobs(date(2026, 10, 31), 1, 12)
    assert jobs == [(date(2026, 10, 31), 12, 'orderbook'),
                    (date(2026, 10, 31), 12, 'trades')]


def test_both_provider_encodings_are_read_without_changing_raw_file(tmp_path):
    table = pa.table({'price': ['77576.30'], 'quantity': ['0.002']})
    raw = tmp_path / 'plain.parquet'
    pq.write_table(table, raw)
    wrapped = tmp_path / 'wrapped.parquet.zst'
    with pa.output_stream(str(wrapped), compression='zstd') as stream:
        stream.write(raw.read_bytes())
    original = wrapped.read_bytes()
    for path, expected in [(raw, 'parquet'), (wrapped, 'zstd-wrapped-parquet')]:
        meta, encoding = inspect_file(path)
        assert encoding == expected
        assert meta.metadata.num_rows == 1
        assert meta.schema_arrow == table.schema
    assert wrapped.read_bytes() == original
    assert not list(tmp_path.glob('*.decoded'))
