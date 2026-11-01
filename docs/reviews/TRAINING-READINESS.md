# Training readiness — independent review

Reviewer: Codex reviewer in the Mac coordination chat. Date: 1 November 2026.
Reviewed evidence commit: `5f32f154a2f13b8c6ceb898dab5736ee49db1f9a`.

## Decision

Ready for data-pipeline implementation and a revised model specification. Not yet ready to accept the current simulator outputs as trusted pretraining data, calibrate entry probabilities, or claim real BTC performance. A small real-data baseline can proceed once its own dataset and leakage checks pass; it need not wait for every simulator question to be solved. No training is started or authorized by this review.

## What was independently checked

Read the extended review, model handoff, completion audit, experiment report, numerical results and preregistration C. Inspected FlowHost.cs, RepeatHost.cs and analysis code. Ran test-research-analysis.py: four checks passed. This is not an independent full replay of the Windows DLL experiments.

Recomputed the fixed-rule scores from main-analysis/origins.jsonl.gz, selecting phase=main, group=all, book not null. There are 10,168 unique selected origins. Pattern-stratum copies were excluded.

| Rule | Accuracy |
|---|---:|
| Always up | 49.5771% |
| Always down | 48.9477% |
| Previous direction | 42.8698% |
| Reverse previous direction | 54.3371% |
| Book imbalance | 56.7172% |

Book minus reversal is 2.3801 percentage points, versus the reported 13.87-point parent-average comparison with momentum. These use different aggregation conventions; calculate the paired parent-level reversal comparison directly. Reversal is a post-hoc baseline suggested by this review and needs new independent confirmation. The current evidence supports further testing, not a calibrated probability.

## Material remaining gates

1. Native-host relationship: declared 200-agent CLR-host configuration is not a verified native scene configuration. Validate what can be validated and maintain explicit boundaries; native export is not mandatory for independently collected real data.
2. Label/ledger validity: reported intratrade OHLC, volume weighting, collateral, partial-fill and accounting defects prevent direct acceptance of uncorrected simulator labels. Use a supported corrected exporter or separately reviewed independent engine before synthetic pretraining.
3. Generalization: current principal studies use one profile. Freeze comparisons and test independent seeds, relevant liquidity/activity/maker profiles and unseen execution sizes. Parent-level dependence and post-hoc comparisons must remain explicit.
4. Entry labels: natural wall studies are unmatched and start before touch; ambiguous same-candle barriers cannot become wins. Ordered execution capture or explicit uncertainty bounds are needed for entry claims.
5. Real-market bridge: acquire and validate same-venue BTCUSDT perpetual candles/books/trades with causal cutoffs. Simulator time and units are not BTC minutes. Real-only versus synthetic-pretrained comparisons require identical untouched real holdouts.

## Coordination protocol

The user authorized this reviewer to push reviews/prompts and periodically review other agents' new commits. `NEXT-RESEARCH-PROMPT.md` is the actionable request. Keep a bounded closure loop: answer these gates with evidence or declare a path unavailable and choose the independent alternative. Do not endlessly repeat control guides, blocked capture attempts or cosmetic report updates.

The monitor compares exact commit hashes, not author names: both AIs may use the same Git identity. Reviewer commit messages start `reviewer:` and reviewer-created hashes are tracked locally outside Git to avoid self-triggering. Review new collaborator evidence only. Do not infer completion from prose alone; inspect code/raw records and relevant checks.

When evidence supports a specific training stage, publish a stage-specific readiness decision and stop monitoring as requested. Do not require proven live profitability before an exploratory baseline, and do not call real-data training ready merely because simulator mechanics research is extensive. Do not start training or place trades automatically.
