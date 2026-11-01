# Current-PC continuation review — 1 November 2026

Subsequent progress supersedes this initial access audit: the user authorized direct capture; both builds now have live functional observations. See CONTROLS-CURRENT-PC.md and LIVE-CONTROL-RESULTS-CURRENT-PC.md. v0.4 was closed after its measured position pass; v0.5 is paused/flat after accumulation/unwind and supply checks. The manual-capture blocker described below no longer applies.

Reviewed the repository Markdown documents using filesystem access, including the frozen specification, training protocol, source and visual ledgers, both operating guides, experiment evidence, continuation/audit notes, prototype and benchmark documentation, and transfer README. Dependency/vendor Markdown is outside this project-document review. Referenced web pages and videos were not newly reviewed; their coverage remains inherited and sampled.

## Fresh verification

Ran `research/simulator_mechanics/tools/audit-evidence.py` with the existing project Python environment. No dependency installation, training, new market simulation or binary modification was performed.

- All six research CSV SHA-256 values match the existing evidence manifest.
- Both extracted executables, both Assembly-CSharp assemblies and both UnityPlayer DLLs match the existing manifest (six checks).
- v0.4: 120 unique scenarios, 40 parent states including 30 main, 4,200 candle rows.
- v0.5: 600 unique scenarios, 40 parent states including 30 main, 21,000 candle rows.
- Every scenario has status `ok`, a matching recorded warmup fingerprint and 35 observations. These checks verify transferred evidence integrity, not a fresh replication or scientific validity.

The current v0.4 Player.log identifies Unity 6000.0.16f1, Direct3D 11.0, Intel Iris Xe, reported VRAM 3967 MB and driver 32.0.101.7088. This is log-reported graphics information, not measured available GPU memory. The older RTX 3060 environment belongs to the previous research machine. Do not inherit its hardware assumptions.

Fresh process inspection found only v0.4 running (PID 10508). Computer Use selected its unique returned window and read accessibility with screenshots disabled. The tree exposes only the title bar and window controls; position, price, chart, pause and PnL are unavailable. No simulator input was sent. No automatic capture was attempted.

## v0.4 first: remaining completion evidence

The v0.4 research is still open. Keep its current session until its observations and log are preserved. Do not close it merely because the numerical host experiments are complete.

1. Obtain a current manual screenshot. Older $10.89/Short observations came from a different session and cannot establish this session's state.
2. Establish pause using two manual screenshots separated by several seconds. Compare last price, newest candle, depth and PnL; stable price alone is insufficient. Send Space only after establishing whether a toggle is needed, and verify the outcome.
3. Verify one action at a time: flat-to-long, repeated buy while long, long-to-flat, flat-to-short, repeated sell while short, short-to-flat. Preserve before/after observations and record whether actions work while paused. Expected mappings are in OPERATING-GUIDE-v04.md; they are predictions until observed.
4. Verify historical/current order bars, pan/zoom and MA toggles. Exact depth cannot be inferred from saturated opacity or normalized bar width. Scene capacity and candle timing remain unmeasured.
5. Record prospective persistent-depth approaches and failures. A screenshot cannot distinguish execution, random removal and pruning. Event-level cancellation/absorption and pattern-versus-book comparisons remain unavailable without suitable instrumentation; do not manufacture numerical probabilities.
6. Update the operating guide and completion audit from actual observations. Preserve the current log before closing v0.4 and starting v0.5, since both builds share the same application log location.

## Queued v0.5 work

After the v0.4 session is finished and closed: establish the initial position, lot and portfolio panels; verify single buy, repeated buy, opposite-side reduction and return to flat. Record immediate displays and the next completed base candle, because statistics can lag. Use intended quantity, achieved quantity and cash transfers separately. Display PnL, volume and position counters have documented defects and cannot independently establish trade profitability. Keep I and snapshot/replay controls untouched during controlled observations.

The original DLL-host results already cover depth-relative impact, slicing, aftermath and round trips. Repeating them does not complete live UI testing. v0.5 has not been launched during this continuation, preserving the requested version order.

## Current blocker and model consequence

Live work needs a current user-supplied v0.4 screenshot under the inherited manual screenshot workflow in CONTINUE-ON-WINDOWS-11.md. The browser URL-policy failure from the previous attempt is separate; native simulator accessibility succeeded but exposes no research fields. Code access resolves document/evidence access, not the missing chart observation.

The proposed v1.1 model handoff remains a proposal. No new model training starts here. Both vendors' display/label defects still require an independent event ledger and validated matching/accounting before synthetic training data can be accepted.
