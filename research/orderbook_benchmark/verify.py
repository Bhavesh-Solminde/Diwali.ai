"""Recheck saved scores and replay ten forecasts from timestamp-truncated history."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from .data import ROOT, FIELDS, CLASSES
from .models import build_model


def verify(output):
    output = Path(output)
    summary = json.loads((output / "summary.json").read_text())
    cases = pd.read_csv(output / "cases.csv")
    test = pd.read_csv(output / "test_predictions.csv")
    book = pd.read_parquet(ROOT / "seconds.parquet")
    torch.set_num_threads(2)
    if hashlib.sha256((ROOT / "seconds.parquet").read_bytes()).hexdigest() != summary["dataset"]["parquet_sha256"]:
        raise ValueError("Dataset fingerprint changed")
    if hashlib.sha256((output / "protocol.md").read_bytes()).hexdigest() != summary["protocol_sha256"]:
        raise ValueError("Protocol fingerprint changed")
    assert len(cases) == 10 and cases["case"].nunique() == 10 and cases.timestamp.nunique() == 10
    times = pd.to_datetime(cases.timestamp, utc=True).sort_values()
    assert (np.diff(pd.DatetimeIndex(times).as_unit("ns").asi8) >= 600 * 10**9).all()
    for frame in (cases, test):
        at = pd.DatetimeIndex(pd.to_datetime(frame.timestamp, utc=True))
        current = book.loc[at, "mid"].to_numpy()
        actual = book.loc[at + pd.Timedelta(seconds=60), "mid"].to_numpy()
        expected = np.where(np.log(actual / current) * 1e4 > 1, 0,
                            np.where(np.log(actual / current) * 1e4 < -1, 2, 1))
        np.testing.assert_array_equal(expected, frame.actual)
        np.testing.assert_allclose(frame.current_mid, current, rtol=0, atol=1e-8)
        np.testing.assert_allclose(frame.actual_mid_60s, actual, rtol=0, atol=1e-8)
    replay = {}
    for name in ("TLOB", "DeepLOB"):
        path = output / f"{name}.pt"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == summary["models"][name]["checkpoint_sha256"]
        saved = torch.load(path, map_location="cpu", weights_only=True)
        model, probability_output, _ = build_model(name)
        model.load_state_dict(saved["state_dict"])
        model.eval()
        all_p = []
        for _, row in cases.iterrows():
            # Independent preparation: truncate by timestamp before constructing model input.
            at = pd.Timestamp(row.timestamp)
            history = book.loc[:at].tail(128)
            assert history.index[-1] == at
            assert (np.diff(history.index.as_unit("ns").asi8) == 10**9).all()
            x = history[FIELDS].to_numpy(dtype=np.float64).copy()
            reference = float(history.mid.iloc[-1])
            x[:, ::2] = np.log(x[:, ::2] / reference) * 1e4
            x[:, 1::2] = (np.log1p(x[:, 1::2]) - saved["volume_mean"]) / saved["volume_std"]
            tensor = torch.tensor(x, dtype=torch.float32).unsqueeze(0)
            with torch.inference_mode():
                p = model(tensor.unsqueeze(1) if name == "DeepLOB" else tensor)
                p = p if probability_output else p.softmax(dim=1)
            all_p.append(p[0].numpy())
        p = np.array(all_p)
        expected = cases[[f"{name}_p_{c}" for c in CLASSES]].to_numpy()
        np.testing.assert_allclose(p, expected, atol=3e-6, rtol=1e-5)
        for frame, key in [(cases, "cases"), (test, "test")]:
            probabilities = frame[[f"{name}_p_{c}" for c in CLASSES]].to_numpy()
            np.testing.assert_allclose(probabilities.sum(axis=1), 1, atol=1e-6)
            pred = probabilities.argmax(axis=1)
            np.testing.assert_array_equal(pred, frame[f"{name}_prediction"])
            count = int((pred == frame.actual.to_numpy()).sum())
            assert count == summary["models"][name][key]["correct"]
            confusion = np.zeros((3, 3), dtype=int)
            for actual, prediction in zip(frame.actual.to_numpy(), pred):
                confusion[actual, prediction] += 1
            support = confusion.sum(axis=1)
            balanced = float((confusion.diagonal() / support).mean())
            assert abs(balanced - summary["models"][name][key]["balanced_accuracy"]) < 1e-12
        replay[name] = {"cases_replayed": len(cases), "max_probability_difference": float(np.abs(p - expected).max()),
                        "saved_case_and_full_test_scores_recomputed": True}
    result = {"passed": True, "dataset_hash_verified": True, "protocol_hash_verified": True,
        "distinct_cases_and_spacing_verified": True, "target_timestamps_and_actual_prices_verified": True,
        "replay_used_only_history_through_prediction_time": True, "models": replay,
        "requested_models_without_predictions": list(summary["unavailable"])}
    (output / "verification.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    verify(parser.parse_args().output)
