# Diwali 1.5: first development period completed

All thirteen planned runs for fold A are complete: twelve neural fits plus one direct-binary baseline. Later folds are running. This is **not** the completed three-period decision, a production model, or independent performance evidence.

All rows below score the same896 August16–18 origins. Neural scores average seeds17/29 equally. The neural fitting set contains1,638 origins from ten distinct calendar days; separate selection/calibration contain420/352. Main result is mean15-close range log loss. Final direction means the15th close versus the frozen reference. Lower log loss is better; AUC measures ranking, not accuracy.

| Method | Mean15 range log loss | Final direction log loss | Final direction AUC |
|---|---:|---:|---:|
| A_original | 2.577083 | 0.688119 | 0.524220 |
| A_lower_lr | 2.582546 | 0.688213 | 0.527373 |
| B_direction025 | 2.579357 | 0.688154 | 0.525940 |
| B_direction100 | 2.581890 | 0.688125 | 0.526276 |
| C_attention_original_lr | 2.582254 | 0.689086 | 0.495618 |
| C_attention_lower_lr | 2.572850 | 0.686061 | 0.516100 |
| D_binary_logistic | Not a range model | 0.705399 | 0.529116 |
| fit_histogram | 2.843222 | 0.687545 | See diagnostic |
| fit_volatility_histogram | 2.684924 | 0.687359 | See diagnostic |

On this period the original control is the strongest neural range model; objective weighting and candle attention have not improved that result. The direct binary model changes the objective as requested, but it does not win probability error here. This is not a reason to terminate the already bounded comparison or increase its search budget: later folds must complete under the frozen rule.

The original control reproduces both seeds' selected epochs and retained range scores exactly. Cache input checks also passed: all fold fit-only transforms equal the original transforms, and all seven input tensors are bitwise equal on30 per-fold sample checks. Reused benchmark row IDs and scores were verified before fitting.

The study contains39 runs total:36 neural fits and three deterministic binary baseline runs. No September15–29 records are opened. Public progress is aggregate-only; complete input records, individual forecasts and model files stay private. Refer to `results/diwali1.5/development-progress.json` and the frozen comparison protocol for current run evidence.
