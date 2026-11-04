# Fixed prospective smoke protocol for0.9 versus1.1

Native receiver: `prospective-diwali05-20261104-v3`, one-hour budget. It preserves received messages and causal input freezes, and also saves its existing0.5 forecasts. Do not confuse those0.5 forecasts with1.1 forecasts.

After1.1's development selection and report are frozen, start two candidate followers on this same receiver: selected0.9 and selected1.1. Each accepts only snapshots frozen after its own startup, issues for600seconds, then drains already-issued15-target forecasts for up to17minutes. Every forecast must be durably committed before its first target begins. No future observations enter inference; labels are scored later. No orders are placed and followers add no feed connections. Require sufficient remaining receiver budget; do not restart or silently substitute another receiver if it fails.

Freeze checkpoints, calibration, reports, preprocessing and predictor dependencies by hashes. Replay the native receipt journal to verify every copied freeze; recompute each prediction and final-direction claim. Verify both UTC and monotonic chronology, target/reference matching, raw manifest/prefix integrity and then-available labels. Reject a missed deadline rather than scoring a late forecast.

Only compare origins shared by both followers with all15 outcomes matured and verified through the common audited source boundary. Report total committed, completed and matched counts separately. Main comparison: final binary log loss/Brier/accuracy and confidence counts; also mean price-range loss and joint loss. Include50–50 loss. Use `research.diwali.compare_candidates` after source audits. Do not treat15 horizons from one origin as15 independent forecasts, or this one session as a calibration study.

Do not change or retune these frozen models in response to partial outcomes. Once inspected, this session is not fresh evidence for a subsequently changed model. All raw recordings, inputs, forecasts and individual outcomes remain private; publish aggregate evidence only. A pending process/status file alone is not proof of completed evaluation.
