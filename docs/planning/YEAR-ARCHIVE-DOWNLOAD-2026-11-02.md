# Twelve-month archive plan — 2026-11-02

Supersedes the earlier 30-day download schedule. User requested at least twelve
months, month-based work division, reuse without duplicates, and independent
request pacing. All five supplied credentials authenticated successfully.

## Coverage and assignment

Target: Binance USDS-M perpetual BTCUSDT, 2025-11-01 through 2026-10-31 inclusive
UTC. 365 days × 24 hours × 2 types = 17,520 unique expected hourly files.
Types: L2 order-book snapshots/updates and executed trades. This is a request
coverage target, not a claim that the provider has every file or that data are valid.

| Local credential slot | Months |
| --- | --- |
| 1 | 2025-11, 2026-04, 2026-09 |
| 2 | 2025-12, 2026-05, 2026-10 |
| 3 | 2026-01, 2026-06 |
| 4 | 2026-02, 2026-07 |
| 5 | 2026-03, 2026-08 |

Five concurrent download workers interleave monthly queues. Each remote file is
scheduled once and belongs to one credential slot; workers never key-hop after a
throttle. Each slot has independent 1.1-second request spacing. Authenticated range
probes succeeded for all five keys but returned no rate-limit headers. Thus this
spacing is our conservative setting, not a verified provider per-key allowance.
Any HTTP 429 imposes a shared server-directed cooldown, honoring Retry-After.
JWTs refresh before expiry. The coordinator enforces one active process per output.

## Reuse and storage

The earlier downloader was stopped before the new coordinator started. 610 existing
files (including the independent sample) were checksum-verified and adopted through
hard links, which share the same disk bytes. Existing paths remain audit references;
they are not extra observations. Canonical paths are under ignored local directory
`data/btc-perp/cryptohftdata-monthly/YYYY-MM/YYYY-MM-DD/HH/`.
Any already-downloaded November 2026 data remain supplemental, outside the year plan.

Metadata and SHA-256 checks prevent successful complete files being fetched again
on resume. `.part` files are incomplete and may be fetched again. Historical files
sometimes use an outer Zstandard frame: preserve those bytes as `.parquet.zst`,
inspect via a temporary decoded Parquet file, and record encoding in metadata.
Newer plain Parquet files remain `.parquet`. Never assume the suffix alone tells
the entire encoding. Raw files and credentials are not published to GitHub.

The downloader checks available disk space (30 GiB reserve) and bounds individual
wire/decoded files at 4 GiB. Monitor storage; no twelve-month size or duration is
guaranteed from the initial hour. The Mac is held awake with caffeinate while the
coordinator runs; reboot, shutdown, loss of network or closing a laptop can interrupt it.

## Operations and readiness

Progress: canonical root `status.json`, per-month counts and failed file identities.
Process information: `process.json`. Log: `/tmp/trading-ai-year-download.log`.
Run/resume from repository:

```sh
python -m research.market_data.archive_sample \
  data/btc-perp/cryptohftdata-monthly --date 2025-11-01 --days 365 \
  --workers 5 --monthly \
  --key-ring "$HOME/.config/trading-ai/cryptohftdata-keys.json"
```

Keys remain in a private owner-readable file outside Git. Code never emits them or
JWTs. Failed files are recorded for retry; completed download does not mean complete
exchange coverage. Training remains blocked on book reconstruction, sequence and
timestamp checks, trade/candle reconciliation, gaps, and chronological dataset
construction. News, missing-book inference and entry-quality modeling remain deferred.

Validation: three focused tests cover exact year boundaries, unique matching jobs,
monthly interleaving, and both provider encodings without mutation of source bytes.
An older January book file decoded successfully (2,282,216 rows).

Provider references:
- https://www.cryptohftdata.com/docs/rest-authentication
- https://www.cryptohftdata.com/docs/rest-introduction
- https://www.cryptohftdata.com/docs/data-gaps-and-corrections
- https://www.cryptohftdata.com/terms
