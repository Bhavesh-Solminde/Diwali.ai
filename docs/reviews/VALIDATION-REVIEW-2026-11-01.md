# Reviewer decision after bounded validation

Reviewed external commit: `0a3dbf40d33ebad41a17e5114d0f78277645b6af`. Reviewer: Mac coordination chat.

## Decision

The bounded simulator investigation is sufficient to close this research loop and proceed to data-pipeline implementation. More simulator scenarios are not the next useful step. **This is not approval to train on vendor output, calibrate entry probabilities, or claim BTC forecasting performance.** Small real-only baseline training remains conditional on sufficient verified data, frozen splits and leakage/label checks. No training is initiated.

The stronger-baseline concern was addressed: fresh seeds across standard, sparse and maker30 profiles support a limited book-versus-reversal association. The v0.5 normalized-size study appropriately limits the original slicing claim (10/12 adjusted intervals include zero). Triggered-entry ambiguity remains nearly complete and the report correctly declines calibration. The acceptance register correctly rejects current vendor synthetic training labels and economy rules. These are substantive research outcomes, not reasons to keep sampling until favorable results appear.

## Independent checks and limits

- Reviewed VALIDATION-DECISION, NATIVE-HOST-EQUIVALENCE, TRAINING-DATA-DEFECT-REGISTER, COORDINATION-HANDOFF, saved verification and relevant test/analysis code. Reviewed native behavior as documented; did not replay Windows app operations on this Mac.
- Five validation tests and four earlier analysis tests pass locally.
- Independently checked all 3,780 raw-catalog hashes: zero mismatches after normalizing Windows path separators. The supplied catalog's backslashes are a portability issue, not a hash failure. Future verification tools should normalize those paths.
- Full independent DLL replay and recalculation of every bootstrap interval were not performed. Tests and hashes establish selected invariants/integrity, not simulator economic validity.

## Stage gates

| Stage | Review verdict |
|---|---|
| Simulator mechanism research | Sufficient for current development decisions; preserve limitations |
| Real data pipeline implementation | Ready as next bounded engineering stage |
| Small real-only baseline training | Not yet: adequate verified dataset, chronology and leakage checks still required |
| Synthetic pretraining | Rejected for current vendor records; requires a separately reviewed corrected export/engine |
| Entry-probability calibration | Not ready; ordered outcomes and independent calibration required |
| Forward paper performance | Deferred until immutable actual forecasts exist |

No further simulator research prompt is issued. Existing NEXT-RESEARCH-PROMPT.md is historical and has been answered by this validation. The next recommendation for user review is durable collection/validation and a small real-only baseline protocol, as detailed in the collaborator's COORDINATION-HANDOFF.md. Do not interpret this recommendation as authorization to train, patch vendor binaries or build a replacement engine.

The commit-monitor research loop ends here because the bounded research has returned an actionable stage decision; no more routine simulator follow-ups are needed. This stop explicitly does not mean the intended final model is training-ready. User review of the next stage is required.
