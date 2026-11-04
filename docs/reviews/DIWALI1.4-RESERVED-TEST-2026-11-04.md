# Diwali 1.4 reserved-test result

**Training and the one-use reserved September 15–29 test are complete. Diwali 1.4 does not establish a useful up/down forecasting advantage.** Its price-range error beats three baselines but loses to the volatility-conditioned frequency baseline. Keep this model as a documented experiment; do not promote it as a reliable trading signal.

## Same examples, frozen models

The selected one-second temporal convolution was trained on August, selected on September 1–7 and calibrated on September 8–14. Its weights, transformations, calibration and all four baseline artifacts were frozen before the reserved test. All five methods score the same 20,004 passing origins, across 15 calendar days, with 15 future closing-price distributions per origin. Lower probability error is better.

| Method | Mean 15-close range log loss | Final-close up/down log loss | Final-close Brier error | Final-close direction accuracy |
|---|---:|---:|---:|---:|
| diwali1.4 | 2.881076 | 0.694003 | 0.250428 | 49.54% |
| fit_histogram | 2.984478 | 0.696905 | 0.251874 | 49.54% |
| fit_volatility_histogram | 2.870450 | 0.696462 | 0.251653 | 49.54% |
| flow_logistic | 3.096418 | 0.696140 | 0.251072 | 51.26% |
| flow_boosted_trees | 2.908308 | 0.705288 | 0.255900 | 50.09% |

A constant 50–50 direction probability has log loss 0.693147 and Brier error 0.25. Diwali 1.4's 0.694003 and 0.250428 are slightly worse. Its 49.54% accuracy is not a trading win rate. The observed final-close up fraction is 50.46%, while this model always favours down or unchanged. A retrospectively chosen majority side would not be a valid prespecified baseline.

The model beats the unconditional histogram, logistic and trees on range log loss on each of the 15 days. It beats the volatility-conditioned histogram on only five days and loses by 0.010626 overall. These daily comparisons are descriptive, not significance or independence claims.

## Specific failure: weak direction stuck on one side

Across all 20,004 origins the final up probability ranges from 46.62% to 49.96%, averaging 48.35%. It never favours up and never issues a final-direction confidence at or above 60%. First- and fifth-close probabilities also always favour down or unchanged. This is not an 80–20 or 90–10 entry predictor.

Forecast probabilities are not numerically identical: the failure is that their directional variation is too weak to switch sides on this interval. The volatility-frequency baseline also always favours down here. That does not excuse the neural result; it makes the direct 50–50 comparison particularly important.

The retained development-score decomposition separately showed that better placement of price magnitude within each side can conceal weaker direction learning in the total 26-bin objective. It is a measured error-accounting result, not proof of a causal feature failure or a guarantee that adding a loss term fixes direction.

## Quality coverage and audit

21,600 candidate minute origins were considered. Input gates retained 20,401 and rejected 1,199: 422 had no valid pre-window seed, 456 crossed invalid/gap markers, 52 had stale books, seven had insufficient candle context, and 262 lacked a fresh reference. Of the retained contexts, 383 lacked good complete targets and 14 extended past the source boundary. The final 20,004 passing origins are 92.61% of all candidate times. Masks across overlapping input histories account for 49,502 context-minute positions; that is not a count of distinct missing market minutes.

The separate content audit completed before model scoring. A post-score artifact audit verifies the completed one-use claim, unchanged release sources/artifacts, all five saved forecast identities and probability sums, every reported overall/daily metric and paired comparison. Recomputed metric differences are exactly zero. Input and target rejection ledgers reconcile. This is verification of existing forecasts, not a second model evaluation or retry.

The shared one-use claim is complete. September 15–29 is now consumed for subsequent versions too. Do not tune 1.5 on these rows and call it a fresh September test. August remains development data; October was already repeatedly inspected. Later future-issued forecasts are still needed.

## Scope limits

The first target closes 105 seconds after the typical second-15 input freeze; the fifteenth closes 945 seconds after it. Outputs are marginal closing-price probabilities, not a joint intraminute price path or target-before-stop odds. Raw paid inputs, individual forecasts and fitted artifacts remain private.

Historical provider timing is an assumption rather than proven original exchange receipt timing. Native price aggregation checks use the retained executions and do not certify every book level or hidden order. Overlapping origins are correlated; neither 20,004 forecasts nor 300,060 endpoint scores are independent trials. The finite test cannot establish perfect probabilities or profitability.

Evidence: `results/diwali1.4/reserved-final-report.json`, `results/diwali1.4/reserved-final-artifact-audit.json`, and `results/diwali1.4/development-error-decomposition.json`.
