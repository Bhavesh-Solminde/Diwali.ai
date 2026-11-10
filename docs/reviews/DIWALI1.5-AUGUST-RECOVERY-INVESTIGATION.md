# August order-book recovery investigation

The predetermined sample contained 20 UTC time strata across August 1, 8, 15, 22 and 29, at hours 00, 06, 12 and 18. Within each stratum, the sample rule selected the first minute originally rejected for an invalid pre-window book seed. Five strata contained no such eligible rejection and received no replacements. Fifteen rejected origins remained.

| Sample result | Count |
|---|---:|
| Predetermined strata | 20 |
| Selected rejected origins | 15 |
| Empty strata | 5 |
| Origins tested with an independent historical snapshot | 4 |
| Origins requiring additional independent source access | 11 |
| Origins accepted for expanded training | 0 |

## What the source checks established

Tardis's raw API supplied a BTCUSDT Binance USDT-M depth snapshot at August 1, 00:00:01.2004129 UTC, with native update ID 11184978847013. It contained 1,000 bid and 1,000 ask levels. Applying buffered original updates after this snapshot connected 2,546,473 updates through hour 18 with zero sequence gaps and zero invalid events. The replay retained both providers' provenance and released any buffered transition only after the independently received snapshot was available. [Tardis Binance futures channels](https://docs.tardis.dev/historical-data-details/binance-futures)

The fixed 00:00:15 origin required a starting book before 23:59:15 on July 31. The independent snapshot arrived too late for that window. The fixed 06:00:15, 12:00:15 and 18:00:15 windows still had invalid seeds because the top 20 levels were outside the verified bounds of the applicable finite snapshot. A continuous native update sequence alone therefore did not satisfy the existing book gate. These failures occurred before the later trade, candle-history and target checks could establish a complete example.

The first exploratory replay incorrectly discarded updates received by the original recorder before the independent snapshot arrived. That broke the bridge. The corrected attempt buffered updates by native sequence and released them after the snapshot, producing the zero-gap chain above. All earlier attempts remain local. The result reports the corrected replay and the fixed sample without replacement.

Raw Tardis requests for August 8, 15, 22 and 29 returned authorization-required responses. The raw API's unauthenticated first-day access worked for August 1 even though the normalized first-day CSV URL returned 404. These are different access paths. The response does not establish whether every requested later snapshot exists behind an authorized subscription. [Tardis raw API access](https://docs.tardis.dev/api/http-api-reference)

The official Binance August 1 bookDepth archive was available. Its fields were timestamp, percentage, depth and notional. That format lacks native update IDs and individual price levels required to attach a snapshot to the delta chain. It cannot supply this missing seed. [Official Binance bookDepth archive](https://data.binance.vision/?prefix=data/futures/um/daily/bookDepth/BTCUSDT/)

## Coverage of retained examples

Volatility here is the root-mean-square of the preceding 60 completed one-minute close-to-close log returns. Quartile thresholds were computed over August origins with that full calculation available. The official August candle file passed its published SHA-256 checksum. These candles were used for coverage diagnosis only.

| Prior-hour volatility quarter | Candidate minutes | Retained examples | Retention within quarter | Share of retained examples |
|---|---:|---:|---:|---:|
| Lowest | 11,145 | 1,679 | 15.07% | 31.14% |
| Second | 11,145 | 1,550 | 13.91% | 28.75% |
| Third | 11,144 | 1,609 | 14.44% | 29.85% |
| Highest | 11,145 | 553 | 4.96% | 10.26% |

The 61 earliest August origins lack the full volatility calculation within the August file. All 5,391 retained examples have it. Retention also varies substantially by date, from two examples on August 27 to 682 on August 23. Retained counts by hour and day are included in the aggregate evidence. This establishes uneven coverage, while the first-failure ledger leaves the cause of each additional gate failure unresolved.

## Next recovery stage

A useful additional source must provide an applicable, timely historical snapshot for the same contract, with enough verified depth and native IDs to bridge all updates into the fixed window. The August 1 midnight case requires the preceding day's snapshot history. The other tested windows require a more recent or deeper snapshot. Access to raw snapshots for the other sampled dates would let the same fixed sample proceed.

After a seed passes, rerun every existing input and target gate. Record each later failure instead of counting the recovered book as a complete training example. Accepted examples will belong to the separate august-recovered-v1 dataset, with source identities, availability assumptions and gate outcomes. The matched original/attention training comparison begins only after that dataset contains accepted examples. The active three-model forward comparison uses its frozen artifacts.

[Aggregate investigation evidence](../../results/diwali1.5/august-recovery-investigation.json)
