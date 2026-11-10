# Forward readiness checks and per-forecast eligibility

The three checks are three complete input snapshots at consecutive prespecified minute cutoffs after the native warmup. They use the same input and inference path as the forecasts. A snapshot passes only when every required gate and every model output check passes.

“At least two of three” means at least two whole snapshots pass. It does not mean that two kinds of data quality may substitute for a third. Each issued forecast independently requires all of the following.

| Requirement | Enforcement |
|---|---|
| Strictly pre-cutoff messages and completed candles | Native input assembly and strict freeze |
| Valid starting order book and uninterrupted update sequence | Book replay, gap invalidation and event-window checks |
| Fresh book coverage throughout the last 60 seconds | Event-window staleness check |
| Valid completed-second trade reference | Causal candle tape snapshot |
| Required candle history | At least 99% valid out of 1,440, latest candle valid |
| Full probability output from all three frozen candidates | Shared input inference and probability checks |
| Timely forecast file | Durable write finishes before the first target minute starts |

An origin that fails a gate is skipped even after all readiness snapshots have passed. Regression checks exercise failed continuity, failed reference and failed cutoff eligibility after readiness success.

The release file establishes the actual UTC start and stop after readiness. November 12 at 05:30 IST remains conditional on readiness. The 300 matched outcomes across seven days requirement measures coverage. The ten-day window may still produce an inconclusive difference.

Operational monitoring reports receiver health, source continuity, issued forecasts, skips, pending outcomes and independently verified outcomes. Candidate selection remains tied to the frozen final scoring. The operational monitor does not read model accuracy or interim score metrics.
