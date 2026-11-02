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

## 15-candle recursive replay update

The Predict button now runs 15 sequential model calls. Each generated OHLC is
encoded and appended to the rolling 1,440-candle context before the next call.
Book/trade arrays remain copied from the initial snapshot; traded volume, quote
volume and execution count are carried from the last input candle, not read from
future data. The original one-step checkpoint and reported one-step scores are
unchanged. No one-step calibrated intervals are displayed as 15-step confidence.

The initial task predicts the next FULL minute, leaving an unobserved in-progress
minute between last completed context and first target. Before first predicted
feedback is appended, a labelled flat-price bridge fills that context timestamp,
using the last known close and carried volume/count. This bridge is synthetic,
not a recovered or observed market candle. Every later forecast timestamp is
consecutive. Subsequent-step lead/context differs from the trained one-step task,
so this is explicitly experimental inference, not validated multi-step accuracy.

Cases now exclude starts that would put any of the 15 comparison targets outside
available October reference data. Ten cases are evenly selected among eligible
starts, without inspecting rollout errors. `/api/predict` returns `candles`,
`feedback`, assumptions and per-step input hashes; it does not read future raw
rows. `/api/reveal` separately returns all 15 real candles/errors for its token.
The UI displays blue generated candles, revealed real candles, per-step close
errors and an example-only summary. Existing Accuracy & errors tab remains the
ONE-STEP model evaluation and explicitly says it does not score this new rollout.

Tests verify actual feedback, consecutive synthetic context, no mutation of source
arrays, and invariance when future candle/book/trade rows are poisoned. All ten
examples passed the actual API flow and desktop/mobile browser checks. Total
market-data/model tests: 51 passed. See `results/diwali0.1/rollout-verification.json`.
