# Diwali0.5: directly trained probability fan — 4 November 2026

Previous goal turn: progress. Diwali0.4 trained, evaluated and published the first
endpoint price-range model. It beat two range baselines but did not establish a
stable directional improvement or reliable rare high-confidence calls. The
user's broader goal remains active; perfection has not been demonstrated.

## Gap being addressed

The reference purple fan extends across future times. A single closing-time
distribution cannot supply those columns. The old0.1 recursive loop also used
a one-step checkpoint and frozen future context, without training the rollout.
This experiment explicitly supervises15 future candle closes and forecasts
all distributions in one call on the original past snapshot. It does not invent
future orders/trades or reuse actual future market inputs.

## Frozen task, data and boundaries

Inputs remain the0.4 causal1,440 completed candles,60 one-second book/trade
features and observed reference displacement. The reference is the latest
nonempty complete received-second execution VWAP, at most2seconds old; not
absolute midpoint or an executable entry price. Historical candle availability
remains assumed; the source receipt clock is not independently certified.

Horizon1 is the next full-minute candle's close; horizon15 is the15th full-minute
candle's close. At10:01:15 cutoff, first target starts10:02, h1 closes10:03 and
h15 closes10:17. These are not exactly1..15minutes after click. Targets are
future close returns relative to the one frozen reference, not sequential candle
returns. Inference never feeds forecasts back or accesses future labels.

Expand price edges to26 bins using basis points:

`-100,-60,-40,-30,-20,-12,-8,-5,-3,-2,-1,-0.5,0,0.5,1,2,3,5,8,12,20,30,40,60,100`.

First/last tails are unbounded, no target clipping. Upper bounds inclusive
except+2 belongs to bullish. Aggregate bins0–9 bearish,10–15 neutral,16–25
bullish. Collapse the extra tails to the original18-bin grid for an exact h1
comparison with0.4. Both boundary equivalences are tested, including exact+/-2.

Candidate origins are0.4 origins, but all15 target candles must be content-valid
and the whole target span must stay inside its calendar partition. Remove14
origins at each partition end; no additional future-quality exclusion occurred.
Fit24,009; development4,026; calibration2,667; historical comparison11,186.
No training labels may cross into development, and no calibration labels cross
into the benchmark. Old past histories can overlap chronologically when genuinely
available. Outcomes/windows remain correlated and must not be counted IID.

Existing input scalers use fit-period observations only. Purging14 terminal
origins changes supervision, not the fact that those old scaler observations
belong to the fit period. Every retained short input is recomputed and matched
against the parent input cache. Future target content bytes are hash-checked.

## Training and selection

Use the0.4 sequence encoder to obtain33 latent/input-reference numbers. A direct
linear decoder outputs15x26 logits. A separate3-logit head retains h1 candle
colour as auxiliary task. Models have identical architecture and initialization
for each matching seed, differing only in horizon loss weights:

- `equal_horizons`: average categorical cross entropy over all15 horizons.
- `near_weighted`: h1 weight0.5, h2–15 each0.5/14.

Both add0.25 times h1 candle-colour cross entropy. AdamW lr0.0003, weight
decay0.0001, batch128, gradient clip5, max20epochs, patience4; seeds17/29/43.
Checkpoint stopping and architecture choice use equal-average15-horizon
development26-bin log loss. Inference seed17 fixed before evaluation. Always
report h1 and later horizons separately, including if h1 regresses.

Fit a scalar temperature independently for each of the15 horizons on calibration
only, plus one for h1 colour. Use the existing161-point log-spaced0.1..10 grid.
Directions are always sums of calibrated range masses, never independently
contradictory class outputs.

Baselines: per-horizon fit-frequency26-bin histograms and per-horizon conditional
histograms grouped by fixed fit-quartile past15-minute volatility, with add-one
smoothing. No future volatility is used. Compare mean/per-horizon log loss,
ordinal RPS, interval mass/coverage, directional confidence groups, reliability,
daily errors and common18-bin h1 performance against0.4 on matching origins.

October24–31 was already inspected. This remains a descriptive reused benchmark,
not independent confirmation. No reported score may be used to retune0.5.

## Display and probability meaning

The new UI shows26 rows by15 future-close columns, purple opacity encoding
probability mass. Each column sums to100%. Unequal-width bins are displayed as
equal-height table rows, so it is labelled a probability grid rather than a
continuous linear-price density chart. No smoothing is presented as learned
information. Unbounded rows remain visibly open-ended.

Users can inspect a column, see its26 price ranges/directional probabilities,
combine contiguous bins, and reveal all15 actual future closes afterward.
Actual dots are revealed only after prediction; inference includes no target
actuals. Main initial candle bars and colour probability concern h1 specifically.

These are **marginal distributions** at15 closing times, not a joint path model.
Do not claim an80% chance of remaining in the whole fan, infer touch ordering,
connect independently sampled columns into valid trajectories, or price trades
from these alone. A joint/path model and independent prospective testing remain
part of the broader unfinished goal.

## Implementation and checks

`python -m research.diwali.fan --output data/models/NEW-RUN`

`python -m research.diwali.fan_serve --port 8745`

Keep private weights, input matrices, targets, predictions, protocol and
normalization under `data/models/diwali0.5`; publish only code/aggregate reports.

- [x] Freeze direct15-target task, common-grid mapping, training budget and selection.
- [x] Test split-span/quality purging and expanded-to-original bin equivalence.
- [x] Test15 normalized outputs and checkpoint roundtrip.
- [x] Finish six fits, per-horizon calibration and same-origin comparisons.
- [x] Verify all150 replay horizon outputs and revealed labels from ten cases.
- [x] Test rendered grid, horizon selection, range queries and separate reveal.
- [x] Record failures/improvements and next action without declaring perfection.
- [ ] Fresh confirmation, joint path probabilities and high-confidence direction remain unverified.

## Completed results

Six runs completed on Apple MPS in960.83seconds (16.01minutes). Each has28,466
parameters. The predeclared three-seed development comparison selected
`near_weighted`:2.819476 versus2.820063 for equal weighting. Matching seeds17,
29,43 selected epochs14,13,14 for near weighting and14,12,13 for equal weighting.
Deployment remains fixed seed17, not the best benchmark seed.

On11,186 matched October benchmark origins, mean15-horizon26-bin log loss is
2.805561 versus2.921547 past-frequency and2.847118 past-volatility. Equal-weight
model scored2.806389. These values assess probabilistic ranges, not percent wins.

| Future close | Model range error | Frequency baseline | Volatility baseline | Direction accuracy |
|---|---:|---:|---:|---:|
| 1 | 2.635299 | 2.781981 | 2.690340 | 45.71% |
| 5 | 2.778794 | 2.904645 | 2.821568 | 41.16% |
| 15 | 2.876613 | 2.972341 | 2.912606 | 43.73% |

On the identical18-bin h1 grid,0.5log loss2.620042 versus0.4's2.621402,
but ordinal probability error worsened0.139946 versus0.139820. Direction error
1.034119 versus1.034122 is essentially unchanged; direction accuracy fell from
45.95% to45.71%. Therefore this is a useful extension to15 closing times, not
evidence that directional skill materially improved.

H1 made zero bullish/bearish calls at60% or higher confidence; seven at50%
yielded four correct. Its two all-class80% calls were neutral and only one was
correct. Do not call these80–20 directional opportunities. No reliable90–10
directional group was established. At h15, only six directional calls reached50%
and three were correct.

The nominal80% equal-tail bin interval actually carries mean87.98% mass at h1
because whole bins are included; observed coverage87.34%. At h15 the same
construction carries87.04%, observed85.45%. Nominal95% intervals carry97.47%
and97.01%, observed97.23% and97.19%. These are per-time coarse-bin measurements,
not exact80% intervals, simultaneous path coverage or a live calibration guarantee.

## Failure analysis and next action

1. The old recursive point-generation mismatch is removed for this task: all15
   outputs are directly supervised and use one causal observed input. This does
   not make unknown future order arrivals available.
2. Range/volatility estimation improved over simple range baselines, while most
   bullish/bearish probability remains below50%. Increasing the number of outputs
   has not created strong directional information. Broad probabilities are not
   repaired by artificially sharpening them.
3. The33-number common representation and independent horizon heads cannot encode
   conditional dependence among successive future closes. A joint discrete-path
   decoder is a separate next experiment, assessed by a proper joint probability
   score and coherent sampled paths. Independent column samples are not evidence
   of path realism.
4. A previously inspected October benchmark cannot establish fresh performance.
   A bounded forward-only public Binance recorder was launched after model selection.
   It records actual-receipt freezes, immutable pre-target forecasts and separately
   arriving closed-candle labels. Initial warm-up/unverified-book windows were
   rejected; first accepted forecast was saved before its target start. Full sample
   quality review and enough independent days are still outstanding.

`python -m research.diwali.prospective --output data/btc-perp/NEW-CAPTURE --seconds 3600`
uses public read-only feeds and places no orders. It stops on unexpected recorder
failure, rejects missing/stale/future inputs and late forecasts, verifies checkpoint
and scaler hashes, and never replaces committed forecast files. Captures/weights
remain local. This observes future model performance; it does not make its
historical training receipt assumptions independently certified.

## Verification and release

All76 model/market-data tests pass. Live-adapter tests cover relative book
features, common trade sides/reference, receipt cutoffs, stale references,
candle gaps, immutable forecast writes, deferred labels and nonduplicated scoring. Original training source hash matches
the run protocol; source-array hashes independently match recorded manifests.
Ten checkpoint-backed replay cases verified150 horizon distributions and3,900
bin probabilities; maximum saved-versus-CPU difference9.95e-8. Every revealed
bin matches saved target labels; actuals absent from inference response. One
model call per15-column forecast. Warm model calculation median1.02ms,
maximum1.37ms across these ten calls, excluding startup and source preparation.

Headless Chrome at1440px and390px verified Predict,390-cell grid, horizon15
selection, all-bin query100%, zero actual dots before Reveal,15 afterward and
case-switch clearing, with no runtime errors or page overflow. Display is an
explicit unequal-bin probability table, not a fabricated continuous density.

Decision: retain0.5 as an exploratory15-close range baseline; no claim of perfect
probabilities, strong directional edge, profitable trading or a learned joint path.
The broader user goal remains active. Publish code and aggregate results only;
raw data, forecasts tied to raw records, frozen inputs and weights stay ignored.
