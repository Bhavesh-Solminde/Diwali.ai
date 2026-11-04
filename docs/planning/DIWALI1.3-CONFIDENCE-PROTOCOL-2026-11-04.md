# Diwali1.3: controlled confidence regularization

Freeze this comparison before fitting. Diwali1.2's selected midpoint correction slightly improved its unregularized matching control but worsened proper probability scores versus its unchanged parent. The279 >=60%-confidence claims were only49.10% correct. This motivates a training penalty against unsupported changes; it does not prove that the parent is correct or identify the underlying market cause.

Keep the complete1.2 data contract, midpoint-enabled residual architecture, raw frozen0.5 marginal parent and raw0.7 transition parent. Fit two otherwise identical branches: `confidence_control` (lambda0) and `parent_kl` (lambda1). Both use18,465 trainable parameters, same three seeds17/29/43, batch128,20 epochs maximum, patience4, AdamW0.0003, weight decay0.0001, gradient clip5. Keep the previous near-weighted26-bin cross entropy +0.25 colour cross entropy +1.0 final net-direction cross entropy.

The new term is lambda times [near-weighted KL(parent price distribution || corrected price distribution) + KL(parent final net direction || corrected final net direction)]. Sum over categories then average examples. Parent probabilities are detached, uncalibrated frozen neural outputs on the same available inputs. The penalty uses no additional labels, no future book/trades, and no fitted calibration temperatures. At zero correction it is zero. The new branch may still learn and may still be wrong; do not describe this penalty as preventing all overconfidence.

Select checkpoints using development final binary log loss, allowing epoch0. Select branch using three-seed mean development score, control breaks ties; fixedseed17. Save selection before calibration and benchmark access. Then apply the same1.2 calibration rules, once per completed pipeline: h1–14 range temperature; h15 binary loss through full26-bin temperature; colour separate,0.5..2 fixed grid. Include epoch0 with the same calibration as a baseline. Do not widen the grid or change strength after seeing results. Use the unchanged common marginal/joint evaluator and exact marginal-preserving coupling. Final-direction probabilities must remain sums of the displayed price bins.

Report all arms, all seed checkpoints, final log loss/Brier/accuracy/confidence counts, all15 marginal errors, joint errors, daily paired descriptive differences, and50–50/fit-frequency baselines. October is repeatedly inspected research data; it is not fresh confirmation. Current0.9/1.2 forward forecasts stay frozen and must not influence this fitting/selection. Do not relabel their outcomes as fresh for1.3. A new model needs its own subsequent pre-target confirmation. Keep raw data, weights and individual forecasts private.

Implementation reference: [PyTorch KL divergence](https://docs.pytorch.org/docs/2.15/generated/torch.nn.modules.loss.KLDivLoss.html), particularly log-space input and category sums / batch averaging. This reference supports the loss calculation, not a claim that it will improve BTC prediction.

## Completed experiment

Six fits completed in512.23seconds including evaluation. All three control checkpoints exactly reproduce1.2's midpoint-enabled checkpoints (same epochs and every parameter). The three-seed mean development final-direction log loss selected `parent_kl`:0.691604 versus0.691864. Seed17 bestepoch4 in both arms. Selection was saved before calibration and benchmark evaluation.

| Method | Final-direction log loss | Brier error | Direction accuracy | Mean15 range log loss | Joint log loss |
|---|---:|---:|---:|---:|---:|
| Control / Diwali1.2 |0.694900|0.250858|51.23%|2.811592|28.266297|
| Diwali1.3 parent penalty, selected |0.693765|0.250305|51.38%|2.810832|28.256479|
| Epoch0 parent, matching calibration |0.693158|0.250006|50.59%|2.809872|28.260550|

All rows use the same11,186 already-inspected October origins. The penalty improves the control's proper scores and joint score but still underperforms epoch0 on marginal price and final-direction probability scores. Always50–50 has final log loss0.693147/Brier0.25. No claim of a confirmed edge follows from51.38% accuracy; predictions overlap and the fit-majority baseline is separately retained in the report.

Claims >=60% dropped from279 to15; only6/15 of the remaining claims chose the correct side. There are no >=80% claims. Less excessive confidence is useful, but the residual's information is still weak and unstable across dates. The final calibration temperature remains0.615572, selected on calibration dates; it sharpens the distribution. Scores on those dates cannot serve as independent calibration evidence. See all partition scores and paired target-day differences in `results/diwali1.3/confidence-diagnostics.json`.

Decision: retain as a controlled improvement over1.2, not as a dependable replacement for the simpler probability reference. Do not retune this frozen version. Next research should test temporal stability of model/temperature selection across disjoint earlier blocks, without using current live outcomes to choose changes. Improving probability sharpness alone is not the objective; range and direction scores, reliability and future-issued confirmation must all be assessed. Perfect probability prediction remains unproven.

Verification:119 focused tests passed. Ten historical UI cases/150 horizons reproduce saved predictions on CPU within1.31e-7;30 joint-event queries are coherent. Recomputed raw parent logits agree within1.44e-6. Input/artifact/source hashes were verified. Historical answers are separate until Reveal and cannot change the frozen predictions. UI on port8753 includes an explicit actual-dot legend. No1.3 fresh forward accuracy is claimed: the ongoing0.9/1.2 test predates this checkpoint and stays untouched.
