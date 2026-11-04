# Diwali0.7: train individual-close and whole-sequence probabilities together

Previous goal turn: progress.0.6 trained and tested linked15-close probability
paths, improved joint/event scores, and published code/aggregate results as
e1c3928. Its individual-close range scores and direction regressed slightly versus
0.5. The complete user goal remains active; perfection is not established.

## Gap, hypothesis and controlled experiment

0.6 benchmark joint log loss28.15255 beat volatility transition counts29.16847,
but mean marginal range loss2.81034 was worse than0.5's2.80556. These are different
objectives. Conditional errors may accumulate under forward propagation; coarse
bins and finite optimization may matter. These are hypotheses, not isolated
causes.0.7 tests whether explicitly scoring individual closing-time probabilities
during training reduces this trade-off, with a matched additional-training arm.

Keep the exact0.6 architecture21,308parameters and0.5 origins, features, references,
26-bin targets and chronological splits. Check all parent input hashes recorded
by0.6. Start each seed from its corresponding frozen0.6 Markov checkpoint;
optimizer is reset for both arms. No new market/news data, hindsight features or
future orders are introduced. No benchmark tuning during the run.

- `joint_control`: joint conditional NLL averaged over15 steps +0.25colourCE.
- `balanced`: that joint score + unconditional marginal NLL averaged over15
  closing times +0.25colourCE. Coefficient1 is frozen before training.

Generate all26 previous-state transitions from **past input only**. During
balanced training, multiply the learned probability transitions forward and
differentiate through those sums. Actual future bins appear only in loss targets,
not transition generation. This is exact forward marginalization for this
finite-state model, not sampled/teacher-fed marginal prediction. Float32 log
safety floor1e-30 is explicit; joint scores use stable log-softmax.

The logarithmic score is a proper probability score; see
[Gneiting and Raftery](https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf).
Our positive sum of joint and marginal log scores rewards both targets. The
unclipped mathematical joint term retains strict propriety over joint laws;
numerical floors, model restrictions, shared parameters and finite data do not
guarantee calibrated/perfect learned probabilities.

## Frozen training, stopping and calibration

Seeds17/29/43, max20 **additional** epochs, AdamWlr0.0001, weightdecay0.0001,
batch128, gradientclip5. Same shuffled orders per matching seed. Both arms stop
on the same development composite: mean joint NLL perstep plus mean marginal NLL
perstep, patience4. Parent epoch0 is a valid checkpoint candidate, preventing an
unhelpful continuation from automatically replacing it. Choose the arm by mean
three-seed development composite; deployseed17 fixed.

The joint-control training can use shifted conditional logits instead of computing
all unused previous states. Its joint objective and parameter gradients are
tested equivalent. Balanced training necessarily computes all transitions for
marginal gradients. Capacity, data, update budget, selection and calibration match;
actual compute per update differs because of the objective.

For **both** arms, choose one common conditional temperature on calibration data
only,41 logarithmic candidates0.5..2, minimizing the same joint+marginal composite.
Record all candidates and flag boundary selection; do not silently expand it.
This differs from0.6's separate horizon temperatures, so0.7 versus0.6 is not a
single-change attribution. The matched0.7 arms isolate the training objective.
Colour receives its existing separate scalar calibration. Calibration results are
in-sample for that scalar, not an independent test.

Report full joint/marginal scores separately; a better sum cannot conceal a worse
component. Retain0.6,0.5, fit transition and volatility-transition comparisons;
range-event Brier/log-loss reliability, h1 direction and rare-direction coverage;
daily comparisons and adverse results. October24–31 has been examined repeatedly,
so this remains descriptive model development rather than fresh confirmation.

## Verification and implementation

`python -m research.diwali.balanced --output data/models/NEW-RUN`

Parent array/checkpoint hashes and trainer source are frozen in protocol. Private
weights/probabilities stay local; publish only source and aggregate results.
Tests compare differentiable scores/gradients against independent NumPy recursion,
shifted-likelihood gradient equivalence and explicit calibration-bound behavior.

The broader goal still requires stronger direction, reliable fresh performance,
and honest range visualization. No result establishes perfect forecasts or
profitability; no orders are placed.

## Forward0.6 check, kept separate from0.7 training

A follower was started on the existing public receiver's new frozen requests.
It opens no new market-data connection, recomputes each request from then-received
source rows, ignores snapshots predating its startup and rejects late commits.
It writes immutable0.6 forecasts before targets begin and then waits for all15
labels. Forecast issuance is bounded so the last targets can mature before the
receiver's planned shutdown. These forecasts cannot use historical availability
assumptions or be backdated; their actual computation/commit times are recorded.

`python -m research.diwali.forward_follower --source SOURCE --output NEW-CAPTURE --issue-seconds 600`

Joint scores use transition probabilities saved before future labels arrived.
The follower preserves original receiver receipt times and records the receiver
path in its manifest; it is not an independent second receiver. Forward outcomes
are not used for0.7 fitting or selection. Small overlapping samples cannot
certify calibration, market regime coverage or an80–20 directional edge.

## Completed0.7 training and decision

All six fits, common-temperature calibration and exact evaluation completed on
Apple MPS in691.62seconds (11.53minutes). The frozen three-seed development rule
selected `joint_control`: composite4.739935 versus balanced4.743621. Control
checkpoints selected additional epochs12/17/9; all balanced checkpoints selected
epoch1 and stopped after four subsequent non-improving epochs. Parent epoch0
was considered as declared. Deployment remains fixedseed17.

Both calibration searches selected global temperature1.0, with no bound hit.
No benchmark outcomes changed the selection or calibration.

Same11,186 inspected benchmark origins:

| Model | Joint path log loss ↓ | Mean individual-close range loss ↓ | Joint/15 + marginal ↓ |
|---|---:|---:|---:|
| Diwali0.6 | 28.152549 | 2.810344 | 4.687180 |
| Diwali0.7 joint control (selected) | **28.074578** | 2.810822 | **4.682461** |
| Diwali0.7 balanced arm | 28.139057 | **2.807807** | 4.683744 |

The balanced arm improved both components numerically versus0.6 on the benchmark,
but did not win the predeclared development comparison. Do not switch deployment
after seeing this.0.5's direct mean range loss2.805561 remains better than either
0.7 arm. Thus the goal of retaining the best direct marginals alongside better
joint behavior is still unmet.0.7 versus0.6 also changes stopping, continuation
and calibration; the matched0.7 arms are the objective comparison.

Selected h1 direction accuracy45.77%, log loss1.036490.0.5 on matching origins
had45.71% and1.034119: accuracy is slightly higher, but probability error is worse.
H1 bullish/bearish calls>=50%:80 cases,42 correct;>=60%:three cases,two correct;
>=70/80/90%:none. Balanced h1 accuracy45.16%, log loss1.036812. Neither supports
dependable high-confidence directional entries or trading profitability.

For all15 closes staying in the20bp bin union, selected Brier0.155536 versus
0.6's0.155405 and balanced0.156139. This range-event metric did not improve merely
because joint log loss improved; preserve that adverse result.

Exploratory eight-day block comparisons,10,000 resamples seed17, selected minus0.6:
joint-perstep−0.005198 (7/8 days better), marginal+0.000479 (2/8 days better),
combined−0.004719 (7/8 days better). Their respective intervals:
[−0.008555,−0.002263], [−0.002396,+0.003050], [−0.009757,−0.000125]. These are
descriptions of repeatedly inspected, dependent days, not fresh significance.

## Error analysis and next action

1. Continuing optimization helped the joint score modestly, consistent with the
   capped0.6 learning curves. This does not establish better individual ranges.
2. Explicit marginal training reduced fit loss, but its development composite
   worsened after epoch1 for all seeds. That is evidence of poor generalization
   for this coefficient/continuation setup, not proof that marginal scoring is
   inherently wrong. The resulting benchmark benefit in marginal loss does not
   justify overriding development selection.
3. A summed objective can still trade one component against the other; coarse
   first-order states and representation limits remain plausible causes. A next
   architecture experiment should test coupling the stronger direct marginal
   distributions with a coherent dependence model, rather than repeatedly
   adjusting weights on this same inspected benchmark. Any coupling targets must
   be model-predicted probabilities, never actual future prices.
4. Strong unconditional direction is still absent. More confident-looking output
   is not a substitute for information or fresh calibration evidence.

Decision: retain0.7 as a small joint-score continuation and a completed controlled
loss experiment. Keep0.5 as the stronger inspected marginal-range reference.
Do not claim perfection, universal improvement or a new directional edge. The
broader goal remains active, including genuine fresh evaluation.

## Verification

All93 model/market-data tests pass. Differentiable joint/marginal losses match
independent NumPy recursion; the optimized control's parameter gradients match
full transition enumeration. Forecasting takes past features only. Frozen trainer
and0.6 model-definition hashes matched; parent arrays were verified unchanged.

Ten checkpoint-backed cases verified150 distributions and30 joint-range queries.
Maximum saved-vs-CPU bin difference9.66e-8, event difference1.77e-7. Actual bins
matched all150 labels and were absent until Reveal. Median warm calculation1.23ms,
max1.63ms for these calls, excluding startup/source preparation; no live deadline
claim. Desktop1440px and mobile390px browser checks passed Predict, horizon15,
all-bin queries100%, separate15-dot reveal, comparison table and case reset
without runtime errors or page overflow. UI: `python -m research.diwali.balanced_serve --port 8747`.

`audit_follower` separately validates the receiver's original freezes, copied
input hashes, startup/commit/monotonic chronology, frozen0.6 model recomputation
and then-available target outcomes. It audits a shared bounded chronological
prefix while writers are live, verifies complete manifests when present, and
rejects partial appended tails. These checks concern source/computation integrity,
not a claim that seven overlapping origins can establish market reliability.

## Completed forward0.6 smoke check (not0.7 performance)

The follower issued seven forecasts from new, source-verified freezes, then stopped
issuing and waited. It exited normally with all seven15-close paths complete,
105 outcomes verified and zero pending paths. Each forecast was committed at
least44.58seconds before the first target start; recomputed initial, transition,
marginal and direction probabilities matched exactly. Source and follower journals
remain separately identified; the underlying receiver was still recording when
the bounded audit ran. Its eventual full capture is not claimed complete here.

Matched same-input, same-reference prospective comparison:

| Model | Whole-sequence error ↓ | Mean individual-range error ↓ | H1 direction correct |
|---|---:|---:|---:|
| Diwali0.5 independent product | 43.175942 | 2.878396 | 4/7 |
| Diwali0.6 learned chain | 35.208282 | 2.792951 | 1/7 |
| Fit volatility-transition rule | 39.856675 | 2.995692 | 5/7 |

Range/joint improvements in this tiny session coexist with weak direction. All
seven paths left the20bp union at some closing time. The0.6 mean stay probability
was14.99%, versus30.18% for the volatility rule and0.037% for the independent
product. Do not report only favorable metrics, infer a direction edge, treat105
overlapping outcomes as105 independent forecasts, or present this as a multi-day
calibration study. No model was retrained from these outcomes.

The forward checkpoint was frozen0.6, not0.7.0.7 fitting/selection used only the
predeclared October arrays and development criterion. The seven forward origins
are now inspected evidence; they cannot be reused as fresh confirmation for
subsequent models influenced by these findings. Next versions require new
pre-target forecasts after their own selection.
