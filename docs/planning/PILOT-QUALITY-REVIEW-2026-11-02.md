# Corrected audit and October pilot review — 2 November 2026

Scope: continue investigating snapshot exclusions and October gaps, then freeze
the pilot dates and publish eligible sample counts. No model fitting yet.

## First-pass results and correction

The original scan completed every downloaded file with matching hashes, sizes and
row totals. Its reconstruction findings are preliminary, not all provider defects.
The original report remains preserved under local `validation-20261102/`.

Older April/May files sometimes interleave two copies of each snapshot level:
one has the recorded receipt timestamp; the other has an exchange-derived synthetic
receipt timestamp. The v1 validator grouped by receipt timestamp, splitting these
interleaved levels into incomplete snapshots and greatly inflating invalid-snapshot
counts. The corrected scanner groups consecutive snapshot rows by native sequence
and exchange event time, verifies that repeated side/price quantities agree and
retains the raw receipt-clock anomalies. Conflicting copies are rejected. No raw
file is rewritten. Fixing reconstruction does not certify synthetic receipt times
as genuine live availability. The provider documents older duplicated snapshots.

Real-file regression: `2026-05-01/15/BTCUSDT_orderbook.parquet` replayed
6,053,144 rows. The corrected scan found one complete snapshot containing 1,000
duplicate level rows, accepted 25,702 subsequent updates, and ended with valid
sequence state. The 1,000 backward raw receipt rows remain visible; the earlier
orphan prefix and periods outside known top-20 bounds remain excluded. This proves
the grouping correction on that file, not full timing validity or archive-wide recovery.

The earliest five months contain updates without a snapshot in the scanned files.
They cannot be reconstructed by assuming an empty book. Recovery from an earlier
verified state remains separate work; this review does not claim it completed.
October receipt reversals inspected in the sample involved buffered updates listed
after a REST snapshot with a later receipt timestamp. Full affected hours remain
conservatively excluded from causal candidate coverage; no event-time sorting is
used to hide that distinction.

## Independent October reference recovery

The official monthly October kline ZIP contains 43,200 rows, omitting October 28.
Its daily ZIP also returned 404. Binance's public futures REST klines endpoint
returned all 1,440 aligned October 28 minutes. The raw REST response, request URL,
receipt timestamp and SHA-256 are stored privately alongside references. The
supplement is validated for exactly one complete day and may fill missing reference
minutes; it must agree with any overlapping archive candles. It does not overwrite
the original ZIP or supply guessed book records.

## Corrected run and quality-only pilot choice

A new full scan runs under local `validation-v2-20261102/`, prioritizing October.
Its fingerprint covers current scanner/driver code and input manifest; the installed
Arrow runtime is used for decoding. Earlier incomplete pilot shards are recomputed where fingerprints differ.
The month/type boundaries are conservative replay restarts; recovered reference
candles can provide context across those boundaries. The full scan will reassess
the entire year, while the completed October shards allow pilot review first.

October is the pilot month because of audited paired coverage, prior to any model
scores. The first pass had 39,630 October candidates; those counts are superseded
by the corrected reconciliation with the recovered independent reference day.
The pilot uses the validated subset of October, not a claim of a perfect gap-free
month. Market-condition coverage and day-level exclusions must be reported.

## Frozen calendar boundaries

All periods below are UTC and end-exclusive. Their candidate times are frozen by
`research/market_data/freeze_pilot.py` after both corrected October shards finish.

| Partition | Start | End exclusive | Calendar budget |
| --- | --- | --- | --- |
| Fit | 2026-10-01 | 2026-10-19 | 18 days |
| Development/model selection | 2026-10-19 | 2026-10-22 | 3 days |
| Probability calibration | 2026-10-22 | 2026-10-24 | 2 days |
| Locked pilot test | 2026-10-24 | 2026-11-01 | 8 days |

Warm-up starts September 30 for the 1,440 completed-minute candle context.
Input history remains 60 seconds for observable book/trades. Targets must finish
inside their own partition. Past context may extend into an earlier period only
when available before issuance. Invalid origins are omitted, retaining timestamps
and gap masks; they are never concatenated into fake continuous time. Neither
normalization nor learned calibration sees the locked test.

The local pilot manifest records origin counts, date boundaries, coverage, audit
fingerprint and SHA-256 of each origin list. Freezing candidate timestamps is not
training approval: actual causal feature arrays, max-availability checks, labels,
purging and hardware/model budget must pass next. Existing scope remains fixed
baselines then small MLP versus compact sequence model; news, fallback, entries,
synthetic pretraining and trading remain deferred. A later three-month comparison
must not reuse an inspected pilot test as an untouched final test.

## October corrected results and frozen candidate counts

All 744 October book files and 744 October trade files passed size/hash/row-count
and decode checks in the corrected scan. Independent October 28 reference recovery
was included. Final candidate origins: **42,457 of 44,640 minutes (95.11%)**.

| Partition | Eligible candidate origins | Calendar coverage |
| --- | ---: | ---: |
| Fit | 24,402 | 94.144% |
| Development | 4,078 | 94.398% |
| Calibration | 2,686 | 93.264% |
| Locked test | 11,291 | 98.012% |

Counts and timestamp-list hashes are saved privately in
`data/btc-perp/pilot-202610-review/pilot-manifest.json`. These counts describe
quality-filtered prediction origins, not independent samples or training scores.
The data review does not inspect predicted outcomes/model accuracy and does not
consume the locked test for model selection. The corrected full-year audit continues
separately; the original global snapshot-error totals must not be used as final
evidence until that corrected audit finishes. Model fitting has not begun.

Commands:

```sh
python -m research.market_data.validate_archive \
  data/btc-perp/cryptohftdata-monthly data/btc-perp/validation-v2-20261102 \
  --workers 3 --priority-month 2026-10
python -m research.market_data.freeze_pilot \
  data/btc-perp/validation-v2-20261102 data/btc-perp/pilot-202610-review
```

References:
- https://www.cryptohftdata.com/docs/python-orderbook
- https://www.cryptohftdata.com/docs/wire-format-binance-futures
- https://www.cryptohftdata.com/docs/data-gaps-and-corrections
- https://data.binance.vision/
- https://fapi.binance.com/fapi/v1/klines
