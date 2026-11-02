# Direct Wi-Fi + USB download resumption

User explicitly requested direct automated workers, without Plexo, and continuation
if a useful speed increase was demonstrated. Existing twelve-month month/key/file
assignments remain in effect. Credentials and raw data remain local and ignored.

## Matched benchmark

Archive workers were cooperatively drained before comparison, so they did not
compete with the test. Four sequential batches each downloaded five copies of the
same 15,921,067-byte public BTCUSDT book file to temporary scratch storage. Every
copy matched the previously recorded SHA-256. Scratch files were removed and are
not counted as observations in the research dataset.

| Batch | Routes across five transfers | Elapsed seconds | MB/s |
| --- | --- | ---: | ---: |
| 1 | Wi-Fi only | 36.794 | 2.164 |
| 2 | Three USB, two Wi-Fi | 14.066 | 5.659 |
| 3 | Three USB, two Wi-Fi | 8.622 | 9.233 |
| 4 | Wi-Fi only | 34.173 | 2.329 |

Total bytes divided by total time for each mode: Wi-Fi 2.24 MB/s; dual-route
7.02 MB/s, approximately 3.13× (+213%). The reversed batch order reduces simple
warm-up bias. This is a short matched-file benchmark, not a guaranteed speedup
for the whole year or a comparison with the exact conditions of the older run.
Network variability, source/CDN delays and changing file sizes still apply.

## Resumed operation

- Five workers: three bound to USB `feth0`, two to Wi-Fi `en0`.
- Direct curl transfers, not Plexo UI downloads or device-wide network bonding.
- Whole files are distributed across routes; individual files are not split.
- Curl binds the tested interface, verifies TLS, restricts redirects to HTTPS,
  limits file size and time, and receives the JWT privately over stdin.
- Per-key pacing and provider-directed 429 cooldown remain respected.
- Preflight verifies saved checksums and schedules only missing files, maintaining
  one canonical copy per remote file and accurate reused-file counts.
- The resumed checkpoint contained 2,693 files (29,906,462,952 bytes).
- Live market recording remains stopped; this resumption is for historical archives.

Current process and progress live in the archive root's `process.json` and
`status.json`. Log: `/tmp/trading-ai-dual-network-download.log`.
For future graceful pause, create the local archive-root `PAUSE` marker. Queued jobs
start no new requests, open responses finish, and metadata/manifest are saved.
Remove the marker only when authorized to resume. A disconnected route fails with
bounded retries; it does not silently claim that both links are still working.

Resume command, after removing the pause marker:

```sh
python -m research.market_data.archive_sample \
  data/btc-perp/cryptohftdata-monthly --date 2025-11-01 --days 365 \
  --workers 5 --monthly --key-ring "$HOME/.config/trading-ai/cryptohftdata-keys.json" \
  --interfaces feth0 feth0 feth0 en0 en0
```

Validation: 11 market-data tests passed, including transfer-interface selection,
credentials absent from process arguments, year partition uniqueness and both
archive encodings. Actual USB full-file checksum and all 20 benchmark checksums
also passed. No training readiness is implied by faster or completed downloads.
