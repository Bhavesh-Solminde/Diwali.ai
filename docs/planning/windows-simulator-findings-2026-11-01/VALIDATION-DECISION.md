# Validation decision report — 1 November 2026

This report answers reviewer commit `cb2ae3fd1b69f6afa814af3b50c54016ac2bf393` and the user’s focused validation request. Existing runs and original conclusions are preserved. The reversal audit is explicitly post hoc; fresh-seed results use the separately frozen VALIDATION-PREREGISTRATION.md. No model was trained, no real trades placed, no vendor binaries patched and no replacement engine built.

## Stage-specific decision

| Stage | Decision | Required next evidence |
|---|---|---|
| A. Data-pipeline implementation | Ready to proceed; bounded engineering recorder implemented and tested | Durable reconnect/resnapshot, storage, clock monitoring and complete-candle/coverage validation before production collection |
| B. Small real-data baseline | Conditionally ready as the next reviewed experiment; no training started | Acquire sufficient same-venue data; freeze chronology, preprocessing and baselines; pass leakage/label checks. Does not need every simulator question solved |
| C. Synthetic pretraining | Not ready; reject current vendor outputs as trusted training records | Supported corrected exporter or separately reviewed independent event engine with matching, collateral, fill, candle and replay invariants |
| D. Entry-probability calibration | Not ready | Executable triggers, ordered executions or useful ambiguity bounds, enough independent out-of-sample predictions and coverage/calibration |
| E. Forward paper evaluation | Infrastructure planning ready; measured evaluation deferred | A frozen real-data forecast/baseline, immutable issuance/cutoff log and matured outcomes with costs. No forward forecasts exist yet |

Simulator robustness does not certify BTC transfer or profitability. A real-only baseline may move forward after its own gates and review, rather than waiting for a synthetic engine.

## Corrected existing baseline audit — post hoc

Selection is phase=main, group=all, book prediction available; exactly one record per run/candle. Pattern-stratum copies are excluded. There are 10,168 unique origins from 30 independent parents, versus 14,100 candidate origins: 445 locked/absent-book exclusions and 3,487 missing-10-bp-depth exclusions. Common-grid coverage is 72.11%. Rules make a prediction on 100% of that eligible grid; this is not 100% feed coverage.

| Rule | Accuracy | Balanced accuracy | Recall down / neutral / up |
|---|---:|---:|---|
| up | 49.5771% | 33.3333% | 0.00% / 0.00% / 100.00% |
| down | 48.9477% | 33.3333% | 100.00% / 0.00% / 0.00% |
| momentum | 42.8698% | 29.8695% | 43.34% / 2.67% / 43.60% |
| reversal | 54.3371% | 37.6293% | 55.07% / 2.67% / 55.15% |
| book | 56.7172% | 39.6727% | 57.91% / 4.00% / 57.11% |
| pilot_majority | 49.5771% | 33.3333% | 0.00% / 0.00% / 100.00% |
| neutral | 1.4752% | 33.3333% | 0.00% / 100.00% / 0.00% |

All five reviewer figures reproduce. Book-minus-reversal origin-weighted difference is 2.3800 percentage points. Equal-parent paired mean difference is 2.41 [1.13, 3.63] pp (95% parent bootstrap). The majority class is frozen UP from earlier pilot counts: 1,652 up / 1,644 down / 41 neutral, not selected from the final test. Reversal was suggested after outcomes were reviewed, so this audit is not confirmatory. The previous 13.87-point comparison against momentum remains its original, weaker-comparator exploratory result.

## Fresh-seed v0.4 confirmation

Three host profiles were frozen: standard=(200 agents, .10 activity, .10 maker); sparse=(100, .05, .10); maker30=(200, .10, .30). Sparse changes two settings, so it tests a joint profile rather than identifying their isolated causal contributions. Each has 60 new independent parents, 100 warmup plus 500 observation base candles. Profile/seed ranges, primary contrasts and sample-size reasoning are in the preregistration. Total: 180 untouched scenarios and 108,000 raw candle boundaries, including warmup. No extra scenarios were added after results.

All rules use identical origins and the next completed base-candle last-trade label, ±1 bp neutral. Inputs stop at the origin. Parent IDs, not overlapping candles, are bootstrap units. Three primary book-minus-reversal comparisons use Bonferroni-adjusted 98.333% intervals; other scores are descriptive.

| Profile | Eligible / candidates | Coverage | Book / reversal / momentum accuracy | Book − reversal, pp [adjusted CI] |
|---|---:|---:|---|---:|
| standard | 20,007 / 28,200 | 70.95% | 57.28% / 54.52% / 43.00% | 2.76 [1.57, 3.89] |
| sparse | 20,049 / 28,200 | 71.10% | 60.99% / 55.29% / 39.81% | 5.68 [4.57, 6.84] |
| maker30 | 25,864 / 28,200 | 91.72% | 63.97% / 60.63% / 31.29% | 3.35 [2.51, 4.20] |

The frozen book rule beats reversal within all three declared host profiles after this familywise adjustment. The effect is smaller than comparison against momentum and differs by profile. This confirms a limited simulator association, not a calibrated entry probability or real-market effect. Source matching/removal artifacts still contaminate path history even after invalid-origin exclusion.

| Profile | Locked/absent exclusions | Missing-depth exclusions | Book balanced accuracy | Book recall down / neutral / up |
|---|---:|---:|---:|---|
| standard | 895 | 7298 | 39.94% | 58.01% / 3.82% / 57.98% |
| sparse | 1207 | 6944 | 43.71% | 62.17% / 6.12% / 62.84% |
| maker30 | 770 | 1566 | 45.91% | 66.89% / 4.06% / 66.79% |

Full constant-rule, pilot-majority, momentum, reversal and book per-class recalls, predicted-class counts and origin counts are in analysis-final/v04-statistics.json. Low neutral recall and changing class balance matter; ordinary accuracy must not replace balanced/class-conditional reporting.

## v0.5 size/depth and schedule robustness

Three profiles × 40 parents × 9 conditions = 1,080 scenario identities, with an untouched baseline in each parent/profile. All 1,080 completed and matched their warmed baseline fingerprint; exact aggregate cash/coin transfers reconcile at every recorded boundary. Both schedules achieved their intended quantities; no partial/zero-fill failures occurred in this finite study, which does not eliminate the confirmed boundary defects. There are 120 independent v0.5 parents, not 1,080 independent samples.

Totals target 0.5× and 2× initial opposite-side depth within 10 bp, rounded upward to a multiple of five (minimum five). Actual ratios are reported because the small minimum/multiple materially changes low-depth sizes. One shot at origin versus five equal slices at 0/5/10/15/20. Cost is achieved-quantity VWAP versus the original arrival, signed by side. Twelve profile/side/size primary contrasts use Bonferroni-adjusted 99.583% intervals. Negative five-minus-one is cheaper.

| Profile / side / target | Paired parents | Mean quantity / achieved depth ratio | Five − one cost, bp [adjusted CI] |
|---|---:|---|---:|
| standard / buy_d0.5 | 40 | 16.12 / 0.702× | 1.81 [-3.32, 6.97] |
| standard / buy_d2 | 40 | 57.38 / 2.177× | -0.01 [-4.70, 4.89] |
| standard / sell_d0.5 | 40 | 14.75 / 0.661× | -2.65 [-7.99, 2.36] |
| standard / sell_d2 | 40 | 52.50 / 2.160× | -4.47 [-9.75, 0.55] |
| sparse / buy_d0.5 | 40 | 11.25 / 0.773× | -1.20 [-5.19, 2.99] |
| sparse / buy_d2 | 40 | 36.88 / 2.186× | -3.25 [-7.00, 0.95] |
| sparse / sell_d0.5 | 40 | 13.50 / 0.654× | 1.05 [-2.83, 5.07] |
| sparse / sell_d2 | 40 | 47.12 / 2.106× | -0.76 [-4.46, 2.87] |
| maker30 / buy_d0.5 | 40 | 18.75 / 0.642× | -0.46 [-3.58, 2.60] |
| maker30 / buy_d2 | 40 | 68.12 / 2.102× | -2.87 [-5.96, -0.12] |
| maker30 / sell_d0.5 | 40 | 19.00 / 0.724× | -1.22 [-4.17, 1.61] |
| maker30 / sell_d2 | 40 | 68.62 / 2.183× | -3.09 [-5.94, -0.37] |

Ten of twelve adjusted intervals include zero. Only the two maker30 / 2× contrasts exclude zero in favor of slicing, with endpoints near zero; finite-bootstrap Monte Carlo precision and the limited profile budget warrant caution. Therefore the earlier fixed-500-unit slicing result is not a universal execution rule. Preserve it as the original size/profile-specific finding; the new normalized-size study limits its generalization.

Deadline outcomes are recorded at common origin +1/+5/+15/+30/+50, and at +1/+5/+15/+30 after the last fill. Common +50 uses 50 candles after the one-shot fill and 30 after the final slice; elapsed exposure is explicit. The +50 mark-to-market sensitivity is not an actual unwind. No fees, funding, latency, spread decomposition or opportunity-cost penalty is modeled. Total VWAP cost and actual fill quantity are separate from price movement and vendor display PnL. Baseline-relative outcomes can be reconstructed from the retained common-parent rows; no unmatched/native equality is claimed.

## Triggered entry labels and matching

Walls were defined before the event using trailing quantity thresholds, five-boundary persistence and strictly positive distance within 10 bp. First eligible event per parent/side/strength only. Trigger is the earliest next-15-candle OHLC range spanning the frozen level; this is a touch proxy, not proof that a limit order fills. Target/stop are ±10 bp from that level, with a 30-candle horizon after touch. Untriggered events are retained.

If either barrier appears in the trigger candle, its timing relative to touch is unknown, so the primary label is ambiguous. Subsequent same-candle double crossings also remain ambiguous. No wins are assigned from convenient OHLC ordering. A separately labeled complete-bar-after-touch sensitivity is recorded, but it is a different policy and cannot repair missing execution ordering.

| Profile / level group | Signals / 60 parents | Triggered / untriggered | Win / loss / ambiguous / timeout | Success-probability bounds among triggered |
|---|---:|---:|---|---|
| standard / bid_strong | 60 / 60 | 56 / 4 | 0 / 0 / 56 / 0 | 0.00%–100.00% |
| standard / bid_weak | 60 / 60 | 56 / 4 | 0 / 0 / 56 / 0 | 0.00%–100.00% |
| standard / ask_strong | 58 / 60 | 55 / 3 | 0 / 0 / 55 / 0 | 0.00%–100.00% |
| standard / ask_weak | 60 / 60 | 54 / 6 | 0 / 0 / 54 / 0 | 0.00%–100.00% |
| sparse / bid_strong | 60 / 60 | 58 / 2 | 0 / 0 / 58 / 0 | 0.00%–100.00% |
| sparse / bid_weak | 60 / 60 | 52 / 8 | 0 / 0 / 52 / 0 | 0.00%–100.00% |
| sparse / ask_strong | 59 / 60 | 52 / 7 | 0 / 0 / 52 / 0 | 0.00%–100.00% |
| sparse / ask_weak | 60 / 60 | 59 / 1 | 0 / 0 / 59 / 0 | 0.00%–100.00% |
| maker30 / bid_strong | 60 / 60 | 53 / 7 | 0 / 0 / 53 / 0 | 0.00%–100.00% |
| maker30 / bid_weak | 60 / 60 | 57 / 3 | 1 / 0 / 56 / 0 | 1.75%–100.00% |
| maker30 / ask_strong | 60 / 60 | 54 / 6 | 0 / 0 / 54 / 0 | 0.00%–100.00% |
| maker30 / ask_weak | 60 / 60 | 53 / 7 | 0 / 0 / 53 / 0 | 0.00%–100.00% |

The bounds are nearly [0,1]; these data cannot calibrate entry quality. A near-perfect result in the complete-bar sensitivity would not change that verdict: it discards the unobserved trigger-bar ordering and changes the policy.

Strong/weak matching used no future outcomes: same profile and side, distance difference ≤2 bp, volatility ratio .8–1.25 and normalized-volume difference ≤.25. Greedy ties are deterministic and weak events are not reused. Before/after standardized covariate balance and unmatched counts are in entry-balance.json. Parent components are used because cross-parent matching can correlate pairs.

| Profile | Matched pairs | Both triggered | Independent matching components | Paired success-difference bounds |
|---|---:|---:|---:|---|
| standard | 99 | 86 | 2 | [-1.0, 1.0] |
| sparse | 99 | 86 | 1 | [-1.0, 1.0] |
| maker30 | 90 | 72 | 2 | [-1.0, 1.0] |

Only 1–2 connected parent components remain per profile, so no reliable matched-pair bootstrap CI is claimed. Bounds remain [-1,1]. Matching reduces observable covariate differences but neither resolves ordered executions nor proves an effect. There is no 80% entry claim.

## Native versus host and label acceptance

NATIVE-HOST-EQUIVALENCE.md documents initialization, five-sweep scheduler, frame-time differences, CLR/Mono randomness, manually seeded portfolios, profile selection and bypassed chart/bot/audio lifecycle. A fresh native v0.5 process supplied archived original screenshots for untouched baseline, one buy, repeated buy, reduction/close, one sell and close. Nominal lot 100 and net supply reconciliation agree behaviorally with prior checks. Exact native/host trajectories are not compared because state, RNG and scene parameters cannot be matched.

Fresh native baseline paused at $102.96. Two paused buys moved last to $103.39 and $104.00. A documented resume refreshed +200 nominal units and supply fell by 200. Subsequent opposite actions closed both lots; another sell opened short, and a buy closed it. Final refreshed nominal size and worth are zero, supply returned to 1,787,178, and the app is verified paused/flat at $103.80, total display PnL −3.11. Stats refresh intervals advanced the market. These are behavioral observations, not equivalent-state execution-cost trials. Images and a numeric transcription are retained; full native cash/VWAP remains unavailable.

TRAINING-DATA-DEFECT-REGISTER.md distinguishes confirmed code/fixture behavior from suspected consequences, including intratrade extrema, player-volume weighting, partial/zero fills and nominal positions, reservations/negative balances, unverified cancellation unlock, v0.4 equality/removal/pruning/counters and incomplete state/RNG restoration. **Current vendor outputs are rejected for trusted synthetic pretraining.** Exact diagnostic level arrays/ledgers do not repair unobserved trades or defective economy rules. No historical records were silently repaired.

## Real BTC bridge: acquisition actually started

Public Binance USD-M BTCUSDT REST and routed WebSocket endpoints were reachable. A bounded 300-second engineering sample collected raw depth, aggregate executions, kline events, a depth snapshot, server time, instrument metadata and 1,500 recent one-minute exchange klines. No keys, signed/account requests or orders were used. Raw capture is preserved locally and a copy is included with these research artifacts for reviewer reproduction.

Captured 2,925 depth events and 1,366 aggregate-trade events. Two pre-snapshot stale events were dropped; 2,923 updates were applied, with zero detected pu gaps or crossed books. Top-20 snapshots retain exchange event/transaction and local receipt timestamps. Four complete captured minutes matched official OHLC; three also matched base volume exactly, while one differed by 0.001 BTC. Partial first/last minutes are explicitly excluded from completeness claims.

This demonstrates feasible engineering acquisition, not a training dataset or a complete execution feed. The official aggregate stream groups market fills and excludes insurance/ADL trades; visible public depth excludes RPI orders. A finite depth snapshot also cannot certify every outside level. The volume discrepancy is retained, not patched. Raw messages retain first/last trade identifiers and aggregate IDs for subsequent coverage analysis.

### Acquisition contract for the next pipeline stage

- One venue/instrument: Binance USD-M BTCUSDT perpetual. Verify exchange symbol status, contractType, base/quote/margin assets and quantity/price filters. Keep the spot prototype and 2023 unidentified-venue midpoint dataset separate.
- Bootstrap by buffering routed public depth, fetching REST snapshot, dropping older events and requiring the documented U/u overlap. Thereafter require each pu to equal previous u. A gap or invalid/crossed state invalidates the segment until a fresh snapshot bridges buffered events. Never forward-fill a broken book as real liquidity. The bounded recorder has no daemon/reconnect/resnapshot loop; implement that before durable recording.
- Store original payload, exchange event E and transaction/trade T, receive UTC nanoseconds, receive monotonic nanoseconds, connection/sequence/segment IDs, snapshot request/response times and clock-offset diagnostics. Base quantity in BTC; quote notional in USDT; use decimal arithmetic. Preserve local clock uncertainty and out-of-order/duplicate flags.
- Build UTC minute candles from verified ordered executions: first/last trade, every price extreme, sum base and quote quantity. Do not force next open to prior close. Reconcile closed candles against the exchange; distinguish missing trade coverage, timestamp aggregation and source-specific excluded events. Official closed klines may support a separate candle-only experiment with explicit provenance; aggregate-derived volume is not silently substituted.
- At forecast origin, save immutable exchange cutoff, maximum sequence/trade IDs, actual issuance and all input availability times. Inputs must be both exchange-time eligible and received by issuance. Late messages/revisions cannot retroactively alter stored forecasts. Score only matured targets; no real-market error panel exists before actual forward predictions.
- Freeze historical same-venue candle/trade splits and a separate prospective book split. The existing proposal is 60/15/15 usable days for book fitting/validation/test with selection/calibration separated. A candle-only baseline can use independently acquired verified history sooner. Preserve entire days/segments, gaps and embargoes, fit scalers only on training data, and never choose a majority class from final test labels.

Sources checked 1 November 2026: [Binance local-book sequencing](https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/websocket-market-streams/How-to-manage-a-local-order-book-correctly), [routed stream endpoints](https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/websocket-market-streams/Connect), [public depth schema](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/ws-streams/public), [aggregate trade stream](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/ws-streams/market). These protocol facts are separate from the measured capture counts.

## Updated feature dictionary and development gates

| Candidate | Live availability | Current decision |
|---|---|---|
| Completed candle returns, body, range, wicks, base/quote volume | Same-venue verified candles/executions | Eligible after gap, unit and reconstruction checks; vendor v0.5 OHLC/volume rejected |
| Spread, depth imbalance, distance to visible liquidity | Sequenced public book within covered depth | Candidate supported in declared simulator profiles; not demonstrated BTC skill |
| Level persistence, additions/removals | Causal book history | Observable net-level feature; no individual order age, cancellation reason or hidden reserve implied |
| Signed aggressive flow and impact | Public executions plus synchronized arrival book | Aggregated/excluded-trade coverage must be flagged; own exact costs require actual fills or a documented simulation |
| Absorption/refill estimates | Book plus executions | Hypothesis with uncertainty; no calibrated hidden quantity or whale identity |
| Agent inventory, RNG, player identity | Simulator internal only | Diagnostic/oracle fields, excluded from deployable predictor |
| News, exact hidden liquidity, liquidation mechanics | Not supplied by these experiments | Deferred; do not invent labels from candle shape |

The proposed 1,440-minute context and MLP baseline remain independent design choices. Next approved implementation can build the causal data pipeline and dataset validator. Before a small real-only baseline: enough valid origins, frozen target/horizon/splits, strongest frozen same-information baselines, leakage tests and metric units. Before synthetic pretraining: new valid event labels and economic invariants. Before entry calibration: triggered, cost-aware ordered outcomes and out-of-sample reliability. Before forward paper reporting: immutable real forecasts and matured outcomes. No training is started by this report.

## Evidence integrity, deviations and coordination

- Fresh raw seeds/manifests are in v04/ and v05/; analysis-final contains unique origins, entry signals, paired summaries, balance and raw SHA256 catalogs. The earlier post-hoc baseline audit has its own file. All attempted runs are retained; the fixed budget has ended.
- An initial derived analysis used low-price rather than entry-level denominator for trigger-bar lower-bound detection; this was corrected to the registered level-based threshold and retained as analysis/ versus authoritative analysis-final/. Primary direction and schedule results were unchanged. This is a documented arithmetic correction, not a new threshold selected for favorable outcomes.
- Five new tests cover neutral reversal/frozen majority, trigger-bar ambiguity, level-denominator boundary and untriggered cases, outcome-blind matching, and sequence-gap invalidation until a fresh snapshot. Existing four analysis tests and preserved-evidence checks are also run. No native exact-state/RNG or clean synthetic-label claim is inferred from passing these tests.
- Reviewer commit cb2ae3f was inspected and fast-forwarded while this work proceeded. The user authorized pushing the completed findings. A thread watcher checks incoming commits every 30 minutes, uses SHA tracking rather than author names and stays quiet when unchanged. It must not execute arbitrary incoming scripts or cross the training/trading/vendor-patch gates.

Stop before training and present this plan for review. The handoff should request a bounded real-pipeline/dataset-validation stage, not another unlimited simulator scenario search.
