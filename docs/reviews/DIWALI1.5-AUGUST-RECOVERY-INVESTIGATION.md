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

## Follow-up: the existing API keys were used

All five existing CryptoHFTData credentials authenticated successfully. Four download workers, each assigned a different credential, fetched the selected rejected hours and their preceding hours into a separate local directory. The predetermined 15 origins required 30 unique hourly files. Every request succeeded. The refreshed files were compared both with the original manifest hashes and with hashes freshly calculated from the original local files.

| Authenticated refresh result | Count |
|---|---:|
| Existing credentials authenticated | 5 / 5 |
| Unique hourly files requested and downloaded | 30 / 30 |
| Refreshed files identical to original local bytes | 30 / 30 |
| Changed files | 0 |
| Files containing no snapshot rows | 29 / 30 |
| Additional usable examples recovered | 0 |

The remaining file contained 2,000 snapshot price-level rows, grouped into two receipt/native-ID groups with 500 bids and 500 asks each. Those rows were already in the original archive. These groups must not be interpreted as two independently captured full books. No new snapshot or update was obtained. The unchanged bytes retain the outcome of the earlier continuous, snapshot-seeded replay; repeating that same replay would not supply additional information.

In plain language, a file can download successfully while still lacking the starting picture needed to interpret its changes. If an existing order never changed, an update stream alone need not tell us that order's quantity. Once the required nearest levels leave the snapshot's verified price range, a connected sequence of updates is insufficient to certify our required book input. Earlier hours have already been replayed continuously; this is not simply a failure to download the preceding hour.

The provider documents snapshots and updates within the same hourly order-book files, and says an hour can omit a checkpoint when it cannot prove the book current. Its documented flat-file interface accesses the shared dataset bucket; it does not establish a separate richer snapshot history. Corrections replace the same object key, making a fresh byte comparison a useful check. The provider's corrections page still marks the October quality release as not deployed when checked. These statements describe the documented interfaces, not proof that the provider has no additional internal recordings. [Order-book access](https://www.cryptohftdata.com/docs/rest-orderbook), [flat-file access](https://www.cryptohftdata.com/docs/flat-file-introduction), [corrections policy](https://www.cryptohftdata.com/docs/data-gaps-and-corrections).

The authorization failures in the earlier section were from **Tardis, a different provider**. They were not failures of these CryptoHFTData keys. No CryptoHFTData credential was sent to Tardis. Buying or supplying another credential for the same unchanged CryptoHFTData files would not, by itself, repair these tested windows.

The next useful recovery evidence is an additional historical snapshot or corrected file for the same exchange and contract, available before the applicable input window, with sufficient depth and native IDs to bridge the updates. Provider confirmation of such recordings, or a verified independent archive, is needed before expanding this attempt. Do not replace absent order quantities with guesses or waive the existing gates. This bounded sample does not establish that all August rejections are unrecoverable. No provider messages were sent, no original files were overwritten, and no forward model or eligibility rule changed.

[Aggregate authenticated refresh evidence](../../results/diwali1.5/august-authenticated-refresh.json). The refresh downloaded files solely for this recovery check; it did not create an expanded training dataset.
