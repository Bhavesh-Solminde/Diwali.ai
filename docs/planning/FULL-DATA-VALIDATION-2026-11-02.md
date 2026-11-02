# Full real-archive validation — started 2 November 2026

User requested full data-quality validation after the download pass. No training
or trading is part of this validation run. This audit concerns real Binance
USDS-M BTCUSDT archives, not Unity or DLL-host simulator diagnostics.

## Frozen input

Period: 2025-11-01 through 2026-10-31 inclusive UTC.
17,319 downloaded files, 178,213,187,469 bytes; 17,520 expected hourly type/files.
All 201 missing files are order-book hours; all 8,760 trade-hour files downloaded.
The book files contain 45,746,422,240 price-level rows. Trade files contain
1,409,281,468 rows, including non-execution messages. No raw file is altered.

## Audit implementation

`research/market_data/validate_archive.py` orchestrates three local workers and
resumes completed month/type shards. The run fingerprint covers the input manifest,
validator source and Arrow version. Interrupted incomplete shards are replayed from
their start, preserving sequence correctness. The native C++ scanner is our own
code linked against the installed Arrow/Parquet libraries; it is not vendor code.

Each archived file is checked against its download-manifest SHA-256 and byte count,
then fully decoded with Parquet page-checksum verification enabled where present.
All rows are scanned, not sampled. Schemas, instrument, decimal values, clocks,
sequence IDs and row-count agreement are checked. Price and quantity arithmetic
uses exact fixed-point values with eight decimals; excess precision or invalid
representations are rejected rather than rounded silently. Quote totals use
128-bit arithmetic.

Books are replayed in published order. Quantities replace levels; zero deletes.
Events are applied atomically, including across Parquet row groups. Snapshot
overlap/successor checks, `pu` continuity, stale/duplicate updates, crossings,
orphans and snapshot duplicates/conflicts are counted. Gaps invalidate the book
until a new valid snapshot. Missing hours invalidate inherited state. Shards
conservatively restart at month boundaries; unverified prefixes are not claimed
usable. Candidate coverage requires top 20 per side within snapshot bounds,
uncrossed and no older than one second on every one-second grid point of the
minute. Receipt-clock anomalies exclude the affected hour from candidate inputs.
Event replay itself uses every event, not only the second grid.

Trade IDs are checked within and across files, including month boundaries.
Non-market Binance `NA` messages with both price and quantity zero are retained
for sequence checks and excluded from execution counts, OHLCV and VWAP. Other
nonpositive executions remain invalid. Aggressor-side availability is checked;
no candle-only inference of hidden orders is introduced.

For independent confirmation, all twelve Binance monthly one-minute kline ZIPs
were downloaded and verified against their published SHA-256 checksums. Rebuilt
trade-minute OHLC, base volume and count are compared exactly; quote volume has
a disclosed 0.01 USDT rounding tolerance. Targets/inputs with discrepancies are
excluded. Candidate origins also require 1,440 contiguous official past minutes,
a following target minute, and valid book/trade coverage of the last minute.

These are candidate origins, not training approval: causal feature extraction,
issuance delay, actual input availability, chronological splits, purging,
normalization and leakage review still follow before model fitting.

## Verified pilot and tests

22 market-data tests passed, including gap/resync, event atomicity, duplicate
handling, corrupt-file recovery, freshness, inter-hour state, exact decimals,
Binance NA handling, independent candle mismatch detection and inventory coverage.
Pilot: the first two November trade hours reconstructed 120 minutes; all matched
the independent Binance OHLCV/count references. The 531 NA records were excluded
explicitly. The corresponding two book hours had no starting snapshot and no
proven inherited state: they remained unverified (138,902 orphan updates), rather
than being initialized by guessing an empty book. Full-history prevalence is
pending, so do not generalize the pilot to the whole archive.

## Run and outputs

Local ignored output: `data/btc-perp/validation-20261102/`.
- `progress.json`: current files/rows/bytes checked, shard completion, errors.
- `inventory.json`: expected/missing/duplicate/size inventory.
- `hours/`: private per-hour audit results and reconstructed candle records.
- `reference/`: independent public Binance archives and checksums.
- `report.json`: final quality counts, mismatches and candidate coverage.
- `usable-origin-times.json`: private candidate origins for subsequent review.
- `process.json`: process information. Log: `/tmp/trading-ai-full-validation.log`.

```sh
python -m research.market_data.validate_archive \
  data/btc-perp/cryptohftdata-monthly data/btc-perp/validation-20261102 --workers 3
```

The Mac is kept awake while the process runs. Do not publish raw archives,
reconstructed price histories, API credentials, or paid simulator artifacts.
Only aggregate quality findings should be promoted to public research reports.

## Limits that must remain visible

Local manifest hashes establish unchanged downloaded bytes, not original-exchange
authenticity. Candle reconciliation independently checks execution-derived prices,
volumes and counts; it does not independently certify every historical book level.
Provider-generated hour checkpoints and clock corrections cannot prove original
receipt timing. Snapshot omissions on halted/empty books may be unrecoverable.
An uninitialized monthly prefix can sometimes be recovered from earlier data;
this run conservatively excludes it. Full scan completion must not be confused
with every minute passing, complete public/hidden liquidity, or trading efficacy.

Sources used to implement venue-specific rules:
- https://www.cryptohftdata.com/docs/wire-format-binance-futures
- https://www.cryptohftdata.com/docs/python-orderbook
- https://www.cryptohftdata.com/docs/data-gaps-and-corrections
- https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/websocket-market-streams/How-to-manage-a-local-order-book-correctly
- https://github.com/binance/binance-public-data
