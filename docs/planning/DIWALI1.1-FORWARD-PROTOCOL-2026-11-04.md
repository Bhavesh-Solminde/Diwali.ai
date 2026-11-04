# Fixed prospective smoke protocol for0.9 versus1.1

Native receiver: `prospective-diwali05-20261104-v3`, one-hour budget. It preserves received messages and causal input freezes, and also saves its existing0.5 forecasts. Do not confuse those0.5 forecasts with1.1 forecasts.

After1.1's development selection and report are frozen, start two candidate followers on this same receiver: selected0.9 and selected1.1. Each accepts only snapshots frozen after its own startup, issues for600seconds, then drains already-issued15-target forecasts for up to17minutes. Every forecast must be durably committed before its first target begins. No future observations enter inference; labels are scored later. No orders are placed and followers add no feed connections. Require sufficient remaining receiver budget; do not restart or silently substitute another receiver if it fails.

Freeze checkpoints, calibration, reports, preprocessing and predictor dependencies by hashes. Replay the native receipt journal to verify every copied freeze; recompute each prediction and final-direction claim. Verify both UTC and monotonic chronology, target/reference matching, raw manifest/prefix integrity and then-available labels. Reject a missed deadline rather than scoring a late forecast.

Only compare origins shared by both followers with all15 outcomes matured and verified through the common audited source boundary. Report total committed, completed and matched counts separately. Main comparison: final binary log loss/Brier/accuracy and confidence counts; also mean price-range loss and joint loss. Include50–50 loss. Use `research.diwali.compare_candidates` after source audits. Do not treat15 horizons from one origin as15 independent forecasts, or this one session as a calibration study.

Do not change or retune these frozen models in response to partial outcomes. Once inspected, this session is not fresh evidence for a subsequently changed model. All raw recordings, inputs, forecasts and individual outcomes remain private; publish aggregate evidence only. A pending process/status file alone is not proof of completed evaluation.

## Completed comparison

Both followers stopped normally with zero pending paths. Nine forecasts per model matched on the same input freezes; all135horizon outcomes per model were verified from then-received native messages. Each forecast was committed before its target; CPU recomputation exactly matches saved distributions. After both followers finished, the helper receiver was closed cleanly before its one-hour maximum budget and both candidate audits rerun against its completed raw-file manifest. The final audits verify complete source/follower manifests, not just growing prefixes. Later native0.5helper forecasts still have pending horizons and are outside this candidate comparison; do not call every helper forecast complete.

| Nine matched origins | 0.9 | 1.1 |
| --- | ---: | ---: |
| Final direction correct | 5/9 | 7/9 |
| Final binary log loss | 0.689402 | 0.634568 |
| Final Brier error | 0.248128 | 0.220884 |
| Mean15range log loss | 2.683121 | 2.646420 |
| Joint log loss | 32.487988 | 32.204463 |

Lower losses are better. **Every final outcome was up.** These9overlapping origins come from one short upward session; they do not test performance across both directions, news regimes or independent days. A constant-up decision would also be correct on all9, descriptively; do not confuse that hindsight observation with a validated trading rule. Neither model claimed60% confidence on any of these final-direction predictions.1.1's mean up claim was53.14%,0.9's50.21%.

This is encouraging for1.1within this session but does not override its weaker historical probability quality or justify promotion over0.9. The one-session comparison has now been inspected and is not fresh confirmation for a later version. Final aggregate comparison and audits are in `results/diwali1.1/matched-forward-comparison.json` and the two `*-final-forward-audit.json` files.
