# New v0.5 repeated-intervention diagnostics

Original-DLL CLR research outside Unity. Read [the report](../../../docs/planning/windows-simulator-findings-2026-11-01/RESEARCH-REVIEW-EXTENDED.md) and preregistration C.

`raw` contains 200 unique scenarios from 40 parents: 10 pilot and 30 main. Each parent has baseline, buy/sell 500 at once, and five 100-unit buy/sell slices at candles 0/5/10/15/20. Every scenario warms up for 100 base candles, then records relative candle 0–50. Siblings are paired, not independent samples. The 200 manifests record failures as well as successes; this collection had no execution failures or partial fills.

Compressed `fills.jsonl.gz`: intended/achieved quantity, exact notional, integer VWAP returned by source, arrival/last-after, opposite 10-bp depth, and cash/coin deltas. Exact VWAP is notional / achieved quantity. Price and notional are raw cents; slippage is side × 10,000 × (VWAP / arrival − 1). No fees are modeled by the invoked player methods.

Compressed `candles.jsonl.gz` is deliberately a **boundary-observation file**, not trustworthy trade-price OHLC. It contains last trade, best bid/ask, depth, aggregate ordinary cash/coins, negative-balance counts and original arrival. Privileged portfolios are diagnostic only. Source volume/OHLC and player display PnL have defects; do not use them as training labels.

`main-analysis/statistics.json` retains both phases, all run metrics, horizon and recovery results, and parent-grouped uncertainty. `pilot-analysis` records the procedure check made before main collection. Raw hashes are in `main-analysis/raw-sha256.json`.

Reproduction from the repository root, using new output directories and separate processes from v0.4:

```powershell
pwsh -NoProfile -File research/simulator_mechanics/tools/run-repeat-host.ps1 -Phase pilot -OutputDirectory results/simulator_research/new-repeat/raw
pwsh -NoProfile -File research/simulator_mechanics/tools/run-repeat-host.ps1 -Phase main -OutputDirectory results/simulator_research/new-repeat/raw
.venv/Scripts/python.exe research/simulator_mechanics/tools/analyze-repeat.py results/simulator_research/new-repeat/raw results/simulator_research/new-repeat/analysis
```

Requires the supplied licensed extracted v0.5 build and NumPy. Baseline ordinary totals conserve cash/coin; player null-trader interventions inject/remove assets. Negative individual balances remain possible despite conserved aggregates. Nothing in this directory certifies live BTC forecasting, portfolio realism or profitability.
