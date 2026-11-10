# Diwali 1.5 bounded architecture/objective comparison

Frozen before new fitting on November 11, 2026. Authority: the user requested A/B/C/D, the original 15-close range primary, a separate final-direction result, matched examples and a comparable bounded tuning budget. Existing 1.4 weights, scoring sources and consumed September records are not changed.

## Exact candidates and budget

| Family | Two settings per seed/fold | Purpose |
|---|---|---|
| A: existing 1.4 architecture | learning rate 0.0003 (exact setup reference), 0.0001 | Reproduce the control and allow an equal two-setting tuning budget |
| B: same architecture + direction loss | lambda 0.25, 1.0; learning rate fixed 0.0003 | Test objective emphasis while preserving range/direction consistency |
| C: same inputs and heads + candle attention | learning rate 0.0003, 0.0001 | Change only the candle branch, on the same 96 compressed steps |
| D: direct binary logistic | fixed C=1, lbfgs, max_iter=1000 | Answer up/down directly on the full matched cohort |

A/B/C each have two configurations × seeds 17/29 × three folds = 12 fits per family. Total: 36 neural fits. D has 15 independent endpoint heads in each of three folds and is deterministic at seed17: three baseline runs, not duplicate seed fits. Exactly 39 runs are planned; no automatic expansion of settings. Start D and B before the other configurations.

A_original remains separately reported even if A_lower_lr is the family's best setting. Matched architecture comparisons exist at both learning rates for A/C, and matched objective comparisons at 0.0003 for A/B. A parameter change is not disguised as an architecture gain.

## Correct architecture description

The actual 1.4 candle branch is a projection/local convolution followed by pooling to 96 candle tokens. It is not a GRU. C retains that identical preprocessing and adds one small Transformer encoder layer across those 96 tokens: width64, four heads, feed-forward128, dropout0, fixed sinusoidal positions. The event branch, seed/reference inputs, context convolution and 15×26 output remain unchanged. C has128,092 parameters versus94,620 for A/B. All declared parameters are trainable, from initialization; no frozen-parent correction is introduced.

This is a candle-attention comparison, not a PatchTST reproduction. PatchTST includes both patching and channel independence; adopting it wholesale would change additional aspects of the representation. [Original PatchTST paper](https://arxiv.org/abs/2211.14730).

## Inputs and actual counts

5,391 is the **complete prepared August labelled cohort**, not merely the ranking diagnostic subset. It is also not the entire downloaded archive. August preparation considered44,640 minute origins, accepted5,519 input contexts and retained5,391 with complete15-close labels. All candidates use the same labelled input IDs and target partitions. No new return-based filtering is introduced.

| Fold | Fit dates | Fit origins | Selection origins | Calibration origins | Transfer dates | Transfer origins |
|---|---|---:|---:|---:|---|---:|
| A | Aug1–10 |1,638|420|352|Aug16–18|896|
| B | Aug1–18 |3,314|260|1,343|Aug24–26|249|
| C | Aug1–23 |4,917|249|25|Aug29–31|200|

The existing chronological partitions, target-boundary purging, quality gates, 1,440-candle masks, strict input cutoffs and exact integer event-second assignment remain unchanged. Every run records its actual first/last input freeze, distinct fitting days and partition counts. A later chosen-model refit on all5,391 origins would be a separate step, not falsely reported as the fitting count of each fold.

Neural inputs are the current exact60 one-second book/trade matrices,1,440 completed candles,80-value book seed and reference displacement. A verified private cache avoids repeatedly reopening raw event windows. All fold fit-only transforms must equal the retained 1.4 transforms exactly; 30 per-fold input checks compare all seven model tensors bit for bit against the original loader. Input caching is an execution optimization, not a new information representation.

D uses the existing447-value summary function on the same raw input windows as the old multiclass flow_logistic. This is a controlled direct-binary objective baseline on matching summary features. It is not claimed to retain all the neural sequence information. Fit-only summary scaling is retained. All D heads use exactly the same primary-cohort fitting rows, not the smaller auxiliary-lifetime subset.

## Loss and selection rules

A/C minimize equal-average categorical cross entropy across15×26 outputs. B minimizes that same range loss plus lambda times binary cross entropy averaged over the same15 endpoints. Its binary logits are logsumexp of bins0–12 versus bins13–25. Thus the up chance is exactly the sum of positive price-bin probabilities; no independent arrow or inconsistent cloud is added.

All neural runs use width64, event block128, batch8, AdamW, weight decay0.0001, gradient limit5, up to12 epochs and patience3. Select the earliest best checkpoint by **uncalibrated selection-period mean15-bin log loss**, keeping the main task intact even for B. Changing the penalty weight is a declared two-setting development search, not later manual retuning.

Neural calibration remains the existing per-horizon26-way temperature minimizing calibration range loss on49 log-spaced values0.5–4. D applies the same grid to binary loss because it has no range output. Require at least100 calibration origins; foldC remains temperature1 for every candidate. Both raw and calibrated direction metrics are reported, so a calibration-method difference is visible.

Choose the neural configuration by equal-fold/equal-seed calibrated development-transfer **mean15-bin log loss**. A tie within0.0001 favours A, then B, then C, then the earlier declared configuration. Also report each family's best configuration. D is not eligible for price-range selection because it does not output a price distribution.

Primary comparison: range error versus the volatility-conditioned histogram on the same origin IDs. Separate direction comparison: fifteenth-close binary log loss/Brier/AUC versus50–50, frequency and volatility baselines, plus D. Report all horizons, every fold/day, confidence/error spread and all tradeoffs. A direction gain with worse range error must remain a disclosed tradeoff. Baseline saved forecast IDs and scores are verified against the new cache before any fit starts.

The first target still closes105 seconds after the usual freeze, and the fifteenth closes945 seconds afterward. Up means close above the frozen reference; equality stays down-or-unchanged. No intraminute path/entry odds or news model is added.

## Exposure, verification and next evaluation

August is already examined development data. September1–14 has also been examined for earlier selection/calibration. September15–29 is consumed and is not read by this comparison. October is not fresh confirmation either. Do not label these new development results independent proof of improvement.

Tests check coherent binary loss, zero-weight equivalence, A/C input-branch equivalence with identity attention, masking, finite gradients and equal tuning counts. The actual Mac MPS path passed Transformer backward/evaluation and CPU parity checks before the first fit. Checkpoint hashes, histories, source graph, cache identity and actual counts are retained. A failed or incomplete run is retained for inspection; no overwrite or automatic retry. Original A reproduction differences are explicitly reported.

After the bounded comparison, freeze the selected checkpoint, transforms, calibration, baselines, eligibility policy and forward evaluation rules **before** issuing new future forecasts. Score only common eligible timestamps with the volatility benchmark and50–50. No newly generated forecast may be backdated. A completed development report alone does not complete that future evaluation or prove profitability.

Only code and aggregate evidence may be pushed. Paid raw records, individual inputs/forecasts, fitted model files and API keys remain local. Public metric groups smaller than ten origins are suppressed.
