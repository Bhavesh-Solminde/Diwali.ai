# What the original-DLL research host reproduces

Exact algorithms are invoked from hashed original managed assemblies in transient CLR objects. This is neither a Unity player run nor an external exporter from the running game. See OriginalHost.cs, ValidationHost.cs and the archived native-v05 images in the new validation results.

| Dimension | Research host | Native application / limit |
|---|---|---|
| Initialization | Uninitialized MarketSimulator/chart objects bypass MonoBehaviour/native constructors; OrderBook/Trader constructors run; declared raw price 10000 | Unity lifecycle, serialized scene settings/components/UI/audio/rendering active; actual initial price/count/maker/activity/retention not fully exported |
| Participants | Original Init builds200 seeded agents. Sparse profile retains first100 and their actions; extra transient construction has no agent actions. Constructor-created random generators are replaced in those host objects before simulation | Creator claim or averaged panel is not exact scene trader count. Native agents initialize with unseeded System.Random objects, so trajectories cannot be aligned |
| Portfolios | v0.5 seeded cash 100000..999999 raw cents, coin 10..99, separate initializer Random(seed*31+17) | Ranges come from inspected code; actual native draws and inventory state differ. Player has no finite portfolio object |
| Randomness | Book Random(seed), agent Random(seed*1009+i*7919); deterministic fresh reinitialization, warmup fingerprints compared | Unity/Mono RNG stream equivalence not certified; native seed UI and complete restore not verified. Host .NET 10.0.11 is a different runtime |
| Sweep scheduler | Exactly five sweeps per base candle; agents called in a fixed list order; each TryPlaceOrders(candle_index); record trade-history boundary, prune v0.4, random-remove, reset live candle | Unity Update accumulates(deltaTime*timeSpeed/100), threshold1/marketSpeed, discards excess, at most one sweep/frame. Focus/render load and scene speed alter wall time |
| Candle/reset | Host manually finalizes selected logic and resets original live-candle objects; volume/OHLC defects retained | Unity chart aggregation, retention, native input timing, rendering and complete lifecycle are bypassed; no minute mapping |
| Player actions | Direct PlaceOrder with buy max price/sell1, null trader; cash/coin deltas recover synchronous achieved fills/notional | B/S also call nominal Long/Short, display/UI callbacks; native nominal lot 100 observed; fields may initialize10 in code. Native display accounting is not the host ledger |
| Pairing | Every condition reinitialized with same profile/seed; warmed book/portfolio fingerprints match; outcomes paired by independent parent | No native equivalent initial state/RNG exists. Even host fingerprint is named-field evidence, not a universal proof of all hidden state; seeded reinitialization avoids broken restore |
| Other components | Bots/training, audio, LiqCycle and most chart methods bypassed | Scene component activation not fully certified; no claim of simulated liquidation, news, leverage or strategic whales |

## Fresh native behavior check

This continuation's single selection/activation succeeded. Prior activation failures remain recorded; no repeated failed captures were used. A new v0.5 process was launched after preserving and closing the prior session. The new untouched session rendered candles/current depth and started with zero position/PnL. It was paused at last$102.96; a second image verified stable candles, book, price and PnL.

While paused, B moved last to$103.39 and another B to$104.00; floating changed0→0.22→1.16 while total stayed0. On a documented resume for statistics refresh, nominal size became+200 and ordinary supply fell1,787,178→1,786,978. Two S inputs after pausing reduced then closed the long (last$102.43 then$102.13; total−0.81 then−1.98; floating 0 after close). A further S opened short (last$101.89, floating+0.12); B closed it (last$103.29, floating 0,total−3.11). Final resume refreshed size/worth to 0 and supply back1,787,178; Space then left the app paused/flat at$103.80, verified by another image.

This is one-session behavioral evidence consistent with host buy/sell consumption, accumulation and opposite-side reduction. It is not a numeric replication: starting prices, depth, quantities, RNG, timing and portfolios differ. Two running intervals for stat refresh are explicit confounders. Paused opposite-depth depletion is visible but exact depth/fills/VWAP/native cash transfer cannot be read. +200 nominal plus−200 aggregate coins supports achieved total 200 under the inspected conservation rules; not per-execution proof. No entry probability, generic impact coefficient or native profitable strategy follows.

Native v0.4 prior direct tests already established mark-only player actions and same-side no-op, with historical depth overlay. Those remain historical evidence; this continuation does not re-document controls or claim a fresh v0.4 native baseline.

Native images are original window captures saved for experiment evidence, not cropped or reconstructed. Exact ordered execution export and scene/RNG access remain unverified. Record this limit once; it does not block independent real-market collection.
