# Original-DLL host: numerical results

These are controlled algorithm tests outside Unity, using the research profile in PREREGISTRATION.md. All intervals below are 95% bootstrap intervals for means across 30 main parents. Pilot parents are separate. This is exploratory evidence from one parameter profile, not adequate statistical power established in advance.

## v0.4

120 attempted scenarios; 30 main parents. Status {"ok":120}. Warmup fingerprint mismatches: 0.

| Condition | Main n | Mean 30-candle return bp | Paired change vs baseline bp [95% CI] |
|---|---:|---:|---|
| baseline | 30 | -1.143 | 0.000 [0.000, 0.000] |
| wall_weak10 | 30 | -23.366 | -22.223 [-56.053, 8.880] |
| wall_strong100 | 30 | 46.350 | 47.493 [6.960, 85.635] |

## v0.5

600 attempted scenarios; 30 main parents. Status {"ok":600}. Warmup fingerprint mismatches: 0.

| Condition | Main n | Mean 30-candle return bp | Paired change vs baseline bp [95% CI] |
|---|---:|---:|---|
| baseline | 30 | 3.100 | 0.000 [0.000, 0.000] |
| buy_d0.1 | 30 | 4.403 | 1.303 [-0.916, 3.445] |
| buy_d0.5 | 30 | 5.336 | 2.236 [-0.598, 4.443] |
| buy_d1 | 30 | 8.574 | 5.474 [2.669, 8.333] |
| buy_d2 | 30 | 14.529 | 11.429 [7.905, 15.000] |
| sell_d0.1 | 30 | 3.204 | 0.104 [-2.014, 2.205] |
| sell_d0.5 | 30 | 1.775 | -1.325 [-3.321, 0.539] |
| sell_d1 | 30 | -2.428 | -5.528 [-8.086, -3.204] |
| sell_d2 | 30 | -6.538 | -9.638 [-13.146, -6.499] |
| buy_one10 | 30 | 3.443 | 0.343 [-3.058, 3.405] |
| buy_slice10 | 30 | 6.092 | 2.992 [-0.112, 5.360] |
| sell_one10 | 30 | 1.542 | -1.558 [-3.797, 0.574] |
| sell_slice10 | 30 | 0.531 | -2.569 [-4.575, -0.743] |
| roundtrip_buy | 30 | 2.879 | -0.221 [-2.441, 1.542] |
| roundtrip_sell | 30 | 1.970 | -1.130 [-3.521, 1.006] |

| Condition | Signed immediate impact bp | Exact fill slippage bp | Partial entries / n |
|---|---:|---:|---:|
| buy_d0.1 | 2.060 | 1.886 | 0/30 |
| buy_d0.5 | 4.791 | 3.224 | 0/30 |
| buy_d1 | 8.022 | 4.984 | 0/30 |
| buy_d2 | 20.993 | 10.738 | 0/30 |
| sell_d0.1 | 1.832 | 1.677 | 0/30 |
| sell_d0.5 | 4.925 | 3.219 | 0/30 |
| sell_d1 | 8.260 | 4.920 | 0/30 |
| sell_d2 | 18.888 | 10.117 | 0/30 |
| buy_one10 | 5.534 | 3.636 | 0/30 |
| buy_slice10 | 1.862 | 2.769 | 0/30 |
| sell_one10 | 5.029 | 3.554 | 0/30 |
| sell_slice10 | 2.036 | 2.069 | 0/30 |
| roundtrip_buy | 5.534 | 3.636 | 0/30 |
| roundtrip_sell | 5.029 | 3.554 | 0/30 |

Roundtrip buy: mean ledger cash PnL $-0.2810 [-0.6480, 0.1130], positive 12/30, residual max 0. No modeled fees; source balance defects apply.

Roundtrip sell: mean ledger cash PnL $-0.6637 [-1.0701, -0.2763], positive 11/30, residual max 0. No modeled fees; source balance defects apply.

buy slices minus one-shot execution slippage: -0.867 bp [-3.315, 1.431]. Positive is worse.

sell slices minus one-shot execution slippage: -1.485 bp [-3.320, 0.224]. Positive is worse.

All per-candle paths and fills remain in evidence/original-host. host-statistics.json contains all horizons, mean/median/quantiles, uncertainty, path failures, negative balances and recovery censoring. Baseline-relative changes are paired by parent. Multiple exploratory comparisons are not multiplicity-adjusted; use them for hypotheses and defect characterization. No result establishes live BTC profitability.
