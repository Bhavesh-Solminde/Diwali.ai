# Missing-data recovery investigation — 2 November 2026

The user asked whether rejected examples can be repaired by obtaining the actual
missing observations. **Yes for at least some execution/candle content.** Do not
substitute interpolation for observations or claim the original receipt clock has
been recovered. Existing datasets and scores remain unchanged pending a separately
versioned recovery build and eligibility audit.

## Verified free source: Binance USD-M futures trade archive

Official [archive documentation](https://github.com/binance/binance-public-data)
lists individual futures trades with native ID, price, quantity, timestamp and
buyer-maker flag. This is the matching venue/instrument family, not BTC spot or a
price index. Direct HEAD requests returned 200 for September 30 and October 1 daily
BTCUSDT trades, October 1 aggregate trades, and September 30 one-minute klines.

Downloaded the September 30 individual-trade ZIP (28,364,221 bytes), verified its
SHA-256 against Binance's `.CHECKSUM`, and rebuilt three source-problem candles
with Decimal arithmetic. All three match the existing independent Binance
OHLC/base-volume/execution-count reference exactly and quote volume within $0.01.

| UTC minute | Existing provider executions inspected | Official executions | Official candle matches |
| --- | ---: | ---: | --- |
| 2026-09-30 09:32 | 15,690 | 16,912 | Yes |
| 2026-09-30 16:29 | 3,637 | 5,706 | Yes |
| 2026-09-30 21:15 | 0 | 845 | Yes |

The official artifact is:
`https://data.binance.vision/data/futures/um/daily/trades/BTCUSDT/BTCUSDT-trades-2026-09-30.zip`

Its checksum is obtained by appending `.CHECKSUM`. The downloaded ZIP and full raw
rows stay private under ignored `data/btc-perp/official-recovery-probe-20261102/`.
Public aggregate evidence: `results/market_data/pilot-review-20261102/official-recovery-probe.json`.

These checks establish recovery of trade contents in three selected minutes, not
recovery of all 85 rejected minutes or a specific number of reinstated examples.
Official trade files do not contain our original provider's receipt times. Do not
assign artificial arrival timestamps to repaired trades or mark them timely under
the original minute-open input contract. Native IDs can support a later exact
missing-ID comparison; the count difference alone does not certify every row.

## Other sources for historical books and arrival evidence

- [Tardis Binance futures](https://docs.tardis.dev/historical-data-details/binance-futures)
  documents raw depth/trade replay, snapshots and local timestamps. Previously
  tested October 1 public book/trade CSV paths returned 404; availability through
  other products and an entitlement remain unverified. No purchase was made.
- [CandleFeed Binance USD-M books/trades](https://candlefeed.ai/data/order-book/)
  documents its own three-node collection, native U/u/pu IDs, snapshots and receipt
  clocks, with BTC book coverage beginning June 2026. It advertises an October 1
  free book sample. These are provider statements, not independently checked
  overlap or a verified repair. Inspect schemas, gap log, actual requested dates,
  sample bytes and matching sequences before choosing a subscription.
- [CryptoHFTData corrections](https://www.cryptohftdata.com/docs/data-gaps-and-corrections)
  says published corrections replace existing object keys; planned corrections
  are not deployed repairs. Compare a corrected file's provenance and hash before
  replacing anything; preserve originals. No promise that all October gaps are fixed.

A new recorder's receipt times describe that recorder, not our earlier provider.
It can support an explicitly separate timing experiment, not rewrite the original
latency history. Full historical books require compatible snapshots and unbroken
native update chains; candles or individual executions cannot reconstruct every
missing resting level.

## Recovery order

1. Inventory all 85 failed source minutes and obtain official individual-trade files
   for their dates, with checksums; use ordinary capped/resumable downloads.
2. Compare native execution IDs and reconcile repaired candles. Preserve source
   labels, originals and an exact repair ledger; do not mix receipt clocks silently.
3. Separate candle/trade-content recovery from actual receipt-time eligibility.
   Retain original strict timing results. Any finalized-official-candle or delayed
   issuance experiment needs an explicit versioned availability policy, not a false
   claim those candles were known at the original cutoff.
4. Rebuild eligibility to measure the actual number of restored examples. Repairing
   one minute can restore many overlapping histories, but overlapping repairs mean
   gains cannot simply be added or promised in advance.
5. Pursue a second book recorder only for book/independent timing evidence that the
   free official trade files cannot provide. Do not buy another full archive before
   testing exact overlapping samples.

No model training, new purchase, full archive redownload or original-dataset
replacement occurred in this probe.
