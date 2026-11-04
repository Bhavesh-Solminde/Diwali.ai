# Diwali 0.8: preserve endpoint probabilities, improve their linkage

Protocol recorded before running the coefficient search or inspecting its benchmark.

0.5 has the strongest mean individual closing-range score so far; 0.7 improves the joint sequence score while weakening those individual scores. This experiment combines their frozen predictions. It fits one dependence coefficient, not new neural weights. Neither direction accuracy nor the individual closing-range probabilities can improve by construction.

## Fixed experiment

- Frozen parents: selected 0.5 marginal model and selected 0.7 sequence model, with checkpoint and report hashes. Same October inputs, targets and purged partitions; no new data or future inputs.
- Constrain adjacent predicted state pairs to the two predicted endpoint distributions. Scale the positive 0.7 transition kernel raised to gamma. This is matrix scaling, related to the algorithm described by [Cuturi (2013)](https://proceedings.neurips.cc/paper_files/paper/2013/file/af21d0c97db2e27e13572cbf59eb343d-Paper.pdf). It does not recover a uniquely true market dependence law.
- Fit gamma on 2,048 deterministic evenly spaced fit origins, from 0 to 2 in increments of 0.25, using joint log loss. Compare independent (gamma 0), unit dependence (gamma 1), and fitted dependence on all development origins; lowest development joint loss selects, declared order breaks ties.
- Save selection before benchmark evaluation. Evaluate all three on the full unchanged partitions. Preserve and publish negative results too.
- Solver tolerance: relative pair error 1e-8, maximum 2,000 iterations; nonconvergence stops the run. Maximum forward marginal difference 2e-7; saved predictions compared with 0.5 within 1e-6. Preflight at gamma 2 on 2,048 fit origins required at most 1,065 iterations and differed by approximately 1.01e-9.
- No new temperature fitting. Parent calibration remains embedded; their development/calibration usage means these outputs are not pure cross-fitted predictions. October's repeatedly inspected benchmark is not fresh confirmation.
- Compare joint log loss, individual range log loss, direction, and closing-time stay/visit probabilities. No intraminute path, executable entry, hidden liquidity, profitability or perfect-probability claim.

## Display plan and critique

Use the frontend-design skill. The reference asks for a future price cloud next to candles. Equal-height rows for unequal price bins obscure that relationship; replace the main chart with linearly price-aligned discrete probability columns while retaining the exact accessible table.

Palette: navy #121827 chart surface, lavender #c5b2e4 labels/accent, purple #8865c4 probability mass, teal #12b6a0 up candles, rose #df6a83 down candles, pale #d3deea axis text. System sans type, stable numeric widths, no decorative animation. Existing light dashboard remains quiet around the dark market chart.

Layout: past candles at left, a timestamped frozen-input boundary, then 15 future closing-time columns, all on one linear price axis. Label actual UTC closing times. Use responsive canvas with an accessible adjacent table. Reveal overlays the actual candles only after the explicit button action.

Review against brief: a smooth purple cloud would imply within-bin density we have not trained. Use discrete rectangles with their true price heights, colour by whole-bin probability, and explicitly identify open tails and view clipping. Do not interpolate candle paths, invent price points, or call each column an independent trade opportunity. Explain that the latest visible history is only the chart view; the model still receives the full 1,440-candle contract.

## Results

Completed in 175.46 seconds on MPS. The fit search chose gamma 1.0; unit and fitted variants therefore tied on development (28.901638 joint log loss), and declared order selected unit dependence. Independent development loss was 42.281347. Selection was saved before benchmark evaluation.

| Already-inspected October benchmark | Whole-sequence log loss | Mean closing-range log loss |
| --- | ---: | ---: |
| 0.5 independent product | 42.083419 | 2.805561 |
| 0.7 selected joint model | 28.074578 | 2.810822 |
| 0.8 selected coupling | 28.124498 | 2.805561 |

Lower is better. **0.8 is a tradeoff, not a universal improvement:** it restores 0.5's stronger individual ranges but loses about 0.04992 joint log-loss units against 0.7. The joint regression appears on all eight inspected days; the exploratory equal-day resampling comparison is in `results/diwali0.8/paired-comparison.json`. Do not select a different variant using these benchmark observations.

First-close bearish/neutral/bullish accuracy is 45.7089%, identical to 0.5. This is a three-class score, not a binary coin-flip comparison. No directional prediction reaches 60% confidence on this benchmark; there is no evidence for reliable 80–20 or 90–10 entries. Closing-time stay-event Brier errors are 0.060894 (5bp), 0.188717 (12bp), and 0.155350 (20bp), slightly better than 0.7 for these events. That does not establish target-before-stop behavior.

Why the remaining error: preserving 0.5's marginal distributions mathematically prevents this experiment from correcting their wrong directional calls. It changes dependence only. Predicted constraints also prevent retaining every 0.7 transition unchanged; the measured joint regression is consistent with that necessary tradeoff, not proof of a specific causal feature failure. Both parents retain the same limited input representation and already-inspected historical sample. A later version needs an actual input/encoder or training improvement to individual forecasts; more coupling searches cannot solve this limitation. Preserve 0.7 as the strongest historical joint scorer and 0.5/0.8 as the stronger marginal scorers.

## Verification and delivery

- All four partitions completed with identical origins; maximum forward marginal difference 1.73e-9. Maximum saved difference from 0.5, including floating-point device effects, 1.25e-8.
- Ten CPU replay cases / 150 horizons matched saved MPS probabilities within 9.68e-8. Thirty exact joint range queries passed; reveal probabilities match the precommitted predictions. Each Predict runs two neural parents; future actuals are absent from Predict and returned separately on Reveal.
- 96 Diwali and market-data tests pass. Broader repository test run: 106 passed, two unrelated legacy order-book benchmark tests fail because optional `einops` is absent. No claim of an entirely green repository suite.
- Desktop 1440px and mobile 390px browser checks passed with no JavaScript errors or page overflow. Before Predict there are zero forecast columns; after Predict there are 15; actual overlay remains absent until Reveal. Linear-price rectangles and readable axes visually inspected. Full exact bin table remains accessible for mobile/keyboard use.
- Native 0.5 live capture v2 finished normally: source-replay audit verified 229,084 messages, 38 forecasts and 477 matured horizon outcomes with zero recomputation difference. Twelve forecasts still have pending horizons at the fixed capture end; do not call all 38 paths complete. This is older-parent evidence, not prospective validation of 0.8.
- Replay at http://127.0.0.1:8748 (`python -m research.diwali.coupled_serve`). Predictions, inputs, weights and model definitions remain local. Only source and aggregate reports are published.

The full goal remains incomplete: perfect probabilities cannot be certified, high-confidence direction is unproven, and this checkpoint has no fresh prospective validation.
