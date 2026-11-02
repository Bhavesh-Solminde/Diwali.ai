# Reusable trading-model checklist

Copy this document to a dated run file for EVERY new model/experiment. Leave the
master unchecked. A tick requires evidence (artifact, hash, test result or report),
not copying a previous run's status. Separate before-training tasks from checks
that can only happen after training. Never make live-readiness claims from an
exploratory historical run. Unresolved observational limitations may be accepted
for a labelled experiment; known bad inputs or future-information leakage may not.

## Run identity — fill before fitting

- Model/run ID:
- Market, exchange and instrument (spot/perpetual):
- What is predicted, and exact prediction/target times:
- Dataset version/fingerprint and source manifests:
- Input/label/feature-code versions and hashes:
- Protocol file/hash and date frozen:
- Training/development/calibration/final-test dates:
- Seeds, parameter count, device, environment/dependency versions:
- Reviewer and date:
- Evidence/report locations:

## Before training — data and timing

- [ ] Confirm venue/instrument, timestamp units, price/quantity units and aggressor-side meaning.
- [ ] Verify unchanged source bytes and recorded download/source provenance.
- [ ] Reconcile candles/labels with independent delivery evidence; document repairs and conflicting IDs.
- [ ] Validate book snapshot/update chain, known price bounds, crossing, freshness and restart/gap exclusions.
- [ ] Keep all required consecutive history; do not interpolate unknown orders or join separated times.
- [ ] Freeze input snapshot time and exact target interval; enforce result-ready deadline.
- [ ] Check maximum source/receipt times and reject future inputs. Mark assumed historical candle availability explicitly.
- [ ] Report usable examples and exclusions by partition/day/market condition. Neighboring samples are dependent.
- [ ] Ensure inputs, targets and calendar partitions are aligned; all versions of a target stay in the same partition.
- [ ] Preserve final test for final evaluation. Data-integrity checks/hashes are allowed; no model-selection scores.
- [ ] Fit normalization, target scales and other learned preprocessing using training data ONLY.
- [ ] Audit representative source-to-feature examples, including boundaries, late data and gaps.

## Before training — live/history input agreement

- [ ] Use identical feature order, units, transforms, time-window boundaries and price anchors in both paths.
- [ ] Distinguish individual executions from aggregate messages. Do not equate message count to execution count.
- [ ] Remove unsupported count/features from BOTH paths or prove equivalent definitions.
- [ ] Check buy/sell quantities, notional and VWAP on matching native execution-ID groups; record overlap/exclusions/errors.
- [ ] Test split/merged messages, empty buckets, future messages and special non-market events.
- [ ] Rebuild/version changed features and fit-only scalers; require the aligned contract in training/inference.
- [ ] Document unresolved receipt/batching delays. Common definitions do not prove identical cross-recorder seconds.

## Before training — frozen experiment and baselines

- [ ] Freeze models, parameter limits, optimizer, learning rate, seeds, batch size, epochs and resource limits.
- [ ] Freeze checkpoint selection, architecture selection, tie-breaking and permitted search budget.
- [ ] Define price errors, direction reference and class handling. Close versus old input close is NOT candle green/red accuracy.
- [ ] Define interval/confidence calibration using a separate block; never calibrate on the final test.
- [ ] Run fixed no-change, momentum, reversal, majority and book/flow/current-price baselines on the SAME cohort/target.
- [ ] Include per-day/class-aware results, data coverage and a price-error baseline; one accuracy number is insufficient.
- [ ] Record immutable protocol/data hashes before score-driven decisions. Amendments require a new version and disclosure.
- [ ] Run relevant correctness checks and save results. Do not require proven profitability before a pilot can start.

## After training — do not check these beforehand

- [ ] Save all seeds, failed runs, actual epochs, checkpoints, parameters, cost/device and reproducible manifests.
- [ ] Compare development results with frozen baselines; select without final-test feedback.
- [ ] Calibrate confidence on its separate block and record the fixed procedure.
- [ ] Evaluate the locked test only after selection/calibration are fixed; report all predefined metrics and failures.
- [ ] Report training error, past-unseen error and recent-market error separately. Historical development error is NOT live error.
- [ ] Save prospective predictions and their frozen inputs BEFORE target outcomes; evaluate only after targets finish.
- [ ] Measure inference delay, missed prediction deadlines, live gaps and calibration drift.
- [ ] Preserve failed tests. A test used to motivate a change is no longer a fresh final test for that change.

## Required limitation ledger — reassess for every run

| Limitation | Status/evidence | Effect on claims | Accepted for historical pilot? |
| --- | --- | --- | --- |
| Original arrival times of repaired history | | | |
| Independent verification of historical book levels | | | |
| Date/regime coverage and exclusion bias | | | |
| Actual prospective model predictions and outcomes | | | |
| Public visible orders versus hidden liquidity; news/entry/fallback scope | | | |

## Decision

- Historical training: READY / NOT READY. Blocking items and reason:
- Historical conclusion permitted (including timing assumptions):
- Live input/inference readiness: READY / NOT READY. Remaining issues:
- Live trading: separate decision; never implied by this checklist.
- Next work, owner, and report links:
