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

## Event-book replay preflight completed

An independently versioned event observer now emits exact integer top20 prices and quantities after each complete provider L2 batch, along with receipt/exchange/availability times, source sequence, snapshot/update flags, validity and ordinal. It records snapshots and invalid batches as well as accepted updates, rather than concealing gaps. Availability is the maximum of receipt and exchange time; downstream windows must enforce it. These records do not claim to recover individual exchange orders. Deeper source updates remain in the immutable archive.

The original `archive_scan.cpp` and `feature_scan.cpp` are unchanged. At build time, copies receive an explicit event observer hook and a renamed executable entry point; source checks require the expected insertion locations. Native replay tests confirm multi-row batches emit one state, a later exchange timestamp remains explicit, and sequence gaps invalidate the emitted book. All output raw levels remain private.

Four target hours plus their preceding warmup hours replayed successfully. Every one of14,400 original one-second feature rows matches byte for byte, including validity and metadata. The new event output contains545,186 batches:545,182 accepted updates plus four snapshots. The initial isolated-hour comparison failed on the first invalid grid's carried age; this was fixed by replaying preceding-hour state, not by ignoring that field or weakening parity. Earlier failed local build/preflight attempts are superseded by `event-replay-preflight-20261104-v3`.

Aggregate evidence: `results/event-replay-preflight`. This completes a bounded **book** replayer preflight only. Trade-event integration, price-aligned change features, causal model windows, wider continuity/quality checks, prior-exposure inventory, sealed evaluation protocol and new end-to-end training remain outstanding. Do not call this a trained1.4 model or a finished full event dataset.

## Individual trades and causal row windows completed as preflights

The four matching trade hours now preserve520,778 original records:518,559 market trades and2,219 nonmarket markers. Integer prices and quantities retain1e-8 units. Buy/sell aggressor direction is derived from buyer-maker status, not guessed from candle colour. Invalid/nonmarket rows are retained as markers rather than fabricated fills. All14,400 original per-second trade rows match byte for byte, including counts and metadata.

An independent Python/Decimal pass compared every retained trade's receipt/event/trade timestamp, trade ID, exact price/quantity, maker side and nonmarket classification directly against its original Parquet row. All520,778 rows matched. This supplements the shared-scanner grid parity check.

The new window builder returns all raw row references in each60-second input interval plus its pre-window book seed. It does not resample or cap event counts. Per-source availability is a prefix maximum of receipt and exchange times, so a later transition cannot leap over an earlier not-yet-available transition. Cutoff is strict: events exactly at the freeze are excluded. Equal availability timestamps retain a time-group ID; deterministic serialization within that group is not asserted to be exchange-wide causal order. Invalid markers or book staleness reject a window. No future outcome labels enter these preflights.

At fixed minutes2/9/16/23/30/37/44/51, second15, all32 sampled windows passed without truncation or rejection. Raw row references, seeds and individual windows remain private. Aggregate results: `results/trade-event-preflight` and `results/event-window-preflight`. Tests cover strict cutoff, timestamp groups, blocked out-of-order availability, future-payload invariance, invalid markers and staleness.

This advances event preservation and alignment; it does not finish a normalized training dataset. Still required: price-aligned order-flow features, broader continuity checks, explicit source-exposure inventory and sealed walk-forward evaluation, end-to-end model definitions and training. Older0.9/1.2 forward captures remain unmodified.

## Price-aligned feature and temporal-plan progress

The32 private preflight windows now contain156,508 rows with103 unscaled features per event. Book rows retain their80 level-state coordinates relative to the known pre-window midpoint. Additional channels describe elapsed times, spread/midpoint/imbalance, changes at matched exact price levels, top20 visibility entry/exit, trade price displacement, signed trade size/notional and nonmarket markers. A separate seed vector initializes the pre-window state. There is no silent fixed-length truncation or one-second aggregation.

Matched-price depth changes are separated from changes in level rank. Entry/exit at the top20 boundary is labelled visibility change, never uniquely identified cancellation, execution or refill. Trades use their fixed pre-window price coordinate and own fields; they do not read a same-timestamp book transition as confirmed earlier context. Explicit timestamp groups remain part of the model-input contract. Tests verify rank shifts do not manufacture matched-price quantity changes, buyer-maker side mapping, future-payload invariance and same-time cross-stream isolation. All source event hashes are checked before preparation.

Aggregate output: `results/event-feature-preflight`. The private first feature-preparation run is superseded by version2, which adds direct event-file hash checks. No scaler or model is fitted in either run.

The bounded exposure register and chronological date plan are now recorded in [DIWALI1.4-EVALUATION-EXPOSURE-AND-SPLITS.md](DIWALI1.4-EVALUATION-EXPOSURE-AND-SPLITS.md). August rolling development folds are followed by final August fitting, September1–7 selection, September8–14 calibration and reserved September15–29 final scoring. Prior archive-quality access is disclosed; these are previously unevaluated model-performance periods in retained records, not provably unseen raw prices. No model forecasts for the reserved final block have been evaluated in this reset.

Remaining work: expand verified event extraction beyond these sample hours; prepare eligible feature/context/target cohorts under the frozen dates; implement final-label access separation; specify bounded end-to-end models and baselines; train and evaluate. This is not yet a trained1.4 model or completed implementation of all evaluation gates.

## Expanded storage and end-to-end candidates implemented

The new hourly event-shard writer uses lossless Zstandard Parquet, with exact integer roundtrip verification before committing each hour. It stores every retained row without downsampling. Per-hour manifests preserve source/quality hashes, decoded event-binary hashes and clock flags; interrupted runs may resume only with an unchanged protocol. A full49-hour resume replay matched its previously committed binary hashes. Completed data: July31 and August1 plus a preceding warmup hour. About4.999GB of uncompressed event records occupy244.9MB, a20.4× lossless reduction. These byte counts are decimal units. No event information was deliberately removed for that compression.

August2–31 is being prepared separately (721hours including warmup). It is a finite live job; `results/event-shard-preparation/remaining-august-progress.json` is only a dated progress observation, not final completion. The preparer denies intervals reaching into the reserved September15–29 final period. A30GiB disk reserve stops preparation rather than silently dropping data. This is raw-event storage, not yet the final normalized cohort or training.

Two end-to-end model candidates are implemented in `research/diwali/event_model.py`: local temporal convolution and a compact attention alternative. Every event first receives a learned projection. Identical-availability rows are pooled as an unordered set, preventing deterministic source tie serialization from becoming a claimed causal order. Local causal convolutions process128-event/group blocks before learned pooling. The model retains multiple block tokens,96 locally processed candle-context tokens and a seed token;15 learned horizon queries read these tokens directly to produce15×26 price-range scores. It does not feed every horizon a single33-value snapshot vector and has no frozen parent.

This model still compresses information through learned set/block pooling. The design moves compression after local processing and preserves more time-local representations; it is not mathematically lossless neural encoding and its forecasting benefit remains untested. All events enter the encoder; no busy-period event cap is applied. The candle branch processes minute detail before15-minute pooling. The attention candidate sees only already-available past context; it does not receive target candles or future book/trade messages.

Candidate parameter counts are94,556 and111,196, all trainable. Tests verify gradients reach event-tail/candle/seed inputs, padding cannot change forecasts, and equal-time permutations cannot change predictions. Both candidates completed untrained MPS forward/backward runs with29,965 real fit-hour event inputs and synthetic zero candle context. The recorded cold timings are engineering evidence only, not comparable steady training speeds or performance results. Aggregate record: `results/event-model-engineering`.

Still outstanding: complete August extraction and cohort construction, actual candle/label availability alignment, fold-specific normalization, simple baselines and controlled representation variants, frozen training/selection/calibration settings, real model training and the deliberately released final evaluation. Neither candidate is trained yet.
