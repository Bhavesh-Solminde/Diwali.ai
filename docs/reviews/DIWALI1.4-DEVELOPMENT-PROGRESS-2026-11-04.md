# Diwali1.4: training in progress, no final model decision

The study has completed the first fold's six neural fits and baselines, plus both event-convolution fits in foldB. Later fits remain running. Do not treat this document as the completed three-fold comparison, a selected production model or independent September test result.

## First fold, fixed earlier fit and later transfer dates

All rows below score the same896 August16–18 origins, with15 future-close distributions per origin. Two neural seeds are averaged equally here; baseline settings use their fixedseed17where applicable. Lower log loss is better.

| Method | Mean15 price-bin log loss | Final net-direction log loss |
|---|---:|---:|
| Event convolution, mean of seeds17/29 |2.590611|0.687006|
| Event attention, mean of seeds17/29 |2.581623|0.687784|
| Corrected one-second convolution, mean of seeds17/29 |2.577083|0.688120|
| Fit-frequency histogram |2.843222|0.687545|
| Fit-volatility conditional histogram |2.684924|0.687359|
| Flow logistic |3.031402|0.689181|
| Flow boosted trees |2.718260|0.696168|

On this fold, the richer event representations have not beaten the simpler one-second control on the primary range score. Direction scores are close to the constant fit-frequency predictor; direction accuracy alone would overstate the result because55.58%of these endpoints went up. These are overlapping examples across only three transfer days. The full study will use the frozen three-fold/two-seed selection rule, not choose a winner from this table or retune on these outcomes.

The result distinguishes two questions: a newly trained multi-token model can improve the range score against simple histograms here, while retained subsecond detail has not yet established additional benefit over the matched early-compression network. It does not prove that event information is useless, or that the observed advantage generalizes to later dates.

## Errors found and corrected

The first one-second control stopped during transfer inference because float32elapsed time rounded a valid event just below60seconds to60.0. Exact saved availability nanoseconds reveal15 bucket differences across5,391 labelled inputs, including seven fitting rows. The corrected controls are retrained from initialization with integer bucket assignment. There is no clipping or removal of the failed transfer event. The original failed control is retained and excluded, and the four already completed raw-event fits are imported unchanged with hash checks.

Separately, a synthetic input-only probe shows that normalized same-time set pooling can discard multiplicity:1,2or16identical fill vectors give probabilities differing by less than5e-8in both fitted seed17event models. Their projection sees every row, but later averaging can still erase the number of trades. This is a structural counterexample, not proof of the cause of the natural prediction errors. Its practical relevance must be checked before using it to justify a model change. The current study stays frozen.

Follow-up relevance check: the actual18,868,954August input events have18,868,954distinct availability groups. None of the6,484,263market fills shares a group with another fill. The synthetic multiplicity edge case is therefore not activated in this retained cohort and is **not** an evidence-based explanation of its errors. An explicit same-time count addition is not justified as the next fix by that probe alone. The frozen comparison continues unchanged.

## Horizon diagnostic and remaining work

The first fold's fixed logistic diagnostic does not show a simple monotonic relationship between shorter horizon and predictive benefit. It beats its fitted frequency baseline at some horizons and loses at others, including the15thfull-close endpoint. The5/15/30/60-second labels use latest available trade prices, while105/345/945-second labels use full-candle closes. Both bid/ask noise and the endpoint-definition difference limit interpretation. This is a simple-model development diagnostic, not a universal lifetime estimate or entry signal.

September1–14source replay has completed and context construction is running. September15–29remains outside preparation. Final building requires the complete development decision, audited later selection/calibration inputs, separate fit-only transforms and fixedseed17. A final-build runner is implemented but not started. A deliberate one-use final evaluation and later new future-issued forecasts remain required.

The earlier frozen0.9/1.2prospective comparison has also finished and been audited separately: six matched, fully matured,15-close forecasts with nonoverlapping target sets. That tiny session is smoke-test evidence only and cannot confirm1.4, whose weights were not yet fitted when those forecasts were issued.

Sources: `results/diwali1.4/development-progress.json`, `results/event-model-engineering/exact-second-binning-audit.json`, `results/event-model-engineering/diwali14-group-cardinality-probe.json`, and `results/forward-comparisons/diwali09-vs12-spaced-final.json`. Individual predictions, inputs, paid data and weights stay private.
