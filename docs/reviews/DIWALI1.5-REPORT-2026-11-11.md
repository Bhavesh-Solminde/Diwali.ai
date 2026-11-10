# Diwali 1.5 development comparison

The original Diwali 1.4 configuration won the primary score across the three August development periods. All 39 runs finished, and the saved forecast audit passed. The result retains the original model for the fresh comparison. Its unchanged full-August checkpoint, input transforms and calibration are identified by hash in [the selection record](../../results/diwali1.5/selected-artifact.json).

| Configuration | Range log loss, raw → calibrated | Final direction log loss, raw → calibrated | Calibrated Brier | Calibrated AUC |
|---|---:|---:|---:|---:|
| A · original | 2.797535 → **2.791701** | .691799 → .691911 | .249382 | .500567 |
| A · lower learning rate | 2.798925 → 2.793019 | .694703 → .695131 | .250986 | .495383 |
| B · direction weight .25 | 2.798228 → 2.791829 | .692476 → .692304 | .249577 | .497624 |
| B · direction weight 1 | 2.804294 → 2.797593 | .691022 → .690070 | .248473 | .508876 |
| C · candle attention | 2.849002 → 2.832951 | .682150 → .685756 | .246311 | .535780 |
| C · candle attention, lower learning rate | 2.813773 → 2.804723 | .687049 → .687980 | .247428 | .542955 |
| D · direct binary logistic | — | 1.170928 → .796826 | .288248 | .440807 |
| Volatility histogram | 2.841790 calibrated | .682562 calibrated | — | — |
| Fixed frequency histogram | 3.008487 calibrated | .687185 calibrated | — | — |
| 50–50 | — | .693147 | .250000 | .500000 |

Range log loss measures the probability assigned to the price bin that occurred, averaged across all 15 closes. Direction compares close 15 to the frozen price reference. Lower log loss and Brier are better. AUC measures ranking, with .5 representing chance. Each fold receives equal weight, and the two neural seeds are averaged equally within each fold.

The stronger direction penalty improved final direction log loss by .001841 versus A but worsened range loss by .005892. The best attention range setting beat A in the first and last periods and lost more in the middle period. The other attention setting had the best raw neural direction score. The calibrated attention score remained .003194 behind calibrated volatility. D lost to 50–50 in all three periods despite an average threshold accuracy of 53.8%.

| Calibrated range loss | Aug 16–18 | Aug 24–26 | Aug 29–31 |
|---|---:|---:|---:|
| A · original | 2.577083 | 2.867590 | 2.930430 |
| B · direction weight .25 | 2.579357 | 2.868695 | 2.927436 |
| C · candle attention, lower learning rate | 2.572850 | 2.949440 | 2.891881 |

The 5,391 available inputs are the complete prepared August cohort. The three fits use 1,638, 3,314 and 4,917 examples respectively. Each configuration scores the same 896, 249 and 200 later examples in those periods. Fold C used temperature 1 for every candidate because its 25 calibration examples fell below the predeclared minimum. The full report retains raw and calibrated scores by horizon and period.

The audit recomputed the reported metrics with zero discrepancy, checked all 39 runs and repeated sampled neural inference from the saved checkpoints. The maximum difference between saved and recomputed neural probabilities was 2.23 × 10⁻⁷. A reproduced the original checkpoint epochs and range scores in all six runs.

These are development results. The selected setup beat volatility on August range error by .050089. In the already consumed September 15–29 evaluation, the same model family lost to volatility on range error. The fresh test remains pending and requires verified live inputs, a frozen issuance window, and forecasts saved before the market outcomes. The reused model was fitted on 5,391 August examples, selected on 862 September 1–7 examples and calibrated on 1,476 September 8–14 examples.

[Full scores](../../results/diwali1.5/development-report.json) · [Artifact audit](../../results/diwali1.5/artifact-audit.json) · [Forward evaluation protocol draft](../planning/DIWALI1.5-FORWARD-EVALUATION-DRAFT-2026-11-11.md)
