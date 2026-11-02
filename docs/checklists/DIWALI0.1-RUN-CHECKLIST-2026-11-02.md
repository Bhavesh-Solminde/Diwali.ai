# diwali0.1 completed run checklist — 2 November 2026

Based on [the reusable template](MODEL-TRAINING-CHECKLIST.md). This is an evidenced
run record, not an instruction to tick future models automatically.

Run: diwali0.1. Market: Binance USD-M BTCUSDT perpetual. Target: next full calendar
minute after a primary :15 snapshot. Inputs: 1,440 candles plus 60 seconds of book/
trade measurements. Dataset: aligned-button-pilot-202610-v1. Conditional historical
availability assumption retained. Protocol: configs/experiments/btc-button-pilot-v1.json.
Exact protocol/source/checkpoint hashes: results/diwali0.1/run-protocol.json and report.json.

## Before fitting

- [x] Source recovery/reconciliation, unchanged bytes and exclusions documented in recovered-button dataset report.
- [x] Chronological fit/development/calibration/test periods preserved, full histories retained.
- [x] Native book sequence/bounds/freshness and trade-time/receipt guards retained.
- [x] Historical candle availability explicitly marked assumed; no invented receipt timestamps.
- [x] Aligned five-field trade definitions and fit-only scalers used. No aggregate-message counts as execution counts.
- [x] Baselines and model/seed/optimizer/resource/selection budgets frozen before neural fitting.
- [x] Target scales fitted only on fitting labels; all model inputs use past windows only.
- [x] Future-input and checkpoint/output correctness checks passed.

## Training and evaluation

- [x] Both architectures trained on seeds 17, 29 and 43 within the prescribed budgets.
- [x] All runs and losses preserved; no cherry-picked discarded seed.
- [x] Development-only architecture/checkpoint selection completed before test access.
- [x] Preselected seed 17 used for the interactive model.
- [x] Residual intervals calibrated only on the separate calibration block before test evaluation.
- [x] Final test evaluated once under this selection, against all seven fixed baselines.
- [x] Training, historical unseen and unmeasured recent-live errors are distinguished.
- [x] Price errors, both direction definitions, class-aware metrics, per-day errors and interval widths/coverage reported.
- [x] Result judged honestly: small price-error improvement; candle-colour accuracy remains 48.6%.
- [x] Test period marked consumed; later score-driven changes cannot reuse it as fresh unseen evidence.

## UI verification

- [x] Predict runs actual saved weights; reveal is a separate request.
- [x] Ten evenly selected examples checked against stored test predictions/labels.
- [x] Historical snapshot, future target and current calculation times are clearly distinguished.
- [x] Desktop/mobile screenshots inspected; no JS errors or horizontal mobile overflow.
- [x] 49 automated correctness tests passed; API inference is consistent across CPU/MPS within documented tolerance.

## Remaining evidence, not silently checked

- [ ] Original historical candle receipt times: unavailable; assumption remains.
- [ ] Second-recorder confirmation of every historical book level: not complete.
- [ ] Broad regime/multi-month confirmation: one conditional October month only.
- [ ] Prospective live model predictions/outcomes and real deadline/missed-target rate: not measured.
- [ ] Predeclared additional timing-sensitivity evaluation: not included in this first UI release.
- [ ] Hidden-order/news/entry features: explicitly outside this model's scope.

Decision: historical pilot completed; local historical replay ready. No certified
live accuracy, profitability or live-trading readiness is claimed. See the
[training record](../planning/DIWALI0.1-TRAINING-RECORD-2026-11-02.md).
