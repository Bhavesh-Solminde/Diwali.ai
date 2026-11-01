# Simulator mechanics and experiment report — 1 November 2026

The experiments support liquidity-dependent price movement in these algorithms, while revealing defects that prevent direct use of the displayed labels as trustworthy ML data. They do not establish BTC predictability or whale profitability.

## Evidence and method

- Archives preserved and SHA256 recorded. Extracted Assembly-CSharp hashes match archive entries. No binary patches or paid asset redistribution.
- Original DLL `OrderBook.GetSnapshot` invoked outside Unity throws InvalidCastException in v0.5; original order execution also demonstrated negative inventory and 100x player volume. See `original-v05-snapshot.json` and `original-v05-orders.json`.
- 18 isolated extracted-code diagnostics, each run in ten pilot and thirty main fixture iterations. All anticipated code behaviors reproduced; the normal equality-match and small/large level-removal controls behaved as expected. Some checks repeat identical arithmetic, so 40 is a reproducibility denominator, not an independent-market sample size. See `diagnostics-results.json` and `diagnostic-fixtures.json`.
- Original-DLL market host: v0.4 120 scenarios, v0.5 600 scenarios, each 10 pilot and 30 main independent seeded parent states per version. Sibling conditions are paired, not independent. All 720 final scenario identities completed; no zero-depth exclusions or execution exceptions. Warmup price/book/balance fingerprints matched baseline for every sibling. This is one explicit 200-agent profile, not the live scenes' measured settings.
- Five agent sweeps/base candle, 100-candle warmup, 34-candle observation. No bot evaluation/training. The final CSVs preserve all conditions, outcomes and fills. Mean intervals use 2,000 parent bootstrap resamples. These exploratory comparisons are not multiplicity-adjusted and n=30 is not certified adequate power.

An earlier collection pass was rerun with identical seeds after adding immediate book-last-price and reference-level columns. The final files supersede that first schema. A combined same-process attempt to load the second build failed because UnityEngine.CoreModule with the same assembly identity was already loaded; the v0.5 rerun succeeded in a fresh PowerShell process. No scenario exclusion was made to improve results. These are technical reruns, not additional independent parents.

Full numeric tables, all outcome horizons, mean/median/quantiles and uncertainty: [NUMERICAL-RESULTS.md](NUMERICAL-RESULTS.md) and `host-statistics.json`.

Reproducibility verification: an additional fresh-process run of every scenario produced byte-identical manifests, candle files and fill files (all six CSV SHA256 values match). This is a repeatability check, not another 80 independent parents. Both paid Assembly-CSharp hashes were rechecked unchanged. See `evidence/reproducibility.json`.

## v0.4: how the book changes price

Orders below/above last price accumulate into level depth; matching consumes finite displayed quantities. Incoming direction is stochastic while accumulated liquidity is stateful, so repeated paths need not be symmetric around the current trade. Equal-price orders do not initially match in this build: strict crossing comparisons can leave a locked book. Every main untouched baseline exhibited mismatched stored depth counters during observation (30/30); 16/30 exhibited a locked or crossed book at a sampled candle boundary. Reconstruct quantities from actual levels rather than using the counters.

A strong 100-unit bid submission 10 bp below origin changed the 30-candle mean return by +47.49 bp versus the paired untouched baseline (95% bootstrap interval +6.96 to +85.64). A weak 10-unit submission changed it by -22.22 bp (-56.05 to +8.88). This is not a verified bounce win rate: all 30 paths touched the reference price at some point, path outcomes overlap, and submissions can initially take liquidity if the pre-existing book is crossed. Across pilot+main, 8/40 submissions per condition executed some quantity immediately. The strong reference level remained present at candle 30 in 6/30 main paths, the weak in 2/30. Retain those fills and failures; do not call every submission a purely resting wall.

One important artifact explains persistence: random removal refuses levels above 30 quantity units. In 40/40 fixtures, a 31-unit level survived 100 forced removal calls; a sole 30-unit level was deleted. This is not immortality against executions or price-band pruning. Large walls have artificial selection advantages, so apparent support/resistance cannot be transferred directly to live BTC. There is no explicit per-order aging timestamp in this implementation.

The weak condition and several individual strong-condition paths failed to improve the 30-candle outcome. The main strong-condition paired effect ranges from about -199 to +293 bp, showing substantial state dependence. The untouched baseline's 30-candle range was approximately -1,109 to +937 bp; a mean near zero conceals extreme paths in this small profile.

v0.4 player Buy/Sell does not consume book liquidity. It is useful as a position marker/evaluation toy, not as the intervention tool for a whale experiment. The host's wall submissions invoke actual OrderBookReal.PlaceOrder; they are not UI buy markers.

## v0.5: large trades and execution schedule

Player orders consume opposite-side FIFO queues at their price levels. Ordinary maker/taker transactions transfer raw cash/coins between agents. A player is represented by null trader, so the matching method transfers balances only on the ordinary-agent side. Player buy removes coins and injects cash; player sell adds coins and removes cash. This is an open intervention economy.

Both signs show increasing immediate movement and execution slippage at larger quantity relative to available opposite depth within 10 bp. Main n=30/sign/size. At 0.1x versus 2x depth, mean buy signed last-price impact rises from 2.06 to 20.99 bp, and exact fill slippage from 1.89 to 10.74 bp. Sell impact rises from 1.83 to 18.89 bp and slippage from 1.68 to 10.12 bp. All requested quantities filled in this profile; deliberately thin fixtures separately demonstrate partial/zero-fill failures. Last trade, not mid, is the reference; spread crossing is included in these slippage numbers and is not isolated as pure impact.

At candle 30, the 2x-depth buy condition differs from paired baseline by +11.43 bp (+7.90 to +15.00); the sell by -9.64 bp (-13.15 to -6.50). These are host/profile-specific persistent effects, not proof of permanent live impact. Full 1/5/15/30 outcomes and recovery censoring are saved.

For equal intended total quantity 10, five 2-unit slices have mean execution slippage lower by 0.87 bp for buys (-3.32 to +1.43), and lower by 1.49 bp for sells (-3.32 to +0.22) relative to one shot. Both intervals include no difference. This pilot does not establish slicing superiority. Execution takes longer and observed future paths differ; all slices and common-end outcomes are retained. The immediate impact of a first 2-unit slice must not be compared as if it represented the full 10-unit schedule.

## v0.5: round trips, PnL and portfolios

Independent ledger: achieved entry quantity 10, unwind after five base candles, cash change derived from actual ordinary-agent transfers, no fee modeled by these methods. Main buy round trips average -$0.281 (interval -$0.648 to +$0.113), 12/30 positive; sell round trips average -$0.664 (-$1.070 to -$0.276), 11/30 positive. Every roundtrip had zero residual coins in this profile. These toy dollar amounts are tied to the configured $100 starting price and quantities; they are not BTC dollar forecasts. No profitable manipulation strategy is established.

Displayed PnL cannot replace this ledger: player bookkeeping omits quantity, tracks nominal clicks even on partial fills, and uses integer averaged prices. A +100 raw-price-unit change on a size-10 position records +100 rather than +1,000 raw cash units. A one-coin partial fill of a ten-unit request still records a nominal ten-unit position. A zero-filled order divides by zero. The declared commissionRate is not used in player Long/Short accounting. Total PnL is realized-only; floating is separate and also quantity-defective.

Portfolios are finite at initialization but not fully constrained: resting orders do not reserve collateral, and fill-time checks do not prevent overselling or overspending. A deterministic two-order fixture sells two coins from a one-coin seller and ends at -1. In ordinary, untouched main baselines, 11/30 parents already had a negative balance at warmup; 10/30 had at least one negative balance at final observation. This is enough to reject an assumption of enforced finite-inventory realism, even without player interventions. No selective exclusion of these states was made.

The 100-trade market-cap assumption is display accounting: `S + 100*PlayerTradeSize`. Isolated Long bookkeeping accepts 101 nominal lots in 40/40 checks. This test does not claim 101 successful live fills. Market cap and supply are algebraic summaries, not independent predictive signals. LiqCycle is audio, not a liquidation engine; holding I injects ordinary-agent capital per rendered frame and must be excluded from controlled runs.

Failure examples retained for inspection (selected after analysis to illustrate failures, not used as an accuracy sample): `v04-20026-wall_strong100` ends candle 30 down 816.30 bp from its 7,926-cent origin despite the strong bid submission; `v05-20006-roundtrip_buy` spends 99,280 raw cents and receives 99,073, a $2.07 cash loss with zero residual; `v05-20004-baseline` already has one negative-coin agent at warmup without a player trade. All paths and conditions remain in the CSVs. Aggregate ordinary-agent cash and coin sums stayed constant over the observation window in 40/40 untouched v0.5 baseline parents, even though individual balances could become negative. Conservation of the sum therefore does not establish valid collateral constraints.

## Other studies and limits

| Requested study | Outcome / evidence limit |
|---|---|
| Untouched baselines | completed in original-DLL host for both profiles; returns, OHLC/volume, book, balances and extreme paths retained; live Unity profile/time mapping not measured |
| Wall/bounce failures | controlled bid submissions and level-removal fixtures completed; no prospective calibrated bounce predictor; no individual order-age strata |
| Wall removal / thin liquidity | removal size filter and execution exhaustion tested; sampled CSVs do not identify every cancellation/fill event; no event-rate claim |
| Absorption/replenishment | visible replenishment mechanism exists through new requests; no hidden reserve found; no rigorous event-level absorption estimator validated |
| Pattern vs book information | no predictive model fitted and no shape-only versus book benchmark claimed; invalid source vectors and lack of clean labels block that conclusion |
| Large-trade impact | both signs, four actual-depth-normalized sizes, all requested future horizons in original-DLL host |
| Execution schedule | both signs, equal total quantity, ledger and paired uncertainty; inconclusive advantage |
| After large trade | 34-candle paths, return distributions and censored half-impact recovery available; no universal continuation/reversal rule |
| Round-trip economics | exact host cash ledger and residuals, both signs; displayed accounting defects separately verified |
| Inventory feedback | untouched negative balances, overcommitment fixtures and supply/PnL formulas documented; realistic exhaustion/recovery cannot be established from defective collateral constraints |

No theorem that all patterns fail, no calibrated 80/90% probability, no whale identity from candle shape, no liquidation cascade, and no real BTC profitability follows. The main scientific result is a list of useful mechanisms **and** concrete artifacts an independent ML engine must avoid. Broadening sample size cannot repair systematic matching/label/accounting defects. Preserve the original applications for visual intuition; use a corrected independent, event-instrumented engine and real data to validate learning.
