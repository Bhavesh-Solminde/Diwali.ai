# Before-training limitation plan — 2 November 2026

User requests a plan to address the listed archive limitations before training.
No training is authorized by passing a file scan alone. This plan adds a review
gate to the existing staged pilot; it does not start training or change dates.

## Honest objective

Remove known defects from retained examples, recover missing information only
where evidence supports recovery, and document uncertainties that cannot be
removed. No historical archive can prove complete hidden liquidity or predictive
success. If zero historical source/timing uncertainty is mandatory, the existing
archive cannot meet that demand; a newly recorded dataset is the practical route,
and still cannot expose all hidden orders or guarantee model performance.

## Current evidence

The local causal feature build reports completion with no training started.
Its manifest fingerprint is
`640d56f62479e42c54899564eec340932d2c75963492185afe0f9204862349a1`.
At the zero-added-delay setting, 7,150 of 42,457 quality candidates survive:
fit 4,754; development 468; calibration 606; locked test 1,322.
The remaining candidates fail complete/reconciled 1,440-minute context or receipt
cutoff checks. These are overlapping histories, not 7,150 independent samples.
Reported completion and leakage tests do not independently certify provenance.

## Ordered work and acceptance evidence

1. **Explain exclusions before recovering anything.** Produce per-day and partition
   coverage, missing-hour and exclusion-reason tables. Trace representative
   failures to raw rows. Separate provider defects, validator defects and strict
   availability exclusions. Compare retained versus excluded periods using
   predeclared volatility, volume and trend summaries, without model scores.
   One bad context minute can disqualify many subsequent origins: count both
   failed minutes and affected examples. Deliver a reproducible exclusion ledger.

2. **Strengthen source checks.** Preserve original files, hashes, download metadata,
   official candle references and reconciliation results. Inventory a second
   independent recording of the same Binance futures instrument and overlapping
   dates, including quiet and volatile intervals. Establish whether it collected
   independently rather than reselling the same feed. Compare trades by native
   IDs and books at common native sequence boundaries, allowing documented depth
   and snapshot differences. Investigate all discrepancies within the declared
   comparison scope. Retain a comparison report and an explicit unverified scope;
   a sample comparison cannot certify every historical level. Finding a suitable
   source is work, not an assumed entitlement or an authorized new purchase.

3. **Recover book state where possible.** Replay a verified earlier snapshot and
   continuous updates across the month boundary. Test that replay produces the
   same state at later verified checkpoints. A sequence gap, halted/empty state
   or missing snapshot invalidates the affected book until a trustworthy restart.
   Recover from a second source only with compatible sequence/depth semantics and
   documented provenance. Otherwise exclude the interval and any dependent input
   windows. Never initialize an unknown book as empty, interpolate missing levels,
   or silently replace real observations with simulator output.

4. **Audit availability and realistic prediction time.** Trace selected examples
   from raw exchange and receipt timestamps through feature cutoffs. Test future
   messages, late trades, checkpoint resets, duplicate snapshots and out-of-order
   receipts. Existing 250 ms/1,000 ms backward-cutoff scenarios are conservative
   input stresses; they are not proof of historical network delay. Review their
   changed sample populations. A forecast issued after minute open must state its
   actual issue time and target; do not backdate it. Any timing-policy change is
   versioned and frozen before model evaluation. Do not loosen rules to improve
   scores or recover attractive outcomes.

5. **Record new direct evidence for timing.** Prepare a separate direct exchange
   collector with snapshot/update sequence checks, UTC receipt timestamps,
   monotonic ordering, clock-offset monitoring and disconnect/resync logs. Preserve
   raw messages. Where feasible compare a simultaneous independent recording.
   Check sustained ordinary and busy periods, missingness and restart recovery;
   report measured coverage rather than promising a fixed collection duration
   proves completeness. This strengthens future evidence; it cannot repair an
   unknown historical clock. Live recording does not place trades.

6. **Freeze the actual dataset and independently review examples.** Regenerate
   eligible-origin manifests after verified fixes, recording changes against the
   original frozen candidates. Reinstatement requires separately documented data
   evidence and a new manifest, not a model score. Preserve chronological pilot
   partitions, targets inside partitions and fit-only preprocessing. Review raw
   provenance for examples near gaps, month/split boundaries and late arrivals.
   Automated checks must reject future inputs, discontinuous histories and invalid
   books; replay must be reproducible. Report whether retained days/conditions
   support the proposed experiment. Never silently shorten the 1,440-minute input.

7. **Publish a stage-specific go/no-go decision before fitting.** Every limitation
   must be marked fixed, excluded, independently checked within a stated scope,
   or unresolved. Known invalid input/target records, future leakage and unexplained
   material discrepancies block training on affected examples. Insufficient usable
   coverage requires more clean data or a separately agreed scope change. Historical
   authenticity/timing uncertainty may permit a clearly labelled exploratory
   archive pilot, but cannot support claims of certified live readiness. If the
   user requires those uncertainties resolved first, keep training paused and use
   the newly recorded dataset. Hidden liquidity remains outside the initial scope.

## Limits that cannot be removed before training

- Public feeds do not provide all hidden orders. The model uses observed visible
  depth and executed trades, with no claim to know the entire market.
- Data quality cannot prove trading effectiveness. That requires later untouched
  prediction evaluation against fixed baselines, followed by forward observation.
  Proven profitability is not a prerequisite for an exploratory baseline.
- Independent agreement reduces uncertainty; it is not mathematical proof that
  every historical exchange event or original arrival timestamp is authentic.

## Deliverables and execution order

First deliver exclusion/coverage and selected raw-example review. Next inventory
independent source availability and perform supported state recovery. Then finish
timing checks and specify direct collection. Finally publish the limitation ledger,
new dataset hashes/counts if changed, and an explicit readiness decision. Keep data
and credentials private; publish code and aggregate evidence only. No new paid
subscription, mass redownload, model fitting or trading is implied by this plan.

Related: [causal feature contract](CAUSAL-PILOT-FEATURES-2026-11-02.md),
[October quality review](PILOT-QUALITY-REVIEW-2026-11-02.md),
[staged training decisions](STAGED-TRAINING-DECISIONS-2026-11-02.md).

## Execution record and limitation ledger — 2 November 2026

The bounded local review is complete. See the
[executed October review](OCTOBER-PRETRAINING-REVIEW-2026-11-02.md) and aggregate
artifacts in `results/market_data/pilot-review-20261102/`. Completion of this
review does **not** mean every limitation has been removed.

| Plan item | Work completed | Disposition |
| --- | --- | --- |
| 1. Explain exclusions | Recomputed all partition/delay eligibility arrays; identical results. Generated full private per-origin ledger, public daily coverage and pre-origin condition summaries; five raw candle cases checked. | Complete within October scope. 85 invalid candle minutes propagate into 31,543 rejected candidates; 3,764 further late-context exclusions. |
| 2. Strengthen source checks | Original hashes/reference evidence retained; selected raw files rehashed. Reviewed Tardis's collection documentation and tested October 1 public BTCUSDT book/trade file availability; both returned 404. | Source inventory complete; independent overlap comparison unresolved. No second-source agreement claimed or purchase implied. |
| 3. Recover supported state | Separate Python book replay confirmed one native-sequence top-20 record against the C++ features. Reviewed dominant losses: candle context/availability, which a book-prefix replay cannot repair. | No examples reinstated. Earlier snapshot-free months remain deferred outside October. Unknown or omitted state remains excluded/uncertain, never guessed. |
| 4. Audit availability | Recomputed 0/250/1,000 ms eligibility, checked a genuinely late last trade and a timely retained context directly; independent book source clocks matched. Existing future/boundary tests retained. | Implemented cutoff checks pass. Original historical receipt provenance remains unresolved; delay stresses do not certify it. |
| 5. Record direct evidence | Existing public collector ran a fresh finite capture and integrity audit; raw messages, sequence state, UTC/monotonic times, server-time probes and shutdown manifest saved privately. | Collector smoke passes. Sustained busy/ordinary periods and observed reconnect coverage remain deferred; historical clock uncertainty cannot be repaired by this recording. |
| 6. Freeze and review | All frozen origin hashes/indices matched. Targets remain partition-contained and preprocessing fit-only. No silent context/split changes; selected independent raw reader checks completed. | Same feature fingerprint and counts retained. Coverage is too concentrated for reliable model selection; no new manifest or recovered dataset claimed. |
| 7. Publish readiness | Six predeclared fixed rules scored only on development, with class-aware direction and OHLC errors. Test/calibration target files unopened by the review program. | GO for pipeline/fixed exploratory baselines. DEFER reliable MLP/sequence selection until a quality-defined cohort has multiple usable development days. Not live-ready. |

Status of the specific original limitations:

- **Unchanged bytes versus authenticity:** hashes verified; authenticity unresolved.
- **Candle agreement versus every book level:** candle reconciliation plus one
  independent implementation check; archive-wide independent book certification unresolved.
- **Checkpoints/corrected clocks versus original receipts:** strict cutoff handling
  implemented; historical timing provenance unresolved. Do not relabel it fixed.
- **Empty/halting snapshot omissions:** no fabricated recovery. Structural replay
  cannot certify absence of unpublished resets; this remains a provider limitation.
- **Uninitialized month prefixes:** excluded unless separately recovered; earlier
  months deferred, not required to repair the present October candle-context losses.
- **Every minute, hidden liquidity and trading efficacy:** exclusions/coverage
  published; hidden liquidity outside scope; no profitability or forecast superiority claim.

### Concrete continuation boundary

The current month has 4,754 fitting examples across eight days, but only 468
usable development examples on October 20. Retained fitting periods are quieter
than excluded ones. The archive therefore supports an engineering pilot, while
claims of broad model superiority would be premature. Fixed baselines are now
recorded; no neural training has started.

Next data work is to identify a new chronological cohort using only quality and
pre-origin condition coverage, preserving the full context and untouched targets.
Version any split/date change before fitting. Do not repeatedly tune this month's
rules against its one development day or use the locked test to compensate.
Sustained direct evidence and a suitable independent source are explicit deferred
improvements; neither should become an endless demand for perfect data before an
honestly labelled exploratory experiment. No news, inferred book, entry-quality
model, simulator pretraining, deployment or trading is included.

Recovery follow-up: the [official-source probe](MISSING-DATA-RECOVERY-2026-11-02.md)
verified that Binance's free individual-trade archive recovers the contents of
three selected bad/missing source minutes. This improves the recovery options;
original receipt times and the 7,150-origin strict dataset remain unchanged until
a versioned repair and availability review. Do not treat the earlier source
inventory's lack of a second book sample as absence of recoverable execution data.

### Implemented recovery/button follow-up

See [recovered dataset and frozen input implementation](RECOVERED-BUTTON-DATASET-2026-11-02.md).
All 85 selected candle-content defects now have reconciled reconstructions (84
using official daily trades; one consistent official/provider native-ID union).
The original strict dataset is preserved. The new explicitly conditional button
cohort has 42,484 primary examples and all three development days represented,
superseding the one-day coverage blocker for that new experiment only. No original
receipt clock was recovered or fabricated. Six actual-receipt live input freezes
passed hash/provenance/cutoff checks; no neural predictions or trades were made.
Readiness is GO for a small exploratory comparison under the documented historical
availability assumption; live-performance and historical timing-certification
limitations remain. The insurance/ADL filtering correction is scoped to the new
trade stream; the original full-year audit is not silently relabelled corrected.
