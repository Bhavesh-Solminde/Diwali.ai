# October pretraining review — 2 November 2026

Decision: **ready for pipeline experiments and fixed exploratory baselines;
not enough development-day coverage for a reliable MLP-versus-sequence selection.**
This is a coverage decision, not a profitability requirement. Do not consume the
locked test or silently shorten the 1,440-minute history to bypass it.

## Completed evidence

The corrected full-year audit reports `scan_complete: true`. October's causal
feature build completed. Its eligibility was independently recomputed from stored
validity/receipt arrays and the frozen candidate lists; all twelve partition/delay
index arrays matched exactly. Source archives and partitions were not changed.

| Partition | Calendar minutes | Quality candidates | Causal examples | Days represented |
| --- | ---: | ---: | ---: | ---: |
| Fit | 25,920 | 24,402 | 4,754 | 8 of 18 |
| Development | 4,320 | 4,078 | 468 | 1 of 3 |
| Calibration | 2,880 | 2,686 | 606 | 2 of 2 |
| Locked test | 11,520 | 11,291 | 1,322 | 4 of 8 |

Causal counts above use zero additional delay. Across September 30 context and
October there are 85 invalid source candle minutes: 65 source/audit rejections,
14 execution/reference mismatches and 6 missing execution minutes. Eight are in
the warm-up day; 77 are in October. Reasons are first-failure classifications,
not necessarily mutually exclusive underlying defects. Among 42,457 candidates,
31,543 fail complete candle context, 3,764 more fail receipt availability, and
7,150 remain. One bad minute can affect up to 1,440 following forecasts.

The local private `exclusion-ledger.jsonl` records every candidate's first failure,
number and causes of bad context minutes and latest receipt relative to cutoff.
Its hash and full daily counts are in the aggregate coverage report. Excluded
periods are not silently joined or fabricated. October has all 744 expected files
of each type; missing records/minutes can still exist inside a present file.

Retained fitting contexts have median preceding-hour return volatility 2.07 bp
versus 3.59 bp for excluded candidates, and median preceding-hour base volume
2,187 BTC versus 3,868 BTC. These are descriptive pre-origin comparisons, not
independent hypothesis tests. The retained sample underrepresents busy conditions.
The sole surviving development day is October 20. The 468 neighboring samples do
not supply 468 independent market regimes.

## Selected raw-data checks

A separate Python/Decimal reader examined raw executions in adjacent arrival hours,
without rewriting, deduplicating or interpolating them:

- September 30 09:32 UTC: 15,690 execution rows, source rejection, does not match
  the independent candle reference.
- September 30 16:29: 3,637 rows, independently confirms a candle mismatch even
  though the source's `bad` flag alone was false.
- September 30 21:15: no executions found in the selected adjacent-hour scope.
  This confirms the archive omission within that scope, not absence of exchange trades.
- October 3 14:36: 825 rows, matches reference; final receipt precedes the next
  minute by 422.30 ms. This is the last candle of a retained example's context.
- October 3 14:34: 286 rows, matches final reference, but last receipt is 68.15 ms
  after the next minute opens. Rejecting the 14:35 forecast is correct under the
  frozen minute-open rule; eventual candle correctness is insufficient.

A separately written Python/Decimal book replay applied 6,736 events to native
sequence 11726981172474 at October 3 15:02:59. All 80 top-20 price/quantity features
matched the C++ output within declared float32 tolerance; source receipt and event
clocks matched exactly. This checks one selected reconstruction, not every book
feature, every sequence, hidden depth or independent exchange authenticity.

## Fixed development baselines

Six rules were fixed in code before scoring development. No model hyperparameter
search, neural fitting or probability calibration was performed. Each predicts
next-minute OHLC relative to the last known close. Open persists at that close;
previous candle wicks supply upper/lower excursions. Momentum/reversal use the
previous close change; majority, top-20 imbalance and aggressive-flow rules use its
absolute magnitude with their respective direction. Majority direction uses only
fitting targets. The weak magnitude choice is explicit; these are starting rules.

| Fixed rule | Close MAE (bp) | Close direction correct |
| --- | ---: | ---: |
| No close change | 2.847 | 1.28% |
| Previous direction/magnitude | 4.076 | 46.79% |
| Previous move reversed | 3.798 | 50.21% |
| Fit majority direction | 3.897 | 49.36% |
| Book top-20 imbalance | 3.840 | 50.00% |
| Aggressive trade flow | 3.898 | 50.85% |

Direction uses three exact classes: down, flat, up relative to pre-origin close.
A flat forecast is correct only on flat outcomes, explaining its low direction
score despite the lowest close MAE. Full OHLC MAE/RMSE, class counts and balanced
accuracy are in the results JSON. These numbers do not establish a useful advantage;
one development day cannot support reliable day-to-day uncertainty estimates.
No calibration or locked-test target file was opened by this review program.
Quality checks may inspect reference candles as data evidence; the test has not
been used to select or score models.

## Independent source and recovery status

[Tardis Binance futures documentation](https://docs.tardis.dev/historical-data-details/binance-futures)
describes separately recorded depth/trade channels, REST bootstrap snapshots and
sequence checks; first-of-month CSVs are documented as public. However, HEAD checks
for October 1 BTCUSDT book and trade CSVs both returned 404. This does not establish
absence from all Tardis products. No overlapping independent book comparison was
possible with the publicly tested files, and no new purchase was made. Recorder
independence and matching native sequence semantics still need verification before
using a second source to certify or repair our archive.

[CryptoHFTData's corrections notice](https://www.cryptohftdata.com/docs/data-gaps-and-corrections)
still lists empty-snapshot omission and clock-related behavior. File presence and
successful replay cannot prove such omissions never happened. No undocumented
recovery or guessed replacement is permitted. October's main loss is the candle
context and receipt cutoff, so carrying earlier book state alone cannot restore
these examples. Earlier snapshot-free months remain outside this pilot; their
recovery is deferred, rather than pretending the October review repaired them.

A fresh direct Binance capture requested 90 seconds, lasting 100.01 seconds with
setup/shutdown, recorded 875 depth updates, 872 accepted book rows and 1,042 market
messages. Hash/chronology/book integrity passed, with no recorded connection error,
clock-step or trade-gap event. Two server-time probes had RTTs 242.80 and 164.10 ms;
the possible local-minus-server clock offsets were [-99.11, 143.69] and
[-95.28, 68.82] ms. These bounds include network uncertainty. The 1,500 fetched
closed reference candles are not 1,500 minutes of paired live book data. This is a
finite smoke capture, not sustained coverage, busy-period testing or proven reconnect
recovery. Raw data remains private and the process completed normally.

## Stage-specific next step

Keep the October feature fingerprint and exclusion rules frozen. Use this pilot
for correctness and later hardware smoke tests, with source/timing uncertainty
clearly labelled. Before treating a neural comparison as meaningful, build a new
quality-only chronological cohort with multiple usable development days and varied
pre-origin activity. Audit coverage before fitting or moving calendar boundaries;
record any revised split as a new version, preserving this pilot and its baseline
results. Do not select dates using model accuracy, alter timing to admit favorable
outcomes, or require a profitable model to justify reporting a failure.

A second-provider comparison and sustained direct recording are deferred evidence
improvements; the absence of either is not an endless bar to an explicitly
exploratory archive experiment. They remain necessary for stronger authenticity or
live-readiness claims. No historical repair can retrospectively establish unknown
original receipt times, and public feeds cannot supply all hidden liquidity.

## Reproduce and artifacts

```sh
python -m research.market_data.review_pilot \
  data/btc-perp/pilot-features-202610 data/btc-perp/pilot-202610-review \
  data/btc-perp/validation-v2-20261102 data/btc-perp/pilot-review-20261102
python -m research.market_data.trace_pilot \
  data/btc-perp/cryptohftdata-monthly data/btc-perp/pilot-features-202610 \
  data/btc-perp/validation-v2-20261102 data/btc-perp/pilot-review-20261102
python -m pytest tests/market_data -q
```

33 market-data tests passed. Aggregate coverage, development scores, selected raw
check summaries, independent-source probes and fresh-capture audit are published
under `results/market_data/pilot-review-20261102/`. Raw vendor rows, direct captures,
credentials and the per-origin private ledger are excluded from Git.
