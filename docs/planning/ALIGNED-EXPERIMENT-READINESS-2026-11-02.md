# Completed three preparation tasks — 2 November 2026

Status: **all three preparation tasks complete for the small conditional historical
pilot. No neural fitting or final-test scoring was performed.** Use the reusable
[model training checklist](../checklists/MODEL-TRAINING-CHECKLIST.md) for every new
model, copying it to a dated run record rather than checking the master template.

## 1. Trade-input alignment — complete

The shared trade representation has five features per complete receipt-second:
log buy BTC, log sell BTC, log buy USDT, log sell USDT, and VWAP offset from the
last input candle close. VWAP means traded money divided by traded quantity.
Individual execution counts, buy/sell execution counts and aggregate message counts
are excluded from BOTH paths. Closed-candle execution count remains a candle
feature: it comes from the exchange's candle record in both paths, not a count of
live messages. Live quantities use `q`, not RPI-excluding `nq`.

`trade_alignment.transform` is shared by historical preprocessing, the live request
adapter and baseline calculations. Counts cannot accidentally enter via the
trade scaler: its width/order are explicitly five. The aligned scaler was refit
only on the 24,421 primary fitting windows. Parent inputs and origin counts are
unchanged; use the NEW alignment contract/scalers, not the old eight-feature
trade scaler, for the coming experiment.

Live overlap evidence: a 90-second requested probe (97.25 seconds including setup
and shutdown) compared aggregate messages with individual Binance recent-trade
records by exact native execution IDs. It observed 2,988 aggregate messages and
8,824 distinct individual IDs. **2,961 complete groups matched exactly**, covering
7,738 executions; 1,259 groups contained multiple executions. Twenty-seven groups
lacked complete overlap and were excluded, rather than guessed. No complete group
mismatched and no connection/request error was recorded. Pass gate: at least 100
complete groups, ten bundled groups, 95% complete overlap and zero mismatches/errors.
The measured complete overlap was 99.10%.

Unit checks also verify invariance when same-price/side trades split or merge,
empty seconds, use of `q` when `nq` differs, feature shape, and future-message
rejection. No real matched group in this short probe had `q != nq`; the differing
RPI case is covered synthetically, not claimed observed live.

Scope of completion: feature MEANINGS now agree. Batching/network delay can still
put the same execution in different receipt-second buckets at different recorders.
This is a remaining timing/distribution limitation, not evidence that every
historical/live second is identical. No artificial arrival time was introduced.

## 2. Experiment settings — frozen before new baseline scoring

Machine-readable protocol: `configs/experiments/btc-button-pilot-v1.json`.
The baseline run saves its protocol SHA-256 before reading labels and refuses to
reuse an output directory with a different protocol hash.

- BTCUSDT perpetual; 1,440 candles and 60 book/trade seconds; primary snapshot at
  :15, assumed historical candle finalization grace one second; target next full minute.
- Unchanged calendar splits: fit October 1–18; development October 19–21;
  calibration October 22–23; final test October 24–31, all UTC.
- Small MLP: flatten complete histories, hidden layers 32/32, under one million
  parameters. Sequence model: candle convolution covers all 1,440 inputs in
  nonoverlapping 15-minute blocks, then GRU; separate projected book/trade GRU;
  fused head, under 100,000 parameters. The full history is retained, not shortened.
- Three seeds 17/29/43; AdamW; learning rate 0.0003; batch 128; max 20 epochs;
  patience four; 30-minute/seed and 18 GB peak-memory budgets. Record actual device,
  determinism, parameters and costs; resource-capped runs must be labelled.
- Checkpoints/architecture selected by development mean OHLC MAE; architecture
  comparison uses all three seeds. Tie within 0.01 bp favors the smaller model.
  Seed 17 is preselected for eventual forward inference, not chosen from test scores.
- Valid OHLC output construction; fit-only input and target scaling. Calibrate
  per-OHLC 80%/95% residual intervals on calibration only with a fixed rank rule.
- Test scores remain unavailable until checkpoint/architecture/calibration choices
  are fixed. Timing stresses are predefined, compared on common targets, without
  a new hyperparameter search for each case.
- Training error, historical unseen error and genuinely prospective recent-market
  error remain separate. No model/live error exists yet.

## 3. New baselines — complete

Scored 24,421 fitting and 4,079 development targets using aligned inputs. Seven
rules fixed before scoring; no test or calibration target file was scored.
All rules use exactly the same eligible targets. Per-day, class-count and balanced
metrics are in the aggregate result JSON.

| Rule | Mean OHLC MAE (bp) | Close MAE (bp) | Close direction vs last input close |
| --- | ---: | ---: | ---: |
| No change from last candle close | 4.091 | 4.637 | 0.34% |
| Continue previous move | 4.572 | 5.907 | 48.10% |
| Reverse previous move | 4.435 | 5.670 | 50.55% |
| Fitting majority direction | 4.508 | 5.788 | 49.13% |
| Book imbalance | 4.313 | 5.445 | 55.80% |
| Aggressive trade flow | 4.453 | 5.705 | 52.41% |
| Recent received trade VWAP persists | 3.653 | 4.295 | 62.66% |

One basis point (bp) is 0.01%. MAE is average absolute price error. For example,
4.295 bp is about 0.04295% average close error, not return or profit.

The last rule anchors its forecast at the most recent nonempty complete-second
VWAP; it is a stronger current-price reference than the older completed candle.
**62.66% is not next-candle green/red accuracy or a trading win probability.**
It compares the future close with the LAST INPUT candle close, which is older
than the snapshot. Some of that direction can already be visible at the snapshot.
Flat forecasts are correct only on exactly flat outcomes under the three-class
metric; this explains no-change's very low directional score. The price-error
comparison is essential. Three development days remain a small dependent sample;
no useful live advantage or profitable strategy is established by these rules.

## Updated original readiness checklist

- [x] Recover the 85 identified candle-content problems.
- [x] Preserve original data and version the new experiment.
- [x] Keep the full candle/book/trade history contract.
- [x] Exclude invalid order-book intervals.
- [x] Keep chronological training/development/calibration/test partitions.
- [x] Fit preprocessing on fitting data only.
- [x] Implement immutable input freezes and result-time guards.
- [x] Verify recorded live input freezes and correctness tests.
- [x] Align historical/live trade feature definitions (scope/latency limits above).
- [x] Freeze this experiment's models, resource limits, metrics and selection rules.
- [x] Run fixed baselines for the new target/cohort.
- [ ] Recover original arrival times for repaired history — unavailable; keep the assumption explicit.
- [ ] Independently confirm historical book levels — not completed across the archive.
- [ ] Demonstrate broad market-condition coverage — one October pilot remains limited.
- [ ] Evaluate prospective MODEL predictions — input recording alone does not do this.
- [ ] Add hidden-order/news context — deliberately deferred first-model scope.

Thus **11 of the original 16 items are checked**. All three preparation items are
cleared; none of the five observational/scope limitations was silently removed.
They do not require an endless search for perfect data before an explicitly
conditional pilot. This checklist is a run record, not a permission to trade.

## Evidence and rerun

Private outputs: `data/btc-perp/aligned-button-pilot-202610-v1/`,
`trade-alignment-probe-20261102/` and `aligned-button-baselines-20261102/`.
Public aggregates: `results/market_data/aligned-preparation-20261102/`.

```sh
python -m research.market_data.trade_alignment prepare \
  data/btc-perp/button-pilot-202610-v1 data/btc-perp/aligned-button-pilot-202610-v1
python -m research.market_data.button_baselines \
  data/btc-perp/aligned-button-pilot-202610-v1 configs/experiments/btc-button-pilot-v1.json \
  data/btc-perp/aligned-button-baselines-20261102
python -m pytest tests/market_data -q
```

Next: implement and run the two neural models within the frozen budget. Future
forward evaluation must use the common trade adapter and measured receipt-based
requests. Do not present this preparation or these baselines as trained-model accuracy.
