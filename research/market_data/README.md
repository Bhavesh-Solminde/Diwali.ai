# Initial real-data pipeline

Scope agreed 2 November: public BTCUSDT perpetual candles, book and executions, fixed baselines, then a small MLP/sequence comparison once the paired dataset passes review. News, missing-book inference and entry modeling are deferred. No account credentials or trading endpoints are used.

`collect` records append-only hourly UTC JSONL, receipt UTC/monotonic times, exchange payloads, snapshot request times, instrument metadata, public aggregate trades and exchange candles. It reconnects after connection errors with bounded backoff; depth errors restart a fresh connection and snapshot, never carrying the previous book across a gap. `book` follows Binance USD-M U/u snapshot overlap then pu continuity. Duplicate/old updates cannot rewind a book; empty/crossed/invalid books are unavailable. Top20 snapshots include source receipt, update and snapshot IDs and connection segment. Finite snapshot range is not complete distant depth or hidden liquidity.

Raw data stays under ignored `data/`; output directories must be new. Status is periodically flushed/fsynced and atomically replaced. Graceful completion produces an SHA256 manifest. Interrupted captures without a final manifest require recovery/audit before use. No claim of crash-proof storage or perpetual service supervision. Collectors have a finite requested duration and must be supervised for long runs.

```sh
python -m research.market_data.collect data/btc-perp/run-UNIQUE --seconds 300
python -m research.market_data.quality data/btc-perp/run-UNIQUE
python -m unittest discover -s tests/market_data -v
```

Requires Python 3.11+ and `websockets` (tested local 17.3); quality/book use stdlib only. CPU/storage and hourly size must be measured before a sustained run.

The quality audit verifies hashes, row chronology, basic book integrity and closed exchange-candle bounds. It deliberately does not certify training readiness. Connection gaps, missing trade IDs, cross-stream alignment, actual paired feature windows and chronological holdout sufficiency need a subsequent dataset builder. Aggregate trades may differ from all exchange executions; do not use them to silently replace official candle volume.

Official sequence reference, checked 2 November 2026: https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/How-to-manage-a-local-order-book-correctly . Stream routing reference: https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams .

Recovery and button-timing implementation: see
`docs/planning/RECOVERED-BUTTON-DATASET-2026-11-02.md`.
`recover_candles` validates selected failed minutes against official individual
trades and records native-ID source comparisons. `button_dataset` creates a NEW
conditional historical cohort; official candle arrival time is assumed, not
invented as an observed receipt. `collect --snapshot-every 15` records immutable
actual-receipt input requests; `audit_freezes` checks bytes and replay provenance.
`frozen_inputs.prediction_record` rejects backdated or target-already-started
results. No model inference, website UI or trading is introduced by these modules.
