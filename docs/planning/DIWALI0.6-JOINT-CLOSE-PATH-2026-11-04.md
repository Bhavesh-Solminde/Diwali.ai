# Diwali0.6: joint discrete future-close paths — 4 November 2026

Previous goal turn: progress.0.5 finished six fits, tested15 marginal closing-time
forecasts and was pushed as824b871. Its range scores beat simple frequency and
volatility baselines at every horizon, but directional confidence remained weak.
The broader goal remains active; perfect probabilities are not established.

## Concrete gap and method

0.5 predicts15 separate distributions. It does not define probabilities for an
entire future close sequence.0.6 adds explicit dependence between successive
future price bins. It models:

`P(y1|past) * product(h=2..15) P(yh|past, y(h-1))`.

Each y is one of the same26 closing-price bins relative to the frozen reference.
This is a first-order future-bin Markov approximation, not a claim that market
dynamics have only one-step memory. Past context still includes1,440 candles and
the observed60second book/trade input. Unknown future orders remain unknown.

Autoregressive likelihood forecasting is established in
[DeepAR](https://arxiv.org/abs/1704.04110). Exact finite-state forward summation
uses the standard transition recursion described in
[Rabiner's tutorial](https://www.fceia.unr.edu.ar/prodivoz/Rabiner_1989.pdf).
This implementation is our categorical context-conditioned Markov design; it is
not a reproduction of DeepAR or a hidden-state HMM.

Training/scoring uses the observed previous target bin to evaluate conditional
likelihood. A prediction call receives **past input only**, enumerates all26
possible previous states, and sums their probabilities forward. No actual future
bin is supplied during forecasting. Marginals are exact for this model, without
sampling noise. A coherent probability exists for every26-state15-step sequence.

## Frozen comparison and settings

Reuse0.5's identical origins, features, reference and26-bin targets, including
14-origin split-boundary purges. Verify parent array hashes, recomputed labels and
calendar endpoints. FitOct1–18, development19–21, calibration22–23, benchmark24–31.
The benchmark has been inspected in older versions; it is descriptive, not fresh.
No news, invented liquidity or additional markets are introduced.

The same33-number past encoder feeds a first-close26-logit head and a shared
conditional decoder. The decoder combines past context33, previous-bin embedding8
and horizon embedding8, then linear49→64, GELU and linear64→26. An auxiliary
three-class candle-colour head remains. Two variants have identical trainable
capacity and matching random initialization:

- `independent_control`: future previous-bin input always receives a fixed token.
- `markov`: future previous-bin input receives the shifted actual label in
  likelihood training; inference enumerates every possible previous bin.

Train seeds17/29/43, max20epochs, patience4, AdamWlr0.0003, weightdecay0.0001,
batch128, gradientclip5. Loss mean15 conditional categorical cross-entropies plus
0.25h1 colour CE. Stopping uses development **joint path log loss**, summed over
15 steps per origin. Choose architecture by three-seed mean, deploymentseed17
fixed before evaluation. Each conditional horizon gets a scalar temperature on
calibration only (existing161point0.1..10grid); colour calibrated separately.

## Required evidence

Compare joint path log loss with the matched independent control,0.5 product of
marginals, fit-only Markov transition counts and fit past-volatility-quartile
Markov transition counts. Add-one count smoothing; no benchmark adjustments.
Per-step joint log loss is total divided by15 and labelled distinctly from
unconditional marginal log loss. A lower conditional error must not be presented
as high-confidence unconditional direction accuracy.

Report exact marginal range scores and direction reliability at all15 horizons,
including regressions. Report daily joint errors, rare-direction confidence and
event Brier/log loss for all15 closes staying inside a fixed bin band, and at
least one close entering it. Predeclared bin unions: indices8–17,6–19,5–20
(approximately±5,±12,±20bp; use actual edge inclusivity). Compare the same events
with volatility-conditioned Markov counts. Brier/log loss are proper scores;
raw frequency alone is not a calibration proof.

Tests must show exact recursion matches exhaustive toy path enumeration;
future labels affect only the shifted conditional during likelihood evaluation;
the independent control ignores previous-bin values; prediction requires no
future labels; normalization, gradients and checkpoint roundtrips work.

## Limits retained

These paths concern only15 full-minute **closing prices**, not intra-minute
trajectories, candle highs/lows, target-before-stop ordering or executable trades.
Within-bin state is unknown; tails are unbounded. First-order bins can discard
useful future dependence, and uncertainty about fitted parameters is not solved
by normalization. Historical receipt/availability assumptions remain. A separate
0.5 forward-only capture is running; it is not0.6 prospective validation and is
not used to train/tune0.6. Enough fresh independent evidence is still required.

Training: `python -m research.diwali.path --output data/models/NEW-RUN`.
Raw inputs, targets and weights remain local; publish only source and aggregate
reports. Do not overwrite an existing run directory. Preserve adverse results.

## Completed experiment

Six fits completed on Apple MPS in1,016.28seconds (16.94minutes),21,308 parameters
each. The three-seed mean development joint log loss selected `markov`:28.920590
versus42.289387 independent control. All three Markov seeds selected epoch20;
controls selected14,11,9. Deployment remains predeclared seed17, not a benchmark
winner chosen among seeds. The recorded trainer source hash remained unchanged.

Same11,186 benchmark origins and labels:

| Model | Whole15-close path log loss ↓ |
|---|---:|
| Diwali0.5 product of separate marginals | 42.083419 |
| Diwali0.6 matched independent control | 42.071553 |
| Fit-only transition counts | 29.289384 |
| Fit-only volatility-conditioned transition counts | 29.168473 |
| Diwali0.6 learned Markov chain | **28.152549** |

The joint score beat the volatility-count baseline on all eight benchmark days.
Exploratory10,000 day-block resamples, seed17: paired mean difference−1.015924,
interval[−1.119157,−0.922425]. This describes eight inspected, dependent days;
it is not fresh-market significance or a guarantee of future accuracy.

The improvement does **not** carry to every objective. Mean unconditional
15-horizon range log loss worsened from0.5's2.805561 to2.810344. H1 range loss
2.638036 versus2.635299, direction log loss1.036761 versus1.034119, direction
accuracy45.17% versus45.71%. H15 range loss2.887653 versus2.876613.

H1 had79 bullish/bearish calls at50% confidence (42correct,53.16%); only three
at60% (two correct), none at70%,80% or90%. No dependable80–20/90–10 directional
entry or profitable trading claim is supported. Conditional likelihood scores
must not be presented as unconditional directional accuracy.

## Range-event probability results

These concern closing times only, using the exact predeclared bin unions.
`20bp` means the union(−20,+20]bp around the observed reference, not a stop/target
or a claim about intra-minute excursions.

| All15 closes inside band | Mean claimed probability | Observed frequency | Model Brier ↓ | Volatility-count Brier ↓ |
|---|---:|---:|---:|---:|
| 5bp | 5.52% | 7.24% | 0.061426 | 0.063137 |
| 12bp | 40.14% | 42.28% | 0.188515 | 0.227568 |
| 20bp | 69.63% | 68.85% | 0.155405 | 0.218984 |

For20bp stay-event claims between80% and90%,2,784 cases averaged85.04% and
observed87.25%. For claims>=90%,2,065 cases averaged93.81%, observed91.38%.
For12bp stay-event80–90% claims,468 cases averaged84.26%, observed79.49%.
These show useful but imperfect range-event reliability on the inspected month,
not a high-confidence bullish/bearish forecast. Overlapping cases are correlated.
All six fixed stay/visit event Brier/log-loss comparisons improved over the
volatility-count baseline; complete reliability tables retain the adverse bins.

## What remains wrong and next experiment

1. Separate0.5 columns assumed independence when multiplied into a whole path.
   Controlled comparison strongly supports replacing that assumption for joint
   scoring.0.6 now defines a coherent discrete path law and exact event queries.
2. Better conditional likelihood did not improve unconditional marginals. This
   is an observed trade-off. Conditional-bias accumulation, coarse-bin state and
   optimizing joint rather than marginal error are plausible mechanisms, not
   experimentally isolated root causes. The next version should test retaining
   the better direct marginal forecasts while learning coherent dependence, or
   a controlled joint/marginal objective. Do not merely sharpen probabilities.
3. All Markov fits reached their budget at their best epoch and were still
   improving on development. Optimization may be incomplete; a longer-budget
   controlled follow-up is justified, but improvement is not established yet.
4. Fresh0.6 validation and calibration remain absent. The forward recorder below
   uses0.5, not0.6. Do not attribute its results to this new checkpoint.

Decision: retain0.6 as a better exploratory **joint close-sequence** model; retain
0.5 for its better individual-close range score. Neither meets the full goal of
perfect probabilities or dependable high-confidence direction. The goal remains
active. October has influenced repeated model design and is not a fresh test.

## Replay verification

Local UI: `python -m research.diwali.path_serve --port 8746`.
It shows the15-column range table, separate actual reveal, baseline errors and
range-event reliability. The range selector now also asks for the probability
that all15 closes stay inside, or at least one closes inside. Both use exact
forward sums. All-bin query is100%; invalid bounds clear stale results. A
Revealed result is added only after Reveal and never changes the forecast.

All85 model/market-data tests pass, including exhaustive toy path equivalence,
shifted future-label causality, independent control, checkpoints and gradients.
Ten replay cases checked150 marginal distributions,3,900 range probabilities
and30 fixed path-event queries against saved outputs. Maximum probability
difference1.30e-7; path-event difference1.57e-7 CPU/MPS. All revealed bin labels
matched. Median warm model calculation1.17ms, max1.57ms in these ten calls,
excluding startup/source preparation. These are not live deadline measurements.
Desktop1440px and mobile390px browser checks cover horizon selection, range
queries, separate reveal, calibration table and case reset without errors/overflow.

## Forward evidence and collector correction

An independent source-replay audit of the first0.5 forward recording verified
63,963 records, three frozen inputs/forecasts and all45 future-close outcomes.
Forecasts reproduced exactly and were committed at least44.94seconds before
their first target start. Three origins are far too few to establish performance;
their45 overlapping outcomes are not45 independent forecasts. The recording was
closed deliberately only after all pending labels arrived.

The finished capture's raw bytes also matched its complete manifest; the audit
rejects appended/modified bytes and duplicate outcome horizons.

The capture exposed a collection defect: continuous depth IDs do not guarantee
that price remains within the finite initial REST snapshot bounds. Quality gates
correctly rejected those views, but the collector did not request a new snapshot.
`collect.verified_top` now forces reconnection/resnapshot when the current top20
extends outside verified bounds. Its regression test simulates depletion beyond
known depth and verifies recovery only after a genuinely new snapshot. No quality
gate was relaxed. Existing download workers/data were untouched.

A separate0.5 recording with the fix is running. An early bounded-prefix audit
verified10 new pre-target forecasts and36 then-matured outcomes, reproducing all
probabilities exactly. That capture was still running, not a finished accuracy
study. Source hashes are recorded locally. No orders were placed.

`python -m research.diwali.audit_forward CAPTURE --run data/models/diwali0.5`
verifies a bounded source prefix, reconstructed freezes, input/forecast hashes,
actual commit deadlines, checkpoint recomputation and source-backed outcomes
as they were available at scoring time. It labels incomplete captures honestly;
none of this independently certifies historical provider receipts, hidden
liquidity, sustained model calibration or trading effectiveness.
