# October causal feature build

User authorized implementation after an explanation of the next stage. Scope is
input/target construction and leakage checks; no model fitting, news, fallback,
entry scoring or trading is part of this build.

The builder replays all October books and September 30–October 31 trades from
unchanged hash-verified files. September 30 provides the preceding candle day.
It uses the corrected audit and the frozen 42,457 candidate-origin manifest. Only
accepted origins can remain; this step may shrink that set and never reinstates
excluded origins. Its output is local under `data/btc-perp/pilot-features-202610/`.

## Inputs, targets and clocks

- Candle input: exactly 1,440 completed consecutive minutes, with local candle
  features for body/range, volume, count and UTC minute encodings. Every source
  candle must reconcile with independent Binance OHLCV/count. Availability uses
  the latest observed receipt time among its execution messages, not the archive's
  eventual download time. This is an experimental historical availability proxy,
  not proof of the vendor's original clock or the client's live collection latency.
- Book input: 60 complete one-second records. Each contains the top 20 bid/ask
  distances from midpoint and log quantities, spread, top1/5/20 imbalance, depth
  totals and microprice offset. Replay must be sequence-valid, uncrossed, fresh and
  inside verified snapshot bounds. Source receipt/event times and sequence IDs are
  retained. Checkpoint or receipt anomalies excluded by the audit remain excluded.
- Trade input: receipt-time second buckets of aggressive buy/sell quantity,
  notional, counts and VWAP. Binance NA zero-price messages keep their IDs for gap
  checks but contribute no execution price, volume or count. Buyer-maker means
  aggressive sell. Empty-second VWAP change is zero, not a fake negative price move.
- Target: the following independent Binance one-minute OHLCV/count. Target arrays
  are separate from indexed input histories. Each target must finish within its
  frozen fit/development/calibration/test partition.

Strict cutoff: every included receipt and exchange event timestamp must be before
the prediction origin. A candle whose final used execution arrived at or after
the cutoff is rejected. No filling a previous candle with a late value while
claiming that value was available at minute open. This can materially reduce the
sample count; report that result rather than loosening the rule to improve scores.

Build additional 250 ms and 1,000 ms delayed-information scenarios by shifting the
input cutoff backward. Only fully observed receipt-second buckets may be used;
the 250 ms case therefore conservatively drops the unfinished second. Scenarios
can have different eligible samples. Compare future model results on common origins
if making an incremental-performance claim. These are input-availability stresses,
not a calibrated simulation of the vendor's unknown timing errors.

## Leakage and output contract

Frozen partition origin hashes must match. Partitions cannot share targets; target
minutes cannot cross boundaries. No timestamp compression or joining gaps.
Input histories contain no target-minute observations. Fit scalers only using the
input windows of eligible fitting examples; calibration/development/test values
must never contribute. Store fit-only means/std, feature order and provenance.
Historical context can precede a partition if already available at issuance.

Outputs: hash-identified binary one-second records; indexed input windows; separate
next-minute target arrays; candle features/raw references and receipt masks; fit-only
scalers; per-partition rejection counts at each delay; dataset manifest. Repeated
overlapping windows are not independent samples. No inference of hidden orders is
introduced. Full-history arrays stay local; publish aggregate quality summaries only.

The build uses two extraction workers. Progress files: `book-progress.json`,
`trades-progress.json`, `build-state.json`; log `/tmp/trading-ai-pilot-feature-build.log`.
Successful extraction is resumable if source/code fingerprints and output hashes
agree. An interrupted incomplete stream is rebuilt to preserve replay correctness.
No eligible fitting examples produces an explicit failed-data-gate summary and no
scaler fitting, rather than silently changing the cutoff.

Validation: 30 market-data tests passed, including receipt-cutoff boundaries,
future trade rejection, incomplete context, invalid book seconds, empty-bucket
handling and scaler arithmetic. Real-hour smoke test: 3,600 aligned seconds each;
3,599 book seconds valid (initial second unavailable), 3,600 trade seconds valid;
all features finite. The full run must finish before final counts are claimed.

Next after completion: review per-day/partition coverage, independently check the
feature provenance on selected examples, freeze baseline/model budgets and only
then fit the authorized small pilot. Training readiness is separate from source
authenticity, live performance, probabilistic calibration or trading profitability.

Completed-run update: all 744 book hours and 768 trade hours finished. The frozen
feature build retains 7,150 origins at zero additional delay. See the
[executed coverage/limitation review](OCTOBER-PRETRAINING-REVIEW-2026-11-02.md)
for the severe day-level concentration, development-only baselines and readiness
decision. Earlier statements about awaiting the full run are historical.
