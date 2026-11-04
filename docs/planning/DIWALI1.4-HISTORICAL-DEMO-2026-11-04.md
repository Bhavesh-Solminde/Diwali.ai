# Diwali 1.4 historical probability demo

The trained final-build model is available locally at http://127.0.0.1:8754/. It uses the released weights and training-only transforms; opening the page does not train or change the model.

## What the page shows

- Ten evenly spaced examples from September 1–7 selection dates. They are already used dates, not fresh evaluation or live performance.
- Forty displayed past candles reconstructed from only the trade messages available strictly before each input freeze. All 400 displayed candles match their saved model-input features exactly. The model itself receives 1,440 candles.
- Fifteen direct closing-price probability distributions, plus up versus down-or-unchanged probabilities at selected closing times. The first target closes 105 seconds after the usual second-15 input freeze; it is not a 60-second-after-click outcome.
- Actual future **closes**, with no invented future OHLC candles, shown only after a valid prediction token is revealed. Predictions do not change after Reveal. White dots on the chart and dots in the detailed grid are answers, not AI price predictions.
- Completed development comparison and the reserved-test status. When the one-use final report exists, the page displays its aggregate comparison automatically.

The forecast cloud retains probability on both sides when the model is uncertain. It must not be cut to the side that later happened. Each column sums to 100%; unequal-width bins show whole-bin mass rather than density per dollar. The exact +2bp boundary follows the trained target convention. Marginal closes do not define the order of intraminute touches, a jointly likely path or target-before-stop entry odds.

## Validation and limitations

The input-only inference helper does not read future labels. Unit checks enforce no label access, case/token validation, probability mass and direction consistency, and immutable predictions after actuals are changed or revealed. All ten real local API examples passed predict/reveal/determinism checks. A local JavaScript DOM/canvas harness passed the 15-column, hidden-answer, reveal/reset and exact-boundary checks.

Visual browser inspection remains outstanding because the computer-use tool reported browser access disabled in Work settings. API and DOM checks must not be described as a screenshot review.

Run from the repository with the project Python environment:

```sh
../.venv/bin/python -m research.diwali.event_serve --port 8754
node tests/diwali/check_event_dashboard.cjs
```

Private demo artifact: `data/models/diwali1.4-final-v1/historical-demo.json`. Its contents and fitted weights are not published. Source and aggregate validation only may be pushed.
