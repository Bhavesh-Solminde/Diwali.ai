# Diwali 1.0: train the overall direction explicitly

Protocol recorded before training. The user's example (October 31,23:44:15) had 52.8783% final-up probability and 47.1217% down-or-unchanged in0.8;0.9 gives53.7211% versus46.2789%. The upward revealed outcome does not justify erasing the earlier downside probability. Current painting gives every nonzero bin colour and maps whole-bin mass to intensity across unequal price widths. It is explicitly a probability-mass display, not a density; wide painted areas must not be read as extra confidence or evidence of correct direction.

The training issue is weak directional information. In0.9, final net-direction accuracy on the inspected benchmark is50.4202%; no forecast reaches60% confidence. This is not a strong directional predictor. A wide two-sided fan does not itself demonstrate accurate probabilities.

Target: final (15th) forecast close greater than the frozen input reference, versus at-or-below it. Equality stays explicitly grouped with down/unchanged because the bins do not isolate a zero atom. This is not the first candle's ±2bp label, a majority of green candles, a monotone15-minute path, or a profit event.

Two matched new7,929-parameter recent60-candle residual branches over the frozen selected calibrated0.9 parent. Both start at zero correction and can retain epoch zero. Range control uses the same near-weighted26-bin plus0.25colour loss. Direction arm adds weight1.0 binary endpoint cross entropy, calculated by summing the appropriate13+13 price-bin probabilities. No independent direction head can contradict the range cloud.

Seeds17/29/43; up to20epochs, patience4; batch128; AdamW0.0003, weight decay0.0001, clip5. Select on three-seed mean DEVELOPMENT final binary log loss, seed17fixed, range-control wins exact ties. Freeze selection before calibration/benchmark. Use identical calibration rules for both arms: h1–14 range log loss, h15 endpoint binary log loss with temperature applied to the full26-bin distribution, grid0.5..2; colour separately. Upstream calibration has already been reused; no independent-calibration claim.

Keep fixed unit coupling to0.7 for joint events. Compare binary log loss, Brier score, accuracy, calibration, high-confidence sample counts against0.9, fit-only frequency, and50–50. Also report changes to range/joint errors rather than hiding regressions. Do not fabricate confidence or repaint using actual outcomes. Benchmark is repeatedly inspected; further live verification is still needed. Raw data, caches and weights stay private.

## Result: explicit direction loss did not fix the problem

All six fits chose epoch0. Every trained correction worsened the development final-direction probability error, even though training loss decreased. Both variants therefore tied at0.694286573 development binary log loss and the predefined tie-break selected range control. There is no learned residual correction to deploy. This is a negative experiment, not a newly learned directional edge.

After the predefined calibration, both retained-parent variants give identical inspected-benchmark results:

| Metric | 0.9 parent | 1.0 retained-parent/recalibrated |
| --- | ---: | ---: |
| Final binary log loss | 0.693088 | 0.693260 |
| Final direction accuracy | 50.4202% | 50.5543% |
| Mean range log loss | 2.805340 | 2.805673 |
| Joint log loss | 28.113849 | 28.121852 |

Lower loss is better. A constant50–50 forecast has binary log loss0.693147, better than1.0. Fit-frequency binary loss is0.693326; the fit-majority side achieves48.4713% accuracy on this benchmark. Neither arm produces even60% directional confidence; no80–20 claim is supported. Do not promote1.0 over0.9: higher accuracy alone hides worse probability, range and joint errors. There is no fresh prospective test for either version.

Training-versus-development divergence is evidence against this correction generalizing. It does not establish a unique cause such as missing whales or inadequate model size. The new branch could only relearn recent candle features; book/trade representation remained frozen. Further work must test information/representation and generalization, not force the purple cloud to one side. A correct net-up forecast can still allow a downward move before the final close, so final-direction training would not justify removing all earlier downside either.

Training source/data hashes and CPU replay are verified in `results/diwali1.0`. Ten origins/150 horizons and30 joint-event queries match saved outputs within1e-6;104 focused model/data tests pass. Source and aggregate evidence are published; raw data and weights stay private. The0.9 replay remains the active UI, with explicit direction probabilities and a reference line. No model output is recoloured using actual outcomes.

Goal remains active; directional weakness is unresolved. No perfect-probability or entry-profitability claim.
