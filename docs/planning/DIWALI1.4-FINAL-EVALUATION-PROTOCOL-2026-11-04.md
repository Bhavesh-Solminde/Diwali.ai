# Diwali1.4 final evaluation: frozen artifacts and one-use scoring

This implements the already chosen September15–29evaluation strategy. It does not change model families, fitting budgets, primary scores or the reserved dates. Development is still running; no real final release or scoring claim has been created.

## Earlier stages and available inputs

September1–14preparation has completed. Its2,398joined inputs retain8,257,963event rows;2,341origins also have complete15-close targets. Independent native aggregation matches35,115target-close coordinates exactly. Three origins are purged from selection because their15thtarget crosses the September7partition end. Final-build counts are5,391August fit,862September selection and1,476September calibration origins. These are data-quality counts, not forecast performance evidence.

The fixed histograms, conditional-volatility histograms, logistic and boosted-tree baselines have been fitted on August, selected where applicable on September1–7and calibrated on September8–14. They did not load reserved final labels. Their artifacts stay private in `data/models/diwali1.4-final-baselines-v1`; all artifact hashes are recorded in its report. No baseline settings were chosen from the eventual final score.

The primary model build remains gated on the complete August development report. `event_final_train.py` recomputes its frozen family-selection rule and then fits fixedseed17on August, selects a checkpoint on September1–7and calibrates on September8–14. It does not compute a final-score partition. Both its data wrapper and the ordinary partition helper deny final scoring without a deliberate release.

`event_build_when_ready.py` is running as the continuation for this stage. While waiting, it verifies that the specific development process is live and still running the expected study command; a state file alone is not accepted as proof. A failed/terminal study without a complete report makes the continuation fail rather than start another fit. After a valid completed decision it fits the final model and runs the nonfinal preflight. It stops before release, final-period preparation or scoring, and refuses existing final-build output paths. Current local state is in `data/models/diwali1.4-final-continuation-v1`; the development study remains `data/models/diwali1.4-development-exact-v2`.

## Nonfinal engineering preflight and release

Before opening the reserved period for model evaluation, `event_final_preflight.py` must exercise the selected model and all four baselines on ten already-used selection inputs. It checks finite15×26probability outputs, normalization and CPU/MPS agreement when MPS is available. Existing selection labels are loaded for the verified loader but are not used to score this engineering check. This does not consume the reserved final test.

`event_make_release.py` requires the completed model, baselines, development selection and successful preflight. It freezes the training protocol, selected weights, fit transforms, calibration, development report, baseline artifacts and preflight hashes. It also freezes the scorer/guard and feature/replay/quality preparation source. The guard verifies the fit-transform date range, candidate/seed, model/calibration identity, baseline cohort identity and unchanged source files. A release cannot legitimately substitute another model after seeing test results.

These checks are programming safeguards against accidental reuse and edits, not an operating-system secrecy boundary or evidence of exchange authenticity. The underlying archive has already had broad quality inspection. The independent claim concerns new model-performance evaluation, not never-seen historical prices.

## Reserved-period preparation after release

`event_shards_final.py` permits only September14–29source hours, with earlier snapshot initialization as needed, and requires a verified release. September14provides completed-candle context for the first September15origin. It reuses the existing lossless replayer and records a separate wrapper/release authorization; the ordinary development replayer's date guard remains unchanged. No new source data are invented and no paid files are published.

The context builder permits `reserved-final` only with the same verified release. The final native content auditor also requires it. Quality gates, clock exclusions, missingness policy, strict freezes, event retention and target-horizon purges remain the same as earlier stages. Feature preparation uses the existing verified implementation. These stages derive and check historical content/counts after all predictive artifacts are frozen; they do not score model/outcome pairs. They must not choose favourable days or loosen exclusions from a forecast result.

## One-use scoring and failure handling

`event_final_score.py` verifies the release and atomically creates a shared registry claim **before its loader opens labels for scoring**. The registry key names the BTC period, not an output directory or model version. A copied release or a different output path cannot make it fresh again. Concurrent attempts are tested to allow only one claim. Later model versions also inherit that consumed-period status.

Scoring reports all eligible origins and the frozen15-close marginal range task. Report mean/per-horizon price-bin log loss, ordered probability score, net-direction probability scores, accuracy, confidence reliability, per-day results and paired differences against every frozen baseline. Save individual forecasts only locally. Daily comparisons remain descriptive because target windows overlap and there are few calendar days.

If scoring fails after the claim, record the failure and retain the consumed state. Do not silently delete the registry or relaunch into another folder. Any exact recovery would require an explicit audit proving the model, inputs and scoring path are unchanged; it is not an excuse to tune and rerun. The nonfinal preflight is intended to catch engineering failures before this irreversible test use.

After the score, publish aggregate results and limitations regardless of improvement or regression. The period is consumed and must not select subsequent revisions. A later new version needs a documented new evaluation period or newly issued prospective forecasts. The old0.9/1.2live session cannot confirm1.4. No result here establishes profitable entries, complete hidden liquidity or perfect conditional probabilities.
