# diwali0.1

First small conditional historical BTCUSDT next-full-minute candle model. Local
weights/data stay under ignored `data/`; the report and code are in Git. A Python
standard-library HTTP server serves the UI and runs real inference from saved
weights. No frontend package installation, hosted service or account key is needed.

From the repository, with the prepared aligned dataset and recorded environment:

```sh
python -m research.diwali.serve --port 8741
```

Open http://127.0.0.1:8741 . Choose a historical case, click **Predict next candle**,
then **Reveal real candle**. Ten examples are evenly spaced through held-out
origins, selected without inspecting their prediction errors. The forecast is
computed now using trained weights and saved past inputs; it was not issued live
in October. Actual values are returned by a separate reveal request, not included
in the prediction inputs or initial case response.

UI tabs expose historical training/development/test errors, seven test baselines,
candle colour versus close-to-old-input direction, interval coverage, daily test
results, and every architecture/seed training run. “Live accuracy” stays unmeasured.
Chart whiskers represent the calibrated 80% closing-price interval, not a trade
win probability. Past-chart display is a subset; the model receives all 1,440
candles and 60 seconds of book/trade features.

A fresh rerun requires a NEW output directory:

```sh
python -m research.diwali.train --output data/models/NEW-RUN
python -m pytest tests/market_data tests/diwali -q
```

The current first-release trainer's report model name is diwali0.1; version the
name/protocol explicitly for later models. Never reclassify October 24–31 as an
untouched final test after using its results to improve a model. A later version
needs new unseen confirmation data or must label results as a shared benchmark.
The full history, corrected source exclusions, aligned five-field trade contract,
fit-only scalers, frozen model budget and date partitions are used unchanged.

Training selects checkpoint/architecture on development only, over three seeds
for each architecture. Seed 17 is preselected for inference, not chosen from test
results. Per-OHLC residual calibration is fitted on its separate block, before
opening final-test labels. The sequence model is 15,236 parameters, epoch 9 of
seed 17. MPS training and CPU interactive inference can differ slightly numerically;
all ten API examples agreed with stored MPS predictions within $0.01 in the check.

The historical arrival-time assumption remains. Short input-freeze/probe captures
and this demo do not establish live model accuracy, strategy profitability,
hidden liquidity or news/entry capability. The notebook-style charts use public
reference candle summaries; raw vendor rows, weights and arrays are not published.
