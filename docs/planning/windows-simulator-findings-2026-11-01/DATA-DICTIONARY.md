# Data dictionary and export feasibility

Scope: original Windows DLL methods invoked in a controlled CLR host outside Unity. Profile and seeds are in PREREGISTRATION.md. Files are `evidence/original-host/{runs,candles,fills}-v04.csv` and corresponding v05 files. The host never edits the paid DLLs or attaches to the running apps.

| Field / concept | Unit and timing | Evidence quality / use |
|---|---|---|
| run_id / parent_id / seed / phase | scenario ID, common parent, external host seed, pilot/main | exact host metadata; all siblings stay together in data splits |
| version / scenario / status / error | hashed build family, intervention condition, all attempts | exact; `ok` means execution completed, not economic validity |
| initial_fingerprint / matched_baseline | SHA256 of warmup price/index, aggregate levels and ordinary balances | exact for named fields; not a full serialized RNG/FIFO snapshot; deterministic reinitialization supplies matching before intervention |
| candle_index / relative_candle | five agent-update sweeps per base candle; origin after 100 warmup candles | exact host scheduler; no exchange time, no UTC minute equivalence |
| last_price / arrival | integer raw cents; dollar display=raw/100 | original book last trade; no claim these are BTC prices |
| open/high/low / reported_volume | original LiveCandlestick fields at each observation | v0.5 misses intermediate sweep extremes and weights player volume 100x; do not use as verified training labels |
| relative_candle=0 | immediate post-intervention state | baseline has reset empty live candle; v0.4 bid submissions can execute immediately in an already crossed/locked book |
| best_bid / best_ask | raw cents | 0 bid / int.MaxValue or long.MaxValue ask means absent; not an executable quote; mask absent sides |
| bid_sum / ask_sum | actual aggregate quantities from dictionaries | numeric observed book depth in simulator units; no BTC calibration |
| counter_bid / counter_ask | stored totalBuyVolume / totalSellVolume | diagnostic only; v0.4 wrong-side decrements make these disagree with actual levels |
| depth_10bp | sum actual opposite-side quantities within ±10 bp of last trade at origin | numeric, last-price anchor; not mid-based depth. Compute side-direction distances and reject crossed books for any production feature |
| reference_price / bid_at_reference | floor(arrival*.999), its current aggregated bid quantity | diagnostic wall-level persistence; orders at one level lack individual age |
| baseline_volume_30 | sum original reported volume during last 30 warmup candles | no player interventions in warmup, so no player-volume multiplier; source OHLC issue still applies |
| intended / filled / notional / integer_vwap | requested quantity; aggregate agent-coin delta; agent-cash delta; returned integer VWAP | exact portfolio transfers for synchronous player order, outside ordinary sweeps. Exact fill price=notional/filled; source returned VWAP truncates cents |
| notional_entry / notional_exit | integer raw cents across all achieved entry / unwind fills | ledger evidence; buy roundtrip cash=(exit-entry)/100, sell=(entry-exit)/100; residual assets separate |
| residual_coin | achieved entry quantity minus achieved unwind quantity | exact host ledger; a marked position does not equal executed quantity in app bookkeeping |
| negative_cash_agents / negative_coin_agents | number of ordinary agents with balance <0 | diagnostic state, never a deployable observable feature |
| total_agent_cash / total_agent_coin | sums across ordinary agents | diagnostic accounting; player t=null transfers alter totals; ordinary-only runs should conserve sums absent overflow/capital injection |
| return_h_bp | 10,000*(last_h/arrival-1), h=1/5/15/30/34 | future label only; not model-visible. Source is last trade, not mid |

All rows in these six files are numeric host observations or host metadata, not OCR estimates. Unavailable: live-app settings, exchange timestamps, per-order age/IDs in v0.4, complete trade-by-trade trace, native player-cash portfolio, calibrated real fees, news, funding, reserve/iceberg truth and margin/liquidation events. Missing fields must stay unavailable, not zero-filled.

For five-slice schedules the last slice is after candle 4. Final-slice +1/+5/+15/+30 outcomes are raw rows 5/9/19/34. Their prices can be compared against the original arrival, or against a separately identified final-slice reference; do not silently change the denominator. Ordinary table return_30 is 30 after the first order. Fill CSV records all five slices. The reported immediate sliced impact refers to the first 2-unit slice, whereas one-shot impact refers to 10 units; only total execution slippage compares equal intended quantity.

## Verdict

No native CSV/event exporter, persistent replay/seed API or documented headless research interface was found in inspected application scripts. Public getters and serialized fields do not establish a supported exporter. Screen captures alone would not yield a rigorous event-level book dataset, and native screenshot capture currently fails even though the user confirms charts visibly update.

Read-only algorithm access **is feasible**: the included research host loads the original managed DLL and initializes transient objects/parameters. This produced 720 scenario records and 25,200 base-candle observations across both builds. It bypasses Unity native constructors, audio, rendering, scene parameters, chart retention, wall-clock scheduling and bot components. It is an alternate experimental environment, not an exporter from the user's running sessions. System.Random is seeded in this CLR; Mono stream equivalence is unverified.

Training-data verdict: **do not train directly on these uncorrected simulator labels or built-in bot vectors**. Numeric extraction being possible does not make matching, inventories, volume, OHLC, PnL or temporal alignment valid. Use the files for mechanics diagnosis. A clean independent engine or creator-provided correction needs invariant tests before synthetic pretraining. No paid code or full transcripts should be committed to Git or passed to another service; the handoff reports and original research tooling are sufficient for another AI.
