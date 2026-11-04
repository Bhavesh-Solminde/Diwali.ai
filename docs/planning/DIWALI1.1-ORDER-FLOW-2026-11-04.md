# Diwali1.1: test a direct book/trade sequence correction

Protocol recorded before training.1.0's extra final-direction objective did not generalize. Its new branch saw candles only; the book/trade representation was frozen.1.1 tests a new branch over those market-flow features, rather than another candle-only correction.

Two parameter-matched branches take60seconds×92channels (87book,5trade). The sequence variant preserves their order; the mean control repeats the same92channel means60times. GRU hidden size24,15×26 range and3colour heads, initially zero output. Existing0.9 parent remains frozen. This is not raw order-by-order data: one-second aggregation, top20book levels and omitted subsecond activity remain limitations.0.5 already has a learned flow encoder; this tests a new direct representation, not adding flow for the first time.

Both arms use the same loss: near-weighted range cross entropy plus0.25colour cross entropy plus1.0 final net-direction cross entropy aggregated from price-bin probabilities. Same fit/dev/calibration/inspected benchmark and data hashes as0.9/1.0. Seeds17/29/43,20epoch maximum, patience4, batch128, AdamW0.0003, weight decay0.0001, clip5. Epoch0 parent is eligible. Select by three-seed mean development final binary log loss; deploy fixedseed17; mean-control wins exact ties. Freeze before calibration/benchmark.

Calibration and joint evaluation match1.0: h1–14range temperatures, h15full-histogram temperature minimizing binary endpoint loss, colour separately; same bounded grid and fixed unit coupling to0.7. Parent calibration already reused. Target remains final15th close above reference versus at-or-below, not an intraminute path or an entry event.

Report accuracy, binary log loss/Brier/calibration/high-confidence counts, range/joint scores, and fit-frequency/50–50 baselines. Never force a one-sided distribution or repaint using actual candles. The benchmark has been inspected many times; historical improvement does not establish fresh generalization. Keep private data and weights local; publish source and aggregate evidence. Run source must be frozen before training.

## Result

Finished in339.79seconds. Mean-control development final binary loss across three seeds:0.692696; flow sequence:0.694182; epoch-zero0.9 parent:0.694287. The mean-control selection was saved before calibration/benchmark. Its selected seed17 chose epoch4; other mean seeds chose6and13. Temporal-sequence seeds chose3,0,2. Each branch has18,321 trainable parameters. The development result does not support the hypothesis that extra time detail helps this representation.

| Already-inspected October benchmark | Final binary log loss | Final accuracy | Mean range loss | Joint loss |
| --- | ---: | ---: | ---: | ---: |
| 0.9 parent | 0.693088 | 50.4202% | 2.805340 | 28.113849 |
| 1.1 selected mean control | 0.695152 | 51.0549% | 2.809358 | 28.207323 |
| 1.1 sequence comparison | 0.693174 | 51.2605% | 2.805861 | 28.131253 |

Lower loss is better. Constant50–50 binary log loss is0.693147; fit-frequency loss is0.693326. **The selected candidate regresses on probability quality, range error and joint error.** Do not adopt it over0.9 or change the frozen selection to the sequence arm using this benchmark. Higher accuracy is insufficient when probability errors worsen.

Of338selected-model forecasts claiming at least60% confidence, only54.7337% were correct. None reached70%. In the upward60–70% bin,252examples averaged61.6364% predicted up but only50.3968% actually rose. This is overconfidence, not an80–20edge. Joint loss worsens on all eight benchmark days; final binary loss worsens on six. See aggregate paired-day results. Correlated origins and reuse of the same development/benchmark periods prevent a fresh significance claim.

The observed development improvement did not carry into the benchmark. That is evidence of limited generalization, not proof of one uniquely missing market variable. Direct flow access helped development, but temporal order did not. Future work should prioritize independent validation and representation/data quality rather than increasing confidence or repeatedly optimizing the inspected October sample.

## Verification and live follow-up

109focused model/data tests pass. Ten CPU replay origins/150horizons match saved predictions within1.18e-7;30joint range queries passed. Overall direction equals sums from the same price cloud. Desktop1440px/mobile390px checks passed; actuals remain absent until Reveal, and Reveal does not change direction probabilities. Training source/dependency and parent-data hashes remain unchanged.

Research replay: http://127.0.0.1:8751 (`python -m research.diwali.flow_serve`). It is an experimental view, not a recommendation to replace0.9.

The [fixed forward protocol](DIWALI1.1-FORWARD-PROTOCOL-2026-11-04.md) is running0.9 and1.1 on identical new received snapshots. Initial bounded audit recomputed two forecasts per model with zero probability difference and at least44.54seconds of pre-target lead. No complete15-close paths had matured at that audit. This verifies forecast timing and computation only, not accuracy. Followers issue for10minutes and then wait for already-issued labels; their completion must be checked later. Do not claim pending paths are tested or tune from partial outcomes.

Raw messages, individual forecasts/outcomes, caches and weights remain private. Only source and aggregate evidence are published. Full goal remains active; direction and perfect-probability requirements remain unfulfilled.

Update: the [prospective comparison](DIWALI1.1-FORWARD-PROTOCOL-2026-11-04.md#completed-comparison) has completed with9matched fully matured paths per model.1.1scored better in this one upward session, but all9final outcomes were up and the forecasts overlap. It is not a multi-regime reliability result and does not resolve the benchmark regression. Initial `prospective-prefix-audits.json` is preserved as an in-progress historical record; the final audit/comparison files supersede its pending status.
