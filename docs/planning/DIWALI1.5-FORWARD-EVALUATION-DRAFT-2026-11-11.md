# Diwali 1.5 forward comparison

The comparison has three candidates. The retained original model versus the volatility histogram is the primary comparison. The lower-learning-rate candle attention model is the declared challenger against both. The constant 50–50 direction score is a reference calculated in scoring.

| Candidate | Frozen fitting choice |
|---|---|
| Original control | Reuse the verified Diwali 1.4 full-August checkpoint |
| Volatility benchmark | Reuse the matched, fit-only volatility histogram and its calibration |
| Candle attention | C_attention_lower_lr, learning rate 0.0001, seed 17, one refit |

The challenger choice follows the original 15-close range objective. Its August development range log loss was 2.804723, compared with 2.832951 for the other attention setting. Both neural candidates use the same 5,391 August fitting origins, 862 September 1–7 checkpoint selection origins, and 1,476 September 8–14 calibration origins. The September 15–29 test remains consumed. [August data accounting](../reviews/DIWALI1.5-AUGUST-DATA-ACCOUNTING.md)

## Live issuance

The forward runner collects Binance BTCUSDT perpetual individual executions and full-speed depth, recording UTC and monotonic receipt times. It requires a full 24-hour native history and at least two of three prespecified engineering input checks. This is a new continuous recorder so warmup, forecasts and scoring use the same native journal. Completed hourly files are compressed and verified against their original byte hashes. The original short preflight remains separate.

After warmup, the runner writes an exclusive release with the next full UTC day as the start, the ten-day stop, the model and calibration hashes, source hashes, eligibility rules and scores. It issues every 15 minutes at second 15, up to 960 slots. The same strict-before-cutoff input and reference go to all three models. The native input gate requires a valid book seed and continuity, fresh book and completed-second reference, at least 99% valid candles in the 1,440-minute context and a valid latest candle. Missed or invalid inputs are journaled as skips. The forecast file must finish writing before the first target minute opens.

At a cutoff of 10:00:15, the first target closes at 10:02:00 and the last at 10:16:00. The outcomes are written separately after the final close and a 60-second grace. All 15 native closes, base volumes and execution counts must match the exchange's closed candles. This check applies equally to every candidate. [Binance USDⓈ-M candle API](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data#kline-candlestick-data)

## Evaluation

Score the fixed window once, with a minimum of 300 matched mature origins across seven distinct UTC days. Insufficient coverage is recorded as its own result. The primary result is the paired difference in average price-bin log loss over all 15 closes, control minus volatility. Separately report attention minus control and attention minus volatility. Lower log loss is better.

Report final-close up/down log loss, Brier and ROC-AUC against the 50–50 reference and the other candidates, plus raw and calibrated scores at each horizon and daily paired results. Up means close above the frozen reference, with equality treated as down or unchanged. Daily groups remain related through market conditions. Individual forecast, outcome and model files remain local.

The runner starts in warmup. The first eligible UTC day and exact stop are recorded by the release only after readiness passes. The readiness checks and any later scoring output belong to separate stages.
