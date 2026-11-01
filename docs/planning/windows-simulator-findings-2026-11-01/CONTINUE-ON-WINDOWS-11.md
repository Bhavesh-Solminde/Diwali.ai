# Continue the simulator research on Windows 11

**Superseding current-PC update:** the user explicitly requested direct Computer Use on Windows 11 instead of the inherited manual workflow. Foreground screenshots now work for both builds. Read CONTROLS-CURRENT-PC.md and LIVE-CONTROL-RESULTS-CURRENT-PC.md first. v0.4 was tested and closed after preserving its log; v0.5 live control/supply checks were performed and it is left paused/flat. The manual-only instruction and no-v0.5-interaction statements below describe the older handoff and no longer apply to this session. Event-level research remains incomplete.

This is the current continuation handoff, written 1 November 2026. Research is **incomplete**. The user requested pushing all research so work can continue on another PC. No new model training has started. Read this file before older access-status notes.

## Start here

1. Pull this repository's `main` branch. Read this directory's README, USER-ASSISTED-v04.md, COMPLETION-AUDIT.md, both operating guides, EXPERIMENT-REPORT.md, NUMERICAL-RESULTS.md and MODEL-HANDOFF-v1.1.md. Also read the original WINDOWS-AI-PROMPT.md and frozen model/training protocols in the parent planning directory. The proposed v1.1 model plan still needs review before training.
2. The user subsequently authorized uploading the original simulator ZIPs. They are now under `Krafer Agent Trader Sim/`; extract the appropriate Windows ZIPs on the new PC. Purchased source/decompilation, downloaded tooling and full source transcripts remain outside Git. Do not assume the previous PC's absolute paths, handles, processes, settings or simulation state exist here.
3. Use Computer Use window enumeration and accessibility with `include_screenshot: false`. Select the unique intended simulator from fresh returned windows. Read the installed Computer Use skill before input.
4. **Keep the user's manual screenshot workflow on the new PC unless they explicitly change it. Never call automatic screenshot capture, retry capture, troubleshoot/reinstall the runtime, or assume Windows 11 fixes it.** Ask the user to capture/upload a screenshot whenever visual state is needed. They use Win+Shift+S themselves; do not automate that shortcut. Inspect the upload, perform one supported keyboard/accessibility action, then verify using accessibility or another uploaded screenshot. Do not assume a successful input API means the simulator changed.
5. Prioritize the remaining simulator research. Do not substitute more DLL-host experiments for missing live tests. Do not start training or real exchange trading.

## Where the live session stopped

The last screenshot on the Windows 10 PC (desktop clock 18:58) showed v0.4 **Short**, last price **$10.89**, floating **-1.75**, total PnL **0.13**. Previous flat total was **1.88**, so displayed total reconciles as 1.88 - 1.75 = 0.13. The assistant then sent **Space once** to request pause. **No screenshot verified pause.** No further simulator input was sent after that request. On another PC, obtain a fresh screenshot and establish state from scratch.

Verified live sequence, with user-uploaded images: an initial blank position/zero PnL; user-assisted Long; assistant `s` once from Long followed by Flat/zero floating/total 1.88; assistant `s` once from Flat followed by Short/-1.75 floating/0.13 total. Historical order-bar overlay is visibly present in v0.4. Images and action limitations are in USER-ASSISTED-v04.md and the results evidence directory. Markets advanced between screenshots; exact entries/exits, price impact, scene quantities and fees were not measured. There was no verified assistant live interaction with v0.5.

## Next measured work

- Establish paused state using two manual screenshots several seconds apart, comparing latest candle, last price, depth and PnL. If not stable, reassess rather than toggling blindly.
- Finish v0.4 state transitions and repeated same-side behavior. Test whether trade shortcuts respond while paused, using the operating guide's actual v0.4 code behavior; do not assume v0.5 behavior applies. Use one action and one verification at a time. Reconcile displayed realized + floating total while respecting raw price/PnL unit differences.
- Validate order-bar visibility, current versus historical depth, chart controls and price/volume units. Track visible persistent depth before price approaches, survives, executes or disappears. Document that screenshots alone cannot distinguish cancellation from execution without an event ledger. Do not claim predictive wall probabilities from a few selected charts.
- On v0.5, establish initial panel/position/lot settings, then verify repeated accumulation, opposite-side reduction, impact/slippage and PnL/portfolio panels. Stats update at completed base candles, so compare immediate action results and the next completed candle. Test partial/zero fills only with a deliberate documented setup. Avoid holding I (cash injection) and avoid backup/restore shortcuts until the documented exception and state limitations are considered.
- Complete the preregistered persistent-wall, absorption/replenishment and pattern-versus-book research where measurable. If the simulator lacks necessary export/instrumentation, document the exact missing evidence and propose a scoped replacement for user review. No arbitrary screenshot count establishes completion.
- Update the audit, numerical/report limitations and revised ML plan. Present the revised plan before fitting. Keep diagnostic host evidence, live observations and real-market evidence separate.

## Existing numerical work: do not redo without a reason

720 original-DLL host scenario identities (120 v0.4, 600 v0.5), 25,200 candle rows, ten pilot plus thirty main parents per version. Sibling scenarios are correlated, not independent replications. Six CSVs reproduced byte-identically in fresh processes. Eighteen local extracted-method diagnostics used explicit UI/audio stubs. These are configured CLR experiments, not native Unity runs or BTC-minute observations. Research profile and reproducible original host/analysis tools are included. Purchased extracted fixture source is intentionally excluded.

Mechanism findings include v0.4 strict crossing at equality, bad aggregate counters and large-level removal immunity; v0.5 size-dependent impact, FIFO consumption, missing collateral reservation, negative ordinary balances, quantity-defective player PnL, partial-fill position overstatement, player volume weighting, missing intratrade extrema and broken/incomplete snapshots. Review the reports for exact denominators, confidence intervals and conditions. Do not train on uncorrected simulator displays or built-in bot vectors.

## Transfer contents and limits

Git contains reports, operating guides, proposed ML handoff, original research host/analysis tooling, numeric evidence, manifests, verification results and the five user-uploaded simulator screenshots. Screenshots include ordinary desktop UI around the simulator. Following the user's explicit archive-upload request, Git also contains the five original simulator ZIPs under `Krafer Agent Trader Sim/` and a Markdown bundle under `transfer/`. See `transfer/SHA256.json` for archive hashes. Paid decompiled source, full video transcripts, local registry preferences, app logs, downloaded decompiler dependencies, duplicate rerun CSVs, credentials and model weights remain excluded. Earlier statements that simulator ZIPs were excluded describe the preceding research-only push.

Historical log/status entries describe earlier points in time. The manual-workflow evidence supersedes statements that no assistant Buy/Sell was ever performed or that automated capture must be restored before any live work is possible. Overall research remains open even though this transfer is complete.
