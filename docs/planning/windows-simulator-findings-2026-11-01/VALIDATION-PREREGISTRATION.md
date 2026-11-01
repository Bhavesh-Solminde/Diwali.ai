# Bounded validation protocol — 1 November 2026

Registered after reproducing the post-hoc reversal audit, before the following fresh-seed runs. Preserve all previous conclusions as exploratory; do not relabel them confirmatory. No model fitting, replacement engine, vendor patches, historical-label repairs or live orders.

## Profiles and fixed sample budget

Three research-host profiles, not verified native settings:

| Profile | Agents | Activity per agent/sweep | Maker probability per request |
|---|---:|---:|---:|
| standard | 200 | 0.10 | 0.10 |
| sparse | 100 | 0.05 | 0.10 |
| maker30 | 200 | 0.10 | 0.30 |

Sparse varies both agent count and activity and therefore tests a joint liquidity profile, not their isolated effects. Start raw price 10000, five sweeps/base candle, random removal .1/candle and default v0.4 pruning. Ordinary v0.5 seeded initialization retains existing cash/coin ranges. Keep these settings fixed; no search or extra profiles after results. Use original DLL methods in separate fresh CLR processes per version. Native scene count, RNG, timing and settings remain unmatched.

v0.4: 60 independent parent seeds per profile: standard 51000–51059, sparse 52000–52059, maker30 53000–53059. All untouched; 100 warmup+500 observation candles. Prior pilot SD of parent book-minus-reversal is0.0496. A 2 pp effect with Bonferroni-adjusted three-comparison two-sided z≈2.394 and 80% power z≈0.842 gives n≈65; budget 60/profile is near that planning target, not certified power. Report uncertainty rather than guarantee detection. No interim stopping based on effect. All attempted parents retained; unhandled/numerical failures stop affected profile and are reported, not replaced.

v0.5: 40 independent parents/profile: standard 61000–61039, sparse 62000–62039, maker30 63000–63039. Four primary schedule contrasts: standard/sparse × intended size0.5/2.0 times initial opposite-side depth within10 bp, separately for buy/sell, yielding EIGHT primary contrasts; maker30 is a prespecified additional sensitivity profile with four more, so TWELVE primary contrasts total. Familywise alpha .05 via individual two-sided alpha .05/12 intervals. Existing paired-slippage SD≈10–12 bp, a 10 bp difference and z≈2.865+0.842 gives n≈20; 40/profile allows some variability but not guaranteed power at smaller effects. No result-driven expansion.

For each profile/parent, untouched baseline plus buy/sell ×0.5/2×one/five slices:9 scenarios.100 warmup and50 followup base candles. At warmup define total intended quantity=max(5,5*ceil(ratio*initial opposite10 bp depth/5)), recording rounding. If depth unavailable/zero, mark that condition unavailable; do not invent a ratio. Reinitialize each condition from the same seed; validate warmup fingerprints. Siblings correlated and paired. One-shot at origin; five equal slices at 0/5/10/15/20. No trade after final slice and no unwind. Preserve partial/zero fills and exceptions. Record exact aggregate cash/coin transfers, VWAP, depth ratio, arrival and achieved quantities.

## Frozen direction rules and exclusions

At each v0.4 completed boundary c =100..569, use the current post-pruning/removal book and completed candles only. Require both valid best sides and best bid < best ask; exclude absent/locked/crossed origins and count them. Depth windows use last trade as anchor: bid prices<=last within10 bp, ask>=last within10 bp; missing total depth excludes origin from ALL rules' common grid. Exactly one record/run/candle, no pattern-stratum duplication.

Actual next-close direction is ±1 bp neutral. Momentum=previous completed close movement, same neutral band. Reversal=-momentum, preserving neutral. Book=sign(imbalance) with cutoff ±0.2, neutral inside. Alwaysup/down and neutral reported. Majority baseline is the UP class frozen from the previous ten-pilot eligible labels (1652 up,1644 down,41 neutral); no selection from fresh tests.

Primary v0.4 endpoint:equal-parent mean(book accuracy−reversal accuracy), separately for3profiles. Resample parent IDs 10000 times, fixed 617. Bonferroni individual98.333%intervals (alpha .05/3) plus ordinary95%descriptive intervals. Report weighted accuracy, balanced accuracy, per-class recall, class counts, predicted-class counts and coverage over candidate origins. Confirm positive effect only if adjusted interval excludes0; no global simulator-to-BTC claim. Momentum, constant rules and volume strata are secondary descriptive comparisons.

Primary v0.5 endpoint:paired total execution slippage difference(five−one) relative to ORIGINAL arrival, for each of12profile/side/size comparisons; negative favors slices. Report achieved quantity, partial fills, all attempted scenarios and failures. A primary cost contrast is interpretable only when both schedules achieve the intended total; report incomplete pairs separately, not as wins. Alpha .05/12 per contrast. All followups have common origin deadlines+1/+5/+15/+30/+50, with additional final-fill horizons. Cash/coin ledgers must reconcile; source display PnL/volume/OHLC are not ground truth. Time exposure, no modeled fees/funding and unpriced opportunity cost explicitly disclosed.

## Wall trigger and ambiguity, secondary validation

Use fresh v0.4 boundary arrays. At first eligible origin per parent/side/strength, define strong>=trailing100-boundary90th percentile positive quantity, weak<=median, persistence>=5 boundaries, distance strictly>0 and<=10 bp from last trade, valid uncrossed book. Record trailing100close-return SD, current volume/past100median ratio, side and distance. Freeze the LEVEL before the event; no future wall selection.

Trigger during the next15 completed candles if the candle's traded high-low spans the frozen level. Use earliest such candle, with entry reference at the level. This is a **touch-trigger proxy**, not proof of an executable passive fill. Preserve untriggered cases. The trigger candle's high/low can include prints BEFORE touch; without ordered executions, mark trigger-candle target/stop ordering unknown. For a conservative sensitivity, begin scoring at the first complete candle AFTER the trigger and label the different policy. Target/stop±10 bp from level, horizon30 candles after touch; preserve timeout and both-in-one-candle ambiguity. Require c<=554 for15 trigger+30 outcome candles. Record definite favorable/adverse hits only where temporal ordering is known. Success-probability bounds:known wins/n_triggered to(known wins+ambiguous)/n_triggered; untriggered and signalcoverage separate. No 80% claim.

Match strong/weak without outcomes, within profile and side, no reuse, different parents allowed. Calipers:distance difference<=2 bp, volatility ratio0.8–1.25, volume-ratio difference<=0.25. Deterministic greedy order by strong run ID; minimize standardized squared covariate distance. Report unmatched cases, balance before/after and matched-parent dependence. Because matching can join two parents, resample connected components of the parent matching graph for paired outcome differences; small component counts imply inconclusive intervals. If ordered executions unavailable, bounds/ambiguity prevent calibration regardless of sample size.

## Native check, real-data bridge and stop

One fresh native window selection/activation attempt, with at most the skill-mandated recovery if needed. Do not repeatedly retry equivalent access failures. No matched native/host numeric comparison without equivalent state/RNG. Existing control sequence is behavioral evidence only.

Probe public BinanceUSD-M BTCUSDT endpoints and current official documentation; if feasible record a bounded5-minute raw depth/trade engineering sample with local receipt times, REST snapshot and closed1m exchange klines. No keys or trades. Sequence gaps invalidate book segments; aggregation/missing executions limit candle reconstruction. Record concrete blockers once, no geographical/access bypass or alternate-venue substitution. Long-term90day collection requires durable infrastructure beyond this engineering sample. Stop after the fixed experiments/report, before training. Decide A–E separately.
