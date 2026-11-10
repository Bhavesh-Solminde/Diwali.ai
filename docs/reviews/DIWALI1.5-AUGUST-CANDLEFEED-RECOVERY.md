# August recovery: verified partial result

**Recovery succeeded for August 1. There are 963 newly usable forecast origins, while every original example remains preserved.** The remaining August dates are access-restricted with the supplied CandleFeed key. No model was trained or promoted.

| Measure | Result |
|---|---:|
| Independent August 1 snapshots downloaded | 288 |
| Snapshot price-level rows | 576,000 |
| Original August 1 passing input windows | 196 |
| Reseeded August 1 passing input windows | 1,127 |
| Original August 1 labelled examples | 181 |
| Reseeded August 1 labelled examples | 1,105 |
| Newly eligible labelled origins | 963 |
| Old origins absent from the fully reseeded stream | 39 |
| Original complete August dataset, preserved | 5,391 |
| Fully reseeded experimental August cohort | 6,315 |
| Unique original plus newly recovered origins | 6,354 |

The last two rows describe different collections. The fully reseeded version replaces August 1's book stream and consequently rejects some old windows during fresh-snapshot bootstrapping. The combined research index explicitly keeps the original input at all 5,391 originally accepted origins and adds only the 963 newly eligible origins. It contains no duplicate forecast origins and records each source version. It is not an automatically merged training tensor or a released training split. Both original and recovered cohorts remain intact.

## What was recovered and checked

The existing CryptoHFTData updates already covered August. The additional information came from independently captured CandleFeed REST snapshots. The August 1 snapshot file was 1,231,951 bytes; its size and SHA-256 matched the provider's listing. Native update IDs connect those anchors to the original updates. Buffered original updates become available no earlier than both their original receipt and the independent snapshot receipt. Exact decimal prices and quantities, native sequencing, verified top-20 depth, staleness, clock exclusions, completed candle history, reference prices and cutoff checks retain their existing rules.

The fixed four-origin August 1 test produced three complete examples. Midnight lacked a snapshot available before its required July 31 input window. Its original fixed sample was not replaced. The independent replay at 06:00, 12:00 and 18:00 passed the existing input and target gates. Other fixed sample dates remain blocked by account entitlement.

The full-day reconstruction then used all 288 snapshots, rechecked all 1,440 first-day forecast origins and rebuilt the monthly cohort through the unchanged builder. It recorded one failed native snapshot/update bridge and retained its invalid markers. A later snapshot re-anchors the book; windows crossing an invalid state stay excluded. The full-day book supplied 85,647 valid second grids out of 86,400. More valid seconds do not imply every 60-second event window passes.

The fixed replay uses a pre-window seed and original updates. The full-day stream also receives new snapshots during some windows. Consequently, the fixed and full-day windows need not contain identical events: at two fixed cutoffs, a fresh snapshot already covered four original updates still in flight at the other recorder. Their common native events had identical prices, quantities, validity and timing fields. The extra full-day bootstrap markers can conservatively reject those windows. This difference was audited rather than bypassing the gates.

Validation checked all 1,560 event-shard files, all 6,450 frozen window files, candle-input/target hashes and unique origin identities. All 94,725 target coordinates in the reseeded cohort matched the independent native execution aggregates. For the newly recovered examples, all 14,445 target coordinates also matched the official Binance archive's closing price, base volume and execution count: **zero mismatches**. The official archive passed its published SHA-256 checksum. Those finalized reference candles were used for target verification and coverage diagnosis, never substituted for causal model inputs.

The new source's inherited parent byte totals and raw-quality references were finalized against its own replay audits. Original raw-quality hashes remain recorded separately. This metadata correction changed no selected input, event-shard, window-index or target bytes; its before/after source-report hashes remain local.

## Access result and the remaining plan

An authenticated request covering August 1–31 returned only August 1 and marked the other 30 dates `plan_restricted`. Separate requests for July 31 and the fixed August 15, 22 and 29 dates returned `403 tier_restricted`. The key reports **Free**. The provider documents first-of-month samples for account holders and the full book archive under **Pro**; Builder and Advanced do not unlock the other book dates. Its coverage API lists all August BTCUSDT book days. Coverage metadata is not proof that every minute passes our gates. [CandleFeed access and schemas](https://candlefeed.ai/docs/order-book/), [plan details](https://candlefeed.ai/pricing/).

To continue:

1. Obtain CandleFeed entitlement for July 31 and August 2–31, or an authorized snapshot export for those dates. No purchase has been made. The same key can be retested after its account access changes.
2. Resume the checksum-aware snapshot downloader. It skips verified local files and reports restricted dates. Download snapshot files first; obtain same-venue native updates separately only if a required bridge cannot be established from the existing archive. Do not silently substitute a coarser feed.
3. Apply the fixed recovery tests on the other sampled dates before expanding the same reconstruction across the remaining days. Include July 31 so the August 1 midnight case can be tested.
4. Rerun every input and target gate. Record gains, losses, failed bridges and remaining first failures. Preserve the original dataset and explicit versioned references, then prepare a separately frozen matched training comparison if requested.

The currently supplied access cannot complete full-month recovery. Tardis is an alternative archive, but its supplied public first-day snapshot did not restore these windows and other dates require separate access. No credentials were sent across providers, and no provider messages were sent.

## Remaining limits

The 963 additions fall across the day's available hours. Among additions with a full prior-hour volatility calculation, the counts from lowest to highest original August volatility quarter are 629, 195, 50 and 43; 46 early additions lack that calculation within the August-only reference file. Recovery therefore improves coverage but does not establish balanced market regimes.

CandleFeed's August book receipt times have millisecond precision, and the providers' clocks lack a shared offset calibration. Availability remains a stated historical assumption, not proof of exactly what our live system would have received. The data observes public depth, not hidden liquidity. More usable examples do not establish improved directional accuracy or profitability. The active forward study's models and rules remain unchanged.

[Recovery plan](../planning/DIWALI1.5-AUGUST-RECOVERY-PLAN.md) · [Aggregate audit](../../results/diwali1.5/august-candlefeed-recovery.json)
