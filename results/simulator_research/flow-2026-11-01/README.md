# New v0.4 flow diagnostics

This is original-DLL CLR research, not a native Unity export. Read [the report](../../../docs/planning/windows-simulator-findings-2026-11-01/RESEARCH-REVIEW-EXTENDED.md) and preregistration B before interpreting it.

- `raw-validated`: authoritative 40 independent parent runs (10 pilot, 30 main), each 600 base candles including 100 warmup. Compressed `candles.jsonl.gz` has actual boundary price–quantity arrays and OHLC/volume; `changes.csv.gz` has before/after quantities and cause provenance; manifests record seed, status and reference-scheduler checks.
- `main-analysis`: results for both phases, fixed-rule origins, first-eligible wall events, absorption/sweep proxies, volume strata, raw hashes and figure. All origins within a parent are correlated. Derived events use future labels, so they must not be ingested as unfiltered model features.
- `raw`: preserved initial technical failure before any completed candle.
- `raw-v2`: successful first pilot, same seeds as the final pilot. Not extra samples.
- `pilot-analysis` and `pilot-analysis-v2`: earlier pilot analyses, including the documented bid-distance-denominator correction. The final `main-analysis` supersedes them.
- `compatibility-original-host`: rerun of the original 720 scenarios after exposing research-host configuration helpers. The six CSVs match earlier hashes; these are repeatability checks, not new parents.

In `changes.csv.gz`, candle is zero-based, sweep 0–4 is `agent_sweep_net`, 5 is price pruning and 6 is random removal. Agent changes are net changes per sweep, not an exact fill ledger. Candle boundary persistence cannot see intra-sweep disappearance/recreation. Prices are raw cents and quantities simulator units. No one-minute/BTC mapping exists.

Reproduce using fresh output directories, from the repository root:

```powershell
pwsh -NoProfile -File research/simulator_mechanics/tools/run-flow-host.ps1 -Phase pilot -OutputDirectory results/simulator_research/new-flow/raw
pwsh -NoProfile -File research/simulator_mechanics/tools/run-flow-host.ps1 -Phase main -OutputDirectory results/simulator_research/new-flow/raw
.venv/Scripts/python.exe research/simulator_mechanics/tools/analyze-flow.py results/simulator_research/new-flow/raw results/simulator_research/new-flow/analysis
```

Both phases need the supplied licensed v0.4 extracted build at the expected local path. No binaries are patched, attached to or redistributed by these tools. NumPy is required for analysis. Raw checksum catalog is in `main-analysis/raw-sha256.json`. The common verification file is one directory above, `extended-verification-2026-11-01.json`.
