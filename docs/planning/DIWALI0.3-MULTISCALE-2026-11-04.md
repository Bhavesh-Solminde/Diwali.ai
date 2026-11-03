# Diwali0.3: test longer book/trade history — 4 November 2026

User requested building and testing Diwali0.3 after questioning why 1,440 candle
minutes were paired with only 60 seconds of book/trade history. This experiment
tests longer context without asserting that more observations improve accuracy.

## Frozen scope

Keep the same next-full-minute +/-2bp bearish/neutral/bullish target, observed
latest-received-second VWAP reference (at most two seconds old), and secondary
red/flat/green task. Preserve the exact Diwali0.2 eligible origins, reference
prices and chronological fit/development/calibration/benchmark partitions.

Short branch: existing 1,440 x 8 candles, 60 x 87 book features, 60 x 5 executed
trade features, and reference displacement. Longer branches: 60 consecutive
one-minute bins ending at cutoff, and 24 consecutive one-hour bins ending at
cutoff. These histories intentionally overlap: each branch offers a different
time scale of the same observed market. No future values enter any bin.

Each old bin contains 24 numbers: means and standard deviations of seven
spread/depth-imbalance/microprice features; logged buy/sell BTC and USDT sums;
signed execution quantity imbalance; execution VWAP relative to the frozen
snapshot reference; valid book/trade fractions; execution-present indicator;
and available-history fraction. Book content requires >=90% valid seconds,
trade content >=99%. Otherwise content is suppressed and coverage remains
visible. A valid zero-trade second remains valid; unknown data is distinct.

October source arrays begin Oct1. September30 book/trade history is not silently
invented for early October examples; unavailable bins are explicitly marked.
Prefix sums are only a computation optimization. Block differences access rows
strictly before cutoff, and invalid or future-dated seconds cannot contribute.
This rule is tested by poisoning future rows. All input transforms/scalers are
fit-only. Each original short feature row is recomputed and checked against
the saved0.2 cache, and source byte hashes/partition hashes are verified.

## What this version does and does not test

It tests 24-hour coverage at coarser historical resolutions. It uses the existing
one-second source observations, not subsecond raw messages. It cannot recover
within-second order/trade ordering, individual execution sizes, farther book
levels, or absolute midpoint absent from these arrays. Net depth changes do not
identify exact cancellations, replenishment or order identities. A later raw
event extraction experiment is needed to test those mechanisms. Those claims
must not be attached to this version's results.

## Controlled model comparison

Train two models with identical parameter counts and initialization per seed:

- `short_control`: short branch plus two GRU branches receiving constant zero
  history (matching capacity and compute; no old market content).
- `multiscale`: identical network with the normalized minute/hour sequences.

Both have candle convolution/GRU and short-flow GRU as before, plus GRU16 for
each of the 60 minute and 24 hour sequences. Output is two three-class heads.
Train seeds17/29/43 for each, max20 epochs, patience4, AdamW lr0.0003,
weight decay0.0001, batch128, gradient norm cap5. Loss is primary unweighted
cross entropy plus0.25 secondary colour cross entropy. No class rebalancing.
Model selection is lowest mean three-seed primary development log loss;
inference seed17 fixed. Always report both variants, including if long loses.

Fit Oct1–18, development Oct19–21, calibration Oct22–23, historical benchmark
Oct24–31 2026 UTC. Fit separate scalar temperatures per model/head using the
calibration block and the unchanged0.2 grid. Compare saved0.2 probabilities on
the exact same benchmark examples. Do not retune on benchmark outcomes.

Report accuracy, balanced accuracy, log loss, Brier score, per-class reliability,
confusion, daily paired losses and confidence coverage. Report bullish/bearish
high-confidence groups separately so neutral calls cannot be misrepresented as
directional opportunities. Daily losses are descriptive over eight dependent
days, not proof of significance. No fresh holdout or live accuracy claim.

## Implementation and verification

Training: `python -m research.diwali.multiscale --output data/models/NEW-RUN`.
The completed default run belongs at `data/models/diwali0.3`. Output directories
are never overwritten. Preserve any interrupted preflight separately; an integer
reference dtype edge case discovered by tests was corrected before this run,
and the initial partial run is retained as `diwali0.3-preflight-dtype`.

Private artifacts: causal prefix, prepared feature matrices, frozen source/protocol
hashes, preprocessing, quality coverage, six checkpoints, all training history,
selection, per-model probabilities and report. Public aggregate reports/code
contain no paid raw records, weights, credentials or vendor code.

Replay dashboard: `python -m research.diwali.multiscale_serve --port 8743`.
Ten evenly spaced historical origins; actual labels revealed separately;
inference reads past arrays and saved weights. The original0.2 server stays
on8742. The selected model and both controls are displayed clearly.

Checklist:

- [x] Freeze target, cohort, comparison, capacity and training budget.
- [x] Test history cutoff causality and explicit missing/invalid coverage.
- [x] Test that long history affects only the appropriate model.
- [x] Finish all six fits, separate calibration and shared benchmark.
- [x] Verify checkpoint inference, separate reveal and dashboard.
- [x] Record aggregate findings and stage-specific conclusion below.
- [ ] Fresh unseen/prospective confirmation (deferred).

## Completed result and decision

Completed in 1,294.01 seconds (21.57 minutes), Apple MPS. The longer-history
variant won the predeclared development selection: mean three-seed primary
log loss 1.076443 versus control 1.078106. Each longer-history seed beat its
matching control on development. Selected epochs for both modes: seed17=14,
seed29=11, seed43=10. Inference remains the preselected seed17.

Historical comparison uses the exact same 11,200 origins/references/labels:

| Model | Primary accuracy | Balanced accuracy | Primary log loss (lower better) | Brier sum (lower better) |
|---|---:|---:|---:|---:|
| Diwali0.2 saved sequence | 45.83% | 43.30% | 1.033835 | 0.622785 |
| Diwali0.3 matched short control | 45.15% | 42.94% | 1.038304 | 0.625927 |
| Diwali0.3 longer history | 45.63% | 43.46% | 1.039317 | 0.626561 |

The longer-history model improved accuracy over its matched control, but primary
probability log loss worsened. Relative to0.2, both accuracy and probability
error worsened. Longer history lost on log loss to0.2 on all eight benchmark
days; it beat the matched control on three days and lost on five. The small
development benefit did not carry to the later benchmark.

Exploratory 10,000 day-block resamples (seed17; eight days, neighboring observations
not IID): long-minus0.2 log loss +0.005482, interval [0.003192,0.007966];
long-minus-control +0.001013, interval [-0.000082,0.002240]. This describes the
inspected month, not fresh-market confirmation or a reliable significance claim
across unseen regimes. Temperature was separately fitted per mode/head:
control primary1.122018, colour0.917276; long primary1.188502, colour0.917276.

Long model primary metrics by partition (post-calibration; calibration is itself
in-sample for temperature):

| Partition | N | Accuracy | Log loss |
|---|---:|---:|---:|
| Fit | 24,023 | 50.65% | 0.983110 |
| Development | 4,040 | 41.31% | 1.075204 |
| Calibration | 2,681 | 39.95% | 1.074461 |
| Inspected benchmark | 11,200 | 45.63% | 1.039317 |

Direction-specific benchmark calls from longer history: >=50% confidence190
(90 correct,47.37%); >=60% seven (five correct,71.43%); >=70%, >=80% and >=90%
zero. Seven cases cannot establish a dependable directional edge. There were69
all-class >=70% calls, all neutral, with84.06% outcomes correct; none >=80%.
Candle-colour accuracy48.72% remains weak. No reliable80–20 or90–10 directional
opportunities, trade profitability or live accuracy have been established.

Decision: **retain0.3 as a completed negative experiment; do not promote it over
0.2 or scale it to the full year on this evidence.** This rejects this particular
long-summary setup as an improvement, not all possible uses of longer/raw order
history. Older book/trade representations, full event sequencing and longer
training periods remain untested alternatives, requiring a separate controlled
experiment and new confirmation rather than repeated benchmark tuning.

## Verification

All60 market-data/model tests pass. Real-source minute/hour recomputation of20
bins agreed with prefix summaries within9.34e-7 maximum feature difference,
below0.001 tolerance; coverage matched exactly within numeric tolerance.
All10 checkpoint-backed replay cases matched saved probabilities within4.48e-8
CPU/MPS difference. Actual outcomes remained hidden until Reveal and matched
saved labels. Median model calculation3.97ms, maximum4.81ms across these ten
warm replay calls; this excludes startup/preprocessing and is not a live deadline
measurement. Model startup also checks the saved run-artifact manifest.

Desktop/mobile browser checks cover Predict, Reveal and example switching.
Coverage ledgers are private: mean old-bin book coverage fit96.74%, development
97.60%, calibration96.53%, benchmark99.75%; trade coverage is >=99.07% on
average. These average fractions do not mean every bin passes its quality gate.
All versions see the same cohort; missing older context is masked, not dropped.

The old0.1/0.2 dashboards stay available. The0.3 dashboard at
http://127.0.0.1:8743/ shows both controls and the selected longer-history model.
Public code/aggregate outputs are under `results/diwali0.3`; raw history, cached
arrays, prefix and weights remain private under ignored `data/models/diwali0.3`.
