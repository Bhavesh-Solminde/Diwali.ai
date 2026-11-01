"""Train, select on validation only, then evaluate a single chronological holdout."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd
import torch

from .data import FEATURES, OHLC, encode, decode, validate
from .model import CandleTransformer, Config, Windows, nll, sample_candles


def split_indices(length, context):
    train_end, val_end = int(length * 0.70), int(length * 0.85)
    if train_end - context - 1 < 100 or length - val_end < 100:
        raise ValueError("Need more history for chronological train/validation/test splits")
    return train_end, val_end


def prepare(bars, context):
    validate(bars)
    features, targets = encode(bars)
    train_end, val_end = split_indices(len(bars), context)
    # Both scalers see strictly the training period. Row zero has no previous close.
    x_mean = features[1:train_end].mean(axis=0)
    x_std = np.maximum(features[1:train_end].std(axis=0), 1e-4)
    y_mean = targets[1:train_end].mean(axis=0)
    y_std = np.maximum(targets[1:train_end].std(axis=0), 1e-4)
    arrays = {"x_mean": x_mean, "x_std": x_std, "y_mean": y_mean, "y_std": y_std}
    return (features - x_mean) / x_std, (targets - y_mean) / y_std, arrays, (train_end, val_end)


def loader(x, y, indices, config, batch_size, shuffle=False):
    return torch.utils.data.DataLoader(Windows(x, y, indices, config.context),
                                      batch_size=batch_size, shuffle=shuffle, num_workers=0)


def density(model, batches):
    means, logs = [], []
    model.eval()
    with torch.inference_mode():
        for x, _ in batches:
            mean, log_std = model(x)
            means.append(mean[:, -1].numpy())
            logs.append(log_std[:, -1].numpy())
    return np.concatenate(means), np.concatenate(logs)


def scores(actual, point, previous_close):
    error = np.abs(point - actual)
    true_return = actual[:, 3] - previous_close
    predicted_return = point[:, 3] - previous_close
    nonflat = true_return != 0
    return {
        "ohlc_mae_usdt": dict(zip(OHLC, error.mean(axis=0).tolist())),
        "mean_ohlc_mae_bps": float((error / previous_close[:, None] * 1e4).mean()),
        "close_mae_bps": float((error[:, 3] / previous_close * 1e4).mean()),
        "close_direction_accuracy_excluding_flat_actual": float(
            (np.sign(predicted_return[nonflat]) == np.sign(true_return[nonflat])).mean()) if nonflat.any() else None,
        "nonflat_actual_count": int(nonflat.sum()),
    }


def evaluate(model, batches, bars, indices, arrays, seed):
    mean, log_std = density(model, batches)
    actual = bars[OHLC].to_numpy()[indices]
    previous_close = bars.close.to_numpy()[indices - 1]
    _, latent = encode(bars)
    # Chunk sampling to avoid allocating samples x entire holdout x OHLC.
    points, bounds, probabilities, clipping = [], [], [], []
    for start in range(0, len(indices), 128):
        end = start + 128
        candles, clipped = sample_candles(mean[start:end], log_std[start:end],
            arrays["y_mean"], arrays["y_std"], previous_close[start:end], samples=1000, seed=seed + start)
        points.append(np.median(candles, axis=0))
        bounds.append(np.quantile(candles[..., 3], [0.1, 0.9], axis=0).T)
        probabilities.append((candles[..., 3] > previous_close[None, start:end]).mean(axis=0))
        clipping.append(clipped)
    point, interval, p_up = np.concatenate(points), np.concatenate(bounds), np.concatenate(probabilities)
    flat = np.repeat(previous_close[:, None], 4, axis=1)
    historical = np.array([np.median(latent[t - model.config.context:t], axis=0) for t in indices])
    rolling = decode(historical, previous_close)
    model_scores = scores(actual, point, previous_close)
    flat_scores, rolling_scores = scores(actual, flat, previous_close), scores(actual, rolling, previous_close)
    coverage = (actual[:, 3] >= interval[:, 0]) & (actual[:, 3] <= interval[:, 1])
    true_up = (actual[:, 3] > previous_close).astype(float)
    # Comparator probabilities estimated from TRAINING rows only, never test outcomes.
    train_end = int(len(bars) * .7)
    train_close = bars.close.to_numpy()[:train_end]
    base_up = float((np.diff(train_close) > 0).mean())
    report = {
        "rows": len(indices), "transformer": model_scores,
        "last_close_baseline": flat_scores, "rolling_median_shape_baseline": rolling_scores,
        "close_80pct_interval_coverage": float(coverage.mean()),
        "close_80pct_interval_mean_width_bps": float(((interval[:, 1] - interval[:, 0]) / previous_close * 1e4).mean()),
        "close_up_brier_score": float(((p_up - true_up) ** 2).mean()),
        "training_frequency_brier_score": float(((base_up - true_up) ** 2).mean()),
        "extreme_sample_clip_fraction_mean_of_batches": float(np.mean(clipping)),
        "beats_both_baselines_close_mae": model_scores["close_mae_bps"] < min(
            flat_scores["close_mae_bps"], rolling_scores["close_mae_bps"]),
    }
    output = pd.DataFrame({"timestamp": bars.index[indices], "previous_close": previous_close,
        "actual_close": actual[:, 3], "close_p10": interval[:, 0], "close_p90": interval[:, 1],
        "probability_close_above_previous_close": p_up})
    for j, name in enumerate(OHLC):
        output[f"predicted_{name}"] = point[:, j]
        output[f"actual_{name}"] = actual[:, j]
    return report, output


def train(data, output, epochs=6, stride=4, batch_size=128, seed=42, config=None):
    if epochs < 1 or stride < 1 or batch_size < 1:
        raise ValueError("epochs, stride and batch size must be positive")
    config = config or Config()
    torch.set_num_threads(2)
    torch.manual_seed(seed)
    np.random.seed(seed)
    torch.use_deterministic_algorithms(True)
    bars = pd.read_parquet(data)
    # Verify provenance when using the bundled downloader's manifest.
    manifest_path = Path(data).with_name("manifest.json")
    digest = hashlib.sha256(Path(data).read_bytes()).hexdigest()
    provenance = None
    if manifest_path.exists():
        provenance = json.loads(manifest_path.read_text())
        if (provenance.get("symbol"), provenance.get("interval")) != ("BTCUSDT", "1m"):
            raise ValueError("Expected BTCUSDT one-minute data")
        if provenance["parquet_sha256"] != digest:
            raise ValueError("Dataset changed since download")
    x, y, arrays, (train_end, val_end) = prepare(bars, config.context)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    training = np.arange(config.context + 1, train_end, stride)
    validation = np.arange(train_end, val_end)
    testing = np.arange(val_end, len(bars))
    train_batches = loader(x, y, training, config, batch_size, shuffle=True)
    val_batches = loader(x, y, validation, config, batch_size)
    model = CandleTransformer(config)
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=0.01)
    best, history = float("inf"), []
    started = time.monotonic()
    for epoch in range(1, epochs + 1):
        model.train()
        total, count = 0.0, 0
        for batch_x, batch_y in train_batches:
            optimizer.zero_grad(set_to_none=True)
            mean, log_std = model(batch_x)
            loss = nll(mean[:, -1], log_std[:, -1], batch_y)
            if not torch.isfinite(loss):
                raise ValueError("Non-finite training loss")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            total += loss.item() * len(batch_x)
            count += len(batch_x)
        val_mean, val_log = density(model, val_batches)
        val_loss = float(nll(torch.from_numpy(val_mean), torch.from_numpy(val_log),
                             torch.from_numpy(y[validation])))
        if not np.isfinite(val_loss):
            raise ValueError("Non-finite validation loss")
        entry = {"epoch": epoch, "train_nll": total / count, "validation_nll": val_loss}
        history.append(entry)
        if val_loss < best:
            best = val_loss
            checkpoint = {"format_version": 1, "config": asdict(config), "state_dict": model.state_dict(),
                "scalers": {k: torch.from_numpy(v.copy()) for k, v in arrays.items()},
                "symbol": "BTCUSDT", "interval": "1m", "features": FEATURES,
                "train_last_open": bars.index[train_end - 1].isoformat(),
                "validation_last_open": bars.index[val_end - 1].isoformat(),
                "data_sha256": digest, "selected_epoch": epoch, "seed": seed}
            torch.save(checkpoint, output / "model.pt")
        print(json.dumps(entry), flush=True)
    checkpoint = torch.load(output / "model.pt", map_location="cpu", weights_only=True)
    model.load_state_dict(checkpoint["state_dict"])
    report, predictions = evaluate(model, loader(x, y, testing, config, batch_size), bars, testing, arrays, seed)
    predictions.to_csv(output / "test_predictions.csv", index=False)
    summary = {"status": "historical_exploratory", "created_at": datetime.now(timezone.utc).isoformat(),
        "symbol": "BTCUSDT", "interval": "1m", "config": asdict(config),
        "parameters": sum(p.numel() for p in model.parameters()), "data_sha256": digest,
        "source_provenance": provenance, "seed": seed, "training_stride": stride,
        "epochs": epochs, "selected_epoch": checkpoint["selected_epoch"], "history": history,
        "splits": {"training_targets": len(training), "validation_targets": len(validation),
            "test_targets": len(testing), "training_last_open": bars.index[train_end - 1].isoformat(),
            "validation_first_open": bars.index[train_end].isoformat(),
            "validation_last_open": bars.index[val_end - 1].isoformat(),
            "test_first_open": bars.index[val_end].isoformat(), "test_last_open": bars.index[-1].isoformat()},
        "elapsed_seconds": time.monotonic() - started, "test": report,
        "limitations": ["One historical period and one seed; no established trading edge",
            "Gaussian coordinates conditionally independent; tails and probabilities may be miscalibrated",
            "Numerical caps limit sampled gap/body to 10% log move and log1p wick to 7",
            "No fees, spread, slippage, order book, execution or profitability evaluation",
            "Minute observations are dependent; no independent-sample significance claim",
            "Custom datasets without manifest rely on caller-supplied symbol identity"],
        "runtime": {"torch": str(torch.__version__), "numpy": np.__version__, "pandas": pd.__version__},
        "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in Path(__file__).parent.glob("*.py")}}
    (output / "report.json").write_text(json.dumps(summary, indent=2, allow_nan=False))
    (output / "report.md").write_text(render_report(summary))
    print(json.dumps({"output": str(output), "test": report}, indent=2), flush=True)
    return summary


def render_report(report):
    test = report["test"]
    lines = ["# BTC/USDT next-minute candle prototype", "", "Historical exploratory run; forecasting quality is not trading profitability.", "",
        f"Training: {report['splits']['training_targets']:,} sampled targets. Validation: {report['splits']['validation_targets']:,}. Test: {test['rows']:,}.",
        f"Test: {report['splits']['test_first_open']} through {report['splits']['test_last_open']}.",
        f"Selected epoch {report['selected_epoch']} using validation loss only; {report['parameters']:,} parameters.", "",
        "| Forecast | Close MAE (basis points) | Mean OHLC MAE (basis points) |", "|---|---:|---:|"]
    for key, label in [("transformer", "Transformer"), ("last_close_baseline", "Last close"),
                       ("rolling_median_shape_baseline", "Rolling median candle")]:
        row = test[key]
        lines.append(f"| {label} | {row['close_mae_bps']:.4f} | {row['mean_ohlc_mae_bps']:.4f} |")
    lines.extend(["", f"Nominal 80% close interval coverage: {test['close_80pct_interval_coverage']:.2%}.",
        f"Close-up Brier score: {test['close_up_brier_score']:.4f}; training-frequency baseline: {test['training_frequency_brier_score']:.4f} (lower is better).",
        f"Beats both close-price baselines: **{test['beats_both_baselines_close_mae']}**.", "", "Limitations:", ""])
    lines.extend(f"- {line}." for line in report["limitations"])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data/next_candle/btc-2024-q1/BTCUSDT-1m.parquet"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=6)
    parser.add_argument("--stride", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--context", type=int, default=64)
    args = parser.parse_args()
    train(args.data, args.output, args.epochs, args.stride, args.batch_size, args.seed, Config(context=args.context))
