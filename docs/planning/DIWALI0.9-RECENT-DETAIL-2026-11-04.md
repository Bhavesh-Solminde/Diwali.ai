# Diwali 0.9: preserve recent candle detail

Recorded before training. 0.8 preserved individual probabilities, so it could not correct 0.5's directional errors. The existing candle encoder compresses groups of 15 minutes before its recurrent layer; this experiment tests a separate view of the latest 60 complete one-minute candles.

Two identical trainable branches: an 8-input, 16-hidden GRU with 15×26 range and 3-colour output heads. The grouped control receives four 15-minute feature averages repeated to 60 steps. The detail branch receives those same 60 minute feature vectors intact. All other inputs, target origins, normalization, losses, optimizers and seed schedules are matched. This tests retained detail rather than simply adding parameters. No new book/trade information is introduced.

Selected calibrated 0.5 predictions are frozen. Branch output heads start at zero; epoch zero is a candidate, so training can retain the parent if development fails to improve. Each arm uses seeds 17/29/43, up to 20 epochs, patience 4, batch 128, AdamW 0.0003, weight decay 0.0001, gradient clipping 5. Loss matches the parent's near weighting: half the range loss on h1 and half shared over h2–15, plus 0.25 first-candle colour loss.

Select by mean development equal-average 15-horizon range log loss across three seeds; deploy seed 17. Exact ties choose grouped. Save selection before calibration or benchmark. Fit separate bounded temperature per horizon and colour on the existing calibration period; parent calibration was already used, so this is reused upstream calibration, not an independent calibration guarantee. The exact October cohort and parent hashes must remain unchanged.

For joint probabilities, reuse 0.8's fixed unit coupling to the frozen selected 0.7 network. No dependence search or benchmark-based model selection. Evaluate each arm's range, direction, coverage, joint sequence and closing-time event scores against existing baselines. October is repeatedly inspected, so improvement there does not establish live performance. No entries, news, hidden-book fallback, or trading in this experiment.

Training uses cached parent log probabilities to avoid repeatedly evaluating the frozen network. Replay must recompute both parent and residual from the frozen past input and agree with cached evaluation within 1e-6 probability. Test zero correction, matched parameter counts, grouped-versus-detail transformation and finite learning gradients before training. Keep raw inputs, local caches and weights private; publish aggregate results and source.

## Results

Finished in264.46seconds. Detailed-candle development mean across seeds:2.818340; grouped control:2.818598. The detailed branch was frozen as the selection before calibration/benchmark. Selected seed17's best epoch was3; other detailed seeds chose epoch2. The grouped arm chose epochs1,1,0. Each branch has7,929 trainable parameters.

| Inspected October benchmark | Mean range log loss | Joint log loss | First-close3-class accuracy |
| --- | ---: | ---: | ---: |
| 0.8 selected | 2.805561 | 28.124498 | 45.7089% |
| 0.9 grouped control | 2.805316 | 28.117503 | 45.8162% |
| 0.9 selected minute detail | 2.805340 | 28.113849 | 46.1380% |

Lower errors are better. Improvements are small; the grouped control actually has slightly better benchmark marginal error than the selected detailed arm. Do not select again on benchmark. This does not establish a robust causal benefit of minute detail or a profitable directional edge. 0.7 retains the best joint loss among these historical versions.

## Overall-direction clarification from the user

The purple distribution must express directional preference, not just possible movement. Added an explicit final-close event computed from the very same distribution: probability the15th close is above the frozen reference, versus at-or-below it. Boundary is zero displacement, not the first-candle ±2bp neutral band. Equality cannot be separated from negative displacement by the current bins and is explicitly labelled down-or-unchanged.

On the user's exact October31,23:44:15 example,0.8 assigns52.8783% to final-up and47.1217% to down-or-unchanged.0.9 assigns53.7211% and46.2789%. Both sides being coloured is therefore faithful to a weak forecast, not evidence of a confident upward prediction. Do not delete downside using the subsequently revealed upward candles.

Selected0.9 final net-direction accuracy on11,186 inspected examples is50.4202%, binary log loss0.693088, Brier0.249971; no forecast reaches60% direction confidence. Always predicting the benchmark majority side would achieve51.5287% accuracy (descriptive benchmark majority, not a trained deployment rule). A broad fan is not sufficient evidence that probabilities are good. Next experiment1.0 tests explicit coherent final-direction training rather than forcing one-sided colours.

## Verification

Ten replay cases /150 horizons and30 joint queries passed; CPU replay differs from saved evaluation by at most1.25e-7. Direction percentages equal sums of the same forecast bins. Actuals remain separate until Reveal. Training source and parent-data hashes unchanged. Aggregate reports in `results/diwali0.9`; raw inputs/caches and weights remain private. Replay at http://127.0.0.1:8749.

The full goal remains active; finite data cannot certify perfect market probabilities.
