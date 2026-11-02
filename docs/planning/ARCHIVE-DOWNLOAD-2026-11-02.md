# Real BTC archive download — 2026-11-02

User authorized CryptoHFTData access and historical order-book downloads. Credentials
are stored outside this repository, with owner-only file permissions. No key,
token, or raw authenticated response belongs in reports or Git.

## Started

- Binance USDS-M futures, BTCUSDT, 2026-10-03 through 2026-11-01 inclusive UTC.
- Hourly order-book snapshots/updates and matching executed trades: 1,440 files.
- Four workers, globally spaced requests (1.1 seconds minimum), HTTP retry handling,
  local SHA-256 manifests, Parquet metadata checks, resumable complete files.
- Data remains ignored under `data/btc-perp/cryptohftdata-20261003-20261101/`.
- Progress: that directory's `status.json`. Logs: `/tmp/trading-ai-archive-download.log`.
- Existing live recorder remains independent. No model training has started.

Run/resume from the repository with an environment containing requests and pyarrow:

```sh
python -m research.market_data.archive_sample \
  data/btc-perp/cryptohftdata-20261003-20261101 \
  --date 2026-10-03 --days 30 --workers 4
```

The key is read from `CRYPTOHFTDATA_API_KEY` or the private local credential file.
Keep the Mac awake and the download process alive. A full run needs at least about
27 minutes just for request spacing; transfer, retries and disk checks add time.
This is not a completion-time guarantee. Failed files remain listed for retry.

## Initial sample evidence

Separate sample: 2026-10-31 12:00–13:00 UTC, authenticated download succeeded.
Book: 3,512,497 level rows, 15,921,067 bytes. Trades: 57,466 rows, 689,853 bytes.
Both parsed as Parquet. Receipt times span the requested hour; receipt order did
not move backward in the book. Trade IDs were unique and contiguous in this file.
These are basic checks only, not proof of complete exchange coverage.

Full book replay/sequence checks, checkpoint handling, cross-file continuity,
trade/candle comparison against Binance, timestamp causality and usable-period
selection remain necessary. Downloaded files are explicitly NOT training-ready.
Hour-start checkpoints can contain state observed before the hour; do not treat
their generated boundary timestamp as original receipt-time evidence.

## Sources and limitations

- https://www.cryptohftdata.com/docs/rest-authentication
- https://www.cryptohftdata.com/docs/rest-orderbook
- https://www.cryptohftdata.com/docs/rest-trades
- https://www.cryptohftdata.com/docs/data-gaps-and-corrections

Provider documentation discloses older duplicate Binance snapshots and other
corrections. Preserve originals and record exclusions instead of silently repairing
or calling downloads validated. Book rows are price levels, not individual orders
or hidden liquidity. Aggressor mapping: buyer-maker true means aggressive sell;
false means aggressive buy. The generic order_type field must not imply actual
order instructions. News, hidden-book fallback and entry models remain deferred.
