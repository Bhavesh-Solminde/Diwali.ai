# Diwali.ai — BTC trading-AI research

Research on BTC next-minute candle generation, order-book forecasting and Krafer market simulator experiments. Work is exploratory; simulator behavior and forecasting scores do not establish live trading profitability.

## Start here

- [Midpoint input audit](docs/planning/MIDPOINT-INPUT-AUDIT-2026-11-04.md) — explicit book midpoint recovered with exact parent replay/validity matching across October; unchanged cohorts, fit-only scaling. [Next1.2protocol](docs/planning/DIWALI1.2-ANCHORED-INPUT-PROTOCOL-2026-11-04.md) is specified, not trained.
- [Diwali1.1 direct order-flow correction](docs/planning/DIWALI1.1-ORDER-FLOW-2026-11-04.md) — averaged flow won development but regressed on benchmark probability quality; no promotion over0.9. Research replay at http://127.0.0.1:8751; matched prospective comparison completed9origins, all in one upward session.
- [Diwali1.0 explicit overall-direction objective](docs/planning/DIWALI1.0-DIRECTION-OBJECTIVE-2026-11-04.md) — negative controlled experiment: extra direction loss failed development checks, so no learned correction was adopted. Probability errors remain near50–50;0.9 stays the replay UI.
- [Diwali0.9 recent-candle detail](docs/planning/DIWALI0.9-RECENT-DETAIL-2026-11-04.md) — matched grouped/detail corrections; small historical changes, no strong directional edge. Replay at http://127.0.0.1:8749 includes net final-close up/down probabilities from the same price cloud.
- [Diwali0.8 coupled closing-price probabilities](docs/planning/DIWALI0.8-COUPLED-PROBABILITY-2026-11-04.md) — preserves 0.5 individual range forecasts while linking them with 0.7; replay and price-aligned chart at http://127.0.0.1:8748. A measured marginal/joint tradeoff; reliable high-confidence direction remains unproven.
- [Diwali0.7 joint/marginal training experiment](docs/planning/DIWALI0.7-BALANCED-PROBABILITY-2026-11-04.md) — matched continued-training and balanced-loss arms; replay at http://127.0.0.1:8747. The frozen selection chose continued joint training; individual-range error remains above0.5.
- [Diwali0.6 joint future-close paths](docs/planning/DIWALI0.6-JOINT-CLOSE-PATH-2026-11-04.md) — learned links between15 future closes, exact whole-range event probabilities; replay at http://127.0.0.1:8746. Joint scores improved over transition rules; individual-close scores/direction regressed slightly against0.5.
- [Diwali0.5 direct 15-close probability fan](docs/planning/DIWALI0.5-DIRECT-PROBABILITY-FAN-2026-11-04.md) — 26 price ranges at each future close, one forecast from frozen past inputs; replay at http://127.0.0.1:8745. Range errors beat frequency/volatility baselines; reliable high-confidence direction and joint path probabilities remain unproven.
- [Diwali0.4 closing-price ranges](docs/planning/DIWALI0.4-PRICE-RANGE-2026-11-04.md) — 18 learned endpoint price bins and coherent directional probabilities; local replay at http://127.0.0.1:8744. Range scores beat two simple baselines; directional improvement remains unproven.
- [Diwali0.3 longer order-history experiment](docs/planning/DIWALI0.3-MULTISCALE-2026-11-04.md) — controlled comparison of 60-second inputs with additional minute/hour histories; local replay at http://127.0.0.1:8743.
- [Diwali0.2 probability model](docs/planning/DIWALI0.2-PROBABILITY-TRAINING-2026-11-03.md) — next-full-minute bearish/neutral/bullish probabilities; local replay at http://127.0.0.1:8742.
- [diwali0.1 trained model and UI](research/diwali/README.md) — local historical replay at http://127.0.0.1:8741; [training results](docs/planning/DIWALI0.1-TRAINING-RECORD-2026-11-02.md).

- [Reusable model-training checklist](docs/checklists/MODEL-TRAINING-CHECKLIST.md) — copy for every new model/run; leave master unchecked.
- [Current aligned pilot readiness and baseline results](docs/planning/ALIGNED-EXPERIMENT-READINESS-2026-11-02.md) — three preparation tasks complete, limitations retained.
- [Frozen current experiment settings](configs/experiments/btc-button-pilot-v1.json)

- [Frozen specification and handoff](docs/planning/btc-model-frozen-spec-and-sol-handoff-2026-11-01.md)
- [Training and evaluation protocol](docs/planning/btc-model-training-protocol-2026-11-01.md)
- [Krafer source review](docs/planning/krafer-source-review-2026-11-01.md)
- [Visual coverage ledger](docs/planning/krafer-visual-review-pass-2026-11-01.md) — exhaustive viewing remains incomplete.
- [Windows simulator research prompt](docs/planning/windows-simulator-research/WINDOWS-AI-PROMPT.md)
- [Simulator rendering diagnosis](docs/planning/simulator-diagnostics-2026-11-01/report.md)
- [Windows simulator mechanics and ML handoff v1.1](docs/planning/windows-simulator-findings-2026-11-01/README.md) — v0.4 book logic; v0.5 whale impact, accounting defects and reproducible original-DLL host experiments.

- [Continue simulator research on Windows 11](docs/planning/windows-simulator-findings-2026-11-01/CONTINUE-ON-WINDOWS-11.md) — current state, verified manual tests, remaining work and screenshot workflow.

## Existing experiments

- [Candle generation prototype](research/next_candle/README.md) and [first saved forecast](results/next_candle/kronos-btc-1m-first/forecast.json).
- [Order-book benchmark](research/orderbook_benchmark/README.md), [protocol](research/orderbook_benchmark/PROTOCOL.md), [results](results/orderbook_benchmark/btc-60s-v1/report.md) and [ten-case charts](results/orderbook_benchmark/btc-60s-v1/ten-cases.png).

The limited benchmark did not establish a winning neural model; the simple imbalance baseline beat both tested neural entries. Read the report for exact scope, scores and unavailable models. The new simulator-informed model has not been trained. Windows original-DLL mechanics experiments are now documented separately from live Unity UI testing, whose automated frame capture remains unavailable.

## Migration and reproducibility

Moved from the BTC-AI portion of the local 100_TO_750k workspace on 1 November 2026. `MIGRATION.json` lists migrated paths. Other strategy research in that workspace is outside this repository's scope. The small existing foundation-model adapter was copied as a dependency, leaving the unrelated original project intact.

Research code, tests, protocols, recorded metrics and charts are included. Raw market datasets, environments, weights, purchased simulator applications, extracted vendor IL, full YouTube transcripts and machine preferences are excluded from Git. Some excluded evidence is retained in the local checkout. Existing research READMEs reference local foundation environments/data that must be provisioned separately; migration does not make those environments portable. No simulator license or paid assets are redistributed.

Run checks from this repository root with the required Python dependencies installed:

```sh
python -m unittest discover -s tests/next_candle -v
```

Some integration/model checks need separately acquired pinned model source/data. See the module READMEs before trying reproduction commands. Legacy historical notes may mention the former workspace; treat those as provenance, not current absolute paths.
