# Krafer source review — 1 November 2026

## Coverage and limits

All eight supplied video transcripts have been read in full. Selected actual video frames were inspected across all eight; eleven user-supplied screenshots from The Most Accurate Model Yet were also read. This is not a completed continuous visual review of every second. Do not describe it as having watched every video in full. Native Chrome subsequently exposed the authenticated KAT page, including sentiment labels and chart controls. The earlier domain-resolution failure applied to the in-app browser. In the latest review attempt, Chrome screenshot and accessibility reads worked, but Predict help did not open and scrolling failed with noWindowsAvailable. Inventory still lists Chrome running and an in-app YouTube tab; fallback visual review has not been completed. No new model training or trading was performed.

## Requirements traced to the sources

| Source | Finding and location | Consequence for our independent model |
|---|---|---|
| [News](https://www.youtube.com/watch?v=3AsLPM0a3r8) | 2:00–4:22 separates forecast-minus-previous from actual-minus-forecast; 6:32–10:24 discusses different pre/post announcement effects. CPI curves inspected visually. | Separate pre-release expectations and post-release surprises. Preserve release timestamps and missingness; test the claimed directions rather than hard-code them. |
| [Simulator preview](https://www.youtube.com/watch?v=N4OJuoeNtkw) | Order history, zoom, accelerated generation; future simulator-trained AI is proposed at 1:52. Historical red/green depth and volume inspected. | Simulator needs event-level matching, historical depth and adjustable rendering. A proposal for future AI does not establish Tiger's eventual training dataset. |
| [Simulator construction](https://www.youtube.com/watch?v=oWheof70O9g) | 1:15 nearby random orders; 3:05–4:42 wall accumulation and changing maker/taker behavior; 7:02–8:21 orders accumulating around visited prices. Visual book bars and support zones checked. | Calibrate order placement, cancellation, consumption and replenishment; avoid indefinitely accumulating unrealistic liquidity. Patterns can emerge under these assumptions, without proving all real traders behave randomly. |
| [Entry study](https://www.youtube.com/watch?v=bfPtChR2knw) | Saved-state stochastic branches, 6:46–7:45 middle-of-cloud 50/50 versus waiting near a buy zone; 7:53 hidden orders; 11:03 volume/wicks; 16:25 wedge; 18:36 contrasting bull flag; 21:32–28:46 failures/reversals; 29:40 90% graphic; 31:03–32:46 80/20 coin analogy. Selected cloud, wedge and 90% frames checked. | Train distributions and target-before-stop outcomes; wait/reassess entries. Include cancellations and latent reserves. Simulated probabilities and analogies are not calibrated real-market win rates. |
| [Website demonstration](https://www.youtube.com/watch?v=jJkyUgwvcrU) | 1:04 historical book; 2:01–3:07 liquidity/news overlays; 3:18 tickers/models; 6:36 lower-timeframe detail when zooming. Visual heatmap and chart checked. | Candle viewer with historical heatmap, volume, news markers, model selector, origin markers, stored forecasts and resolution-aware historical zoom. Do not treat ten-minute depth snapshots mentioned casually as sufficient event-level training data. |
| [Tiger errors](https://www.youtube.com/watch?v=cVzO9GOW3WA) | 0:58–1:23 450→1,440 candles; 1:27–2:00 train/unseen/recent24h; 6:23 HLCV versus close. Error charts checked. | Match the 1,440 completed-candle context; clearly separate train/validation/test/recent outcomes and one-step versus recursive forecasting. Exact scaling not established. |
| [Accuracy](https://www.youtube.com/watch?v=JXw4bo59BpY) | 0:41 fulfillment; 1:52 threshold curves; 4:32 direction; 6:02 raw≈49.5%; 6:40–8:59 modified subset; 10:15 historical replay. Charts, website examples, and user screenshots checked. | Keep fulfillment, raw direction, conditional diagnostics and executable trade success separate. Never use the 76% headline as next-candle accuracy. |
| [Secret](https://www.youtube.com/watch?v=mIZEFP7af0w) | 1:13–1:28 time-of-day input; 1:30 BTC focus; 2:10–2:57 cross-crypto agreement; 3:23 session performance. Prediction overlays inspected. | Add calendar/session features and session-stratified tests. Cross-asset confirmation is an optional ablation, not a proven rule. Exact hours/timezone/horizon are not disclosed in narration. |

## Exact figures recovered from the user's screenshots

Tiger threshold table (share of samples attaining at least the stated fraction of the predicted move):

| Fulfillment threshold | Reported share |
|---|---:|
| 0% | 100.00% |
| 25% | 91.97% |
| 50% | 75.96% |
| 75% | 57.10% |
| 100% | 36.91% |

Separate table: Dir Acc 49%; Ave Pred 76%; Including 100% 59%; >90% 62%; >80% 65%; >75% 67%; >50% 80%. Those labels alone do not define denominators. Narration describes excluding fully fulfilled samples for the approximately 60% statistic, while the displayed label says including. Preserve the inconsistency until code or full methodology resolves it. The 80% row is not an established prospective entry-confidence threshold.

The screenshots show random-walk mean fulfillment 33.35% and full fulfillment 1.6%, Lion mean fulfillment 64.76%, full fulfillment 31.04%, and a separate strict win-rate card of 52.81% with TP count 367 and SL count 327. The bar chart shows Bobcat roughly 55% average fulfillment and 16% full fulfillment; Tiger roughly 76% and 36–37%. These are creator-reported results from an incompletely specified evaluation, not our replication.

The early screenshots show training/validation MSE curves with persistent gaps and different scales: approximately 10^-4 in one plot and hundreds of thousands in another. They do not identify all model versions, target transforms, or datasets. A generalization gap warrants investigation; the pictures alone do not prove leakage or diagnose its cause. Do not infer a learning rate or layer configuration for Tiger from a screenshot of one experiment. The 1e-5 example explicitly includes discussion of model collapse below the plot; realistic-looking generated candles are not sufficient evidence of forecasting skill. RSI/Stochastic/MACD panels shown in a comparison chart do not prove those indicators are input features.

## Architecture evidence

The creator [describes the implementation as custom and says it does not use LSTM](https://www.youtube.com/watch?v=JXw4bo59BpY&lc=UgyPzGSLaUJX4ezkuAp4AaABAg.AYWNz8FE7TGAYgi1VMRkGG). A [second author reply reports roughly seven million parameters](https://www.youtube.com/watch?v=JXw4bo59BpY&lc=UgyeddYPVjY9QbJ3rU94AaABAg.AZTOCLzOy0eAZzyiJnrHvz). Both were read from expanded comments. Neither specifies all layers, loss weights, preprocessing, or training inputs. The older LSTM/CNN comment thread did not finish loading on the latest attempt, so no content is attributed to its unread reply.

Our MLP is a proposed independent baseline, not an exact clone. Our explicit inputs are 1,440 candles plus public book/trade evolution, calendar information, available news and inferred hidden pressure. Direct book training of Tiger remains unverified.

## Corrections to avoid carrying into implementation

- Existing book liquidity influences price, but future market orders, new limit orders and cancellations are unknown at forecast time. No static book determines every future candle.
- The construction video actually argues patterns can emerge; the later video argues shape-only breakout rules can fail. Neither supplies a controlled real-market proof that every pattern is useless or every bounce is profitable.
- Candles and volume can suggest absorption or liquidity zones. They do not uniquely identify an exact hidden order quantity, participant or remaining reserve.
- An empty area in a finite simulated path cloud is not a proof of zero probability.
- 90/10 and 80/20 are the complementary examples in the entry video. “90/20” is not a complementary binary probability pair.
- “Recent market error” measures already completed predictions. It does not predict candles by itself.
- Hitting a predicted high/low at any point does not show a trade won: stop ordering, fills, fees, spread and timing matter.
- Historical prediction mode can replay a later-trained model on dates it may have seen. It is not automatically an unseen backtest.
- BTC is continuously traded. Session effects should be measured with explicit timezones, daylight-saving handling and weekend strata.

## Remaining work before claiming the user's full review is complete

1. Finish continuous visual coverage if the requirement is literally every moment, rather than selected demonstrations plus full narration. Current coverage must remain honestly labeled.
2. Complete authenticated KAT help and finalized forecast inspection. Page labels and screenshots have been inspected, but the selected model was ChatGPT Mini and the captured generation state was Predicting. Do not attribute that forecast to Tiger.
3. Resolve source ambiguities if a public methodology becomes available; otherwise leave unknowns explicit rather than inventing exact layers or metric formulas.
4. Present the revised training protocol before starting training. This note and the protocol do not authorize a training run.


## Signed-in website review update

Authenticated in-app KAT access succeeded after the user signed in. The narrow responsive chart showed Predict, ChatGPT Mini, density controls, DoM, 4 hours DoM, Cross, S/R, MA25/50/200/500/1000, Pred, Full and clear-predictions controls. Visually confirmed historical red/green liquidity heatmap behind observed candles, a vertical present-time boundary, a current-price label and depth bands to the right. Future-axis depth bands must not be interpreted as knowledge of future liquidity. Desktop help controls were not exposed in this responsive view; a temporary viewport override did not change the captured layout.

Read https://krafercrypto.com/ai-models: the creator advises against use during trends/extreme news conditions and claims strongest performance in low-volume/chop or after an extreme move. These are creator claims to evaluate with regime-stratified held-out tests. The page describes Bobcat relevance up to about 30 bars, Lion as trained longer with less extreme outputs, and Panther as trained on broader data. It does not establish Tiger's exact architecture or direct order-book training. The page advertises free signed-in ChatGPT 5.4-mini access; this is distinct from Tiger.

Read https://krafercrypto.com/gallery: five curated cases include a failed breakout labeled 30% and successful/partial moves labeled 80–90%. The text explicitly discusses early directional calls, timing/path deviations, reversals and moves completing hours later. These are illustrative selected cases with incompletely specified scoring, not an unbiased benchmark. Our test must score time-to-target and fixed forecast expiry; a target reached hours after expiry is not a success within the original horizon.

One free ChatGPT Mini generation was initiated to inspect its rendering. The UI changed to Predicting, a roughly 15-minute timer in the model selector, and a Receiving marker near the forecast origin. The timer's meaning was not verified; do not call it the generation duration or horizon. No finalized output was observed. The next YouTube screenshot failed with browser.user unavailable. Remaining continuous visual review and completed prediction/help checks are still incomplete. No training or market-data collection started.


## Resumed eight-video visual pass

See krafer-visual-review-pass-2026-11-01.md for newly inspected decoded frames across all eight sources, explicit stale-frame exclusions and remaining gaps. Playback and screenshot inspection worked again, including signed-in Premium. This expands evidence but does not complete literal every-section/transition coverage. No training or collection started.
