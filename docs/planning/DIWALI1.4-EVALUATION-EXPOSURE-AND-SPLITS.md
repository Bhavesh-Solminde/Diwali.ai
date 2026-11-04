# Diwali1.4 chronological evaluation and exposure register

Frozen before new model fitting on2026-11-04. This replaces repeatedly using October24–31 as evidence of improvement. This is a bounded review of retained repository records, not a guarantee about every conversation or unrecorded external experiment.

## Prior exposure found

| Period | Retained evidence | Treatment |
|---|---|---|
|2023-01-09–20|`results/orderbook_benchmark/btc-60s-v1/summary.json`: Kaggle book sample, train/validation/test results for the earlier model comparison.|Previously evaluated; separate venue-provenance limitations. Not a fresh test.|
|2024-03-31 /2024-04-01|`results/next_candle/kronos-btc-1m-first/forecast.json`: earlier candle demonstration.|Previously demonstrated.|
|2026-09-30|October warmup and missing-trade reconciliation examples in `MISSING-DATA-RECOVERY-2026-11-02.md` and pilot inputs.|Previously inspected input/reconciliation material; do not call the raw observations unseen.|
|2026-10-01–31|Diwali0.1–1.3 inputs, training/selection/calibration and reused benchmark; October5/12 event preflights.|Exploratory diagnostic cohort. No further independent-confirmation claim.|
|2026-11-04|Recorded prospective runs and their inspected outcomes/status.|Freeze-specific live evidence, not reusable fresh labels for a later-trained version.|
|2025-11–2026-10 archive generally|Download inventories, row/clock/book continuity validation and candle reconciliation.|Quality inspection is already present. It is not the same as evaluating model probability forecasts. Do not claim these bytes/prices were never accessed.|

Repository searches of the Diwali source/results, prior benchmark/next-candle reports and planning documents found no documented model-performance evaluation on the August/September2026 periods below. This supports their selection as **previously unevaluated in the retained experiment record**, not a claim of provably unseen source prices. Broad quality checks and engineering exposure are disclosed. If contrary evidence is found, record it and replace the final period before any performance evaluation; do not silently retain a contaminated test.

## Development walk-forward folds

All intervals are UTC calendar days, inclusive. Cut features at each input availability time; purge any origin whose last forecast target crosses its partition end. A context may include preceding days, but never later observations. A label from an earlier fold may enter a later fold's training because time has advanced; the fold results are correlated, not independent trials.

| Fold | Fit weights/scalers | Select architecture/epochs | Calibrate probabilities | Score development transfer |
|---|---|---|---|---|
|A|Aug1–10|Aug11–13|Aug14–15|Aug16–18|
|B|Aug1–18|Aug19–21|Aug22–23|Aug24–26|
|C|Aug1–23|Aug24–26|Aug27–28|Aug29–31|

Use these transfer blocks to select the bounded model family and assess variation across dates. They are development evidence, not a sealed final test. All fitted transformations must be rebuilt from each fold's fit partition. Early stopping never sees the calibration/transfer labels. Freeze output/event definitions, architectures, seed/tuning budgets and selection rule in a separate executable run protocol before fitting.

## Final candidate build and reserved test

- **Final fit:**2026-08-01–31, with at most July31 as preceding candle context where needed.
- **Final model/epoch selection:**2026-09-01–07.
- **Final calibration:**2026-09-08–14.
- **Reserved final evaluation:**2026-09-15–29.
- September30 and October are not needed to score final target labels. Exclude end-boundary targets instead of reading beyond September29.

The final model family is already chosen by the August development study before this final build. September1–7 may select an epoch under the frozen rules, not initiate another architecture search. Calibration occurs only after selecting that completed network. No normalization, class weights, price-bin edges, event caps or model tuning may use the reserved final outcomes. Report window losses/quality exclusions rather than selecting favourable days or fixing target thresholds after seeing performance.

Do not evaluate September15–29 until source/feature audits, all candidate definitions, model selection and calibration are complete and their hashes are frozen. Implement a deliberate final-evaluation release in the eventual training runner; ordinary diagnostics must not read its prediction/outcome pairs. Once evaluated, this period is consumed. Later model revisions need new future-issued confirmation or another documented reserved block; they must not keep tuning to this result.

Current engineering preflights stay on already-exposed October fit hours. New end-to-end training has not started. These dates freeze the temporal design; data quality/coverage, storage budget and actual eligible counts still need preparation. Quality rejection may reduce counts, but it must not silently change the dates or use outcomes to choose replacements.

The requested first-full-candle and15-close fan remain primary outputs. Auxiliary short-horizon measurements are separately labelled. Report log loss, Brier/ordered-range scores, reliability, appropriate baselines, date variation and correlated-window caveats. No profitability, target-before-stop, hidden-liquidity or perfect-probability claim follows from this schedule.
