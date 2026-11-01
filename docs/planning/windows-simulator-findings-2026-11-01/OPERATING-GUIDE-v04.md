# Windows v0.4 operating guide

Evidence: hashed installed assembly, read-only decompilation; executable process detected. Runtime chart rendering and interactive control outcomes remain unverified because captures time out. This is a code-verified guide with explicit runtime gaps.

Executable: `Krafer Agent Trader Sim/Kat0-4(Win)/Kat 0.4/MarketSimulation.exe`. Relevant classes use the suffix `Real`; the name does not mean live exchange data.

| Control | Installed code behavior | Runtime verification |
|---|---|---|
| B / Buy | flat opens long; short closes to flat; already long does nothing | pending |
| S / Sell | flat opens short; long closes to flat; already short does nothing | pending |
| Hold fast-forward | sets active=true and timeSpeed=100; release returns speed to 1 | pending; it can unpause |
| Space | toggles active | pending |
| 1 / 2 / 3 | backup / restore / toggle repeated future runs | pending; random state is not saved; do not use as deterministic branches |
| Esc / F11 | windowed / toggle fullscreen-window mode | code verified, UI outcome pending |
| Drag / wheel / Shift+wheel | pan / horizontal zoom / vertical zoom | pending |
| Show/Hide Order Bars | toggles historical book drawing | historical snapshots continue being captured in code even if hidden |
| MA toggle | Indicator_Amigo toggles its own SMA; configurable period | scene periods 25/50/200/800 not independently read |

Player actions do not submit orders into the order book. They mark a hypothetical position at last traded price. Position-size formula is `100 / (rawPrice*(1±commissionRate))`, with initializer commissionRate=0.001. Actual scene override is unknown. Opposite-side action closes; a further action is required to open the other side. Total PnL combines realized and floating calculations. Last price UI divides raw price by 100; PnL text uses its calculation without that display division. Do not assume the fixed 100 numerator represents a verified $100 notional.

One base candle is five ProcessMarket sweeps; each sweep gives all traders a chance to act. `tickInterval` is declared but unused in scheduling. Time accumulates as timeSpeed/100 * deltaTime, with threshold 1/marketSpeed; excess elapsed time is discarded, and at most one sweep happens per rendered Update. No one-minute or real-session timezone mapping exists here. At field defaults, nominal candle wall time would be 500/marketSpeed seconds, but actual scene settings, frame rate, focus and load are unverified. Measure by base-candle indices.

Raw OHLC is built from individual matched price levels. Volume adds filled quantity. Last price is execution price, not mid. Equal-price incoming orders do not cross because initial crossing conditions are strict > or <; a locked market can remain unexecuted. `totalBuyVolume` and `totalSellVolume` decrement the wrong side on executions. The imbalance update in TakeOrder uses integer division. Recompute book totals/imbalance from price-level dictionaries if instrumented.

Green book bars are buy depth; red bars are sell depth. Current widths are normalized to the largest current level, not absolute depth. Historical opacity saturates at level quantity/40. Thus a saturated historical bar cannot reveal its exact size. Aggregated depth levels have no order IDs or birth timestamps, so individual order age cannot be recovered from these structures. Persistence of a level is not individual order age.

Removal is stochastic whole-level deletion, not an explicit age timer: levels over 30 units are skipped, with up to 25 recursive retries. Once per base candle, additional price-band pruning removes outer levels using default factors .67/1.33 and budget 64 per loop. Scene overrides unknown. Disappearance must be separated into fill, random removal and pruning with an event trace.

Maker mode is a new Bernoulli draw on each agent request using proportionMaker; not a permanently assigned 10% of traders. Placement multiplier averages two independent uniforms, giving a triangular distribution, not a normal distribution. Default code spans ±0.5% around last price before rounding. Maker quantities are random 1–20; nonmaker quantity is deterministic in candle index, rounded/clamped 1–20 from three sinusoids with periods about 14.142136, 40.840704 and 27.506578 candles. No single verified daily period or timezone; initial phase at index zero is fixed by the formula.

Chart maxCandles trims retained raw and drawn history while windowStart advances; it is not a simulation lifetime limit. Initializer is 1,024; advertised 4,096 requires scene/runtime confirmation. A 1,440-candle context is not guaranteed by this initializer.

Seed selection, persistent save file, native export, replay file and command-line batch interface: not found in inspected application scripts; UI availability unknown. Backup omits RNG and mid-candle state, resets position/PnL and does not preserve the saved partial candle. Treat replay as approximate resampling, not a complete restored state. No new training was started.
