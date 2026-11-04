# Diwali model experiments

## diwali0.4 closing-price probability ranges

```sh
python -m research.diwali.distribution --output data/models/NEW-DISTRIBUTION-RUN
python -m research.diwali.distribution_serve --port 8744
```

Default completed run `data/models/diwali0.4` predicts18 next-full-minute closing
return bins. Softmax probabilities sum toone; bearish/neutral/bullish probabilities
are coherent sums of those bins. Open tails are retained, not clipped. Select
adjacent bins in the UI to query their combined probability, then Reveal to see
the actual close's bin. This is one closing-time endpoint, not a15-minute path.

Categorical loss selected over ordinal-penalty alternative on three-seed mean
development bin log loss. Historical benchmark18-bin log loss2.62078 versus
fit-frequency2.76711 and past-volatility2.67456. Direction accuracy45.99%
versus0.2's45.83% is a tiny, unconfirmed change. Rare80% confidence calls were
all neutral and only7/12 correct; no dependable directional edge is established.
The requested full time-varying probability fan and fresh validation remain
outstanding. See `docs/planning/DIWALI0.4-PRICE-RANGE-2026-11-04.md`.

## diwali0.3 longer order-history experiment

```sh
python -m research.diwali.multiscale --output data/models/NEW-MULTISCALE-RUN
python -m research.diwali.multiscale_serve --port 8743
```

Default output: `data/models/diwali0.3`. It compares a matching short-history
control against the same network with 60 minute summaries and 24 hour summaries
of past order-book/trade observations. The original 60-second and 1,440-candle
branches remain. Invalid/missing history has explicit coverage indicators.
Both variants use 19,532 parameters and the same three seeds/training budget.
The0.2 saved probabilities are compared on identical benchmark examples.

This experiment tests longer context using existing one-second observations;
it does not restore subsecond events or identify cancellations/refills from
net depth changes. Fresh prospective confirmation remains outstanding. See
`docs/planning/DIWALI0.3-MULTISCALE-2026-11-04.md` for definitions and results.
Completed result: longer history selected by development, but historical
benchmark accuracy45.63% versus0.2's45.83%, with worse probability log loss
(1.03932 versus1.03383). No directional calls reached70% confidence. Keep this
as a negative experiment; do not promote over0.2 or scale on this evidence.

## diwali0.2 probability model

Train the single next-full-minute bearish/neutral/bullish probabilities with:

```sh
python -m research.diwali.probability --output data/models/NEW-PROBABILITY-RUN
python -m research.diwali.probability_serve --port 8742
```

The default completed run is `data/models/diwali0.2`. The probability server
shows the report and ten checkpoint-backed Predict/Reveal examples. The original
diwali0.1 UI remains on port 8741. Reference is explicitly the latest nonempty
received-second execution VWAP, at most two seconds old, not exact last trade or
absolute book midpoint. Primary neutral means closing within +/-2 basis points;
secondary flat means target close equals its own open. They are different events.

Selection compares three-seed development log loss for logistic, MLP and sequence
models. Calibration uses a separate chronological block. October24–31 was already
inspected in diwali0.1 and remains a disclosed shared historical benchmark.
This run's high-confidence forecasts were all neutral; it establishes no
80–20 bullish/bearish trading opportunities. A categorical model alone cannot
draw a valid continuous future-price cloud. See the 3 November training record
in `docs/planning/DIWALI0.2-PROBABILITY-TRAINING-2026-11-03.md`.

## diwali0.1 candle model

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
