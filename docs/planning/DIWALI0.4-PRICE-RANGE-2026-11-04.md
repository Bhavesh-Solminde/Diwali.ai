# Diwali0.4: calibrated closing-price ranges — 4 November 2026

Previous goal turn classification: progress. Diwali0.3 was built, trained and
tested; its longer-history experiment worsened the inspected benchmark relative
to0.2. The broader goal remains active, with no claim of perfect probabilities.

## Error diagnosis and actual objective

The user's goal references both three-outcome bars and a purple price-uncertainty
area. Those images were visually inspected on this continuation. The existing
three-class model cannot answer arbitrary price-range questions or justify a
continuous future-path cloud. This is a target/output limitation, not a cosmetic
UI problem. Diwali0.4 therefore trains an endpoint return distribution instead
of merely redrawing0.2's three probabilities.

The0.3 result also shows a generalization issue: all three longer-history runs
beat their matching controls on development, but selected seed17 worsened later
probability error. Adding coarse old history is not supported by that experiment.
The following run returns to the0.2 short-input representation to isolate the
distributional target and loss. It does not claim to fix within-second event loss.

A diagnostic checked flat candles before deciding whether data corruption was
responsible: training had1,144 exact flat-body targets among24,023; benchmark337
among11,200. None had zero volume or execution count. Flat-body candles have
much smaller average ranges than other candles; flat does not imply an empty
or fabricated candle. Source reconciliation and known arrival-time limitations
still apply. No new unexplained data rows were removed.

## Frozen experiment

Keep exact0.2 origins, reference VWAP and freshness exclusions, timing, input
arrays/scalers, fit/development/calibration/shared benchmark partitions. Every
cached short input is recomputed from source and matched; partition bytes and
target equivalence are verified. Scalers remain fit-only.

Target: closing return at the end of the next full calendar minute, relative
to the observed latest received-second VWAP before cutoff. It is not the next
tick, current candle remainder, rolling60seconds, high/low or a future path.

18 categories with fixed edges in basis points:

`-20, -12, -8, -5, -3, -2, -1, -0.5, 0, 0.5, 1, 2, 3, 5, 8, 12, 20`.

The first/last bins include unbounded tails; targets are never clipped. Upper
edges are inclusive except+2, which belongs to the bullish category. Direction
is always computed coherently by summing bins0–5 bearish,6–11 neutral,12–17
bullish. This reproduces the existing <=-2 / strictly between / >=+2 labels,
including exact boundary cases. No independent direction head can contradict
the range probabilities. Candle-colour is a separate secondary head.

Architecture: unchanged small0.2 sequence encoder, replaced final output layer
with18 range logits plus3 secondary colour logits. Compare two losses with
identical architecture/seeds: categorical cross entropy, versus the same loss
plus0.5 times mean ranked probability score over17 thresholds. Both include
0.25 times secondary colour cross entropy. RPS respects ordered categories;
it is not labelled continuous CRPS or a dollar-unit price error.

Train seeds17/29/43 per loss, max20epochs, patience4, AdamW learning rate0.0003,
weight decay0.0001, batch128, gradient clip5. Select by mean three-seed
development18-bin log loss, deploy seed17 fixed. Separately calibrate range
and colour scalar temperature on calibration only using the existing bounded
161-point grid. Do not choose models based on benchmark scores.

Baselines: fit-frequency18-bin histogram with add-one smoothing; a fit-only
conditional histogram grouped by quartiles of past15-minute realized volatility.
Use identical groups/transforms on later periods. Compare aggregated direction
with0.2 and the volatility baseline on identical origins. Do not equate18-bin
accuracy or log loss with three-class metrics; report each explicitly.

Report18-bin log loss, ranked probability score, class counts and calibration
of equal-tail bin ranges (80/95% requested mass). Coarse-bin intervals may
contain more predicted mass than requested; report both mass and actual coverage.
Tail intervals can be unbounded, so do not manufacture finite endpoints or means.
Report primary three-class metrics, per-class reliability, daily results and
directional confidence groups. Calibration-block coverage is in-sample for
temperature; October benchmark is already inspected and not fresh confirmation.

## Display contract and sources

The UI may show learned probability for each price range at the target close,
with probabilities summing to100%, and the derived bearish/neutral/bullish bars.
It must not smooth bins into an unstated continuous density, extrapolate a
15-minute path or suggest a target-before-stop win rate. A time-varying fan
requires a separately trained and validated multi-horizon/path model later.

Primary research considered:

- [Imani & White, distributional/histogram losses](https://proceedings.mlr.press/v80/imani18a/imani18a-supp.pdf).
- [Gasthaus et al., probabilistic forecasting with spline quantiles](https://proceedings.mlr.press/v89/gasthaus19a.html), an alternative distribution representation, not implemented in this version.
- [Haas et al., ordinal ranked probability score](https://proceedings.mlr.press/v337/haas26a.html). This run does not implement their conformal method or claim its guarantees.

Our bin choices, losses and BTC experiment are proposals tested here; the papers
do not prove BTC accuracy, profit or perfect calibration. A finite historical
sample cannot certify exact true market probabilities. We will preserve version
comparisons and require new confirmation rather than repeatedly tuning the same
benchmark until its score looks perfect.

## Artifacts and checks

Training command: `python -m research.diwali.distribution --output data/models/NEW-RUN`.
Default run: ignored `data/models/diwali0.4`. Preserve protocol, source hash,
preprocessing, baseline definitions, six checkpoints, all runs, temperatures,
range/direction predictions and report. Public copies contain only aggregates
and code, no raw paid records, API keys or weights.

- [x] Inspect both user reference images and diagnose the missing range output.
- [x] Freeze boundaries, aggregate-label equivalence, tails and comparison budget.
- [x] Test boundary/tail handling, probability conservation, ordinal score and checkpoint roundtrip.
- [x] Complete fits, calibration and shared historical comparisons.
- [x] Verify endpoint-range replay and reveal against saved probabilities/labels.
- [x] Record strengths/failures and next evidence-based experiment.
- [ ] Fresh unseen/prospective confirmation and time/path probability model remain outstanding.

## Completed results

Completed in800.43seconds (13.34minutes), Apple MPS. Both variants contain15,818
parameters. Categorical selected by mean three-seed development18-bin log loss:
2.657648 versus ordinal penalty2.657702. Selected epochs were14/6/12 for seeds
17/29/43 in both variants; inference seed17 fixed. Range temperature1.0,
colour temperature0.917276, fitted only on calibration.

Same11,200 historical comparison origins:

| Endpoint distribution | 18-bin log loss ↓ | Ordered RPS ↓ |
|---|---:|---:|
| Fit-frequency baseline | 2.767114 | 0.144828 |
| Past-volatility baseline | 2.674561 | 0.141778 |
| Diwali0.4 categorical | 2.620776 | 0.139715 |
| Diwali0.4 ordinal penalty | 2.620849 | 0.139714 |

Both neural variants improved range probability scores over these baselines.
The ordinal penalty did not materially improve the result. Exact18-bin hit
accuracy11.72% is a different task from three-way direction accuracy.

Derived direction: categorical45.99% accuracy,43.49% balanced accuracy,
log loss1.033664, Brier sum0.622695. Saved0.2:45.83%, log loss1.033835.
The new directional difference is tiny. An exploratory paired eight-day
bootstrap (10,000 resamples, seed17) gives log-loss difference -0.000171,
95% interval[-0.001349,0.000818]; only3/8 days improved. This is not evidence
of a stable directional improvement across new markets.

Directional confidence remains weak:49 bullish/bearish calls at>=50% confidence,
21 correct (42.86%); zero at>=60%,>=70%,>=80% or>=90%. Among12 all-class
>=80% calls, all neutral, seven were correct (58.33%). This rare confidence
group is poorly verified and does not justify an80–20 claim. The model's
aggregate range skill does not establish high-confidence direction or trades.
Candle-colour accuracy48.39% remains weak.

| Requested equal-tail bin mass | Mean predicted mass after bin expansion | Observed coverage | Unbounded tail endpoint fraction |
|---|---:|---:|---:|
| 80% | 87.89% | 87.45% | 0.71% |
| 95% | 97.63% | 97.52% | 9.06% |

Coarse bins expand the selected interval: do not call the first row an exactly
80% calibrated interval. Coverage is aggregate on inspected history, not a
conditional guarantee for every snapshot, nor an all-times path guarantee.

Decision: retain0.4 as the first learned **endpoint price-range** model, with
range-baseline improvements and an honest histogram/query UI. Direction remains
approximately0.2-level; do not claim perfection, reliable directional entries,
live accuracy or full time-varying path probabilities.

## Verification and remaining error regions

All64 market-data/model tests pass. All10 checkpoint replay examples match
saved18-bin probabilities within3.35e-8 CPU/MPS difference, sum to1 and exactly
aggregate into the three displayed directions. Separate Reveal returns the
correct stored price bin and outcome. Warm replay calculation median0.82ms,
maximum1.17ms; startup/preprocessing/live network delays excluded. Browser
desktop1440px/mobile390px checks pass Predict/Reveal,18 price bins, combining
all bins to100%, and clearing old forecasts after example switching.

The source hash matches its frozen protocol. Raw records and weights remain
private. Reports, bin definitions and checks are aggregate public artifacts.

Remaining work has two distinct parts: (1) the requested fan over future times
needs explicitly trained multiple horizons; a single close distribution cannot
provide that; (2) rare directional/high-confidence claims remain unsupported,
and repeated October comparisons cannot become fresh evidence. A next version
can test direct multi-horizon range supervision without recursively freezing
future inputs, compare its horizon1 forecast on matching origins with0.4, and
preserve per-horizon calibration and real independent confirmation requirements.
It must not connect independently sampled horizon bins into supposedly valid
price paths or report marginal bands as simultaneous path guarantees.

Posthoc error-region check, not used to retune0.4: grouping the benchmark by
fit-only past-volatility quartiles, range log loss was2.48078/2.58222/2.64567/
2.71200 versus conditional baselines2.54322/2.61199/2.67470/2.80356. Range skill
exceeded that baseline in all four groups. Primary classification accuracy
varied60.46%/47.51%/38.52%/42.68%; different outcome frequencies prevent treating
these raw accuracies as directly comparable measures of directional skill.
The five failed>=80% neutral calls actually moved to four bullish outcomes and
one bearish outcome. This is observed underestimation of movement in those cases,
not proof of which news/order event caused it. `error-regions.json` preserves
the diagnostic, and the broader goal remains active.
