# Read-only original-DLL mechanics research

Extended tools: `run-flow-host.ps1` records untouched v0.4 boundary books and cause-tagged net changes; `run-repeat-host.ps1` compares v0.5 immediate500 versus five100-unit schedules. Both use ten pilot plus thirty main parents; see preregistrations B/C and RESEARCH-REVIEW-EXTENDED.md in the findings directory. `analyze-flow.py`/`analyze-repeat.py` produce parent-grouped diagnostics; `verify-extended-evidence.py` checks catalogs, ledgers, parent counts and original evidence. Four causal/ambiguity checks run with `test-research-analysis.py`. These extend the host; they do not instrument the native app or authorize training.

This tooling invokes the supplied, preserved Windows managed assemblies in a separately initialized CLR process. It does not modify binaries, attach to the running Unity apps, render charts or run bot training. Purchased binaries must be acquired separately. Evidence and limitations: [research handoff](../../docs/planning/windows-simulator-findings-2026-11-01/README.md).

Run from repository root. `-WorkspaceRoot` points to the parent folder containing `Krafer Agent Trader Sim`, not this Git repository. Use separate fresh PowerShell processes because both versions contain assemblies with the same identity. Choose a fresh output folder; completed manifests cannot be overwritten.

```powershell
pwsh -NoProfile -File research/simulator_mechanics/tools/run-original-host.ps1 -Version 04 -WorkspaceRoot .. -OutputDirectory results/simulator_research/reproduction/evidence/original-host
pwsh -NoProfile -File research/simulator_mechanics/tools/run-original-host.ps1 -Version 05 -WorkspaceRoot .. -OutputDirectory results/simulator_research/reproduction/evidence/original-host
node research/simulator_mechanics/tools/analyze-host.cjs results/simulator_research/reproduction
```

Research profile: 200 agents, maker/request probability .1, activity/sweep .1, five sweeps/candle, 100 warmup candles, 34 observation candles, recorded System.Random seeds. These are research settings, not measured live scene defaults. Source behavior is preserved, including its defects. Native Unity constructors, graphics/audio, serialized scene parameters, chart retention and frame-time scheduler are bypassed. .NET 10.0.11 RNG results are not certified equal to Mono. No market-minute equivalence is assumed.

The host uses aggregate ordinary portfolio deltas to recover synchronous player fills and cash transfers. Data are for diagnostics, not a certified training dataset. The 18 extracted-method diagnostic fixtures additionally documented in the results were run locally with explicit UI/audio stubs; paid extracted code is intentionally not included.
