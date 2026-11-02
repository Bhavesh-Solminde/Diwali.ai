# diwali0.1 — first model and historical replay UI

Trained on 2 November 2026 under the frozen `btc-button-pilot-v1` protocol. This
is a conditional historical experiment; candle finalization availability remains
assumed. No live model predictions or trades were performed.

## Result

The selected sequence model has **15,236 parameters**, seed **17**, checkpoint
**epoch 9**. Architecture selection used the mean development result over seeds
17/29/43. Seed 17 was specified before evaluation, not picked from the final test.

| Error view | Examples | Average OHLC absolute error |
| --- | ---: | ---: |
| Training | 24,421 | 2.989 bp |
| Development | 4,079 | 3.538 bp |
| Final historical test | 11,296 | 3.504 bp |
| Recent live market | None | Not measured |

One bp is 0.01%. The test's 3.504 bp is about **0.03504%** average absolute error
across open, high, low and close. Test close MAE alone is **4.276 bp**.

The strongest simple test baseline, recent traded-price persistence, has mean
OHLC MAE **3.588 bp**. The model's error is **2.34% lower** on this one test. This
small descriptive improvement is not evidence of a profitable strategy or broad
statistical superiority.

**Green/red/flat candle-colour accuracy is 48.61%.** This does not demonstrate
strong candle-direction prediction. The different **61.61%** metric compares the
future close with the older final input candle close; some of that movement can
already be visible at the input snapshot. It is not candle-colour accuracy, a
calibrated win probability or a trading win rate. Both definitions appear in the UI.

Calibrated 80% marginal per-price intervals covered about 80.7–80.9% of test
prices. The 95% intervals covered about 93.0–93.8%, below nominal. Calibration
used only the separate 2,688-example block; dependence and two days of calibration
prevent an IID/future-coverage guarantee. These are four separate intervals,
not an 80% chance the entire candle or a trade is correct.

## Prespecified runs and resource use

| Architecture | Seed | Epochs run | Selected epoch | Development OHLC MAE |
| --- | ---: | ---: | ---: | ---: |
| MLP | 17 | 6 | 2 | 3.808 bp |
| MLP | 29 | 6 | 2 | 3.833 bp |
| MLP | 43 | 5 | 1 | 3.792 bp |
| Sequence | 17 | 13 | 9 | 3.538 bp |
| Sequence | 29 | 12 | 8 | 3.543 bp |
| Sequence | 43 | 15 | 11 | 3.533 bp |

Architecture mean: MLP 3.811 bp versus sequence 3.538 bp. No extra search or test-
driven refitting followed the result. Training used float32 PyTorch 2.15.0 on MPS,
with the preset optimizer, budget, three seeds and early stopping. Total wall time
including preparation/calibration/evaluation was approximately **382 seconds**.
Peak recorded epoch process RSS was approximately 3.19 GiB. Seeded MPS execution
is not claimed bitwise deterministic across machines/runtimes.

Final test was accessed only after selection.json was written and residual interval
calibration completed. **October 24–31 is now a consumed test for diwali0.1.**
Changes motivated by these results require new later unseen confirmation data,
or must explicitly report October as a shared inspected benchmark.

## UI and inference

Local URL: **http://127.0.0.1:8741**. Standard-library Python backend, static UI,
no account key and no external chart/runtime dependency. The model and data remain
on the Mac. Tabs: historical replay, accuracy/errors and complete training record.

Ten historical test origins were selected by evenly spacing through eligible
indices, without choosing successes or failures. The replay shows past candle
context and a separate enlarged target comparison; it is not a live chart.

- **Predict next candle** runs the saved sequence weights now on the selected
  historical input window. All 1,440 candles and 60 seconds of aligned book/trade
  features are used; the chart shows only a recent subset for readability.
- **Reveal real candle** obtains the target via a separate API request and displays
  OHLC errors and candle colour. Actual target values are absent from the initial
  case response and the model-input construction.
- Prediction duration is actual measured local calculation time, not an animated
  pretend forecast. It is separate from historical snapshot/target timestamps.
- The demo does not claim the forecast was issued before the historical event.
  CPU demo inference can differ slightly from MPS batch evaluation; all ten API
  predictions matched stored test outputs within $0.01.

The app's native browser-control preview was disabled. An isolated headless Chrome
with a fresh profile was used for UI checks, not the user's personal browser
session. Desktop and 390px mobile renderings were inspected. Predict, reveal,
example switch/reset, accuracy tab and training tab worked; zero JS errors and
no mobile horizontal overflow. Mobile chart layout was adjusted after inspection.

**49 tests passed** across market-data and new model checks. These include valid
OHLC output constraints, weight save/load inference agreement and rejection of
future candle/trade rows by model-input slicing. All ten historical API cases
were checked against saved predictions and target labels.

## Files and rerun

- Public results: `results/diwali0.1/` (report, protocol, selection, calibration,
  environment, UI verification and preview).
- Private weights and arrays: `data/models/diwali0.1/`.
- Source: `research/diwali/`; UI: `ui/diwali/`.
- Run server: `python -m research.diwali.serve --port 8741`.
- Fresh training: `python -m research.diwali.train --output data/models/NEW-RUN`.
  The first-release report name is diwali0.1; explicitly version later releases.

The existing server is detached for local use. Its PID/URL are recorded privately
in `data/models/diwali0.1/ui-process.json`; logs are `/tmp/diwali01-ui.log`.
The UI needs this local Python server and private weights/data; Git alone does
not contain large datasets or trained checkpoints.
