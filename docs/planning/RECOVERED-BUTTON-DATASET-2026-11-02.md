# Recovered data and frozen button inputs — 2 November 2026

Implemented at the user's request to recover real data, explicitly timestamp button
inputs, and separate historical availability assumptions from measured live receipt.
No neural model was trained, no news/entry/fallback component was added, and no
trading endpoint or account credential was used.

## What changed

The original October dataset, its 7,150 strict origins, partitions and baseline
results remain unchanged. A separate `button-pilot-202610-v1` dataset predicts the
**next full calendar-minute candle after the input snapshot**. For example, a
snapshot at 10:01:15 forecasts 10:02–10:03, not 10:01–10:02. Model results ready at
or after 10:02 are rejected for that target. This changes both information time
and forecast lead time, so performance cannot be compared as the identical task.

Historical snapshots are sampled at 0, 15, 30 and 45 seconds of each minute to
represent button clicks. Arbitrary actual click times are supported by the live
freeze function; the four training phases are a declared approximation, not proof
of generalization to every click time. The primary cohort uses phase 15 seconds.
Multiple snapshots for one target are correlated. All snapshots for a target stay
in its calendar partition; compare on common targets and summarize uncertainty by
day/target, not as independent extra candles.

## Content recovery and corrections

`recover_candles.py` fetched only the 24 affected dates from Binance's free USD-M
BTCUSDT individual-trade archive with three capped workers. Completed ZIPs are
reused only after checksum verification; failed partial files are redownloaded,
never treated as finished. Original vendor files are untouched. Provider native
trade IDs were compared within the previous/current/next arrival hours for each
of 85 bad source minutes. Common IDs had to agree on price, quantity, trade time
and aggressor flag. Duplicate/conflicting IDs are rejected, never silently averaged.

All **85 of 85 candle-content problems now have an accepted reconstruction**:
84 from the official daily trade file and one from a consistent native-ID union
of official and provider records. Reconstructions match the independent Binance
candle reference in OHLC, base volume and count; quote tolerance is $0.01.
The scoped comparison found **351,996 market-execution IDs absent from the
provider records inspected**. This is an aggregate over the selected bad minutes,
not a claim about every missing execution in the entire year.

Two findings prevented blindly treating every discrepancy as a provider gap:

- Insurance-fund/ADL records are not ordinary order-book executions for the
  [official market-trade endpoint](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data).
  Our earlier native scan recognized zero NA placeholders but did not separately
  recognize insurance/ADL events. This could mark a candle bad or contaminate its
  volume/count. The new scanner excludes these records from market candles/flow
  while preserving their IDs for continuity. The recovery scope included 156
  insurance-fund records and 628 NA placeholders. This is a validator correction,
  not proof those records were missing from the provider.
- October 30 13:45 UTC: the official daily file has 8,085 executions but the
  independent reference has 8,400. The provider contributes 315 additional market
  IDs. Common IDs agree, and their union reconstructs the full reference candle.
  This repair records both sources; it does not assume the official daily ZIP is
  flawless or fabricate missing executions.

The full-year v2 audit is preserved as historical evidence and has not been
rerun with this new insurance/ADL classification. Original quality exclusions
remain conservative. The new dataset refreshes the 768 trade feature hours with
corrected filtering and a maximum-time guard covering **both event and trade
timestamps**. It reuses the unchanged, hash-verified book stream. Audit clock
exclusions remain in force; recovery does not promote invalid book intervals.

## Timing policy: assumption versus observation

Recovered official trades do not reveal the original provider's receipt clock.
No synthetic `received_time` is assigned to them.

Historical candle features use a versioned assumption: the candle becomes usable
strictly after its close plus a declared grace. Test 1, 5, 30 and 60 seconds; the
primary is 1 second at phase 15. Grace is a sensitivity setting, not a guaranteed
network delay. Because candles are whole minutes, some grace/phase combinations
select identical histories; the longer settings also test older complete history.
Every input still contains exactly 1,440 consecutive reconciled candles. No gap
joining, interpolation or context shortening is introduced.

Book/trade inputs retain the last 60 complete receipt-second buckets strictly
before the snapshot. Every included source event/trade time must also precede it.
Invalid/stale/uninitialized/crossed/out-of-bounds book records and invalid trade
seconds remain excluded. Fixed calendar split dates are unchanged; every target
finishes inside its own partition. Fit-only scalers are learned from primary
fitting windows. No development, calibration or test values contribute to scalers.

This dataset is labelled **historical candle availability ASSUMED** and
`verified_leakage_free_live_test: false`. It supports an exploratory comparison;
it cannot demonstrate that the repaired candle values arrived at a particular
historical computer by a particular millisecond.

## Final primary cohort

| Partition | Examples | Target days represented |
| --- | ---: | ---: |
| Fit | 24,421 | 18 of 18 |
| Development | 4,079 | 3 of 3 |
| Calibration | 2,688 | 2 of 2 |
| Locked test | 11,296 | 8 of 8 |
| Total | 42,484 | 31 of 31 |

These are one phase/one grace counts, not all repeated phases added together.
The original 7,150 set is retained for reference, not overwritten. The improvement
combines content verification, corrected non-market filtering and a changed target/
availability policy; it is not 35,334 examples newly proven timely under the old
minute-open contract. Invalid book/trade intervals still remove examples. No
locked-test predictions or model scores were inspected to choose phases or dates.

The earlier limitation review's one-day development obstacle is superseded for
this **new conditional experiment**. Small exploratory MLP/sequence comparison is
now feasible after freezing its model budget and metrics. Broad real-time
performance still requires prospective predictions, rather than relaxing data
rules until a desirable accuracy appears.

## Actual-receipt live input implementation

`frozen_inputs.py` maintains received finalized exchange candles, verified book
state and trade history. Snapshot creation:

1. Requires continuous trade capture and a fresh complete 60-second book history.
2. Uses only 1,440 received consecutive finalized candles. REST rows are classified
   as closed using a conservative server-clock lower bound, not a fast Mac clock.
   Their actual local response receipt is their availability time in this capture.
3. Keeps source UTC and monotonic receipt times and rejects clock steps, recent
   trade gaps, stale/insufficient depth, future source times or unavailable history.
4. Uses last 60 complete trade buckets and corresponding one-second book states;
   checks top20 against finite snapshot price bounds.
5. Deep-copies inputs and writes an exclusive, SHA-256 identified request file.
   Subsequent chart updates cannot mutate it. No target outcomes enter the request.
6. Provides a result guard that rejects backdated completion times or a prediction
   completed at/after its target starts. The future UI/model must call that guard.

This is the input backend and recording path, not a finished website Predict
button or a trained forecasting service. Scheduled freezes imitate clicks in the
smoke capture. Live aggregate trades remain distinct from full individual archive
executions; future train/live feature alignment must address aggregation semantics
before claiming the same trade distribution.

The final 180-second requested smoke capture lasted 191.94 seconds with setup and
shutdown, saved six eligible requests, and rejected five attempts (four warm-up,
one unavailable book history). All six hashes and raw-source replays matched, and
strict cutoff/target checks passed. It recorded 1,758 depth messages, 1,751 book
records and 9,373 market messages. It made **zero model predictions and zero trades**.
A separate earlier run correctly rejected windows spanning a >1-second stale-book
gap. These are engineering checks, not sustained coverage or forecast accuracy.

## Artifacts and reproduction

Local private outputs:

- `data/btc-perp/official-recovery-20261102/`: checksummed daily ZIPs and per-minute
  source/ID/reconciliation ledger, without invented arrival times.
- `data/btc-perp/button-pilot-202610-v1/`: corrected trade seconds, indexed frozen
  histories, separate next-full-minute targets, fit-only scalers and manifests.
- `data/btc-perp/button-freeze-final-smoke-20261102/`: raw direct recording,
  immutable requests, capture hash manifest and independent request audit.

Public aggregate summaries: `results/market_data/recovery-button-20261102/`.
No paid raw rows, large arrays or credentials are committed.

```sh
python -m research.market_data.recover_candles \
  data/btc-perp/cryptohftdata-monthly data/btc-perp/pilot-features-202610 \
  data/btc-perp/validation-v2-20261102 data/btc-perp/official-recovery-20261102 --workers 3
python -m research.market_data.button_dataset \
  data/btc-perp/pilot-features-202610 data/btc-perp/validation-v2-20261102 \
  data/btc-perp/official-recovery-20261102 data/btc-perp/button-pilot-202610-v1 \
  --archive data/btc-perp/cryptohftdata-monthly
# Use a NEW output directory for every capture; this is finite, not a daemon.
python -m research.market_data.collect data/btc-perp/NEW-CAPTURE \
  --seconds 180 --snapshot-every 15
python -m research.market_data.audit_freezes data/btc-perp/NEW-CAPTURE
python -m pytest tests/market_data -q
```

Next: freeze a small model comparison protocol for this explicitly conditional
cohort, retain development-only selection and untouched test targets, then record
prospective model predictions against actual-receipt requests. Do not describe
input capture alone as a live model test or repaired timestamps as authenticated.
