# Diwali1.4 research objective: representation and evaluation reset

User-directed on2026-11-04. This supersedes another small frozen-parent correction as the next development priority. Keep the original requested price-range probability fan and coherent directional probabilities. Do not redefine success as only a shorter-horizon classifier. Perfect conditional probabilities remain unproven and cannot be certified by finite test results.

## Required changes and evidence

| Requirement | Work to perform | Evidence required before claiming it complete |
|---|---|---|
| Preserve subsecond activity | Reconstruct ordered retained L2 batches and trades, including price-relative level changes, trade sides/sizes, source times, time gaps and availability. Keep source identity and sequence continuity. | Raw-to-event replay parity, full-window cutoff tests, crossed/empty/depleted book handling, gap rejection and comparison to original per-second states. No silent loss of excess events. |
| Replace the33-value snapshot bottleneck | Keep multiple time-local representations through the encoder and feed horizon-specific outputs. Compression may happen after local event processing; it must be explicit and tested. | Architecture/source/shape records and a controlled one-second-input comparison, with matching target origins. No claim that a wider layer is automatically sufficient or lossless. |
| Train end-to-end | Train the new input encoders and probability heads jointly from initialization. Older networks supply baselines only. | Trainable-parameter audit showing no frozen0.5/0.7 dependency in new marginal prediction; matched training budgets and seed schedules. |
| Replace reused benchmark evidence | Build chronological walk-forward development blocks plus a sealed final evaluation with a documented prior-exposure inventory. | Freeze periods/metrics/selection/calibration before training or label-driven exploration; purge horizon overlap; training-only scalers; one final evaluation and later pre-target confirmation. October remains exploratory. |
| Measure signal lifetime | Score explicitly distinct horizons: shorter time/event horizons as diagnostics, the next full candle and all15 requested future closes. | Exact freeze/start/close times, same-information baselines per target, proper scores and daily results. Never pass short-horizon success off as15-minute accuracy. |

## Work sequence and stop conditions

1. Complete a bounded resolution audit on fixed fit-only hours. No outcome-based sample selection. Quantify what the retained provider data contains, not imagined individual orders.
2. Implement an independently versioned event replayer. Do not modify the frozen validator or deployed0.9/1.2 model dependencies. Preserve exact decimal book state; snapshots initialize state only after their full available batch. An update batch is atomic for causal feature emission. Within a batch, row order is not a series of separately observable market states.
3. Prepare raw-event windows and a feature dictionary with availability times. Join book/trades only up to the cutoff. Same-receipt ties have no proven exchange-wide causal ordering: process as an available-time group or document a deterministic source tie-break without inventing causality. L2 depth reductions are not uniquely identified cancellations or executions. No private order IDs, whale identity or hidden reserve labels are fabricated.
4. Inventory prior label/performance exposure before naming fresh dates. Select new chronological periods from the retained archive with matching quality checks; do not assume an older month is untouched simply because it precedes October. Preserve a final block and prevent routine diagnostic scripts from reading its outcomes before release. Until this is recorded, full training is not ready.
5. Freeze a bounded comparison: current one-second baseline; stationary order-flow logistic and boosted-tree baselines; a compact event-sequence convolution/TCN model; a compact causal attention model using local blocks/hierarchical representations. New neural candidates train end-to-end. Give them the same available information, labels, origins and search budget. Maintain separate representations for candle context and recent flow; use horizon queries rather than a single33-value vector for every output.
6. Train/select on earlier rolling blocks. Calibrate after model selection with data unused by that model-selection step. Save every attempted candidate and rejection. Predeclare the final output distribution, horizon weighting, optimizer/seed budget and winning criterion before fitting; this document freezes the strategy, not yet every training hyperparameter.
7. Run the sealed evaluation once, report regressions and calibration reliability, and then make new future-issued forecasts. Model-level uncertainty and out-of-regime behavior must be reported. A new version cannot borrow the earlier0.9/1.2 live test as fresh confirmation.

A long raw event sequence need not enter full quadratic attention. Local processing and hierarchical memory are candidates for tractability, but must not silently truncate busy periods. Report event count, retained coverage, memory/runtime and any explicit cap/rejection. Do not use synthetic order events to fill unknown history.

## Targets and assessment

The historical button contract freezes at the15th second. A freeze at10:00:15 forecasts the next full candle10:01–10:02; its first close is105seconds away, and its15th close at10:16 is945seconds away. Keep that task for comparison. Auxiliary exactly-after-freeze horizons must be separately named and use separately constructed labels. They cannot be inferred from one-minute OHLC when precise subminute endpoints are required.

Use log loss, Brier score, ordered-range scores and reliability by horizon, side, day and past-known volatility/activity regime. Include50–50, fit-frequency, majority, persistence, volatility and simple flow baselines as appropriate. Separate binary net direction, three-class threshold direction, candle colour and trading success. Account for overlapping targets when describing evidence. Target-before-stop, costs, news and missing-book fallback remain separate deferred work.

The current0.9/1.2 prospective test stays frozen and running. Do not stop it or tune from its partial outcomes as part of this reset. No trading. Keep raw paid data, individual live records and weights local; publish source and aggregate findings only.

## Initial resolution audit completed

Fixed four fit-only UTC hours: October5 and12,00:00 and12:00. All eight source files match archive hashes and prior quality records. Counted delta-batch identities equal the existing replayer's accepted-update counts in each sampled book hour. Median book updates per received second are38 across all four hours. Market trade counts are bursty; the maximum sampled second contains5,771 retained trade rows. These statistics confirm substantial retained detail below one second, not predictive usefulness or original exchange-arrival authenticity.

Audit version2 fixes the treatment of positive-price/positive-size NA trades to match the original validator; version1 remains private and is superseded. Three tests verify update grouping across reader batch boundaries, empty batches and that trade-type edge case. Aggregate output: `results/event-resolution-audit`. This is a resolution diagnostic, not new training examples or a complete event replay. Requirements2–7 remain outstanding.
