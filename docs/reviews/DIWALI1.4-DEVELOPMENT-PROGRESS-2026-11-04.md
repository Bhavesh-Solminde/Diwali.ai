# Diwali 1.4 completed development review

All 18 planned neural fits, 12 baseline comparisons and three horizon diagnostics have completed. The frozen selection rule chose **one_second_temporal_conv**. That final model has now been trained on August, selected on September 1–7 and calibrated on September 8–14. The reserved September 15–29 evaluation is running separately; this document contains no score from it.

## What improved, and what did not

The replacement networks train all weights from scratch and retain multiple context tokens instead of the old 33-value snapshot. The richer candidates process every retained event before learned pooling. The selected control still compresses events into one-second inputs. **Retaining subsecond events did not win this bounded comparison.** Do not describe the selected model as the event-detail winner.

The selected control improved the development price-range score against all four baselines. Its final up/down probability score did not beat the frequency or volatility baselines. Improving where price might finish is different from establishing a useful directional advantage. No result here supports an 80–20 or 90–10 trading claim.

## Completed three-fold comparison

Lower log loss is better. Neural rows average the two seeds within each fold, then give the three folds equal weight. Baselines give the same three folds equal weight. Accuracy uses the same averaging and is not a pooled or independent win rate.

| Method | Mean 15-close price-bin log loss | Final-close up/down log loss | Final-close direction accuracy |
|---|---:|---:|---:|
| event_temporal_conv | 2.810989 | 0.694070 | 51.95% |
| event_attention | 2.800579 | 0.700142 | 47.80% |
| one_second_temporal_conv | 2.791701 | 0.691911 | 49.77% |
| fit_histogram | 3.008487 | 0.687185 | 57.11% |
| fit_volatility_histogram | 2.841790 | 0.682562 | 57.11% |
| flow_logistic | 3.067021 | 0.698957 | 52.38% |
| flow_boosted_trees | 2.997395 | 0.697399 | 49.87% |

The three score periods contain 896, 249 and 200 quality-approved origins, with overlapping 15-close windows. They are not 1,345 independent market experiments. A permanent 50–50 direction forecast has log loss 0.693147; frequency and volatility baselines can do better when the outcome mix is uneven.

The selected control's per-fold price-bin losses are 2.577083, 2.867590 and 2.930430. Its lead is not uniform: event attention wins on fold C. The full average, rather than the most favourable fold, determined selection. Fold C had only 25 calibration origins and retained temperature 1 under the already frozen minimum-100 rule.

## Verified corrections and limitations

- Fixed float32 timestamp rounding in the one-second control using exact integer availability times. Fifteen event assignments differed across 5,391 labelled inputs, including seven fitting rows. The affected control was retrained; no failed transfer example was clipped or skipped.
- Recomputed the saved development forecasts against their labels for all 18 models. Selected checkpoint identities, fit-only transform counts, calibration identities and probability sums passed; the maximum reported-metric difference was exactly zero.
- A synthetic same-time multiplicity example found a possible pooling alias, but the actual 18,868,954 retained rows all have distinct availability groups. It does not explain these natural errors and does not justify a count-feature fix by itself.
- Local learned pooling and one-second summarization still discard information. The results do not establish which discarded details would improve later forecasts.
- Early checkpoint selection is common. More training epochs are not automatically an improvement. Subsequent changes need development evidence rather than repeated retuning on the reserved test.

## Signal lifetime

The fixed simple-model diagnostic compared 5, 15, 30, 60, 105, 345 and 945 seconds on common eligible origins. Its benefit over a fitted-frequency predictor changes across folds and horizons; the study does not establish a universal useful lifetime. The short endpoints use available last-trade prices, whereas the longer endpoints use full-candle closes. They differ in both timing and price definition.

## Final model and next checks

Final build: fixed seed 17, 5,391 fitting origins, 862 selection origins after boundary purging and 1,476 calibration origins. The earliest best checkpoint was epoch 1. Engineering inference passed on ten earlier selection inputs for the selected model and all four baselines; maximum CPU/GPU probability difference was about 1.09e-7. This is an inference check, not a final performance result.

The deliberately frozen final release authorizes one September 15–29 comparison, with a shared one-use evaluation claim. No model settings will change from its results within version 1.4. New future-issued forecasts remain necessary afterward. October remains an already inspected diagnostic benchmark; comparing its older-version scores directly with these different cohorts would be misleading.

Data remain incomplete: only quality-approved book windows are represented, older candle gaps are explicitly masked, provider receipt timing is not proven original-exchange timing, hidden liquidity is not observed, and native candle agreement does not certify every book level. Finite forecast scores cannot establish perfect probabilities or trading profitability.

Evidence: `results/diwali1.4/development-report.json`, `development-artifact-audit.json`, `final-build-model-preparation.json` and `final-build-inference-preflight.json`. Individual forecasts, market inputs, fitted artifacts and paid archives remain local.

## Why range quality can improve while direction does not

A separate audit decomposes each 26-bin probability error into two exact parts: the error for choosing the correct side of the reference price, plus the error for choosing a price band within that side. The identity holds for every development forecast, up to floating-point rounding. This is an accounting diagnosis, not a causal explanation of feature importance.

Across all 15 closes, the selected model has direction error 0.690991 and within-side range error 2.100710. The volatility-frequency baseline has direction error 0.684269 and within-side range error 2.157520. The model's gain in move-size placement is larger than its loss in up/down probability quality; the overall range metric therefore improves even while direction gets worse. These average-15 direction scores differ from the final-close-only column above.

This supports separately tracking direction and conditional range quality in the next development protocol. It does not establish that another loss weight or a larger network will fix direction. The reserved September result must remain an evaluation of the already frozen 1.4 model. Evidence: `results/diwali1.4/development-error-decomposition.json`.
