# BTC model specification v1 and handoff — 1 November 2026

## Scope and honest completion status

User authorized only remaining source review and final specification in this turn, then stop for Sol. No collection, implementation, fitting or trading was started. Specification v1 below is frozen as our independent design. Source review remains partial: all eight transcripts and selected visuals were previously reviewed, but continuous visual coverage was not completed. Do not mark step 1 complete or claim every video was watched in depth.

Read the companion krafer-source-review-2026-11-01.md for the eight source links, timestamped claims, screenshot values and unresolved metrics. Read btc-model-training-protocol-2026-11-01.md for splits, evaluation formulas and execution gates.

## Frozen specification

- Instrument: Binance USD-margined BTCUSDT perpetual, UTC one-minute buckets. This venue/instrument choice is ours, not a verified Tiger implementation detail.
- Forecast origin: after each minute closes and required input messages have arrived; save both exchange cutoff and actual issuance time. Score the next minute's exchange trades. Explicitly measure issuance delay and exclude already-observed target events from predictive inputs. Late forecasts are labeled and cannot masquerade as full-minute advance predictions.
- Context: 1,440 completed minute OHLCV candles (24 hours). This matches the creator's stated Tiger context. Book/trade feature context: last 60 seconds, our choice; store at one-second resolution plus current depth at forecast cutoff. Record top 20 bid/ask levels and summarize depth within 1, 5, 10 and 25 basis points where feed coverage permits. Distances relative to midprice, sizes in base BTC; missing depth is masked, never inferred as zero liquidity.
- Other inputs: cyclic UTC time/day and timezone-aware sessions; point-in-time BTC news features when available; optional observable replenishment/absorption estimates. Log every input's availability timestamp. Session features are creator-supported; the exact encoding and book/news design are ours.
- Primary output: joint distribution over next-minute OHLCV, a representative valid candle and 50/80/90% intervals. Enforce positive prices, nonnegative volume, H >= max(O,C), L <= min(O,C). Predict open displacement too; the next minute's first trade need not equal the previous close.
- Direction output: up/neutral/down probabilities from next close versus last observed close, with +/-1 bp neutral band. This is separate from bullish/bearish news sentiment.
- Secondary output: optional 15-minute sampled rollout; no real future book, trade or news inputs. Freeze/mask origin context or use separately labeled simulated flow. Score each horizon separately. One-minute forecasting remains the release's primary task.
- Entry output: long/short/wait/skip with target-first, stop-first and timeout probabilities, plus net expected return. Initial evaluation uses 1 ATR14 stop, 2 ATR14 target and 15-minute maximum holding horizon. Use executable prices and preserve ambiguous outcomes. These settings are our predeclared research policy.
- Candidates: simple baselines, MLP, approximately 7M-parameter learned candidate, optional 15–20M sequence candidate. Seven million is creator-reported scale; exact Tiger layers and direct book training remain unknown. Architecture comparison is validation-selected, not a claim to clone Tiger.
- Hardware: M5 / 32 GB; actual full-context pilot precedes sustained fitting. Three seeds 17, 42, 101. Initial batch 16, 12 GB process-memory target; stream data from disk.
- Evaluation: training error, locked past unseen-data error and recent matured 24-hour error plus 7-day context. Internal validation remains separate. Show close MAE/MSE/RMSE, component errors, documented standardized HLCV error, direction/confusion, probabilistic quality and entry calibration. Move fulfillment is a separate explicitly defined metric. No conversion of MSE to accuracy.
- Viewer: observed candles, distinct forecast candles, uncertainty, origin/issuance time, immutable predictions, observed depth heatmap, news markers, entry assessment, model version and three error panels. Price change, news sentiment, publisher summaries and community voting must be distinct. Finalized KAT forecast alignment/help is still unverified.

## Provenance boundaries

Verified creator statements: 1,440 candles; train/unseen/recent approximately 24h groups; time-of-day information; BTC focus; roughly 7M parameters from author comment. Creator-reported accuracy is not independently replicated. The 76% figure refers to move fulfillment, while ordinary direction is approximately 49–49.5% in the supplied material; adjusted metrics have unresolved denominators.

Our design choices: Binance perpetual venue, direct public book/trade inputs, probabilistic valid OHLCV, explicit hidden-pressure estimates, exact feature depth, news processing, entry policy, splits and cost-aware evaluation. Unknowns remain unknown: exact Tiger architecture, training dataset, normalized error formula, news classifier and publisher weighting.

## Browser status and next action for Sol

Native Chrome was readable at KAT. Clicking Predict help did not produce a help panel. A scroll attempt failed with noWindowsAvailable; inventory still lists Chrome running. An in-app browser exists with a user-owned unrelated YouTube tab. Do not alter that unrelated video; use a new background tab if fallback is needed. No claim is made that the fallback itself is unavailable.

Outstanding source work: finish visual coverage of all eight videos using the ledger; inspect Predict help, KAT Model help, DOM help and a completed forecast without unnecessarily consuming generation quota. Retain the distinction between ChatGPT Mini and Tiger. If new evidence requires specification changes, version and explain them before training. User intends to continue subsequent steps with Sol; this handoff does not assert that the source-review gate has passed.


## Signed-in website review update

Authenticated in-app KAT access succeeded after the user signed in. The narrow responsive chart showed Predict, ChatGPT Mini, density controls, DoM, 4 hours DoM, Cross, S/R, MA25/50/200/500/1000, Pred, Full and clear-predictions controls. Visually confirmed historical red/green liquidity heatmap behind observed candles, a vertical present-time boundary, a current-price label and depth bands to the right. Future-axis depth bands must not be interpreted as knowledge of future liquidity. Desktop help controls were not exposed in this responsive view; a temporary viewport override did not change the captured layout.

Read https://krafercrypto.com/ai-models: the creator advises against use during trends/extreme news conditions and claims strongest performance in low-volume/chop or after an extreme move. These are creator claims to evaluate with regime-stratified held-out tests. The page describes Bobcat relevance up to about 30 bars, Lion as trained longer with less extreme outputs, and Panther as trained on broader data. It does not establish Tiger's exact architecture or direct order-book training. The page advertises free signed-in ChatGPT 5.4-mini access; this is distinct from Tiger.

Read https://krafercrypto.com/gallery: five curated cases include a failed breakout labeled 30% and successful/partial moves labeled 80–90%. The text explicitly discusses early directional calls, timing/path deviations, reversals and moves completing hours later. These are illustrative selected cases with incompletely specified scoring, not an unbiased benchmark. Our test must score time-to-target and fixed forecast expiry; a target reached hours after expiry is not a success within the original horizon.

One free ChatGPT Mini generation was initiated to inspect its rendering. The UI changed to Predicting, a roughly 15-minute timer in the model selector, and a Receiving marker near the forecast origin. The timer's meaning was not verified; do not call it the generation duration or horizon. No finalized output was observed. The next YouTube screenshot failed with browser.user unavailable. Remaining continuous visual review and completed prediction/help checks are still incomplete. No training or market-data collection started.


## Resumed eight-video visual pass

See krafer-visual-review-pass-2026-11-01.md for newly inspected decoded frames across all eight sources, explicit stale-frame exclusions and remaining gaps. Playback and screenshot inspection worked again, including signed-in Premium. This expands evidence but does not complete literal every-section/transition coverage. No training or collection started.
