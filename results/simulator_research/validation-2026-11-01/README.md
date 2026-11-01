# Bounded simulator validation and real-data bridge

Read [the decision report](../../../docs/planning/windows-simulator-findings-2026-11-01/VALIDATION-DECISION.md) and [frozen validation protocol](../../../docs/planning/windows-simulator-findings-2026-11-01/VALIDATION-PREREGISTRATION.md). No model training or real trading occurred.

- `baseline-audit.json`: exact post-hoc audit of 10,168 unique earlier main/all origins, including reversal and pilot-selected majority. Preserves the original weaker-baseline findings as exploratory.
- `v04`: 180 fresh independent untouched parents, three profiles ×60, 600 boundaries each including100warmup. Original DLL logic, not native Unity export. Raw `rows.jsonl.gz` carries actual boundary levels and v0.4 OHLC/volume; manifests carry settings, seeds, status and identity.
- `v05`: 120 independent parents, three profiles ×40, each with9paired conditions. Untouched baseline plus two sides ×two initial-depth size ratios ×one/five slices. Raw rows/fills/manifests retain intended/achieved quantity, exact synchronous notional, cash/coin ledger, arrival and equal deadlines. Related scenarios are not independent parents.
- `analysis-final`: authoritative confirmatory summaries, unique origin records, preregistered first-touch proxies, ambiguity bounds, outcome-blind matching/balance and raw SHA256 catalog. `analysis` preserves the first analysis before the documented trigger lower-barrier denominator correction. Primary rule/schedule results are unchanged.
- `native-v05`: original window JPEG evidence and manual numeric transcription from a fresh native process. Logs remain local. Native and host start states/RNG are not equivalent; these are behavioral checks, not numerical replication.
- `real-data-raw`: original bounded public Binance USD-M BTCUSDT recorder output and manifest, copied byte-for-byte from the ignored local data directory. No keys/account/trades. Contains depth, aggregate trades, klines, metadata and REST bootstrap. This is an engineering sample, not a training dataset or complete execution ledger.
- `real-data-quality-final`: authoritative gap/coverage and minute-reconstruction results. `real-data-quality` preserves the initial audit; a later synthetic gap test strengthened fail-closed behavior without changing this no-gap sample.

Reproduction uses installed licensed Windows builds, PowerShell CLR and pinned Python dependencies in `research/simulator_mechanics/requirements-validation.txt`. Use new output folders; tools refuse to overwrite completed output.

```powershell
pwsh -NoProfile -File research/simulator_mechanics/tools/run-validation-host.ps1 -Version 04 -OutputDirectory results/simulator_research/new-validation/v04
pwsh -NoProfile -File research/simulator_mechanics/tools/run-validation-host.ps1 -Version 05 -OutputDirectory results/simulator_research/new-validation/v05
.venv/Scripts/python.exe research/simulator_mechanics/tools/analyze-validation.py results/simulator_research/new-validation results/simulator_research/new-validation/analysis
.venv/Scripts/python.exe research/simulator_mechanics/tools/test-validation.py
.venv/Scripts/python.exe research/simulator_mechanics/tools/verify-validation.py
```

Recorder: `record-public-btc.py NEW_OUTPUT_DIRECTORY --seconds 300` starts a maximum-five-minute public engineering capture; it is not a persistent service. `validate-public-btc.py RAW_DIRECTORY NEW_OUTPUT_DIRECTORY` audits its sequence bootstrap and aggregate-derived candles. Official endpoint details are cited in the report. Complete durable resnapshot/reconnect and timestamp/cutoff validation before a real-data experiment. No hidden-liquidity sourcing or vendor engine replacement is included.
