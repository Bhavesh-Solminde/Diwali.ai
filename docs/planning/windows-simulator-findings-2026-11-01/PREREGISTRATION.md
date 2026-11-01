# Research protocol — 1 November 2026

Status: registered after reading sources and static inspection, before isolated execution tests. Static findings are already known; this is not a blind preregistration of those findings. No model training authorized at this stage.

## Evidence levels and boundaries

1. Creator narration/release descriptions: hypotheses, not runtime measurements.
2. Read-only decompilation of hashed Windows assemblies: installed code paths, not proof a scene activates every component.
3. Isolated C# execution of extracted methods with explicitly documented Unity/UI stubs: semantic diagnostics, not observations from running Unity apps and not a replacement for independent market runs.
4. Live Windows UI observations: require successful frame capture and verified settings. Neither simulator currently supplies capturable frames; repeated capture timeouts are logged. Do not input trades blindly.

Original archives and binaries remain unchanged. Decompiled paid code is local evidence only and must not be published or redistributed. Research tools and reports are separate from supplied packages.

## Capability/validity gates

- Verify matching at equality; multi-level candle extrema; execution quantity, volume and PnL; aggregate depth totals; collateral reservation; snapshot type compatibility and completeness.
- Fixtures have specified books and portfolios. Each semantic check is deterministic; repeating it is not independent statistical evidence. Vary fixture price/quantity across 10 pilot and 30 main cases where useful. Log every case, including failures/exceptions. Do not claim population confidence intervals for deterministic defects.
- If accounting, OHLC or replay gates fail, withhold economic/probabilistic conclusions that depend on them. Keep unaffected qualitative hypotheses for later testing.
- Never relabel extracted/rehosted execution as installed Unity runtime testing. Stubs deliberately skip rendering and audio. Native event exports have not been found.

## Live market experiments (pending capture and measurement gates)

Untouched baselines: 10 pilot runs per version, then at least 30 independent initial states per comparison after estimating pilot variance. Restart into clean separate working copies, preserve version-specific logs. Actual serialized parameters must be measured; field initializers are insufficient. Warm up 100 base candles, measure 500 completed base candles. Retain at least 1,440 only after capacity is established. Five agent-update sweeps form one base candle; no BTC minute equivalence assumed.

Without complete random-state restoration use randomized interventions across independent runs and matched settings, not paired causal claims from the defective restore. Both signs; allocation by pre-generated seed outside the simulator, with run order logged. Branches remain clustered by parent even if restore is later fixed.

| Study | Hypothesis / condition | Outcomes and failure criteria |
|---|---|---|
| Baseline, both | Economies differ; no directional prediction assumed | return/drift, spread, depth, OHLC/range/wick/volume, balances, extreme paths; stop validity interpretation on impossible books or balances |
| Wall bounce, v0.4 | Persistent large nearby depth changes rejection/break rates | wall >= 90th percentile positive level depth in previous 100 candles, within 10 bp, observed >= 5 candles; weak control <= median depth matched on distance, volatility and volume phase; first eligible event/run; failed wall retained |
| Wall removal, v0.4 | Removal opens liquidity gaps | classify execution, random level removal, price pruning independently; require event trace; screen disappearance alone cannot classify |
| Absorption, v0.4 | Large traded quantity with limited move and refill predicts subsequent behavior | signed fills, depth delta and last price; no hidden reserve label without explicit mechanism |
| Pattern/book, v0.4 | Pre-event book adds information beyond predefined candle patterns | range: prior 20-candle high-low <= median range over preceding 100 windows; triangle: positive low and negative high OLS slopes over prior 20 candles and terminal fitted width <= half initial width; flag: preceding 10-candle return >= 2 prior-window standard deviations followed by 10-candle countertrend retracement <= 50% of pole. Classify before outcome; include failures; no fitting thresholds on test outcomes |
| Impact, v0.5 | Sweeping more opposing liquidity increases slippage | 0.1/0.5/1/2 x opposite depth within 10 bp when numeric depth exists; integer rounding and achieved fills recorded. Otherwise only verified size units / previous 30-candle true executed volume; synthetic display volume invalid unless corrected |
| Schedule, v0.5 | Slicing changes average fill/impact | same intended integer quantity, one order versus five slices one base candle apart; measure actual executed quantity, residuals and VWAP; failed/missing fills remain failures |
| Post-trade, v0.5 | Refill and inventory influence recovery | no additional player actions; outcomes 1,5,15,30 completed base candles after last fill; censor if observation ends |
| Round trip, v0.5 | Profits require fill-based reconciliation | unwind achieved entry quantity; independent cash ledger and residual inventory; exclude UI PnL as ground truth if quantity gate fails |
| Inventory, v0.5 | Constraints alter future flow | cash/coins, locked balances, outstanding obligations, exhaustion and replenishment; test ordinary trading separately from player injections and capital hotkey |

Primary price result: 10,000*(P_h/P_0-1) bp, last trade if mid unavailable. Slippage: side*10,000*(VWAP/P_arrival-1); spread/fees separately. Wall target/stop: 10 bp favorable/adverse from first touch within 30 candles; first hit wins, both in one OHLC candle ambiguous unless executions resolve ordering. MFE/MAE use fill trace; recovery is first return within half immediate signed impact, censor at 30. Event timing base candle and tick, never wall-clock horizon.

Summaries: all attempted/excluded counts and reasons, mean/median/5th/95th percentiles; Wilson intervals for binary rates across independent parents; bootstrap means and quantiles by parent (2,000 resamples), paired only with validated full state/RNG restoration. Pilot variance determines expansion, not an assumed sufficiency of n=30. Prediction probabilities must be timestamped before outcome and tested with Brier score, reliability bins and interval coverage. No live BTC conclusion follows from simulator results.

## Amendment A: original managed-code research host, before market-run collection

Original managed methods can execute in the local PowerShell CLR when unused Unity objects are allocated without their native constructors. This allows numeric algorithm research despite the UI capture failure. It does not reproduce Unity rendering, scene serialization, frame timing, audio, chart retention or original Mono RNG implementation. Use original DLL methods for Trader, OrderBook and LiveCandlestick; manually reproduce the documented five-sweep candle scheduler. Do not invoke bot/training methods. This is a distinct experimental environment, labeled `original_DLL_CLR_host`, and cannot be passed off as live Unity measurements.

Explicit research profile, not an installed-scene claim: 200 agents, initial price 10,000 raw cents, maker probability 0.1 per request, activity 0.1 per sweep, drop rate 0.1 per candle, 100-candle warmup, 30-candle follow-up. v0.4 pruning uses field defaults. v0.5 initial balances sampled from documented constructor ranges with an explicitly seeded separate initializer. Replace private System.Random fields in transient host objects only with recorded deterministic seeds. No game binaries or running-app objects are modified. The new CLR's System.Random sequence is not claimed identical to Mono.

Ten pilot parents (seeds 10000–10009), then thirty main parents (20000–20029). Reinitialize each scenario from scratch with the same parent seed and validate the warmed book/portfolio fingerprint against its baseline before intervention. This supplies common initial states in this research host without using the broken backup. Treat all scenarios from a parent as paired/correlated. No pooling of v0.4 and v0.5 effects.

Conditions: untouched baseline in both; v0.4 extra bid wall at floor(arrival*0.999), weak=10 units and strong=100 units, no player PnL interpretation; v0.5 buy and sell orders at ceil(0.1/0.5/1/2 * actual opposite 10-bp depth), each rounded to at least one unit if depth positive; a separate 10-unit one-shot versus five 2-unit slices one base candle apart for both signs. If opposite 10-bp depth is zero, log that condition as unavailable, rather than inventing normalized depth. Follow-up outcomes for slices are measured relative to the final slice and include a common end at 34 candles for comparison. Round-trip: 10 intended units, unwind achieved entry quantity at +5 candles; record exact ordinary-balance transfers as independent player cash/quantity ledger, no fees assumed in book methods.

Capture each base candle's last trade, reported OHLC/volume, actual book sums/spread, counts and sums of negative ordinary balances, and intervention fills via aggregate portfolio deltas. These host-produced CSVs are diagnostic research data, not a native app export or a training dataset. v0.5 OHLC and weighted volume remain uncorrected source outputs and are explicitly unsuitable for label validation. Price outcomes use last trade. For v0.4 wall events distinguish simple price-level retention from touch/bounce; no assertion that inserted walls represent naturally persistent events. Pattern, absorption, real order-age and execution-vs-cancel classifications remain gated on event capture; do not infer them from candle CSVs.
