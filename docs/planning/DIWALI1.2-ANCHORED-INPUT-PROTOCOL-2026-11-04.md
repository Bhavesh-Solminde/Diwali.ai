# Proposed next controlled model: Diwali1.2

Preparation/specification only;1.2has not been trained. The midpoint input audit completed without changing the October origins. Its new fields may be largely redundant with trade VWAP; test rather than assume improvement. Do not keep adjusting1.1using the reused October benchmark or its now-inspected single upward live session.

## Isolated comparison

Use the frozen selected0.5**raw neural checkpoint**, without its fitted temperatures, as the marginal parent. Its saved neural weights were trained/selected before calibration. Avoid training a new correction on an already-calibrated parent's probabilities as0.9–1.1did; that reused upstream calibration labels and left no independently used calibration interval for the combined pipeline. This change reduces repeated calibration usage; it does not make the already-inspected October dates fresh.

Two otherwise identical18,465-parameter residual branches:94-input24-hidden GRU plus15×26 and3colour heads, initially zero correction. Both receive the mean of the same60×92book/trade features repeated60times. The extra two channels are either zero (no-midpoint control) or the fit-standardized latest midpoint offset and net60-second midpoint log change, repeated60times. Thus the experiment isolates explicit midpoint location/momentum; it does not simultaneously add a new temporal-flow encoder. Mean-control representation follows1.1's development choice, not a switch based on its benchmark results.

The frozen raw parent still receives all1,440candles,60seconds of existing book/trades and reference displacement. Extra midpoint summaries are available before the freeze. Keep all0.5purged origins, parent preprocessing and hashes unchanged. Require the completed midpoint-window manifest and verify every input/artifact hash. Feed no target candle, future book update, hidden order or subsequently revealed answer.

## Fixed training/evaluation

- Same near-weighted26-bin range loss plus0.25colour loss plus1.0 final-direction loss aggregated from the same price distribution. Net event is final15th close above reference versus at-or-below; equality explicit.
- Seeds17/29/43;20epochs maximum, patience4, batch128, AdamW0.0003, weight decay0.0001, clip5; epoch0raw parent is eligible. Select on three-seed mean development final binary log loss, fixedseed17, no-midpoint control breaks exact ties.
- Cache raw parent logits by actual frozen-checkpoint inference; do not reconstruct them by feeding fitted calibration parameters back into training.
- Save selection before calibration/benchmark. Then fit calibration once for the new marginal pipeline: h1–14range loss, h15binary endpoint loss through full26-bin temperature, colour separately; same0.5..2grid. Report epoch0with the same calibration rules as a baseline.
- For joint queries, couple to the raw selected0.7neural transition kernel at temperature1, unit exponent. Verify its checkpoint was saved before its calibration and do not read old fitted temperature parameters into new fitting. Preserve each predicted marginal exactly; no joint-based selection after the fact.
- Evaluate final binary log loss/Brier/calibration/accuracy/confidence counts plus all-horizon range/joint errors and fit-frequency/50–50baselines. Publish regressions as well as improvements. The October benchmark remains exploratory.

A changed1.2checkpoint must make new pre-target forecasts after it is frozen. Today's0.9/1.1outcomes cannot be reused as fresh confirmation. Use the same receipt replay and source/forecast/label chronology audit. Do not erase the lower side of a cloud after an upward result, manufacture confidence, or claim that a finite test proves perfect market probabilities.
