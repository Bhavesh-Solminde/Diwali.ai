# Windows AI handoff: Krafer simulator research before BTC model training

You are continuing my project on a Windows PC. I purchased Krafer Agent Trader Simulator v0.4 and v0.5. Locate the supplied Windows packages in my workspace, preserve originals, and work in separate extracted directories. Our immediate task is to understand both simulators and conduct reproducible research. Do not start model training until the research report and revised model plan are reviewed.

## Objective and current state

We ultimately want an independent model for BTCUSDT perpetuals that predicts the next one-minute candle and estimates entry quality. Proposed context: 1,440 completed one-minute candles plus synchronized real order-book changes and executions, with uncertainty. We want to learn how orders cause candles to form, reject, bounce, sweep and continue, including large-trade effects. We must establish whether simulator observations support useful features and labels before building the model.

The Mac v0.5 runs its simulation but fails to draw candles. Its log reports missing ComputeBuffer bindings in Custom/CandlestickGPU_StyleMatch. Static inspection found partial buffer bindings despite a shared shader declaring Candles, Wicks, VolumeBars, OrderBars, TradeMarkers, Scale and Color. Both Mac builds share these declarations. Windows rendering has not yet been tested. No verified synthetic training dataset or new model has been produced. Do not inherit claims that every earlier video was watched continuously.

## Read the sources before experiments

- Earlier demo supplied for v0.4: https://www.youtube.com/watch?v=FC8N3Jez7cU
- v0.5: https://www.youtube.com/watch?v=1Vw1sULb9tI
- Additional v0.4 entry/branch study: https://www.youtube.com/watch?v=bfPtChR2knw
- Original simulator explanation: https://www.youtube.com/watch?v=oWheof70O9g

Read narration and inspect the visual demonstrations. Record timestamps, screenshots and actual inspected sections. If tools only expose screenshots, disclose sampled visual coverage and log gaps; never equate running playback with footage inspected. Report access problems immediately and continue independent local inspection.

Important source correction: FC8N3Jez7cU calls its demonstrated build **v0.3** at about 0:09–0:11. It explains buy/sell markers, historical order-book visualization and fast-forward, but cannot alone verify v0.4 controls. Confirm those against the actual v0.4 app. The separate entry-study video describes v0.4.

v0.5 creator explanation to verify against the installed app:

- 0:20–0:46: finite portfolios of simulated traders, with dollar/coin inventory associated with orders and trades. “Real trader” here means an agent in this simulated economy, not live exchange participants.
- 0:48–1:16: contrasts earlier unlimited-resource behavior with more bounded behavior after portfolios. The approximately ±1% remark is an observation about the demonstrated configuration, not a universal price limit.
- 1:17–2:55: the user can place large trades that move the simulated market; reversing the position can lose money. The creator says competing whales are not yet represented like real markets.
- 2:55–4:03: trade-volume spikes, clearing the book and reversal/return examples. A similar candle pattern in live BTC does not uniquely prove whale manipulation.
- 4:14–4:42: historical visual order book removed for performance; roughly 16,000 candles mentioned with uncertainty. Check actual available display and capacity rather than assuming either number.
- 4:58–5:10: liquidations, futures and leverage are described as future additions. Do not label observed moves as liquidation cascades without verifying those mechanisms exist.
- 5:13–6:10: portfolio statistics; roughly 100,000 traders claimed for the shown session, not guaranteed for every run.

My intended use: v0.4 is valuable because its order-book entries/history are easier to inspect. v0.5 is valuable for studying large participants and finite-inventory dynamics. Neither is redundant, and they are different simulated economies rather than directly interchangeable datasets.

## Phase 1: establish how each installed build works

### Additional primary evidence: user-supplied Patreon screenshots

Seven screenshots supplied on 1 November 2026 show the creator's post at https://www.patreon.com/krafer/posts/krafer-market-0-130428000, headed version 0.5 and dated 1 June 2025. Treat these as documented creator claims, still requiring installed-build checks. The page includes a separate explicitly labeled v0.4 section; this supplies v0.4 documentation despite the earlier video calling itself v0.3.

v0.4 release notes describe MA lines 25/50/200/800 and toggles; rendering/GC changes for up to 4,096 bars; aging/removal of orders; approximately 10% market makers; normally distributed order placement; and volume varying over simulated trading days. Determine what 4,096 means (retained/drawn history versus simulation lifetime); it is not automatically the run limit. Measure order disappearance due to aging separately from execution or discretionary cancellation. Verify what the 10% denominator is and what variable the normal distribution describes. Test whether the apparent volume/time cycle is deterministic, its period and its phase. Do not infer a real-world session timezone from it.

v0.5 notes distinguish finite ordinary-agent portfolios from the player, who is described as having unlimited money. Orders are associated with portfolios and PnL; maker/taker balance was changed; average entry and market-stat displays were added. Finite agent inventories do not make this a closed economy: the player's interventions can inject/remove resources. The post says its headline market-cap statistic assumes at most 100 trades in either direction, trader supply concerns the agents' coins, and diluted supply adjusts with player buying/selling. These descriptions do not yet give exact formulas or clarify whether the 100-trade assumption is an accounting convention or enforced limit. Test those distinctions and record clicks, units, holdings and executed quantity separately. Do not treat the displayed market-cap number as an independent signal or a calibrated live BTC valuation measure. The claimed $999B+ price support is a numerical-range claim, not economic realism.

Documented controls: B/S or Buy/Sell to enter long/short and the opposite control to close; drag to pan; scroll for horizontal scale and Shift+scroll for vertical scale; Esc/F11 for window/fullscreen behavior. Verify repeated same-side presses in v0.5 because whale accumulation may differ from the simple close-position description. Use these known controls first.

Research additions: stratify v0.4 wall/bounce observations by order age, maker participation and volume-cycle phase where measurable. Measure both versions' maker/taker behavior separately. For v0.5, reconcile player execution, ordinary-agent balances, supply displays, average entry and realized/unrealized PnL before interpreting whale profitability. Run normal-sized interventions first; separately test the boundaries of the 100-trade accounting convention. News and challenges appear in the older roadmap, which is not evidence they are implemented.

Inventory files, archive hashes, actual executable, Unity version, Windows/GPU/driver, display scaling, graphics backend and app logs. Do not disable Windows security globally. Preserve logs before switching versions; inspect whether preferences/logs are shared. Follow applicable confirmation rules for launching unfamiliar executables or security exceptions.

Create a separate operating guide for each version. Verify chart rendering, candle/time/volume units, current versus historical book, meaning of bar width/colors, chart scales, order display toggles, zoom/pan, pause/speed, order size, buy/sell execution, position accounting and PnL. Confirm whether clicking buy/sell opens, closes, adds or reverses; never guess from labels. Inspect actual app help and controls before trying unknown shortcuts.

Look for documented save/restore, random seed, replay branching, scenario parameters, export formats and batch/headless support. Mark each as verified / unavailable / unknown, with evidence. Compiled method names such as BackupState, RestoreState, CaptureFutureRun, GetNetworkInput and GetFuturePrices were seen in Mac assemblies; these do NOT prove the Windows UI exposes them, that state restores include randomness, or that an export/API exists. Read-only local code inspection can help document mechanics, but do not modify binaries or redistribute paid assets without further agreement.

Pause and validate: compare candles against executions if accessible, check spread and book sides, determine volume units and simulated time per candle. If time mapping is unknown, report results in simulator ticks/candles; do not call them BTC one-minute results. Verify financial accounting, whether cash/coins are locked by orders and whether money/inventory is created, injected, burned or replenished. Investigate model assumptions rather than assuming conservation or realism.

## Phase 2: preregister the experiments

First write hypotheses, sampling rules, measurements, horizons and failure criteria. Keep untouched baseline runs in each version. Do not compare a single v0.4 path with a single v0.5 path and attribute differences solely to the version. Use matched parameters where feasible and clearly state unmatched mechanisms.

Begin with 10 independent runs per feasible condition to validate the procedure, then at least 30 independent initial states per main comparison. These are proposed pilot sizes, not evidence of adequate statistical power. Estimate uncertainty and plan expansion from pilot variance. If restore/seed support exists, compare intervention and no-intervention branches from the same saved state; validate full state and random-stream restoration. Branches from one parent remain correlated, not independent samples. Otherwise use randomized interventions and separate matched baseline runs, explaining weaker causal identification. Use simulation time, not wall-clock speed, for outcome horizons.

Research matrix:

| Study | Primary version | Compare and measure |
|---|---|---|
| Untouched market baseline | Both | Returns, drift, volatility, candle/wick distributions, volume, spread, depth, inventory evolution and extreme paths |
| Bounces and wall failures | 0.4 | Price approaching persistent depth versus matched weak depth; fill, rejection, breakthrough and adverse excursion |
| Wall removal and thin liquidity | 0.4 if observable/controllable | Cancellation versus execution, sweep size, spread/depth recovery; do not conflate disappeared orders with trades |
| Absorption/replenishment | 0.4 if detectable | Executed volume relative to price movement and displayed replenishment; hidden reserve is unknown unless explicitly implemented |
| Pattern versus book information | 0.4 | Predetermined triangle/flag/range definitions with and without pre-event book state; include failures |
| Large-trade impact | 0.5 | Buy and sell separately at increasing size relative to available opposite-side depth; immediate movement and slippage |
| Execution schedule | 0.5 | Same intended total quantity as one trade versus fixed slices; achieved fills and average execution price |
| After the large trade | 0.5 | No further action: continuation, reversal, volatility, refill and time to recover |
| Round-trip economics | 0.5 | Entry and unwind, executed prices, realized PnL, residual inventory and costs if modeled |
| Inventory feedback | 0.5 | Portfolio and coin/cash changes, exhaustion, recovery and boundaries; distinguish mark-to-market from realized transfer |

Suggested order-size sweep: 0.1, 0.5, 1 and 2 times opposite-side visible depth within 10 basis points, only if that quantity can be measured. Otherwise use verified app size units and normalize by recent executed volume with its window specified. Never present a guessed bar length as exact depth. Hold other settings constant, include both signs, and avoid numerical overflow/extreme spam cases except a separately labeled robustness test.

Record price outcomes after 1, 5, 15 and 30 simulator candles. Keep next-candle prediction as the future model's primary task; longer horizons describe mechanisms and entries.

## Phase 3: capture evidence and compute reports

Prefer native numeric export with book events, fills and timestamps. If unavailable, record screenshots/video and only measurements the display supports. Log OCR or digitization errors, missing frames and approximate values. Screen images alone may be insufficient for a rigorous order-book training dataset. Do not promise one until export feasibility is tested. Keep camera/zoom fixed where numerical comparisons depend on pixels.

For each run record: version/build hash, run and parent-state IDs, seed if available, settings, simulated timestamp/tick, candle duration, warmup, intervention side/size/schedule, baseline price, spread/depth, fills/execution price, position, cash/coin balances if available, PnL, observed features, future outcomes, errors and evidence paths. Mark every field as numeric export / screen estimate / unavailable. Keep model-visible fields separate from simulator-only diagnostic state and future labels.

Measure where supported:

- Mid-price movement and candle OHLC changes in basis points; use last trade consistently and label it if mid-price is unavailable.
- Execution slippage versus arrival price; distinguish spread, impact, fees and temporary/permanent movement.
- Bounce/break frequency, time to target, maximum favorable/adverse excursion and recovery half-life, with explicit censoring and definitions.
- Order imbalance at defined depths, distance to persistent liquidity, cancellation/replenishment rates and aggressive signed flow where available.
- Calibration of forecasts made BEFORE outcomes. An 80% claim requires repeated comparable predictions, denominators, confidence intervals and coverage. A branching cloud is not automatically an 80% live-market probability.
- Mean/median/quantiles and uncertainty across independent parent states. Report every attempted run, failures, excluded runs and exclusion reasons. Bootstrap by parent run/state if using branches.

Do not conclude that all chart patterns fail, that every wick reveals a whale, or that a synthetic experiment establishes live BTC profitability. News, hidden orders, multiple strategic whales, leverage and liquidations must be marked absent/unknown until verified. Hidden-liquidity sourcing is deferred.

## Phase 4: translate research into a model proposal

After the observations, propose candidate inputs: candle returns/ranges/wicks/volume plus measured depth, imbalance, liquidity persistence, cancellation/refill, signed executions and impact/absorption estimates. Include time context when a real timestamp exists. News is a later real-data feature, not invented simulator news.

Recommend an MLP baseline and a sequence-model comparison only after checking data export and labels. Tiger's exact architecture and direct order-book inputs are not verified. The 1,440-candle context is a previously sourced design reference; confirm the simulator can supply it without mixing incompatible units.

For synthetic data, split by whole runs/parent states AND scenario families. All overlapping windows and branches from one initial state stay in one split. Evaluate unseen sizes and settings. Fit normalizers only on training data. Compare candles-only, candles+book, candles+book+trades, and synthetic-pretrained versus real-only training. Simulator-only full state can be used in a separately labeled oracle experiment, never silently supplied to a deployable predictor.

Plan separate train error, past unseen-data error and recent-market error panels, with specified formulas/units and matured predictions only. Include OHLC error, direction versus simple baselines, interval/probability calibration, entry target-before-stop/timeout and net costs. Recent live error requires real forward predictions, not the latest simulator segment. A simulator profitability result is not a real BTC backtest.

## Required deliverables and stopping point

Create a local research folder containing:

1. Source-review ledger with version corrections, timestamps, inspected visuals and gaps.
2. Verified v0.4/v0.5 operating guides and mechanism comparison.
3. Preregistered experiment plan, run manifest and raw evidence.
4. Per-experiment report with metrics, denominators, uncertainty, failed examples and limitations.
5. Feature/data dictionary and export-feasibility verdict.
6. Research-to-model change log: old assumption, evidence, revised decision, confidence and unresolved question.
7. Revised model specification and training/evaluation plan ready for my review.

Start with source review and local capability checks, then proceed through feasible pilot experiments. Report concrete blockers promptly and continue independent work. Ask only for genuinely missing access or required actions. Stop before training the model; present the evidence and proposed changes first.
