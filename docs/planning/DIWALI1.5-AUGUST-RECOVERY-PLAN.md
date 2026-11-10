# Recovering August order-book inputs

The goal is additional verified August BTCUSDT USD-M perpetual inputs for a separately versioned dataset. The running forward comparison remains frozen. A successful download, a recovered book seed and a complete labelled training example are three separate results.

## Sources in priority order

1. **Existing CryptoHFTData archive:** all August hourly files already exist locally. The continuous replay includes preceding July history. A fresh authenticated check of 30 fixed-sample hours returned identical bytes. Do not repeat the whole download without evidence of a correction. Any provider-supplied additional snapshots must include price levels, native IDs and availability provenance.
2. **CandleFeed:** the documented Binance USD-M archive includes snapshots up to 1,000 levels per side requested every five minutes, with native sequence IDs and receipt times. Its public coverage endpoint lists BTCUSDT books from June 4 through November 9, including all August dates. The August gap log reports a short August 17 interruption. Download access for August requires a CandleFeed account; first-of-month samples are free with an account, other August dates require the appropriate archive entitlement. Existing CryptoHFTData keys do not authenticate here. Start with snapshot files only, then obtain diffs if the native sequence cannot bridge to our existing updates. [Schema and access](https://candlefeed.ai/docs/order-book/), [coverage API](https://candlefeed.ai/api/v1/l2/coverage?dataset=book&symbol=BTCUSDT), [gap log](https://candlefeed.ai/data/order-book/gaps/).
3. **Tardis:** free raw first-day access has already supplied an August 1 midnight snapshot. Scan that day's snapshot channel for additional genuine captures before the predetermined windows. Other August dates require Tardis access. Normalized CSV probes for August 1 returned 404; this does not mean its raw API has no data. [Native snapshot channel](https://docs.tardis.dev/historical-data-details/binance-futures), [raw API](https://docs.tardis.dev/api/http-api-reference).
4. **Binance restricted historical L2 access:** investigate S_DEPTH/T_DEPTH availability only if an entitled exchange data account is available. Public percentage-band bookDepth files lack the per-price levels and IDs needed here. Do not treat account order histories, current REST depth, another exchange's book or spot BTC as the missing perpetual book.

## Fixed recovery procedure

1. Keep the existing 20-stratum sample and its 15 selected rejected origins unchanged; do not replace failures with easier minutes. Download missing snapshots into a new private directory, recording source, request, size, hashes and actual schema. Keep keys and signed URLs private.
2. For each origin, select the latest suitable snapshot **available before the start of its 60-second input window**, not merely before the prediction. Include the preceding day where necessary. Native IDs must overlap the first applied update. Apply any buffered overlapping update in full, and release it no earlier than both its original availability and the snapshot's receipt. A snapshot captured after the cutoff cannot repair an earlier input.
3. Replay forward in native message order, retaining all original raw files and clocks. Reject sequence breaks, conflicting levels, crossed books, stale updates or nearest 20 levels outside verified depth. Record cross-provider timing assumptions; different provider clocks do not establish the user's original live receipt time. CandleFeed's older book receipts have millisecond precision despite their nanosecond storage unit, and its merged nodes do not share a documented clock-offset calibration.
4. Once the book passes, run the unchanged complete input checks: recent trade validity/continuity, source clock exclusions, fresh reference price, 1,440 completed candle context with existing masks and coverage threshold, and strict input cutoff. Freeze successful inputs **before** inspecting their future labels.
5. Validate all 15 target candles and month-end boundaries. Record every first remaining failure. Count an example only after all input and target gates pass. Compare recovery coverage by date, time of day and prior volatility, including rejected origins.
6. Publish only code, aggregate counts and source/limitation reports. Store accepted additions as `august-recovered-v1`, preserving the original dataset and model artifacts. Expand recovery across August only after the fixed-sample adapter and gates succeed. Training or changing the forward study is outside this recovery task.

## Completion and access limits

Do not claim all August data is recovered from a successful sample. A recovered independent book still carries its provider's historical availability assumptions. If a source blocks an entitled request, record the status and the exact access needed; do not invent data, bypass access controls, or send one provider's credentials to another. No new paid purchase or provider message is authorized by this plan alone.

## Accessible-day expansion, declared before its labels are checked

The supplied CandleFeed key authenticated as Free. Its August 1 snapshot file downloaded and passed the provider's size and SHA-256 checks. July 31 and August 15 requests returned `403 tier_restricted`. Three of the four fixed August 1 origins passed the complete existing input and target gates; midnight lacks a preceding-day independent anchor.

Expand only August 1 first: replay all 288 captured snapshots with the original native updates into a separate source version. Keep the existing validator's exact prices, native-ID bridge, depth bounds and invalid-state markers. Retain all source rows and original clocks in their immutable archives; derived buffered availability is explicitly labelled. Then run the unchanged monthly cohort builder at every minute's second 15, replacing only August 1 books and referring to original sources elsewhere. Compare origins with the original cohort, recording gains and any losses. Select no origins using their outcomes. Preserve both complete cohorts instead of silently overwriting or merging their inputs.

No source from November or the active forward run enters this reconstruction. A successful day remains a partial recovery; the rest of August requires source entitlement and the same process. No model is trained as part of this expansion.

## Implemented result and resumption

August 1 expansion and its content audit completed: 963 newly eligible labelled origins; the separate reseeded cohort has 6,315 examples. An explicit research index preserves all 5,391 original examples and adds those 963, for 6,354 unique origins. It records the original/recovered source version and is not marked training-ready. See the [recovery report](../reviews/DIWALI1.5-AUGUST-CANDLEFEED-RECOVERY.md).

The month-wide authenticated request confirmed August 2–31 are plan-restricted. After appropriate access becomes available, resume snapshots without re-downloading verified files:

```sh
../.venv/bin/python -m research.market_data.candlefeed_snapshots \
  --start 2026-08-01 --end 2026-08-31 \
  --output data/btc-perp/candlefeed-august-snapshots-v1
```

Request July 31 separately for midnight continuity. The current replay scripts deliberately implement August 1 only; extend them to the newly authorized dates and rerun the fixed tests before claiming further recovery. No new model fit or forward-study modification is part of this command.

August 1 received a second pass using the most recent eligible snapshot before each input window. It recovered 237 of the 271 origins missing from both earlier input ledgers. The updated research index contains 6,591 unique examples. Use the same causal replay and target verification when access to the other dates becomes available. [Follow-up result](../reviews/DIWALI1.5-AUGUST-CANDLEFEED-RECOVERY.md#follow-up-replay-with-a-snapshot-before-each-input-window)
