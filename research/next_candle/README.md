# BTC one-minute next-candle generation

Input: consecutive, completed BTC/USDT spot one-minute candles, indexed by their
UTC opening timestamps. Output: **one next candle**, containing open, high, low
and close, plus generated alternatives and marginal uncertainty intervals.
These forecasts do not establish a trading edge or measure profitability.

First local check: 131,040 checksum-verified BTC minute candles downloaded for
January–March 2024. Kronos successfully generated 100 alternative candles for
March 31 at 23:59 UTC using only the preceding completed candles. Two of those
100 samples required the documented OHLC range projection. The saved example
is `results/next_candle/kronos-btc-1m-first/forecast.json`. Seven focused checks
pass in the existing foundation environment. This is an inference and software
check, not a forecasting-accuracy benchmark; the custom model remains untrained
on BTC.

## Existing model: Kronos-small

[Kronos](https://github.com/shiyu-coder/Kronos) tokenizes OHLCV candles and uses a
pretrained autoregressive transformer to generate subsequent candles. Its
`pred_len=1` setting matches this task. Kronos-small has 24.7M parameters and a
512-candle maximum context. Its ability to accept minute data does not establish
accuracy on BTC at that frequency. This project already has pinned local
Kronos weights, tokenizer, author source and a compatible environment under
`research/usd100_demo/runtime/`; the new wrapper verifies these existing pins.

[Chronos-2](https://github.com/amazon-science/chronos-forecasting) is a general
multivariate time-series alternative. The earlier project experiment used
15-minute FX data and a four-step close-price filter. It does not answer the
BTC one-minute forecasting question. See the preserved
[earlier results](../usd100_demo/FOUNDATION_MODEL_RESULTS.md).

From the repository root:

```sh
research/usd100_demo/runtime/foundation-env/bin/python -m research.next_candle.data
research/usd100_demo/runtime/foundation-env/bin/python -m research.next_candle.predict \
  --as-of 2024-03-31T23:59:00+00:00 \
  --output results/next_candle/kronos-example
```

The download defaults to January–March 2024, verifies exchange SHA-256 checksums,
and rejects incomplete months, gaps, duplicate minutes and invalid prices.
The original project's reserved 2025–2026 data are not used. Dataset/output
folders cannot overwrite existing completed outputs; choose fresh folders.

The example predicts the **historical** 23:59 UTC candle on March 31, 2024 from
128 completed candles ending at 23:58. Omitting `--as-of` predicts the minute
following the file's final candle, which is still historical for old data.
The last candle must already be closed in real time. No exchange connection,
API keys or orders are involved.

`forecast.json` records the forecast timestamp, context hash, model provenance,
median OHLC candle, marginal p10/p90 ranges and sampled direction fractions.
`generated_candles.csv` preserves each generated alternative. These sample
fractions are **uncalibrated model outputs**, not demonstrated probabilities.
Calling `predict_batch` with `sample_count=1` keeps individual samples; the
author's `sample_count>1` otherwise averages paths internally.

Kronos can decode inconsistent OHLC prices. This wrapper explicitly sets high
to the largest raw OHLC price and low to the smallest, preserves open/close,
and reports how often this projection was required. Non-finite or nonpositive
outputs fail. Missing quote volume (`amount`) uses an explicitly recorded
OHLC-mean × base-volume proxy. Pretraining overlap with historical inputs is
unknown, so zero-shot historical results cannot be certified unseen tests.

## Optional custom model

`model.py` and `train.py` implement a small transformer trained from scratch.
This is a continuous-token research prototype, not a pretrained language model.
It uses 64 completed candles, a causal attention mask, and Gaussian distributions
over gap, body and transformed wick coordinates. Decoding enforces valid OHLC.
Coordinates are conditionally independent; extreme samples have documented
numerical caps and their clipping rate is reported.

```sh
research/usd100_demo/runtime/foundation-env/bin/python -m research.next_candle.train \
  --epochs 6 --output results/next_candle/custom-v1
research/usd100_demo/runtime/foundation-env/bin/python -m research.next_candle.predict \
  --model custom --checkpoint results/next_candle/custom-v1/model.pt \
  --output results/next_candle/custom-example
```

Train/validation/test targets split 70/15/15 in time. Windows and labels use
only earlier candles; input/target scaling fits only training rows. Earlier
observed candles can serve as context in later splits. Training windows can be
shuffled **within** the training split, never across the split boundaries.
Default stride four samples training targets; validation and test use every
target minute. Epoch selection uses validation likelihood only. Holdout
reports include close and OHLC error against last-close and rolling-median
candle baselines, interval coverage and a Brier score against the training
up-frequency baseline. Repeat development after looking at test scores makes
that period exploratory; use a new reserved period for subsequent validation.

The custom model is not BTC-trained until the training command is run. Synthetic
training checks verify that training, checkpoint saving and inference work;
they do not establish real-market skill. Local model files should be trusted.

## Checks

```sh
research/usd100_demo/runtime/foundation-env/bin/python -m unittest discover \
  -s tests/next_candle -v
```

Checks cover future-data invariance, train-only scalers, exact target alignment,
causal attention, invalid/missing/unclosed input rejection, valid decoded
candles, and an end-to-end synthetic training/checkpoint/inference roundtrip.
