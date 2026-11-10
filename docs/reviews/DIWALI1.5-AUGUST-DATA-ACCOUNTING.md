# How August became 5,391 examples

The archive manifest and the replay ledger both cover August 1–31, 2026 UTC. Each of the 744 hours has a BTCUSDT perpetual trades file and an order-book file. The replay also reads 36 earlier hours for initialization and candle context. Those earlier hours supply no August forecast origins.

| Stage | Count |
|---|---:|
| Raw coverage | 31 days, 744 matched hours |
| Potential forecasts at second 15 of every minute | 44,640 |
| Removed because a source file was missing | 0 |
| Removed by input quality gates | 39,121 |
| Inputs passing all input gates | 5,519 |
| Removed because one or more of the 15 future candles was missing or invalid | 128 |
| Removed by sampling, caps, or other preparation rules | 0 |
| **Usable examples** | **5,391 (12.08%)** |

| First recorded input rejection | Forecast origins |
|---|---:|
| No valid order-book state immediately before the 60-second window | 36,084 |
| Unreliable trade timestamps intersected the input history | 1,501 |
| Gap or invalid marker inside the event window | 1,151 |
| Recent source-hour pair was flagged for clock quality | 240 |
| Insufficient valid candle history or missing latest candle | 84 |
| No fresh completed-second price reference | 45 |
| Stale book coverage | 16 |

These input reasons are mutually exclusive because the builder stops at the first failed gate. The 36,084 missing-seed cases explain most of the loss. An hourly file can exist and contain updates while replay still cannot establish a trustworthy starting book. The rejection ledger alone does not say how many of those minutes can be recovered. A prior continuous replay beginning from a verified snapshot already superseded the first one-hour warmup attempt. The most promising follow-up is to compare rejected hours with independent snapshots or sequence-contiguous depth from another archive. Reuse a recovered interval only if it passes the same gates.

The 5,391 are the complete August cohort under these rules. Individual rolling fits use fewer examples because later dates serve as checkpoint, calibration or scoring periods. The retained control and attention challenger use all 5,391 for fitting.

[Machine-readable reconciliation](../../results/diwali1.5/august-origin-accounting.json) · [Original cohort audit](../../results/event-joined-cohort/august-month-audit.json)
