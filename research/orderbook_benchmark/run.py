"""Matched BTC 60-second direction experiment; never scores unavailable models."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd
import torch
from torch import nn

from .data import ROOT, FIELDS, CLASSES, CONTEXT, HORIZON, labels, split_days
from .models import build_model, forward, log_probabilities


class BookWindows(torch.utils.data.Dataset):
    def __init__(self, raw, positions, y, volume_mean, volume_std, context=CONTEXT):
        self.raw, self.positions, self.y = raw, np.asarray(positions), np.asarray(y)
        self.volume_mean, self.volume_std, self.context = volume_mean, volume_std, context

    def __len__(self):
        return len(self.positions)

    def __getitem__(self, i):
        at = self.positions[i]
        x = self.raw[at - self.context + 1:at + 1].copy()
        anchor = (x[-1, 0] + x[-1, 2]) / 2
        x[:, 0::2] = np.log(x[:, 0::2] / anchor) * 1e4
        x[:, 1::2] = (np.log1p(x[:, 1::2]) - self.volume_mean) / self.volume_std
        return torch.from_numpy(x.astype(np.float32)), torch.tensor(self.y[i], dtype=torch.long)


def probabilities(model, name, batches, already_probabilities):
    model.eval()
    values = []
    with torch.inference_mode():
        for x, _ in batches:
            p = log_probabilities(forward(model, name, x), already_probabilities).exp()
            if not torch.isfinite(p).all():
                raise ValueError("Non-finite model probabilities")
            values.append(p.numpy())
    return np.concatenate(values)


def metrics(y, p):
    predicted = p.argmax(axis=1)
    confusion = np.zeros((3, 3), dtype=int)
    np.add.at(confusion, (y, predicted), 1)
    support = confusion.sum(axis=1)
    recalled = np.divide(confusion.diagonal(), support, out=np.zeros(3), where=support > 0)
    precision = np.divide(confusion.diagonal(), confusion.sum(axis=0), out=np.zeros(3), where=confusion.sum(axis=0) > 0)
    f1 = np.divide(2 * precision * recalled, precision + recalled, out=np.zeros(3), where=precision + recalled > 0)
    return {"count": len(y), "correct": int((predicted == y).sum()), "accuracy": float((predicted == y).mean()),
        "balanced_accuracy": float(recalled[support > 0].mean()), "macro_f1": float(f1.mean()),
        "multiclass_brier": float(((p - np.eye(3)[y]) ** 2).sum(axis=1).mean()),
        "actual_counts": dict(zip(CLASSES, support.tolist())),
        "predicted_counts": dict(zip(CLASSES, confusion.sum(axis=0).tolist())),
        "confusion_rows_actual_columns_predicted": confusion.tolist()}


def limited(positions, cap):
    return positions[np.linspace(0, len(positions) - 1, min(cap, len(positions)), dtype=int)]


def run(output, epochs=3, max_train=8000):
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    output = Path(output)
    if output.exists():
        raise FileExistsError("Use a fresh output directory")
    if epochs != 3 or max_train != 8000:
        raise ValueError("Main experiment settings are frozen at 3 epochs / 8,000 maximum training windows")
    frozen = json.loads((ROOT / "frozen-cases.json").read_text())
    protocol = Path(__file__).with_name("PROTOCOL.md")
    if hashlib.sha256(protocol.read_bytes()).hexdigest() != frozen["protocol_sha256"]:
        raise ValueError("Protocol changed after case selection")
    book = pd.read_parquet(ROOT / "seconds.parquet")
    dataset = json.loads((ROOT / "dataset-manifest.json").read_text())
    if hashlib.sha256((ROOT / "seconds.parquet").read_bytes()).hexdigest() != dataset["parquet_sha256"]:
        raise ValueError("Dataset changed")
    splits = dict(np.load(ROOT / "splits.npz"))
    raw = book[FIELDS].to_numpy(dtype=np.float64)
    volume = np.log1p(raw[:book.index.searchsorted(split_days(book)[0]), 1::2])
    volume_mean, volume_std = float(volume.mean()), max(float(volume.std()), 1e-5)
    del volume
    train_pos = limited(splits["train"], max_train)
    val_pos = limited(splits["validation"], 1500)
    test_pos = splits["test"]
    case_pos = np.array([entry["position"] for entry in frozen["cases"]])
    ys = {k: labels(book, v) for k, v in [("train", train_pos), ("validation", val_pos),
                                        ("test", test_pos), ("cases", case_pos)]}
    def batches(positions, y, shuffle=False):
        generator = torch.Generator().manual_seed(42)
        return torch.utils.data.DataLoader(BookWindows(raw, positions, y, volume_mean, volume_std),
                                          batch_size=32, shuffle=shuffle, generator=generator)
    output.mkdir(parents=True)
    (output / "frozen-cases.json").write_text(json.dumps(frozen, indent=2))
    (output / "protocol.md").write_text(protocol.read_text())
    summary = {"created_at": datetime.now(timezone.utc).isoformat(), "task": "BTC perpetual midpoint direction 60 seconds ahead",
        "class_order": CLASSES, "flat_band_bps": 1.0, "dataset": dataset, "protocol_sha256": frozen["protocol_sha256"],
        "normalization": {"prices": "log ratio in basis points to final observed window midpoint",
                          "volume_log1p_mean": volume_mean, "volume_log1p_std": volume_std},
        "splits": {k: {"windows": len(p), "first": book.index[p[0]].isoformat(),
                        "last": book.index[p[-1]].isoformat()} for k, p in [("train", train_pos), ("validation", val_pos), ("test", test_pos)]},
        "seed": 42, "epochs": epochs, "models": {}, "baselines": {}, "unavailable": {
            "LOBERT": {"status": "not run", "reason": "No official downloadable source/weights identified in paper and author sources. Not replaced by unrelated low-rank LoBERT NLP repository.",
                       "sources": ["https://arxiv.org/abs/2511.12563", "https://www.tuni.fi/fi/tau/tutkimus/ai-lob-advanced-limit-order-book-modeling-ai"]},
            "LOBS5": {"status": "not run", "reason": "Author code inspected. Requires individual-order L3 messages and order references; BTC dataset has only aggregate L2 snapshots. No BTC-trained checkpoint identified. Author source also pins CUDA-era JAX/Torch, unavailable as specified on this ARM Mac.",
                      "source": "https://github.com/GereonFranken/LOBS5"}},
        "limitations": ["Two of four requested models could be scored; there is no four-model winner",
            "Fresh task-specific training; not scores of published pretrained checkpoints or paper replications",
            "Midpoint direction, not complete OHLC or executable trade-price prediction",
            "Ten selected extreme cases are illustrative and not a random accuracy sample",
            "Short historical period, one seed, one training budget; no general superiority established",
            "Adjacent minute outcomes/context are dependent; no independent-sample significance claim",
            "No fees, spread-crossing execution, latency, slippage or profitability tested",
            "Observed test period cannot be treated as untouched after results are inspected"]}
    test_frame = pd.DataFrame({"timestamp": book.index[test_pos], "position": test_pos, "actual": ys["test"],
        "current_mid": book.mid.to_numpy()[test_pos], "actual_mid_60s": book.mid.to_numpy()[test_pos + HORIZON]})
    cases_frame = pd.DataFrame({"case": [x["case"] for x in frozen["cases"]],
        "title": [x["title"] for x in frozen["cases"]], "timestamp": book.index[case_pos],
        "position": case_pos, "actual": ys["cases"], "current_mid": book.mid.to_numpy()[case_pos],
        "actual_mid_60s": book.mid.to_numpy()[case_pos + HORIZON]})
    started = time.monotonic()
    for name in ("TLOB", "DeepLOB"):
        torch.manual_seed(42)
        np.random.seed(42)
        model, already_probabilities, provenance = build_model(name)
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)
        history, best, model_started = [], float("inf"), time.monotonic()
        for epoch in range(1, epochs + 1):
            model.train()
            total, count = 0., 0
            for step, (x, y) in enumerate(batches(train_pos, ys["train"], True), 1):
                optimizer.zero_grad(set_to_none=True)
                log_p = log_probabilities(forward(model, name, x), already_probabilities)
                loss = nn.functional.nll_loss(log_p, y)
                if not torch.isfinite(loss):
                    raise ValueError("Non-finite training loss")
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                total += loss.item() * len(y)
                count += len(y)
                if step % 100 == 0:
                    print(f"{name} epoch {epoch}: {count:,}/{len(train_pos):,} windows", flush=True)
            val_p = probabilities(model, name, batches(val_pos, ys["validation"]), already_probabilities)
            val_loss = float(-np.log(np.maximum(val_p[np.arange(len(val_p)), ys["validation"]], 1e-9)).mean())
            row = {"epoch": epoch, "train_loss": total / count, "validation_loss": val_loss,
                   "elapsed_seconds": time.monotonic() - model_started}
            history.append(row)
            if val_loss < best:
                best = val_loss
                selected_epoch = epoch
                torch.save({"state_dict": model.state_dict(), "name": name, "context": CONTEXT,
                    "volume_mean": volume_mean, "volume_std": volume_std, "selected_epoch": epoch,
                    "class_order": CLASSES, "horizon_seconds": HORIZON, "seed": 42,
                    "provenance": provenance}, output / f"{name}.pt")
            (output / f"{name}-training.json").write_text(json.dumps(history, indent=2))
            print(json.dumps({"model": name, **row}), flush=True)
        saved = torch.load(output / f"{name}.pt", map_location="cpu", weights_only=True)
        model.load_state_dict(saved["state_dict"])
        test_p = probabilities(model, name, batches(test_pos, ys["test"]), already_probabilities)
        case_p = probabilities(model, name, batches(case_pos, ys["cases"]), already_probabilities)
        for frame, p in [(test_frame, test_p), (cases_frame, case_p)]:
            frame[f"{name}_prediction"] = p.argmax(axis=1)
            for j, cls in enumerate(CLASSES):
                frame[f"{name}_p_{cls}"] = p[:, j]
        summary["models"][name] = {"provenance": provenance, "selected_epoch": selected_epoch,
            "history": history, "test": metrics(ys["test"], test_p), "cases": metrics(ys["cases"], case_p),
            "checkpoint_sha256": hashlib.sha256((output / f"{name}.pt").read_bytes()).hexdigest(),
            "seconds": time.monotonic() - model_started}
        test_frame.to_csv(output / "test_predictions.csv", index=False)
        cases_frame.to_csv(output / "cases.csv", index=False)
        (output / "summary-progress.json").write_text(json.dumps(summary, indent=2))
        print(json.dumps({"model": name, "test": summary["models"][name]["test"],
                          "cases": summary["models"][name]["cases"]}, indent=2), flush=True)
        del model, optimizer
    majority = int(np.bincount(ys["train"], minlength=3).argmax())
    for key, frame, positions in [("test", test_frame, test_pos), ("cases", cases_frame, case_pos)]:
        y = ys[key]
        past_return = np.log(book.mid.to_numpy()[positions] / book.mid.to_numpy()[positions - 60]) * 1e4
        baseline_predictions = {"Always flat": np.full(len(y), 1), "Training majority": np.full(len(y), majority),
            "Past-minute momentum": np.where(past_return > 1, 0, np.where(past_return < -1, 2, 1)),
            "Depth imbalance": np.where(book.imbalance.to_numpy()[positions] > 0, 0, 2)}
        for name, pred in baseline_predictions.items():
            summary["baselines"].setdefault(name, {})[key] = metrics(y, np.eye(3)[pred])
            frame[name] = pred
    ranked = sorted(summary["models"], key=lambda n: summary["models"][n]["test"]["balanced_accuracy"], reverse=True)
    summary["ranking_of_runnable_models"] = ranked
    summary["highest_test_balanced_accuracy"] = ranked[0]
    score = summary["models"][ranked[0]]["test"]["balanced_accuracy"]
    summary["top_model_beats_all_baselines_balanced_accuracy"] = all(score > x["test"]["balanced_accuracy"] for x in summary["baselines"].values())
    summary["elapsed_seconds"] = time.monotonic() - started
    summary["source_sha256"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob("*.py")}
    test_frame.to_csv(output / "test_predictions.csv", index=False)
    cases_frame.to_csv(output / "cases.csv", index=False)
    (output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False))
    print(json.dumps({"output": str(output), "ranking": ranked, "seconds": summary["elapsed_seconds"]}), flush=True)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.output)
