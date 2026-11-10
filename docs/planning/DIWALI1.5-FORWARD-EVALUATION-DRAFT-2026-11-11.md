# Diwali 1.5 forward evaluation: draft before any new forecast

This document specifies the proposed next evaluation. It does not authorize an already-started live comparison or claim that a selected final model exists. The bounded39-run development study is still running. No forecast has been issued under these rules. Final deployment artifacts and this protocol must be hashed together before the first forecast. These durations and thresholds are our design choices, not Krafer's claimed settings.

## Scope and frozen artifacts

The primary task remains15 direct distributions for future full-minute closes. Pick the neural configuration using the committed mean15-bin development rule. Do not change that choice from a later prospective result. A later single fixedseed17 refit would use all5,391 prepared August labelled inputs, the previously used September1–7checkpoint-selection dates, and September8–14calibration dates; those earlier dates are development, not a new holdout. D uses the same full fitting origins and fixed settings. No new hyperparameter search is added to that refit.

Freeze chosen weights, selected epoch, fit-only transforms, model/source versions, cache/source identities, probability calibration,26-bin edges, reference definition, code/eligibility hashes and all comparator artifacts. Include the volatility-conditioned histogram and a constant50–50 directional baseline. Include D for the binary diagnosis, and the unmodified A control when another configuration was selected. Never compare methods on different surviving timestamps.

If no neural configuration beats the volatility benchmark on development range error, explicitly retain the benchmark as the stronger development reference. A chosen neural configuration may still be examined as research; do not label that choice production promotion or a demonstrated gain.

## Timing and eligibility

Use actual newly arriving public market messages, keeping native UTC receive and monotonic times. Do not replay historical records and describe them as forecasts issued in the past. Complete the24-hour context warmup before scheduling the evaluation start. Freeze a concrete UTC start/end in the release after warmup; start on the next full UTC day. Do not move the start or exclude days based on outcomes.

Run ten consecutive UTC calendar days, issuing at00:00:15,00:15:15,00:30:15,00:45:15and the equivalent slots throughout each day: at most960origins. This15-minute cadence avoids overlapping15-full-candle target sets. Mature the final issued targets after the issuance window ends. If a slot is missed, record it; do not insert a hindsight substitute.

For every comparator freeze exactly the same strict-before-cutoff messages and1,440completed candle context. Apply the existing book-seed, sequence/invalid-marker, staleness, fresh-completed-second reference and masked-history gates from the canonical pipeline. The last completed candle must be valid; older context must meet the existing99%validity rule. Do not manufacture hidden orders or fill unavailable book levels. Record the input-only rejection reason for every skipped slot.

Record input hashes, model/calibration hashes, cutoff, reference, target interval, UTC issuance, monotonic issuance and computation duration before the first target starts. A forecast completed after its target starts is a missed forecast, not an eligible issued prediction. All comparators must meet this timing condition. Once issued, forecasts are immutable; actuals are stored separately and attached only after target maturity/quality checks. A prediction file is not evidence of timely issuance without its corresponding native-clock/source audit.

The usual cutoff at10:00:15 predicts the10:01–10:02first candle and ends at10:16for the15thclose. This still leaves105seconds to the first close and945seconds to the fifteenth. Zero return is down-or-unchanged, with up computed from positive bins.

## Scoring and stopping

Score the full prespecified ten-day issuance window. Do not stop early for good scores, increase confidence thresholds after looking at outcomes, or extend until a model wins. Require at least300matched fully matured origins across at least seven distinct days; otherwise report insufficient coverage and plan a separate future window. Do not replace a failed window with a new one while erasing its record.

Primary: mean price-bin log loss across all15closes, paired on identical eligible origins against the volatility benchmark. Secondary: final-close binary log loss/Brier and ROC-AUC against50–50and volatility/D; report all15horizons, both raw/calibrated diagnostics where available, daily paired differences, probability reliability and coverage. D/50–50do not have range scores and must not be assigned fabricated ones. An architecture or loss that improves direction while worsening range remains a stated tradeoff.

Calendar blocks and neighbouring market conditions remain correlated even when the forecast target sets do not overlap. Report descriptive day variation; do not treat every endpoint as an independent trial or claim perfect conditional probabilities. AUC is undefined for a one-class slice and stays null. Keep private individual records and suppress public aggregate slices with fewer than ten origins.

The ten-day test is consumed once its forecasts/outcomes inform research. Any subsequent changes require new future-issued confirmation. September15–29, the already used October benchmark and this reused August development cohort remain unavailable as fresh holdouts. There is no trading, PnL guarantee, target-before-stop entry estimate or news model in this protocol.

## Work still required

Finish/audit the bounded comparison, inspect the tradeoffs, prepare the single chosen-model build and all comparators, verify actual live input/inference parity, then freeze a release containing a concrete future UTC window and complete source/clock audit rules. None of these remaining steps may be reported as already completed by a development-score table.
