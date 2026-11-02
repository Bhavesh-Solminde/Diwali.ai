# Initial model plan v2 — 2 November 2026

Status: design for review. No training or live trading authorized by this plan. Supersedes conflicting design choices in the earlier frozen proposal; retain historical research/provenance. Simulator research is sufficient to choose experiments, but its defective outputs are not approved training records. This is our independent design, not a verified reproduction of Tiger.

## 1. Product behavior

For BTCUSDT perpetuals on a single exchange, use 1,440 completed UTC one-minute candles, current/recent observable order-book information and executions to predict the next one-minute candle distribution. Bullish/bearish/neutral news supplies context: it changes the estimate according to relevance, novelty and observed order/trade response; it does not override the book with a mandatory direction. News missing/unavailable is a separate state from neutral news.

Show one representative valid candle, sampled alternatives or component intervals, and calibrated up/neutral/down probabilities (initial direction threshold ±1 bp versus origin close). Interval coverage is not trade-win probability and component intervals are not a joint whole-candle coverage guarantee. Do not display unvalidated confidence as 80% or 90%.

Entry quality is a separate task: probability that a defined long/short policy reaches its target before its stop within its expiry. Initial research policy remains 1 ATR14 stop, 2 ATR14 target, 15-minute expiry; ATR uses completed candles only. A wait alert needs a defined trigger and a new prediction at trigger time. Long, short, wait and skip are product actions, not interchangeable direction classes. Deployment is out of scope.

## 2. Inputs and data contract

| Input | Initial design | Required quality information |
|---|---|---|
| Candles | Prior 1,440 completed minutes; returns, body/range/wicks, base/quote volume and time encodings | Source, closure, gaps, instrument, scale and actual availability |
| Book | Top 20 visible levels; 60 seconds of one-second summaries; spread, covered-depth imbalance, distance/persistence and net changes | Sequence validity, segment ID, age, covered price range and per-feature mask |
| Executions | Prior 60 seconds; signed quantity/notional, trade count, execution pressure and price response | Trade IDs, aggregation/exclusions, duplicates, timestamps and coverage |
| News | BTC-relevant bullish/bearish/neutral sentiment plus relevance, novelty, confidence, source and age | Original publication/first-seen times, deduplicated event ID, missing state and model/version |

Depth summaries at 1/5/10/25 bp are used only where the recorded feed covers the band. No extrapolation of top-20 depth to unknown distant levels. At each decision record exchange cutoff, receipt times, actual issue time and maximum eligible sequence/trade IDs. Never add target-minute trades already received into the past context while claiming a full-minute advance prediction. Measure issuance delay; late-origin forecasts are labeled or rejected under a predefined policy.

Use independent immutable exchange candles as a separate source if aggregate execution coverage cannot reconstruct exchange OHLCV. Reconcile sources and retain exclusions/discrepancies; never silently treat an incomplete aggregate stream as complete trade history.

News examples: bearish news plus aggressive sales and vanishing bids may increase downward probability; bearish news plus strong absorption/refill may give a different estimate. Bullish news has symmetric questions. Neutral news need not have zero effect because event importance/uncertainty can change volatility. Unknown/no news must not be assigned neutral sentiment. Macro surprise is available only after release; pre-release consensus is a different feature. Store the text version first available, not later revised content. Freeze any sentiment model and avoid future price outcomes as sentiment labels.

## 3. Missing-book fallback

Actual valid data has priority. When a subset is missing, use causal candles/volume and available executions to estimate coarse pressure, depth imbalance or probable liquidity concentration, with uncertainty and explicit missing/estimated flags. Never claim an exact full order book, hidden reserve, order ID or whale identity from candles. If the entire feed is stale/gapped, invalidate the book until resynchronized and consider skip rather than replacing it with confident estimates.

Train/test the auxiliary estimator on periods with paired candles and genuine valid books. Mask missing fields using realistic outage lengths/coverage patterns. Separate: pressure estimated from candles, exact book observed, partial book and fully unavailable book. A retained historical book must be stored as stale, not relabeled current. Train-only feature generation for the downstream model must use out-of-fold/time-causal estimator predictions, not in-sample fitted reconstructions; holdout estimators must never fit holdout data. Evaluate estimator quality and downstream forecasting/calibration under each missingness mode. Back off or skip when uncertainty is excessive. The fallback cannot restore unavailable information uniquely.

## 4. Model experiment sequence

1. Fixed last-close/rolling candle distributions, majority chosen on training data, momentum, reversal and simple book imbalance on identical origins. Include probabilistic baselines and class balance/coverage.
2. Small MLP combining causal multi-scale candle summaries, book/trade features and availability masks. Keep all 1,440 candles in the source context, but document the information compressed into summaries.
3. A compact causal temporal encoder using the 1,440-candle sequence, a short book/trade encoder and a fusion/output head. Match information, splits and evaluation budgets with the MLP. Let measured validation results determine whether added complexity is useful; approximately 7M parameters is only an initial ceiling candidate, not a target to fill.
4. Add the fixed news representation as an explicit context branch; compare against the identical no-news model on matched origins. Separate before-news and post-news contexts, news classes, release surprises and no-news periods.
5. Add missing-book estimation only after actual-book forecasting and paired-data feasibility pass their checks. Compare candle-only, actual book, masked book without estimates, and masked book with estimates under fixed missingness. Retain direct observable uncertainty and masks.

Primary output: a distribution over gap/body, nonnegative upper/lower excursions and nonnegative volume, decoded into valid positive OHLCV. Predict next open separately from previous close. Train an explicit conditional distribution or valid quantiles and report their actual calibration. Direction probabilities should be derived consistently from the predicted close distribution or checked for consistency if using a separate head.

Do not generate a long path by feeding actual future books/news into a rollout. The first build predicts one candle only. Entry-quality modeling follows verified ordered execution labels and is not implied by a successful candle model.

## 5. Collection and splits

First build durable same-venue acquisition: bootstrap snapshots, sequence continuity, resnapshot after gaps, reconnect, storage manifests, time/clock monitoring and reconstruction checks. Inventory existing data before choosing dates; the brief engineering capture is not enough for training.

Use chronological training, model-selection validation, probability-calibration and untouched testing. Proposed prospective-book budget remains 60 usable days training, 10 selection, 5 calibration and 15 final test; actual sufficiency depends on independent days/events, class/regime balance and learning curves, not minute-row count alone. Start collection early. An earlier candle-only baseline can use independently verified history and must be labeled as such.

Purge origins whose target/entry horizon overlaps another partition. Past context may legitimately extend into the previous partition if it contains only information already available at issuance. Fit scalers, thresholds, feature selection and learned estimators on fitting partitions only; calibrate separately. Keep no future revisions, random overlapping-window splits or holdout-driven revisions. Group news event copies consistently and disclose repeated-event dependence. Keep original test results after changes; use later data for another honest test.

No simulator records enter the initial training set. A later corrected synthetic-data proposal needs its own invariant tests and real-only versus synthetic-pretrained comparison on the same real holdout.

## 6. Evaluation and entry policy

Display the requested three panels using the same documented metrics: training fit error, locked historical unseen error, and recent real-market error on matured immutable forward predictions (24 hours with 7-day context). Internal validation and calibration remain separate. Recent error measures known past predictions, not the next unknown outcome. Historical holdout does not automatically become live recent performance.

Metrics: OHLC MAE/RMSE in USDT and bp, volume error separately, probabilistic score, interval width/coverage, direction confusion/per-class/balanced accuracy, and missingness/latency coverage. Report performance by independent day/regime, news class/age, liquidity, volatility and observed versus estimated-book mode. Parent bootstrap for simulator diagnostics does not substitute for day/event-aware uncertainty on real BTC.

Entry labels: target-first, stop-first, timeout and untriggered where applicable, using executable bid/ask and ordered events where possible. If outcome order is unobservable, preserve ambiguity or bound results. No arbitrary wins. Calibrate on a separate period, report coverage and confidence intervals, and compare against the same-action baseline. An 80–20 or 90–10 binary phrase is allowed only when the outcome/timeout convention is explicit; otherwise show all outcome probabilities. Rare high-confidence predictions require enough independent support.

A 50–50 estimate is not enough by itself to define economic quality. Use expected payoff after costs, uncertainty, liquidity and maximum adverse exposure, as well as a reviewed probability threshold. Keep the user's desired skip-uncertain/consider-favorable behavior, but do not claim an 80% success rate guarantees profitability. Use measured venue fees/spread/latency/funding where available; separate stress assumptions. No real trades in this phase.

## 7. Build order and acceptance gates

| Stage | Concrete output | Gate before next stage |
|---|---|---|
| A. Dataset inventory and recorder | Data manifest, causal snapshots, durable collector and quality report | Valid timestamps, resync/gap handling, instrument/units, adequate paired coverage |
| B. Label builder and baselines | Valid next-minute candles, chronological partitions and fixed-rule scores | Reconstruction/provenance checks, no leakage, strongest simple baselines |
| C. Small real-only candle/book/trade experiment | MLP versus compact sequence protocol; measured hardware pilot | Reviewed dataset/splits/training budget and reproducible run manifest |
| D. News increment | Matched no-news/news experiments and timestamped classifier records | Point-in-time news coverage and held-out incremental benefit/calibration |
| E. Missing-book estimator | Realistically masked evaluation and explicit uncertainty | Beats masked baseline without contaminating real-book inputs or calibration |
| F. Entry quality and viewer | Ordered-outcome labels, calibrated decisions, immutable chart predictions | Valid outcomes/costs, acceptable calibration and clear coverage; review before forward paper phase |

Profile full 1,440-context workloads on the actual machine before choosing batch/size. M5 32GB is the known Mac configuration; Windows GPU availability may differ. Record throughput, peak memory and numerical stability. Compare seeds 17/42/101 where feasible within the reviewed budget. Do not infer full-context performance from older shorter-context tests.

First implementation recommendation: stage A plus label/quality contracts, then present the actual dataset manifest and stage-B/C experiment plan. This document is a planning deliverable, not a claim that those gates already pass.
