# Diwali1.4 bounded event-representation experiment

Freeze before the first new model fit. This is a replacement representation study, not another frozen-parent residual. The authoritative executable settings are `research/diwali/event_protocol.py`; every run writes those settings plus source hashes before fitting.

## Data and unchanged prediction task

Use the quality-approved August2026 BTCUSDT perpetual origins, after continuous snapshot-initialized replay. The one-pass cohort considered44,640 minute origins and retained5,519 joined inputs;5,391 also have valid15-close labels. It preserves18,868,954 event rows in input windows, ranging from1,770 to51,276 per origin. Missing snapshot bounds, markers, staleness and clock exclusions remain reasons to reject data. Older candle gaps use an explicit mask, at least99% context validity and a valid most recent completed candle. This population is not all market minutes.

The independent native candle aggregate check matches80,865 retained target-close coordinates exactly. It checks a separate aggregation implementation using the same source, not exchange authenticity. Historical provider availability clocks remain an assumption. Targets use retained executions through August source end; unrecorded later arrivals outside that range remain unproven. No hidden orders are fabricated.

Inputs freeze at second15:1,440 completed minute candles plus the last60seconds of retained book/trade events, a known pre-window book seed and an explicit reference-to-seed price displacement. The first predicted full candle starts at the next minute boundary and closes105seconds after a typical freeze. All15 endpoint distributions remain direct outputs; the last close is945seconds after that freeze. Use the existing26 price bins and unbounded tails. Direction probabilities must remain sums of these same bins; zero return belongs to down-or-unchanged. No recursive future books or candles are supplied.

## Comparison and fitting

Compare event temporal convolution, event attention and an otherwise matched early one-second-compression convolution control. Event encoders process every accepted row before local learned pooling; equal-availability groups do not claim cross-feed causal order. The one-second control preserves per-second channel means, last within-second book state and log event counts, while discarding individual within-second order and size sequence. It is an explicit compression control, not an exact clone of the old0.5 network.

Both event candidates retain multiple local tokens,96 candle tokens, seed and reference-coordinate tokens. Fifteen horizon queries read these tokens. All declared network parameters participate in training, initialized from scratch. No old parent weights are loaded. The unchanged reference implementation remains available for parity checks; a vectorized feature implementation matched all103 features, masks/indices and reference coordinates bit for bit over3,107 completed August origins (9,403,483 event rows) before training. It also matched32 earlier preflight windows exactly.

For each of the three frozen August rolling folds, use seeds17 and29, width64,128-group local event blocks, AdamW learning rate0.0003, weight decay0.0001, batch8, maximum12epochs, patience3 and gradient clipping5. Minimize equal-average cross entropy over the15×26 outputs. Select the earliest best checkpoint using uncalibrated selection-period mean15-bin log loss. Fit input means/scales only on that fold's training inputs; exclude masked candle contents, and never fit transforms on selection/calibration/transfer inputs. Keep all trials and checkpoints; no event count truncation.

Also run fit-frequency histograms, fit-volatility conditional histograms, a fixed-summary multinomial logistic baseline and fixed-summary boosted trees. The logistic uses seed17,40epochs maximum, patience5, batch128, AdamW0.001 and weight decay0.001. Each tree horizon uses100iterations, learning rate0.05, at most15leaf nodes, minimum30samples per leaf, L2penalty1, no internal random validation split and seed17. All use the same target origins and date partitions. Store fitted artifacts locally.

## Chronology, calibration and sparse coverage

Use the exact dates in `DIWALI1.4-EVALUATION-EXPOSURE-AND-SPLITS.md`. Purge every origin whose15th target extends outside its partition. An origin may use earlier context but never later input observations. Available counts after this purge are:

| Fold | Fit | Select | Calibrate | Transfer score |
|---|---:|---:|---:|---:|
|A|1,638|420|352|896|
|B|3,314|260|1,343|249|
|C|4,917|249|25|200|

These counts are quality/coverage evidence inspected before model performance. Do not move dates to improve a score. Require at least200fit,100selection and100transfer examples. If the calibration partition has fewer than100origins, do not fit temperature: retain1for every model and disclose the unsupported calibration. Thus foldC stays uncalibrated. For supported folds, after checkpoint selection fit a separate scalar temperature per horizon on calibration dates alone, using49log-spaced values0.5–4. This policy is fixed before the first fit.

Choose the candidate family using the three-fold/two-seed mean transfer15-bin log loss. The simpler one-second control wins ties within0.0001. Compare against all simple baselines and disclose regressions; a more complex architecture is not automatically an improvement. Record per-horizon bin log loss, ordered probability score, binary direction log loss/Brier, accuracy, reliability and daily paired scores. Accuracy is not a substitute for probability quality, and overlapping windows are not independent trials.

After this bounded development study, the chosen family alone may be rebuilt with fixedseed17 on August, selected on September1–7 and calibrated on September8–14 under the frozen rules. September15–29 stays reserved until artifacts/source hashes are deliberately released for one final evaluation. The partition guard exists; the final one-use evaluation runner and final candidate build remain required. October stays diagnostic and must not select this model. New future-issued forecasts are needed afterward; earlier0.9/1.2 live outcomes are not fresh1.4 confirmation.

## Signal lifetime diagnostic

Separately record5/15/30/60-second endpoint labels using the latest market execution released strictly before each endpoint and at most2seconds old. These availability-price outcomes differ from execution-time full-candle closes and may include bid/ask trade-price noise. They never enter input features. Keep the primary full-candle task unchanged.

A fixed binary logistic diagnostic compares5/15/30/60/105/345/945-second horizons on identical origins with all labels valid. Use fit-only summary normalization and independent logistic regressions, C1, lbfgs and at most1,000iterations. Calibrate only under the same separate-period/minimum100-origin rule. Compare each horizon against its training-frequency predictor and report daily results. This tests the lifetime of information usable by this simple model, not a universal market law or a replacement for the15-close probability fan.

## Publication and claims

Publish source, protocols and aggregate metrics only. Keep paid raw data, individual input/forecast records, weights and fitted trees local. No trading, news model, target-before-stop entries or hidden-book inference is added here. Finite evaluations cannot establish perfect conditional probability prediction or profitability. No1.4 improvement is claimed before the planned comparisons actually finish.

## Implementation amendment: exact second buckets

The original study stopped during the first one-second control's transfer inference: one valid event just before the strict cutoff had an elapsed time that rounded to60.0 in float32, causing an outside-window rejection. A full scan of5,391 labelled inputs found15 event rows assigned to a different second by the float clock, including seven rows in foldA's fitting inputs and one rounded-to60row. No raw timestamp or event payload was changed.

The corrected control reads the saved, hash-verified integer `available_ns` from each event-window index and subtracts the exact window start before dividing by1,000,000,000. Events at or beyond the true cutoff still fail; there is no clipping. Internal second-boundary rounding is corrected too. Because seven fitting rows were affected, the failed control is retrained, rather than merely skipping its failed transfer example. The original failed run stays private and excluded from comparison.

The four completed raw-event foldA fits and completed baselines are imported unchanged, with their source and artifact hashes verified. New corrected controls use `event_data_exact.py` and `event_train_exact.py`; `event_study_exact.py` resumes the same families, dates, seeds, targets, losses and selection rules in a separate study directory. This amendment repairs preprocessing, not a performance-driven hyperparameter change. Aggregate audit: `results/event-model-engineering/exact-second-binning-audit.json`.

## Remaining representation limitation found during the study

A synthetic input-only counterexample holds the candle/seed/reference inputs fixed and repeats the same known market-fill feature vector1,2or16times in a single equal-availability group. Both fitted seed17event networks change their output probabilities by less than5e-8. Normalized set pooling therefore cannot distinguish the number of otherwise identical rows in this case. Processing every row before pooling is not a guarantee of retaining total trade quantity or group cardinality.

This does not establish how often the limitation affects natural forecasts or explain every error. The frozen1.4 weights and study settings remain unchanged. After this comparison, a bounded representation experiment can test explicit counts/quantity sums or sum-plus-mean pooling while preserving the required same-time permutation invariance. Do not treat another wider hidden layer as recovering this discarded multiplicity. Evidence: `results/event-model-engineering/diwali14-group-cardinality-probe.json`.

## Later final-build preparation

The preparer now additionally supports the fixed September1–14 selection/calibration interval, with August31and preceding snapshot initialization as context. It still denies September15–29. The content auditor separately checks this interval and reports only final-build selection/calibration coverage. This extension does not alter the already completed August cohort artifacts.

`event_final_data.py` joins only audited August and September1–14 components. Its final-score partition remains denied. `event_final_train.py` refuses to select a family from an incomplete development report and recomputes the frozen family-selection rule before fitting. It trains fixedseed17, selects on September1–7 and calibrates on September8–14, without opening final-test labels. This runner is implemented but has not yet been started: the full August comparison and September preparation must finish first. Final one-use evaluation and subsequent prospective confirmation remain required.
