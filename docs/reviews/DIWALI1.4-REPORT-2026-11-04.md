# Diwali 1.4 report

Prepared November 4, 2026 from completed runs, retained forecasts, source code and artifact audits. Training and the reserved test are finished. Work stops here at the user's request; no Diwali 1.5 experiment has started.

## Result in plain language

**Diwali 1.4 is trained, but it has not become a reliable direction predictor.** It learned some useful information about possible price ranges. On the reserved test it beat three simple methods on range error, but lost to a simple method that groups historical outcomes by recent volatility.

For the final forecast close, its up/down accuracy was **49.54%**. Its probability error was slightly worse than always saying **50% up / 50% down**. Across all 20,004 tested examples, its up probability stayed below 50%, so it always slightly preferred down or unchanged. Actual price finished up in 50.46% of those examples.

This is a negative directional result worth retaining. It is not evidence of a profitable strategy, an 80–20 or 90–10 entry detector, or a perfect probability model.

## What 1.4 changed from 1.3

| Area | Diwali 1.3 | Diwali 1.4 |
|---|---|---|
| Training approach | Small corrections on frozen earlier networks | New networks trained from initialization, with all weights trainable |
| Snapshot representation | Shared parent reduces the snapshot to 33 values | Multiple candle/event/context vectors read by separate forecast queries |
| Market detail | One-second book/trade summaries; selected correction repeats a mean summary | Tested individual retained events against an otherwise matched one-second summary control |
| Model families | Restrained correction experiment around shared parents | Event convolution, event attention and one-second convolution |
| Development evaluation | Repeatedly inspected October benchmark | Three chronological August development folds, each with two training seeds |
| Later evaluation | October could no longer support fresh independent improvement claims | September 15–29 reserved until model artifacts and scoring rules were deliberately frozen |
| Horizon research | Main full-candle targets | Same main targets plus an explicitly separate 5/15/30/60/105/345/945-second diagnostic |
| Output dependence | Earlier Markov model supplied linked closing-bin paths | Direct marginal price distributions; no fitted joint path model in this version |

The selected 1.4 model is the **one-second convolution control**, because it won the frozen development selection rule. The raw-event candidates were trained and tested, but their additional detail did not improve the primary development range score. Consequently, the deployed 1.4 demo still uses one-second summaries. We must not say raw events solved the compression problem.

The direct numerical scores of 1.3 and 1.4 are not a valid head-to-head accuracy comparison: their training dates and evaluated market examples differ. In particular, using October-trained 1.3 on September would violate chronology. The comparison above concerns implementation and research design, not a matched performance win over 1.3.

## Exact forecasting question

The market is BTCUSDT perpetuals with one-minute candles. At each input freeze, the model receives 1,440 completed candles plus the preceding 60 seconds of available order-book/trade activity, an earlier known book state, and the recent price-reference displacement.

It directly predicts 26 possible closing-price bands for each of 15 future full candles. The bands are returns relative to the frozen reference, with unbounded outer tails. Each column totals 100%.

Example: freeze at **10:00:15**. The first target candle is **10:01–10:02**, closing 105 seconds after the freeze. The fifteenth target closes at **10:16**, 945 seconds after the freeze. These are not 60 seconds and 15 minutes after clicking.

“Up” means the chosen future close is above the frozen reference. “Down or unchanged” means at or below it. Those probabilities are sums of the same 26 price-bin probabilities. They are not candle colour, the majority of green candles, a continuous path, or target-before-stop success.

Purple on both sides of the chart is the predicted uncertainty. It is not corrected to the side that later happened. White chart dots/lines and grid dots are real historical closes, displayed only after Reveal.

## Data and chronology

These are real retained historical market records, not synthetic simulator candles. Simulator v0.4/v0.5 research did not become the training truth for 1.4. This does not reproduce or verify Krafer's proprietary Tiger model.

August preparation considered 44,640 minute origins, retained 5,519 input contexts and found complete valid targets for 5,391. Retained input windows contain 18,868,954 event rows. Not every market minute passes the book and timing checks.

| Development fold | Fitting examples | Checkpoint-selection examples | Probability-calibration examples | Later score examples |
|---|---:|---:|---:|---:|
| A | 1,638 | 420 | 352 | 896 |
| B | 3,314 | 260 | 1,343 | 249 |
| C | 4,917 | 249 | 25 | 200 |

The three transfer score blocks are August 16–18, 24–26 and 29–31, respectively. Earlier fitting dates expand by fold. Targets crossing a partition end are purged. Input scaling uses fitting data only. Fold C had fewer than the prespecified 100 calibration examples, so its temperature stayed at 1 instead of fitting an unsupported adjustment.

Final build: fit on **August**, select the checkpoint on **September 1–7** and calibrate probabilities on **September 8–14**. Counts were **5,391 / 862 / 1,476**. The final score period was **September 15–29**. Whole-archive data-quality inspection had already occurred; the reserved period is a model-performance holdout, not a claim that nobody ever saw any raw market value.

## Technical implementation, with terms explained

The implementation uses Python/PyTorch and the Mac's Apple MPS GPU backend. These are small supervised models: they learn from past input/outcome pairs, not a language-model pretraining exercise.

- **Features** are numerical descriptions of market messages: top-20 bid/ask price distances and quantities, spread, depth imbalance, observable depth changes, trade side/price/size and elapsed time. Event models use 103 channels. Observed changes do not reveal private order identities or uniquely distinguish every cancellation from execution.
- A **convolution** applies learned local filters to sequences. The event candidates process retained event rows before learned grouping. Equal-availability rows are treated as a set rather than assigned a made-up cross-feed order.
- **Tokens** are learned vectors holding pieces of context. Candle processing retains 96 vectors after grouping the 1,440 candles into 15-minute sections. The selected one-second model groups its 60-second branch into **one event vector**, plus a book-seed vector and a price-reference vector: 99 context vectors in total.
- **Attention** gives a forecast query a learned weighted mixture of those context vectors. Fifteen queries produce the fifteen closing distributions. The selected convolution model also uses attention for this readout; “event attention” names the separate candidate with an additional attention context mixer.
- **Softmax** converts 26 output scores into 26 nonnegative probabilities totalling 100% for a closing time.
- **Cross entropy / log loss** penalizes assigning too little probability to what happened. A confident wrong forecast is penalized more than an uncertain wrong forecast. Training averages this loss equally across the 15 closing times.
- **AdamW** updates the learned weights. Settings were width 64, batch 8, learning rate 0.0003, weight decay 0.0001, gradient limit 5, up to 12 epochs and early stopping after three non-improving selection epochs. An **epoch** is one pass through fitting examples.
- **Temperature calibration** changes how sharp the probabilities are, using a separate chronological block after checkpoint selection. It does not add missing information or guarantee later accuracy.

The selected network has 94,620 trainable parameters. Event attention has 98,908. The study completed **18 neural fits**: three families × two seeds × three folds, plus twelve baseline comparisons and three horizon diagnostics. A separate final selected-family model was then fitted using fixed seed 17. It selected epoch 1; later fitting epochs reduced fitting loss but did not improve checkpoint-selection loss. The final build is not an ensemble.

Its 26 bin boundaries are based on these 25 basis-point edges: −100, −60, −40, −30, −20, −12, −8, −5, −3, −2, −1, −0.5, 0, 0.5, 1, 2, 3, 5, 8, 12, 20, 30, 40, 60, 100. One basis point is 0.01%. The exact +2bp classification boundary follows the retained bullish-band convention.

## Development outcome

Lower price-band log loss was the frozen family-selection criterion, averaged equally across the three folds and two seeds:

| Neural family | Mean 15-close price-range log loss |
|---|---:|
| Detailed event convolution | 2.810989 |
| Detailed event attention | 2.800579 |
| One-second convolution — selected | 2.791701 |

The selected model beat all four baselines on this development average. However, its final-direction log loss of 0.691911 was worse than historical frequency (0.687185) and volatility-conditioned frequency (0.682562). Different scores answer different questions; selecting the best range model did not select the best direction model.

## Reserved test: the decisive later comparison

All methods below use the same 20,004 passing examples. Lower range log loss, up/down log loss and Brier error are better. Direction accuracy measures the chosen side at the fifteenth forecast close.

| Method | Mean 15-close range log loss | Final-close up/down log loss | Final-close Brier error | Final-close direction accuracy |
|---|---:|---:|---:|---:|
| diwali1.4 | 2.881076 | 0.694003 | 0.250428 | 49.54% |
| fit_histogram | 2.984478 | 0.696905 | 0.251874 | 49.54% |
| fit_volatility_histogram | 2.870450 | 0.696462 | 0.251653 | 49.54% |
| flow_logistic | 3.096418 | 0.696140 | 0.251072 | 51.26% |
| flow_boosted_trees | 2.908308 | 0.705288 | 0.255900 | 50.09% |
| Constant 50–50 direction | Not a price-range model | 0.693147 | 0.250000 | No preferred side |

The selected model beat three baselines on range error, on each of the 15 days. It lost to the volatility-conditioned histogram overall by 0.010626 and beat that baseline on only five days. These are descriptive daily comparisons, not independent statistical proof.

For the final close, the model's up probabilities ranged from **46.62% to 49.96%**, averaging **48.35%**. It favoured up in **zero** examples, and made **zero** final-direction claims at 60% confidence or higher. The actual final up frequency was **50.46%**. Its probabilities are not all identical; their directional movement is too small to switch sides in this period.

At the first target close, up probability ranged from 43.80% to 47.32%, accuracy was 50.50%, and binary log loss was 0.695638. It also always favoured down there. Success on the next-close task is therefore not hidden by the weaker fifteenth-close result.

No test setting or weight was changed after viewing the reserved results. The shared one-use evaluation claim is complete, and this September period is consumed for later versions too. Reusing it after another change would be diagnosis, not fresh confirmation.

## Errors investigated and what the evidence establishes

**Timestamp rounding was a real implementation error and was corrected.** Float32 elapsed seconds placed fifteen event rows in a different second from exact integer timestamps; one valid event rounded to 60 and stopped the control. Seven fitting rows were affected. The control was retrained using exact recorded nanoseconds, without clipping or dropping the offending transfer input. Earlier failed artifacts remain retained and excluded.

**Range accuracy can conceal weak direction.** An exact error decomposition on development predictions separates direction error from choosing the right price band within that side. The selected model's average-15 direction error was 0.690991 versus the volatility baseline's 0.684269, while its within-side range error was better: 2.100710 versus 2.157520. The overall range score improved because the magnitude gain outweighed the directional loss. This identifies which error improved; it does not prove why a market feature failed.

**Compression remains in the selected model.** The 60-second branch becomes one learned event vector. An input-only diagnostic on 64 earlier selection examples per fold/seed confirmed this in all six controls. Direct attention to that event vector varied substantially by run/horizon, so token counts alone do not prove the book/trade branch was ignored. Attention weights are not causal feature importance, and neighbouring context filters also mix information.

**A synthetic pooling flaw did not explain this cohort.** Repeating identical trade vectors at exactly the same availability time can be averaged away. But all 18,868,954 retained August rows had distinct availability groups, including 6,484,263 market trades. The synthetic simultaneous-trade case was absent. It would be misleading to claim an extra count feature is a demonstrated fix based on that probe.

**More epochs did not fix later performance.** The final checkpoint was selected at epoch 1 under the already frozen rule. This is evidence that simply training longer was not helping that selection period. It is not proof that a larger model, another loss or more raw events would solve direction.

**Shorter horizons were measured, not assumed to be easier.** A fixed logistic diagnostic compared 5/15/30/60/105/345/945 seconds. Benefits varied by fold and horizon. The shortest labels use available last-trade prices, while longer labels use full-candle closes, so the study does not establish a universal signal lifetime. The primary 15-close task was not relabelled as short-horizon success.

## Data coverage and remaining limits

The reserved interval contained 21,600 possible minute origins. Input gates retained 20,401; complete valid targets left **20,004**, or **92.61%** of possible origins.

| Reason excluded | Count |
|---|---:|
| No valid earlier book seed | 422 |
| Gap/invalid marker in recent input | 456 |
| Stale book coverage | 52 |
| Insufficient valid candle context | 7 |
| No fresh completed-second price reference | 262 |
| Missing or invalid target candles | 383 |
| Target extends beyond source end | 14 |

Older candle gaps remain explicitly masked. There were 49,502 masked minute positions across overlapping input histories; these are not distinct missing market minutes. Exclusions must not be presented as complete market coverage.

Other limits remain:

- Download hashes prove unchanged retained bytes, not original-exchange authenticity. Independent aggregation of the same retained trades checks target prices, not every historical book level.
- Provider receipt clocks and corrections do not prove when an original exchange message first became available live. Historical availability is still a stated assumption.
- The model sees one market's visible top book and trades. Full depth across venues, hidden orders, trader intent and future orders are unavailable.
- Longer order-flow context beyond the recent 60 seconds is still not retained as a raw sequence. The 24-hour input is candle context.
- Outputs concern closing-price bands. They do not estimate candle colour separately, an intraminute path, coherent joint path probabilities, or executable entry success. Some earlier joint-query capabilities were not ported into 1.4.
- News, missing-book reconstruction, hidden-liquidity inference, transaction costs and target-before-stop entries remain deferred.
- Overlapping targets are correlated. Twenty thousand origins and 300,060 endpoint scores are not that many independent experiments.
- No prospective forecast session from the frozen 1.4 weights has been completed. Earlier versions' live records cannot confirm this model.

## What was verified

All eighteen development model artifacts were checked: selected weight identities, the checkpoint rule, fitting-only transformation counts, calibration identities and saved forecasts. Recomputed metric differences were zero.

The final selected model and four baselines passed engineering inference on ten earlier selection inputs, including finite outputs, shapes, normalized probabilities and CPU/GPU parity. Maximum CPU/GPU probability difference was approximately 1.09e-7.

After reserved scoring, a separate artifact audit verified the completed one-use claim and release identity, all five saved forecasts, normalized probabilities, reported overall/daily scores, paired comparisons and quality ledgers. Maximum recomputed metric difference was zero. This audited retained outputs; it did not rerun or retune the model.

The local historical demo at **http://127.0.0.1:8754/** contains ten evenly spaced earlier selection examples. All 400 displayed past candles match the saved model input features. All seven inference tensors match the training loader bit for bit on all ten examples. Tests verify that prediction does not consume future targets, actuals are absent from case/prediction responses, Reveal requires a prediction token, and probabilities remain unchanged after Reveal. The JavaScript behaviour checks passed for prediction, reveal, reset, fifteen columns, actual markers and the exact +2bp boundary.

**Visual browser inspection is outstanding:** the computer-use tool reported browser access disabled in Work settings. API and DOM behaviour tests are not a screenshot review. The historical examples demonstrate inference; they are not independent accuracy evidence.

## Files for examination

- `results/diwali1.4/development-report.json`: completed trial and baseline results.
- `results/diwali1.4/development-artifact-audit.json`: development verification.
- `results/diwali1.4/development-error-decomposition.json`: direction versus within-side error.
- `results/diwali1.4/development-context-diagnostic.json`: token/readout diagnostic.
- `results/diwali1.4/final-build-model-preparation.json`: final fitting, selection and calibration.
- `results/diwali1.4/reserved-final-report.json`: full later comparison, daily results and quality coverage.
- `results/diwali1.4/reserved-final-artifact-audit.json`: final saved-output verification and directional ranges.
- `results/diwali1.4/historical-demo-validation.json`: ten-example inference checks.
- `research/diwali/event_model.py`: network implementation; `event_train.py` and `event_train_exact.py`: training.
- `docs/planning/DIWALI1.4-TRAINING-PROTOCOL-2026-11-04.md` and `DIWALI1.4-FINAL-EVALUATION-PROTOCOL-2026-11-04.md`: frozen protocols and their historical implementation notes.

Raw paid data, individual predictions, fitted weights and the private demo artifact stay local. Source and aggregate research may be published. The objective is not achieved; further experiments are paused pending the user's examination and decision.

## Follow-up: directional ranking audit, November 11

The later development-only audit checks the distinction between preferred side and ranking, raw versus calibrated probabilities, every horizon/period/day, and the exact sign/reference mapping. See [DIWALI1.4-DIRECTION-DIAGNOSTIC-2026-11-11.md](DIWALI1.4-DIRECTION-DIAGNOSTIC-2026-11-11.md). It finds weak final-horizon ranking with reversals across folds, some shorter-horizon ranking, and no zero-bin mapping mismatch. No 1.5 model or calibration correction was trained by that audit. September 15–29 remains consumed.
