# Proposed next controlled model: Diwali1.2

Training and historical evaluation completed in395.52seconds. The midpoint input audit completed without changing the October origins. The added fields are largely redundant with trade VWAP; their controlled benefit was small and did not fix probability quality. Do not keep adjusting1.1using the reused October benchmark or its now-inspected single upward live session.

## Completed result and adoption decision

All six fits completed. The three-seed development final-direction log loss selected `with_midpoint`:0.691864 versus0.692034 for the control. Selection preceded calibration and benchmark evaluation; fixedseed17 selectedepoch4 in both arms.

On11,186 already-inspected October benchmark origins:

| Method | Final-direction log loss | Brier error | Direction accuracy | Mean15 range log loss | Joint log loss |
|---|---:|---:|---:|---:|---:|
| Midpoint disabled |0.695124|0.250967|51.28%|2.812487|28.287489|
| Midpoint enabled, selected |0.694900|0.250858|51.23%|2.811592|28.266297|
| Epoch0 parent, matching calibration |0.693158|0.250006|50.59%|2.809872|28.260550|

Lower loss/Brier is better. A50–50 probability has log loss0.693147 and Brier0.25. The selected correction improves slightly over its matching control but is worse than epoch0 on proper probability scores. Its279 forecasts claiming at least60% confidence were correct49.10% of the time; there were no80% claims. Higher raw accuracy does not establish better probability estimates. Do not promote1.2as a dependable direction model. Diwali0.9 remains a stronger historical reference (final log loss0.693088), itself without a proven dependable edge.

The remaining observed error is overconfidence and weak transfer from development to the October benchmark. Explicit midpoint summaries alone did not solve it. No conclusion about missing hidden orders or news follows from this isolated experiment. Next model changes should test this failure directly using a fixed protocol; do not adjust this frozen checkpoint from partial forward outcomes.

Verification:117 focused tests passed. Ten historical UI origins/150 horizons match saved probabilities on CPU within1.24e-7,30 joint queries are coherent, sources/parent hashes are unchanged, and actuals remain separate until Reveal. Desktop/mobile browser checks found no page errors or document overflow; black actual dots change from0 to15 after Reveal while directional probabilities stay unchanged. Aggregate evidence is in `results/diwali1.2`; private inputs and weights remain local. UI: `python -m research.diwali.anchored_serve`, port8752.

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
