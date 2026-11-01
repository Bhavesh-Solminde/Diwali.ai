# BTC order-book forecast comparison

The completed run is in `results/orderbook_benchmark/btc-60s-v1/`:

- `report.html`: self-contained visual report with all ten detailed charts.
- `ten-cases.png`: all ten contrasting examples on one page.
- `report.md`, `summary.json`: methods, scores, limitations and source hashes.
- `cases.csv`, `test_predictions.csv`: all probabilities, predictions and actual outcomes.
- `TLOB.pt`, `DeepLOB.pt`: freshly trained task-specific checkpoints.
- `verification.json`: saved-score recomputation and ten timestamp-truncated forecast replays.

**Result:** TLOB and DeepLOB each got 4/10 examples right. Across 2,367 later
one-minute decisions, TLOB scored 39.92% accuracy / 35.24% balanced accuracy,
and DeepLOB 39.29% / 34.16%. A simple depth-imbalance rule got 7/10 examples
and 44.91% / 37.09% across the full test. Neither neural model beat that baseline.
This limited run does not establish a generally best model.

Both architectures were trained on the same earlier BTC data, with 8,000 windows,
three epochs, seed 42, Adam 0.0001 and validation-only epoch selection. They predict
midpoint direction 60 seconds ahead, using a fixed ±1 bp flat band. They do not
generate complete next-minute OHLC candles. Fresh task-specific training avoids
silently substituting the published checkpoints' event-count horizon for a minute.

All four requested entries were investigated, but only two could receive scores.
LOBERT has no official runnable release identified in the paper/author sources.
The requested generative LOBS5 model needs individual-order messages, order
references and a compatible trained checkpoint; the BTC dataset provides aggregate
L2 snapshots. The LOBS5 repository also contains auxiliary S5 classification
components; adapting those would be a separately named experiment, not a test of
its end-to-end generative model. No unavailable model is assigned predictions.

Data: 3,730,870 actual snapshot records, ten bid/ask levels, January 9–20, 2023,
from the Kaggle dataset linked by the TLOB author. Train January 9–17, validation
January 18, test January 19–20. UTC epoch milliseconds are authoritative; chart
times are displayed in IST. Missing seconds are not filled. Dataset venue and
size units are not independently certified. Archive/data/source hashes are saved.

The ten contrasting cases were frozen before training/scoring: rising, falling,
sideways, high/low volatility, bid/ask imbalance, wide spread, thin liquidity and
rapid midpoint changes. See [the protocol](PROTOCOL.md). Different criteria can
coexist in real markets. Candidate times are at least ten minutes apart. Because
recorded snapshots arrive at nearly fixed frequency, their count was rejected as
an activity proxy before training and replaced with past midpoint changes.

## Reproduce with the already-downloaded local inputs

From the repository root:

```sh
research/usd100_demo/runtime/foundation-env/bin/python -m research.orderbook_benchmark.data
research/usd100_demo/runtime/foundation-env/bin/python -m research.orderbook_benchmark.run \
  --output results/orderbook_benchmark/btc-60s-reproduction
research/usd100_demo/runtime/foundation-env/bin/python -m research.orderbook_benchmark.verify \
  results/orderbook_benchmark/btc-60s-reproduction
MPLCONFIGDIR=/tmp/btc-orderbook-matplotlib XDG_CACHE_HOME=/tmp/btc-orderbook-cache \
  .venv/bin/python -m research.orderbook_benchmark.report \
  results/orderbook_benchmark/btc-60s-reproduction
research/usd100_demo/runtime/foundation-env/bin/python -m unittest discover \
  -s tests/next_candle -v
```

The model environment already contains Torch, NumPy, pandas and einops. Rendering
uses the main environment's matplotlib. Training refuses to overwrite prior runs.
Existing data/model source downloads live under `data/orderbook_benchmark/` and
are ignored by Git. `acquire.py` fetches a hash-verified subset of pinned TLOB
source/checkpoints. Original-author DeepLOB and LOBS5 source archives and their
fingerprints are retained under `data/orderbook_benchmark/sources/`.

Checks cover exact 60-second targets, split-boundary isolation, missing-second
rejection, causal window preparation, ten unique separated cases and finite
training gradients in both actual author models. All 12 focused candle/order-book
checks pass. Independent saved-checkpoint replay reproduced all 20 case forecasts
within 0.0000001 probability difference and rechecked every full-test score.

No broker access, external messages, subscriptions or trading orders are involved.
