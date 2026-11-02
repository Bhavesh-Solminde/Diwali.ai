# Diwali 0.2 probability training — 3 November 2026

User authorized training after reviewing the probability-model proposal. This
run replaces recursive price generation with a single next-full-minute
classification task. It does not extend the 15-step rollout or add news,
hidden-book inference, entry-quality labels or trading.

## Frozen task and important reference correction

Snapshot phase remains 15 seconds after the minute, with the existing assumed
one-second historical candle availability grace. A 10:01:15 snapshot predicts
the candle from 10:02:00 through 10:03:00. It does not predict a rolling 60-second
interval or the remainder of the current candle. A live result must be ready
before target start.

Primary outcomes: bearish closing return <= -2 basis points; bullish >= +2;
neutral strictly between. All three probabilities sum to one. Secondary head:
red/flat/green relative to the target candle's own opening price, with flat
meaning exact equality; this is not the same event as primary neutral.

The prepared book features contain distances relative to midpoint but do not
retain absolute midpoint. Trade features retain additive BTC quantities and
USDT amounts per received second, not the last individual execution price.
Therefore this run's reference is explicitly the **VWAP of the latest nonempty
complete received second before the snapshot**, computed from those recorded
additive amounts. This is observed information, but neither exact last trade,
executable bid/ask nor click-time midpoint. The pre-training proposal's
illustrative counts used the older completed candle close and are superseded
by this run's actual reference-specific class counts.

Exclude any example with no reference execution in its 60-second causal window
or reference receipt age over two seconds. No stale-candle fallback. Fit initially
contains 24,421 candidates; 398 are excluded (one without executions, 397 stale),
leaving 24,023. Exclusion rules use only input availability, never outcomes.
Every partition has a private reference-quality ledger.

An initial preparation attempt discovered an empty execution window and stopped
before training. It is retained locally at
`data/models/diwali0.2-preflight-no-reference`; it is not a completed training run.

## Models and selection

- Logistic baseline on fixed summaries of the same input histories.
- Small MLP over the full 1,440 x 8 candle / 60 x 87 book / 60 x 5 trade arrays.
- Small convolution + GRU sequence encoder over those same histories.
- Add the observed-reference displacement from the latest completed candle
  close, normalized on fit data only. Existing aligned input scalers are fit-only.
- Train each architecture with seeds 17, 29 and 43, up to 20 epochs, patience 4,
  AdamW learning rate 0.0003, weight decay 0.0001, batch 128, gradient norm cap 5.
- Unweighted main cross entropy plus 0.25 times the secondary candle-colour
  cross entropy. No oversampling or class weights that silently change priors.
- Select architecture by mean primary development log loss across its three
  seeds; deploy seed 17, fixed before comparison. No winning test-seed selection.
- Calibrate the selected model's two heads separately using scalar temperature
  on Oct22–23 only. Deterministic 161-point log-spaced grid from 0.1 to 10.

Dates UTC: fit Oct1–18; development Oct19–21; calibration Oct22–23; historical
comparison Oct24–31, 2026. The last block was inspected during Diwali 0.1 and
is **not new untouched confirmation** for this version.

## Evaluation and interpretation

Report primary and secondary accuracy, primary balanced accuracy, log loss,
multiclass Brier sum, full confusion matrix, class counts, class-specific
reliability bins, confidence bins and 60/70/80/90% confidence coverage/accuracy.
Compare primary probabilities with fit-frequency and uniform baselines on the
same eligible cases. Show each day separately. Sparse high-confidence bins do
not establish dependable 80–20 or 90–10 opportunities. Calibration and accuracy
do not establish profitability or target-before-stop probabilities.

The first probability dashboard shows categorical bars, actual close thresholds
and separately revealed outcomes. Three categories alone cannot support the
continuous price/path heatmap in the user's screenshot; such a display needs
an explicitly trained distribution over price levels and/or horizons.

## Reproducibility and limitations

Code: `research/diwali/probability.py`. Private outputs:
`data/models/diwali0.2/` (nine checkpoints, frozen protocol, hashes, fit-only
preprocessing, selection, calibration, probabilities, quality ledgers and report).
Local replay: `python -m research.diwali.probability_serve --port 8742`.
Fresh training requires a new output directory:
`python -m research.diwali.probability --output data/models/NEW-RUN`.

Historical candle arrival times remain assumed, and provider receipt clocks
remain unverified. No prospective model accuracy has been measured. Neighboring
examples are dependent; confidence-bin counts do not represent independent
trials. Public reports contain aggregate results only, not paid raw records,
weights, API keys or extracted vendor code.

## Run checklist

- [x] Reference, target, timing and outcome definitions stated before fitting.
- [x] Frozen protocol written before preparation/training; preserve failed preflight.
- [x] Existing source/scaler/partition integrity checks retained.
- [x] Reference freshness exclusions use past inputs only.
- [x] Fit-only preprocessing; development-only model/epoch selection.
- [x] Complete nine fits, separate calibration and historical comparison.
- [x] Verify checkpoint replay against saved probabilities and separate reveal.
- [x] Record results and checks in this document and aggregate public reports.
- [ ] Fresh unseen/prospective confirmation (deferred, required before live claims).

## Completed result

Training and evaluation took 374.81 seconds using Apple MPS. Sequence encoder
selected using three-seed development log loss: sequence 1.079194, logistic
1.082863, MLP 1.098825. Saved inference uses sequence seed 17. Temperature:
primary 1.059254, candle-colour 0.891251. Training source hash is frozen in the
run protocol; subsequent replay/UI code is separately versioned.

| Partition | Eligible examples | Primary accuracy | Primary log loss | Fit-frequency log loss |
|---|---:|---:|---:|---:|
| Fit | 24,023 | 49.29% | 0.98789 | 1.07375 |
| Development | 4,040 | 39.98% | 1.07859 | 1.11471 |
| Calibration | 2,681 | 40.99% | 1.07063 | 1.11762 |
| Inspected historical benchmark | 11,200 | 45.83% | 1.03383 | 1.09898 |

Fit/development numbers above use the subsequently fitted calibration
temperature for consistent presentation; selection used raw development log
loss. Calibration-period scores are in-sample for temperature and must not be
treated as independent evaluation.

Benchmark frequency-baseline accuracy 38.53%; balanced model accuracy 43.30%;
multiclass Brier sum 0.622785. A supplementary comparison evaluated the already
trained logistic seed17, calibrated only on the same calibration period: 45.73%
accuracy, log loss 1.03977. Sequence's small advantage over logistic is descriptive;
no statistical significance or profitability has been established.

**All 1,339 predictions with >=60% maximum class probability were neutral.**
411 reached >=70%; 37 reached >=80% (30 neutral outcomes correct, 81.08%). None
reached >=90%. These are not 80–20 directional opportunities. Bullish and bearish
classes have no validated high-confidence group in this run. Exact candle-colour
accuracy remains weak at 48.75%; do not compare that task to the three-outcome
accuracy without noting the different labels.

Benchmark actual counts: bearish 3,500; neutral 4,315; bullish 3,385. Complete
reference-quality exclusions and every architecture/seed history are preserved
locally, with aggregate metrics in `results/diwali0.2/`.

All ten evenly spaced eligible replay origins matched saved probabilities
(maximum CPU/MPS difference 5.21e-8), normalized to one, and separately revealed
the correct stored outcome. Core reference causality/model tests and existing
market-data/model suite pass (57 tests at training completion). Price-boundary
comparison against direct price thresholds was checked across every partition:
zero label differences. No prospective model forecast was scored.

Desktop (1440px) and mobile (390px) browser checks passed Predict, Reveal and
example switching, with zero JavaScript errors or horizontal page overflow.
The dashboard runs locally at http://127.0.0.1:8742/ and explicitly warns that
all of this run's high-confidence calls were neutral. The existing candle
generation dashboard on port 8741 is preserved.
