# Staged training decisions — 2 November 2026

Current direction agreed in conversation: start small, evaluate honestly, improve
the model, then expand the training history. Do not fit the initial model on the
entire downloaded year. This document updates earlier dataset-size proposals;
historical planning documents remain as provenance.

## Scope and progression

| Stage | Data budget | Purpose and next step |
| --- | --- | --- |
| Validation | Entire downloaded archive | Establish usable coverage, exclusions, clock/sequence quality and independent candle agreement. Validation of a year does not authorize fitting on all of it. |
| Quick pilot | One validated month, plus preceding context | Check feature/label correctness, actual Mac training cost, baseline scores and a small MLP versus sequence-model run. Treat results as exploratory. |
| Main initial comparison | About three validated consecutive months | Proposed practical starting budget for development and more varied evaluation; not a guaranteed minimum or a statistically proven optimal size. |
| Expansion | Additional validated history, progressively | Refit the selected protocol and measure whether more history improves out-of-sample performance. Preserve later unseen data for final evaluation. |

The three-month recommendation follows the user's question about one versus two
months; the user requested that these decisions be documented. Exact dates and
usable sample counts remain pending full audit. Do not describe that recommendation
as proof that one or two months cannot work, or that three months will suffice.

Primary task remains BTCUSDT perpetual next-one-minute candle distribution using
1,440 completed one-minute candles, recent valid visible book data and executions.
Keep the full context; do not shorten it silently for the pilot. Start with fixed
simple baselines, then compare a small MLP and compact sequence model on identical
eligible origins. Train no news model, missing-book estimator, entry model or
synthetic pretraining in this initial scope. Live trading is not authorized.

## Date selection and proposed partitions

Select dates after the full audit, using predeclared quality/coverage criteria and
market variety (quiet, trending and volatile conditions). Never select the month
that happened to give the highest model accuracy. A valid subset has no known
unresolved defects under our checks; no historical month can be certified perfect
or free of every observational limitation.

For the main comparison, the proposed budget is twelve consecutive weeks:

- First six weeks: fitting.
- Next two weeks: development/model selection and improvements.
- Final four weeks: locked testing, untouched until the protocol is selected.

Twelve weeks is approximately three months, not exactly three calendar months.
Freeze exact UTC boundaries, treatment of any extra days and eligible origin counts
before fitting. The one-month pilot also needs a chronological fit/development/test
split; its exact boundaries are not yet specified and must be frozen before runs.
Do not import the entire three-month split into a one-month pilot.

Acquire at least the preceding day for the 1,440-candle warm-up. Past context may
extend into an earlier partition if every value was available at forecast issuance.
Targets must not cross partition boundaries. Exclude origins whose required inputs
or targets are invalid; do not join separated clean intervals as if adjacent in time.
Fit scalers and learned preprocessing only on fitting data. Keep a separate
calibration block within the development budget if probability calibration is used;
freeze that subdivision before fitting rather than calibrating on the locked test.

## Iteration and selection

Use development results for bounded model/feature/hyperparameter changes. Preserve
run manifests, seeds, data exclusions, configurations and unsuccessful results.
Repeatedly tuning against a locked test invalidates its role as an independent
test. If a test result motivates a change, preserve that result and use a new later
unseen period for confirmation. Pilot periods already inspected cannot silently
become the main experiment's untouched final test.

The best version means reliable development improvement over the same baselines
in next-candle error and probabilistic quality, considering uncertainty, coverage
and stability across days. Lowest training loss alone is not the selection rule.
Keep the previously defined OHLC MAE/RMSE, direction/class-balance metrics and
interval coverage/width; training fit, historical unseen error and genuinely matured
forward recent-market error remain distinct. Historical testing is not live error.
No guaranteed accuracy threshold or proven profitability is required to publish an
exploratory baseline, and neither is promised.

Full-year expansion follows the pilot/main comparison, rather than all retries on
one small month until a desirable score appears. Use only validated portions of
the year and leave a later holdout untouched. More data is an experiment to compare,
not an automatic improvement or a reason to consume the final test in training.

## Data limitations and mitigations recorded in this decision

| Limitation | Required handling |
| --- | --- |
| Local hashes prove unchanged bytes, not exchange authenticity | Retain hashes and independent Binance candle reconciliation; propose representative second-provider book overlap, especially volatile periods, without claiming that comparison has already run. |
| Matching candles do not certify every book level | Replay all events with snapshot/sequence/crossing checks; investigate disagreements and compare matching venue sequences where independent data are available. |
| Receipt timing/checkpoint clocks are uncertain | Separate exchange-time experiments from live-availability claims, review causality and issuance delay, and evaluate sensitivity to delays. Do not claim a delayed feature was known at the forecast cutoff. |
| Missing snapshots, halts or empty-book omissions | Invalidate the book; restore from a verified snapshot or independent source where possible; exclude unrecoverable intervals. Do not fabricate replacements. |
| Validator restarts at monthly shard boundaries | Propose replaying verified state across months or earlier-hour warm-up; folder boundaries need not be training or state boundaries. Current conservative exclusions remain until recovery is actually verified. |
| Excluding difficult periods can bias results | Report missingness and retained coverage by time/condition; a clean subset is not proof of reliability during outages or extreme markets. |
| Hidden liquidity is not observed | Do not label estimates as true hidden orders; hidden-book inference remains deferred. |
| Clean data does not prove predictive improvement | Compare untouched chronological outcomes against fixed baselines, with day-aware uncertainty and honest failed results. |

No additional archive purchase, second-source recovery or multi-month training run
is claimed complete by this document. Full validation and date selection are the
current prerequisites. Initial model work is authorized within the user's staged
scope once data, chronology, labels and leakage checks pass; deployment/trading
remain out of scope.

Related documents:
- [First build scope](PHASE-ONE-IMPLEMENTATION-2026-11-02.md)
- [Full data validation](FULL-DATA-VALIDATION-2026-11-02.md)
- [Initial model design](INITIAL-MODEL-PLAN-2026-11-02.md)

Evaluation reference: https://scikit-learn.org/stable/modules/cross_validation.html
