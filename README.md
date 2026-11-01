# Diwali.ai — BTC trading-AI research

Research on BTC next-minute candle generation, order-book forecasting and Krafer market simulator experiments. Work is exploratory; simulator behavior and forecasting scores do not establish live trading profitability.

## Start here

- [Frozen specification and handoff](docs/planning/btc-model-frozen-spec-and-sol-handoff-2026-11-01.md)
- [Training and evaluation protocol](docs/planning/btc-model-training-protocol-2026-11-01.md)
- [Krafer source review](docs/planning/krafer-source-review-2026-11-01.md)
- [Visual coverage ledger](docs/planning/krafer-visual-review-pass-2026-11-01.md) — exhaustive viewing remains incomplete.
- [Windows simulator research prompt](docs/planning/windows-simulator-research/WINDOWS-AI-PROMPT.md)
- [Simulator rendering diagnosis](docs/planning/simulator-diagnostics-2026-11-01/report.md)

## Existing experiments

- [Candle generation prototype](research/next_candle/README.md) and [first saved forecast](results/next_candle/kronos-btc-1m-first/forecast.json).
- [Order-book benchmark](research/orderbook_benchmark/README.md), [protocol](research/orderbook_benchmark/PROTOCOL.md), [results](results/orderbook_benchmark/btc-60s-v1/report.md) and [ten-case charts](results/orderbook_benchmark/btc-60s-v1/ten-cases.png).

The limited benchmark did not establish a winning neural model; the simple imbalance baseline beat both tested neural entries. Read the report for exact scope, scores and unavailable models. The new simulator-informed model has not been trained, and Windows simulator pilots have not been conducted.

## Migration and reproducibility

Moved from the BTC-AI portion of the local 100_TO_750k workspace on 1 November 2026. `MIGRATION.json` lists migrated paths. Other strategy research in that workspace is outside this repository's scope. The small existing foundation-model adapter was copied as a dependency, leaving the unrelated original project intact.

Research code, tests, protocols, recorded metrics and charts are included. Raw market datasets, environments, weights, purchased simulator applications, extracted vendor IL, full YouTube transcripts and machine preferences are excluded from Git. Some excluded evidence is retained in the local checkout. Existing research READMEs reference local foundation environments/data that must be provisioned separately; migration does not make those environments portable. No simulator license or paid assets are redistributed.

Run checks from this repository root with the required Python dependencies installed:

```sh
python -m unittest discover -s tests/next_candle -v
```

Some integration/model checks need separately acquired pinned model source/data. See the module READMEs before trying reproduction commands. Legacy historical notes may mention the former workspace; treat those as provenance, not current absolute paths.
