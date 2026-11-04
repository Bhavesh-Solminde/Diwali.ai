# Diwali0.1–1.3: progress, limitations, and the next research direction

Prepared2026-11-04 from the committed experiment reports, training source, model contracts and prospective audit records. This is a review, not a new training run. Version numbers describe experiments, not guaranteed upgrades. There were13 versions and multiple controlled fits per version; these were not13 radically different architectures.

## Main finding

We built a substantially better probability-forecasting **system**, but have not demonstrated a strong directional **predictor**. The current system predicts price-range distributions for15 future candle closes, keeps direction consistent with those ranges, supports joint closing-time questions and records forecasts before outcomes arrive. These are real capabilities. The gains in predicting the correct direction remain small and unconfirmed.

The user's concern is justified: recent work has stayed too close to a small shared encoder and frozen-parent correction approach. More versions of that approach are not enough evidence that we have searched the important alternatives. The results support changing the research strategy; they do not establish which alternative will win.

## What each version actually changed

| Version | Question and implementation | Evidence and conclusion |
|---|---|---|
|0.1|Predict one candle's open/high/low/close; compare MLP and sequence network.|Sequence selected. Historical mean OHLC absolute error3.504 basis points versus3.588 for traded-price persistence, a2.34% descriptive reduction. Candle-colour accuracy48.61%. Later recursive15-candle inference produced nearly flat forecasts; repeating a one-step model with frozen future flow was not validated15-step learning.|
|0.2|Replace exact prices with bearish/neutral/bullish probabilities; compare logistic, MLP and sequence models; add probability calibration.|Sequence selected. Three-class accuracy45.83%, log loss1.033835 versus frequency1.09898. The >=60% calls were all neutral, not confident up/down opportunities. A45% three-class score cannot be compared directly with a50% binary coin flip.|
|0.3|Add60 one-minute and24 one-hour summaries of book/trade history; compare matching short-history control.|Long-history arm won development but worsened later probability error: log loss1.039317 versus0.2's1.033835; accuracy45.63%. This rejected this coarse long-summary design, not all longer order-flow history.|
|0.4|Predict18 closing-price ranges instead of only three direction classes; compare categorical loss with an ordinal penalty.|Categorical selected.18-bin loss2.62078 versus frequency2.76711 and volatility2.67456. Derived three-class accuracy45.99%. Main gain: a learned endpoint price distribution and direction calculated from the same probabilities.|
|0.5|Predict26 price bins at each of15 closes directly; compare equal horizon weighting with weighting that emphasizes the first close.|Near weighting selected. Mean range loss2.805561. It fixed the recursive-input problem by predicting every horizon from the actual snapshot. The15 columns alone did not describe joint path probability. First-close accuracy45.71%; direction gains were essentially absent.|
|0.6|Learn dependence between successive future closing-price bins with a conditional Markov decoder.|Joint loss28.152549, a major improvement over multiplying independent endpoint forecasts. But mean individual range loss worsened to2.810344. Better linked forecasts did not imply better unconditional direction.|
|0.7|Balance whole-sequence and individual-range training objectives while continuing0.6.|The joint-only control won development. Joint loss improved to28.074578, but individual range loss worsened to2.810822. Best joint score among these selected historical versions, not best on every metric.|
|0.8|Combine0.5's stronger individual forecasts with0.7's learned dependence using exact marginal-preserving reconciliation.|Mean range loss remained2.805561 by construction; joint loss28.124498. This was a fitted coupling experiment, not new neural training. It could not improve individual direction because it preserved those probabilities.|
|0.9|Add a small correction network that sees the latest60 one-minute candles individually; compare grouped15-minute inputs.|Detailed arm won development. Mean range loss2.805340 and joint28.113849; first-close three-class accuracy46.14%. Tiny marginal improvement; final net-direction accuracy50.42%, binary loss0.693088. No final-direction claim reached60%.|
|1.0|Explicitly reward correct final up/down probabilities, using an additional recent-candle correction.|All six fits retained epoch0: trained corrections worsened development scores. Recalibration alone produced final loss0.693260, worse than0.9. A negative experiment, not a learned improvement.|
|1.1|Test a correction seeing the temporal sequence of60 seconds of book/trades versus their repeated mean.|Mean control won development. Selected final loss0.695152 and range2.809358, worse than0.9.338 calls claiming >=60% were only54.73% correct. The tested sequence design did not transfer better.|
|1.2|Recover exact replayed historical midpoints; add midpoint location and60-second movement. Use raw parent outputs and calibrate the new pipeline once.|Midpoint-enabled arm narrowly won development and its matching control. Final loss0.694900, range2.811592; still worse than the unchanged parent with matching calibration.279 >=60% calls were49.10% correct. Midpoint inputs were largely redundant with the existing trade-price reference.|
|1.3|Keep1.2's model and inputs; add a KL penalty against unsupported changes from the frozen parent's probabilities.|Penalty won development. Final loss improved to0.693765, range2.810832 and joint28.256479. >=60% calls fell from279 to15;6/15 were correct. Better than1.2, but still worse than the simple parent on marginal/final probability quality.|

One basis point is0.01%; the price-error numbers for0.1 are not probability scores.18-bin,26-bin,three-class,binary and joint losses are different tasks and must not be compared as if their numerical scales were identical. The15-horizon versions use11,186 benchmark origins after boundary purging; earlier one-close cohorts differ slightly.

## Comparable final-direction results

This event means the **15th target candle closes above the frozen reference**, versus at or below it. It is not the next candle's colour, the number of green candles, or target-before-stop trading success. Exactly unchanged is included with down because the price bins do not isolate equality.

| Selected version / reference | Final binary log loss, lower better | Brier error, lower better | Direction correct |
|---|---:|---:|---:|
|Always50–50|0.693147|0.250000|No unique preferred side|
|0.9|0.693088|0.249971|50.42%|
|1.0|0.693260|0.250057|50.55%|
|1.1|0.695152|0.250986|51.05%|
|1.2|0.694900|0.250858|51.23%|
|1.3|0.693765|0.250305|51.38%|
|Unchanged raw parent, matching1.2/1.3 calibration|0.693158|0.250006|50.59%|

The benchmark happened to contain51.53% down-or-unchanged outcomes. Choosing that majority after inspecting the benchmark would achieve51.53% accuracy; this is a hindsight descriptive comparison, not a deployable trained rule. The fit-period majority rule scores48.47% on this benchmark. Both comparisons matter.1.3's higher accuracy does not overcome its worse probability score.0.9's extremely small advantage over50–50 does not prove a stable edge.

## Current technical implementation, translated

This is a small supervised neural model in Python/PyTorch on Apple MPS. Supervised means it learns from historical input/outcome pairs. It is not a ChatGPT-sized language model, and it is not trained by identifying chart drawings.

These Diwali runs use real historical BTC inputs and labels, not simulator v0.4/v0.5 candles as training truth. Simulator research informed hypotheses about liquidity and impact, but did not establish that the simulator reproduces real BTC or that candle wicks identify hidden order quantities. There is no verified reproduction of Krafer's proprietary Tiger weights, architecture or reported accuracy in these versions.

### Available inputs

-1,440 completed one-minute candles, with8 features each: relative candle prices, volumes/count and time-of-day features.
-60 seconds of order-book state:87 features per second, including top20 bid/ask distances and quantities, spread, imbalance and related summaries.
-60 seconds of executed trades:5 features per second covering buy/sell base and quote amounts and trade VWAP displacement. These are second summaries, not an ordered list of every fill.
-The difference between the recent observed trade-price reference and the last completed candle close.
-For1.2/1.3, two additional midpoint summaries: latest midpoint location relative to the candle anchor and net60-second movement. Midpoint is halfway between best bid and best ask.

The total latest input is17,043 numeric features. This is not17,043 raw market events, nor24 hours of full order-book events. The reference is a recent nonempty completed received-second VWAP, not an exact last-trade price or executable entry quote.

### How the parent network reads them

1. A **convolution** reads15-candle groups with stride15, compressing1,440 minutes to96 learned vectors. It learns filters, but fine within-group detail can be lost.
2. A **GRU** (a recurrent network with memory gates) reduces those candle vectors to32 values.
3. The book/trade branch projects each92-feature second to16 values, then another GRU reduces60 seconds to32 values.
4. A small dense layer combines both branches into32 values, then adds the reference displacement:33 values describe the whole snapshot.
5. A linear output layer produces15×26 scores. **Softmax** converts each horizon's26 scores into probabilities summing to100%.

This33-value bottleneck is a deliberate small starting design, not evidence that it preserves everything useful. It has not been eliminated by the later wrappers.

### What1.3 adds

The price parent has28,466 parameters. A new18,465-parameter correction branch takes the60-second mean book/trade vector plus the two midpoint summaries. It repeats that same94-value vector across60 GRU steps. Therefore this correction branch **does not see the order of the60 original seconds**, even though the frozen price parent does. This was the controlled design selected in the recent experiments; it should not be described as rich event-flow modelling.

The correction adds scores to the frozen parent's scores. Training uses:

`weighted price-bin cross entropy +0.25×first-candle-colour loss + final-direction cross entropy + parent-KL penalty`

Cross entropy penalizes assigning too little probability to the actual result. The price term puts half its weight on the first close and splits the other half over14 later closes. The additional direction term concerns the15th close. That combination is explicit, but may involve competing priorities; it needs controlled testing rather than indefinite weight tweaks.

KL divergence penalizes large distribution changes from the parent. It can restrain corrections, but cannot add missing market information. A wrong parent can also constrain learning. Training uses AdamW, batch128, up to20 epochs, early stopping after4 non-improving epochs, gradient clipping and three seeds. The branch is selected on mean development performance, while inference uses the fixedseed17 model—not an ensemble of the three runs.

After selection, **temperature calibration** adjusts probability sharpness on a separate chronological block. A temperature below1 sharpens probabilities; above1 softens them.1.3's final temperature is about0.616. It helped that calibration block but has not delivered stable later reliability. We do not have a mathematical guarantee that the same calibration holds during another market regime.

A frozen21,308-parameter0.7 network supplies26×26 transitions between adjacent future closing bins. Reconciliation adjusts these transitions so propagated marginals agree with the displayed individual price distributions. Total parameters participating in1.3 inference are68,239, of which18,465 are trained in this version. This finite-state, first-order Markov approximation is not a full simulator of future orders or within-candle price paths.

Final up/down probabilities are sums of the same price-bin probabilities. This prevents a separate arrow from contradicting the cloud. Purple on both sides means the forecast assigns both outcomes some chance; deleting the losing side after Reveal would falsify the prediction. Black grid dots and revealed candles are actual answers, not model-generated predictions.

## What improved beyond the neural scores

- We stopped treating a repeated one-step point forecast as validated15-step forecasting.
- Price ranges, direction and joint close-time queries now have explicit, consistent definitions.
- Data availability checks, quality exclusions, split-boundary purging, input/source hashes and independently replayed received-message snapshots are implemented.
- Reports retain matching controls, simple baselines, seed histories, negative experiments and regressions.
- Historical replay keeps actual answers separate until Reveal. Numerical checks verify the displayed output matches saved inference.
- Fresh forecasts are saved before their target begins, with UTC and monotonic timing audits. The current0.9/1.2 comparison uses15-minute spacing; it is still a limited forward experiment.
-119 focused tests passed for the current code. Ten1.3 replay origins/150 horizons match saved inference within1.31e-7, with30 coherent joint queries and desktop/mobile display checks. These checks establish implementation properties, not predictive perfection.

## What remains unchanged or unresolved

The main pilot still uses the same October2026 BTCUSDT perpetual market cohort. Downloading12 months is different from preparing and training on12 months. FitOct1–18, development19–21, calibration22–23 and benchmark24–31 remain the main schedule. Since the benchmark has repeatedly informed research choices, it is no longer an untouched test, even where each individual run freezes selection before reading it. Neighboring15-minute targets overlap; thousands of examples are not thousands of independent market conditions.

Historical receipt timing and provider corrections remain assumptions where original exchange-arrival evidence is unavailable. Checksums prove retained bytes stayed unchanged, not original-exchange authenticity. We do not observe all venues, all depths, hidden orders, private trader intent or future liquidity changes.

The core market representation still compresses book/trade activity into seconds. A wall appearing, cancelling and refilling inside a second can vanish from that summary. Adjacent net depth changes cannot always distinguish cancellation from execution or separate individual orders. L2 data alone does not supply private order identities.1.3 has not recovered those events simply by adding a penalty.

Most recent versions use frozen parents and small residual branches. That limits how much they can revise the original representation.0.3 tested longer summaries, not full-resolution24-hour order flow.1.1's negative temporal-branch result is evidence about that particular design, not proof that time ordering never helps.

News, missing-book inference, hidden-liquidity estimates, executable-entry modelling, target-before-stop probabilities and costs remain deferred. There is no validated80–20/90–10 entry detector. The completed prior0.9/1.1 live comparison had only9 overlapping origins, all final outcomes up; it cannot establish multi-regime reliability. Current pending tests cannot be called completed accuracy evidence.

The snapshot-to-target gap is also unchanged: freeze at10:00:15, first full target10:01–10:02. That is105 seconds to its close, not60 seconds after the button. The15th closes at10:16,945 seconds after the freeze. Using older completed-candle context avoids leaking the in-progress minute, but leaves a real unobserved gap. Any alternative horizon must be evaluated as a new target, not silently substituted.

## Where the approach should change

These are recommendations, not claims of demonstrated BTC improvements.

**1. Prioritize event representation over another correction layer.** Reconstruct the actual ordered L2 updates and trades from the retained raw archive where the provider records support it. Represent price-level changes, aggressor flow, trade sizes/counts, elapsed time, spread, multi-depth imbalance and replenishment proxies. Preserve temporal bursts. Use a recent event window plus longer coarser context; equal calendar durations do not require feeding millions of raw events indiscriminately. Verify sequence continuity and cutoff times first. Do not invent cancellation identities, hidden orders or unavailable events.

**2. Compare meaningfully different models on exactly the same prepared inputs and targets.** Include a stationary order-flow logistic baseline, a boosted-tree baseline, a small convolutional/temporal-convolution sequence model and a compact attention model. Train the neural models end-to-end instead of requiring every candidate to correct the same frozen0.5 encoder. Keep the existing parent as a baseline. An earlier separate DeepLOB/TLOB benchmark exists, but its limited budget/provenance caveats do not establish a winner for this verified October task; it is not a substitute for this controlled comparison.

DeepLOB provides a concrete precedent for learning spatial book structure and temporal dependencies with convolution and LSTM layers; it was studied on equities, not proof of BTC performance. [Original DeepLOB paper](https://arxiv.org/abs/1808.03668).

More directly relevant to the representation question, Kolm, Turiel and Westray report stronger results from order-flow inputs than from many raw-book models on115 Nasdaq stocks. This motivates testing stationary flow features here, while preserving the asset/horizon distinction. [Original order-flow study](https://doi.org/10.1111/mafi.12413).

**3. Fix the validation design before expanding the model search.** Use several chronological walk-forward blocks, with horizon purging, training-only scalers, separate model selection/calibration, and a later final block that is not used to guide repeated research. Evaluate strong majority/frequency, persistence, volatility and flow baselines. Report block/day variation and probability reliability, not just overall accuracy. Prepare additional validated months when this protocol is frozen; more versions on the same inspected week cannot replace independent evidence.

**4. Diagnose the horizon where information actually helps.** Keep the requested next-candle/15-close task, but add explicitly labelled auxiliary event/shorter-time horizon tests. If observed flow predicts the next few changes but not the15th close, that is valuable evidence about the forecast horizon—not a reason to relabel short-horizon success as15-minute success. The order-flow paper reports a short effective horizon in its equity setting; BTC needs its own measurement.

**5. Test probability models and parameter uncertainty properly.** Compare the26-bin histogram with a continuous return-distribution or ordered-CDF head if more precise price ranges are needed. Compare a prespecified ensemble with fixedseed17 deployment; three training seeds used for selection are not an ensemble. Preserve coherent range/direction and tail probabilities. Quantile intervals alone do not automatically answer arbitrary price-bin probabilities or joint path queries. [Deep ensembles paper](https://proceedings.neurips.cc/paper/2017/hash/9ef2ed4b7fd2c810847ffa5fa85bce38-Abstract.html).

Attention is a candidate, not an automatic solution. Multi-horizon methods such as TFT offer a precedent for combining timescales and selecting useful inputs, but do not establish a winning BTC architecture. [Original TFT paper](https://arxiv.org/abs/1912.09363).

The recommended next substantive experiment is therefore a **new end-to-end order-flow representation/model comparison under a frozen walk-forward evaluation**, preceded by a bounded raw-event quality audit. It is more informative than adding another small correction to0.5. Retain the existing pipeline as an auditable reference and reuse its data safeguards. Do not promise a perfect probability oracle: finite data cannot verify exact conditional probabilities, and unpredictable future order arrivals remain unobserved.

## Evidence map

Per-version decisions and caveats: `docs/planning/DIWALI*.md`. Aggregate numerical records: `results/diwali0.1` through `results/diwali1.3`, particularly `report.json`, `run-protocol.json`, `selection.json`, `runs.json`, and the1.2/1.3 confidence diagnostics. Implementation: `model.py`, `probability.py`, `distribution.py`, `fan.py`, `path.py`, `coupled.py`, `refined.py`, `flow.py`, `anchored.py`, `regularized.py` and their trainers under `research/diwali`. No private raw market data, weights or individual live forecasts are included in this report.
