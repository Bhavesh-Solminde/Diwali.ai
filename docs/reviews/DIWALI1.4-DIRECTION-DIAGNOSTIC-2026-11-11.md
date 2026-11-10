# Diwali 1.4 directional-learning investigation

Prepared November 11, 2026. This is a diagnostic of the completed August development artifacts, not Diwali 1.5 training. Neither diagnostic opened September 15–29 records, no new model or calibration correction was fitted, and no architecture was changed.

## Answer to the recommendation

The distinction is correct: always issuing probabilities below 50% does not by itself establish that the model cannot rank outcomes. We have now checked ranking rather than inferred it from its preferred side.

The selected family's fifteenth-close ranking is weak and changes across development periods. Its first and fifth closes have better descriptive ranking on average, with variation across days/seeds. The results do not support treating the fifteenth-close problem as only a calibration offset. They do justify a small, matched direct-binary development experiment before another architecture search.

## Scope and reproducibility

Audited 18 neural runs and 12 baseline runs. For each, compared raw versus calibrated directional probabilities for every one of the 15 horizons on checkpoint-selection, calibration and development-transfer partitions, with per-day metrics. The public aggregate retains all seven method-family transfer means and full selected-family six-run detail, including probability groups. Public metric slices with fewer than ten origins are suppressed; complete diagnostics remain local.

The raw 26-bin predictions are recoverable from saved calibrated predictions and their recorded temperatures: `p_raw = softmax(T * log(p_cal))`. This uses the existing transform, not a newly fitted correction. Round-trip normalization was checked on every distribution. Raw recovery was also compared with checkpoint inference on three transfer origins from each of the 18 neural runs; maximum absolute bin-probability difference was 3.7442e-7. This is sampled inference verification, not a claim that all original logits were re-inferred.

All saved calibrated scores were reconciled with the existing reports. Existing source and selected-weight checks were retained. The new script refuses non-August inputs and does not contain a reserved-period evaluation path.

## Direction/reference mapping

Across all 5,391 August labelled inputs and 80,865 future-close coordinates:

- Recomputed returns from stored actual closes and the frozen input reference match the stored returns exactly.
- Direct `actual close > frozen reference` agrees with the binary target derived from the price bins on every coordinate: zero mismatches.
- The reference is the same frozen completed-second trade VWAP; it is not silently replaced by candle open, last completed close or a midpoint.
- Zero is an explicit price-bin edge. Bin 12 is (-0.5bp, 0bp], and bin 13 is (0bp, +0.5bp]. Up sums bins 13–25; down-or-unchanged sums bins 0–12.
- No price bin straddles zero, so no within-bin probability split is required. Exactly unchanged prices belong to down-or-unchanged; there are 780 such target coordinates in this development cohort.
- Tests cover zero, immediately adjacent representable negative/positive returns, and the separate exact +2bp bullish-band convention. The +2bp special case does not affect up/down sign.

This verifies the implementation mapping. It does not validate original receipt timestamps, hidden liquidity or an executable entry price.

## Calibration method actually used

Each horizon has one scalar temperature chosen from 49 logarithmically spaced values between 0.5 and 4. The choice minimizes **26-bin categorical log loss**, using that fold's separate calibration dates after checkpoint selection. It does not minimize binary direction loss or fit a binary intercept.

There must be at least 100 calibration origins. Fold C has 25, so all temperatures remain 1. Its raw and calibrated predictions are therefore the same. Scores on the calibration partition itself are in-sample for this temperature adjustment; they cannot establish later improvement.

In a binary sigmoid model, a positive temperature preserves ranking. Here temperature acts on 26 bin scores **before** positive-bin probabilities are summed. That summed up probability can change ordering; invariance of binary AUC cannot be assumed. The diagnostic calculates AUC separately before and after this transform, and a unit test demonstrates a valid counterexample to ordering invariance.

## Selected-family development results

ROC-AUC measures ordering: approximately 0.50 means no ranking, above 0.50 means upward outcomes tend to receive higher up scores. It is not an accuracy or probability-calibration measure. Below 0.50 is reversed ordering on that sample. Single-class daily slices have undefined AUC and are recorded as null.

The following gives equal weight to each of three folds and two seeds. These are means of within-run AUCs, not AUC calculated by pooling differently calibrated models. Lower log loss and Brier error are better.

| Future close | Raw AUC | Calibrated AUC | Raw direction log loss | Calibrated direction log loss | Raw Brier | Calibrated Brier |
|---|---:|---:|---:|---:|---:|---:|
| 1 (105s after freeze) | 0.536765 | 0.537248 | 0.687337 | 0.688354 | 0.247113 | 0.247578 |
| 5 (345s after freeze) | 0.550302 | 0.550338 | 0.691228 | 0.691195 | 0.249026 | 0.249004 |
| 15 (945s after freeze) | 0.500366 | 0.500567 | 0.691799 | 0.691911 | 0.249314 | 0.249382 |

A constant 50–50 predictor has direction log loss 0.693147, Brier error 0.25 and AUC 0.50 whenever both outcomes are present. Constant historical-frequency predictors can beat it on probability error without ranking individual examples. At the fifteenth close the fitted frequency and volatility-frequency baselines have calibrated log loss 0.687185 and 0.682562 respectively, better than the selected model's 0.691911.

At the fifth close, all six control-run AUCs are above 0.50, ranging from 0.5103 to 0.5872. Their probability error still does not beat the volatility-frequency baseline (0.686164). This is descriptive reused-development evidence, not sufficient evidence for trading or a validated new forecast horizon. The fifth close is 345 seconds after the typical freeze, not exactly five minutes after clicking.

All fifteen horizon results are retained. We are not selecting a new primary horizon by choosing whichever AUC looks best.

## Fifteenth-close stability across time

Each row below averages the two seeds within that fold. Fold A scores August 16–18, B August 24–26, and C August 29–31.

| Fold | Probabilities | Origins per seed | AUC | Direction log loss | Brier error |
|---|---|---:|---:|---:|---:|
| A | raw | 896 | 0.522807 | 0.689541 | 0.248159 |
| A | calibrated | 896 | 0.524220 | 0.688119 | 0.247486 |
| B | raw | 249 | 0.554613 | 0.688603 | 0.247732 |
| B | calibrated | 249 | 0.553805 | 0.690361 | 0.248610 |
| C | raw | 200 | 0.423676 | 0.697253 | 0.252051 |
| C | calibrated | 200 | 0.423676 | 0.697253 | 0.252051 |

Fold C's reversed ranking is present **without calibration**. That rules out the temperature adjustment as the sole explanation of the final-horizon instability. Calibration slightly helps final probability error in A and worsens it in B. Its six-run average direction loss changes from 0.691799 raw to 0.691911 calibrated; there is no consistent calibration-only remedy demonstrated here.

Daily results vary further. For example, fold B seed 17 has calibrated final AUC 0.5461 across the period, but daily AUCs 0.5227, 0.4464 and 0.4051. Pooling days can mix changing outcome frequencies and prediction levels. Both per-day and whole-period results are needed; no independent-observation significance is claimed.

## Probability groups: does a higher forecast mean more up outcomes?

We recorded fixed probability bands and prediction-only quartiles, separately per horizon/period and before/after calibration. Quartile boundaries use only predictions, not answers; tied forecasts remain together. These are descriptive groups, not selected entry thresholds.

A concrete final-close example shows the reversal in fold C seed 17. There is no fitted calibration in this fold:

| Prediction quartile, low to high | Examples | Average predicted up probability | Observed up fraction |
|---|---:|---:|---:|
| Lowest | 50 | 47.22% | 54.00% |
| Second | 50 | 48.99% | 50.00% |
| Third | 50 | 50.83% | 38.00% |
| Highest | 50 | 52.25% | 36.00% |

Other blocks have weak or positive ordering. For example, fold B seed 29's calibrated final probabilities are all below 50% (46.46–48.07%), yet AUC is 0.5615. This directly confirms the recommendation's logical distinction. Its quartile outcome frequencies are not monotonically ordered, however, and the next fold reverses. One favourable block does not establish a stable ranker or justify flipping signs after looking at outcomes.

## Actual final-build checkpoint, before the reserved test

The rolling models above are not the final deployed weights. We separately re-inferred the actual frozen final-build checkpoint on its existing September 1–7 selection and September 8–14 calibration inputs. No reserved September 15–29 records were read. All 15 horizons and days are recorded, raw and calibrated.

| Existing partition | Close | Origins | Raw AUC | Calibrated AUC | Raw direction log loss | Calibrated direction log loss |
|---|---:|---:|---:|---:|---:|---:|
| select | 1 | 862 | 0.466694 | 0.466661 | 0.705849 | 0.706832 |
| select | 5 | 862 | 0.415113 | 0.416982 | 0.700733 | 0.699765 |
| select | 15 | 862 | 0.502590 | 0.508213 | 0.700615 | 0.698727 |
| calibrate | 1 | 1476 | 0.502516 | 0.502715 | 0.694920 | 0.695345 |
| calibrate | 5 | 1476 | 0.491593 | 0.491478 | 0.695493 | 0.694985 |
| calibrate | 15 | 1476 | 0.524169 | 0.524314 | 0.691555 | 0.691701 |

These periods are not independent tests: selection chose this checkpoint, and calibration chose its temperatures. In particular, a calibration-period score is in-sample for the adjustment. The actual final checkpoint's fifth-close ranking on selection is reversed (AUC 0.4170 after calibration), unlike the positive average in the August study. Do not describe the earlier fifth-close signal as stable later evidence.

On the actual final checkpoint's selection examples, every final up probability is below 50% both before and after calibration. The raw mean is 47.90%, the calibrated mean is 48.39%, while the actual up frequency is 58.12%. Its near-0.5 AUC and large probability bias coexist; a monotone offset alone cannot supply missing ranking. A direction-specific calibration correction could change probability error and deserves a controlled test, but these observations do not prove it would transfer.

Its calibration examples give final AUC about 0.524 before and after calibration, with log loss slightly worsening from 0.691555 to 0.691701. That small in-sample ranking result does not override the inconsistent selection/rolling evidence. No binary intercept correction was fitted in this audit.

The same label/reference audit on these 35,115 prefinal target coordinates found zero mismatches. Together with August, 115,980 retained target coordinates were checked with no sign-mapping mismatch. This remains a check of the retained data and code, not original-exchange authenticity.

Evidence: `results/diwali1.4/prefinal-direction-diagnostic-2026-11-11.json` and `research/diwali/event_prefinal_direction_diagnostic.py`.

## What the existing baselines do and do not test

`flow_logistic` is a linear layer producing 15×26 scores, trained by categorical cross entropy. Direction is summed from its positive bins. It is **not** the requested directly trained binary logistic baseline, despite the shorthand name.

`event_lifetime.py` already fits direct binary logistic models for several endpoints, including the first, fifth and fifteenth full closes. However, it keeps only origins that also have all auxiliary 5/15/30/60-second labels. That is a smaller common-horizon subset. It cannot replace a direct binary comparison on exactly the original primary cohort without a new, explicitly matched experiment.

## What is justified next, subject to the user's decision

A bounded Diwali 1.5 experiment could compare a direct-binary logistic model and one small direct-binary neural model on the full same eligible development origins, against the existing derived range-model probabilities, 50–50 and volatility-frequency forecasts. Keep the fifteenth-close direction as the declared primary decision, all-horizon results as secondary diagnostics, and a separate fixed chronological binary-calibration policy. Do not silently pick the fifth or sixth close because this audit looks better there.

This tests a training-objective hypothesis; it is not a promise of success. Merely adding a binary loss repeats some earlier-version ideas unless the matched data, direct objective, controls and forward evaluation are made explicit. Separate direction outputs also must not be silently presented as consistent with the old price cloud; integration would need its own checked design.

September 15–29 remains consumed. August diagnostics are reused development evidence. Freeze any next selected model, calibration and eligibility policy before future evaluation forecasts are issued, then compare all methods on identical passing timestamps. No new architecture, calibration correction, 1.5 training, or live forecast collection was started by this investigation.

## Evidence and checks

- Aggregate: `results/diwali1.4/development-direction-diagnostic-2026-11-11.json`.
- Source: `research/diwali/event_direction_diagnostic.py`.
- Checks: `tests/diwali/test_event_direction_diagnostic.py`.
- Existing decomposition: `results/diwali1.4/development-error-decomposition.json`.
- Full local diagnostic: `data/diagnostics/diwali1.4-direction-development-2026-11-11.json`; it contains aggregate groups/metrics, not a replacement training dataset.

The finite and overlapping development samples cannot establish the true conditional probabilities or demonstrate future profitability. All model weights, individual forecasts and paid inputs remain local.
