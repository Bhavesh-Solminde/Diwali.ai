"""Generate just the next BTC minute candle with local Kronos or a custom checkpoint."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .data import OHLC, encode, validate


def context_at(bars, context, as_of=None):
    if as_of is None:
        as_of = bars.index[-1] + pd.Timedelta(minutes=1)
    as_of = pd.Timestamp(as_of)
    if as_of.tzinfo is None or as_of.value % (60 * 10**9):
        raise ValueError("as-of must be a timezone-aware exact minute boundary")
    available = bars.loc[bars.index + pd.Timedelta(minutes=1) <= as_of].tail(context + 1)
    validate(available)
    if len(available) != context + 1 or available.index[-1] + pd.Timedelta(minutes=1) != as_of:
        raise ValueError("Not enough consecutive, closed candles immediately before as-of")
    return available, as_of.tz_convert("UTC")


def kronos_samples(bars, samples, seed):
    import torch
    from research.usd100_demo.foundation_models import Forecast
    forecast = Forecast("kronos-small")  # Verifies pinned local source, model and tokenizer hashes.
    torch.manual_seed(seed)
    window = bars.iloc[1:].copy()  # Extra preceding row is only needed by the custom encoding.
    # Quote volume is preserved by our downloader; old/custom OHLCV files are explicit approximations.
    amount_source = "exchange_quote_volume" if "amount" in window else "ohlc_mean_times_base_volume_proxy"
    if "amount" not in window:
        window["amount"] = window[OHLC].mean(axis=1) * window.volume
    stamps = pd.Series(window.index.tz_convert("UTC").tz_localize(None))
    future = pd.Series([stamps.iloc[-1] + pd.Timedelta(minutes=1)])
    paths = []
    with torch.inference_mode():
        for start in range(0, samples, 16):
            size = min(16, samples - start)
            predictions = forecast.pipeline.predict_batch([window] * size, [stamps] * size,
                [future] * size, pred_len=1, sample_count=1, T=1.0, top_p=.9, verbose=False)
            paths.extend(frame[OHLC].iloc[0].to_numpy(dtype=float) for frame in predictions)
    raw = np.array(paths)
    if not np.isfinite(raw).all() or (raw <= 0).any():
        raise ValueError("Kronos generated non-finite or nonpositive prices")
    valid = (raw[:, 1] >= raw.max(axis=1)) & (raw[:, 2] <= raw.min(axis=1))
    candles = raw.copy()
    # Independent tokenizer decoding does not enforce OHLC ordering. Explicitly project ranges.
    candles[:, 1], candles[:, 2] = raw.max(axis=1), raw.min(axis=1)
    return candles, {"model": "kronos-small", "model_provenance": forecast.provenance,
        "tokenizer_provenance": forecast.tokenizer_provenance,
        "raw_invalid_ohlc_fraction": float(1 - valid.mean()), "amount_source": amount_source,
        "range_projection": "high=max(raw OHLC), low=min(raw OHLC); open/close preserved",
        "pretraining_overlap": "unknown; historical forecasts are exploratory"}


def custom_samples(bars, samples, seed, checkpoint):
    import torch
    from .model import CandleTransformer, Config, sample_candles
    saved = torch.load(checkpoint, map_location="cpu", weights_only=True)
    if saved["symbol"] != "BTCUSDT" or saved["interval"] != "1m" or saved["format_version"] != 1:
        raise ValueError("Unsupported checkpoint")
    config = Config(**saved["config"])
    if len(bars) != config.context + 1:
        raise ValueError("Input context must match the checkpoint")
    torch.set_num_threads(2)
    model = CandleTransformer(config)
    model.load_state_dict(saved["state_dict"])
    model.eval()
    arrays = {k: v.numpy() for k, v in saved["scalers"].items()}
    x, _ = encode(bars)
    x = (x[1:] - arrays["x_mean"]) / arrays["x_std"]
    with torch.inference_mode():
        mean, log_std = model(torch.from_numpy(x[None]))
    candles, clipped = sample_candles(mean[0, -1].numpy(), log_std[0, -1].numpy(),
        arrays["y_mean"], arrays["y_std"], bars.close.iloc[-1], samples, seed)
    return candles, {"model": "custom-transformer", "checkpoint_sha256": hashlib.sha256(Path(checkpoint).read_bytes()).hexdigest(),
        "selected_epoch": saved["selected_epoch"], "extreme_sample_clip_fraction": clipped,
        "training_last_open": saved["train_last_open"], "validation_last_open": saved["validation_last_open"]}


def predict(data, model="kronos", checkpoint=None, context=None, samples=100, seed=42, as_of=None):
    if samples < 100:
        raise ValueError("Use at least 100 samples for uncertainty estimates")
    if model not in ("kronos", "custom"):
        raise ValueError("Choose kronos or custom")
    if model == "custom":
        import torch
        if checkpoint is None:
            raise ValueError("Custom predictions need a trained checkpoint")
        saved = torch.load(checkpoint, map_location="cpu", weights_only=True)
        expected = saved["config"]["context"]
        if context is not None and context != expected:
            raise ValueError("Context must match checkpoint")
        context = expected
    else:
        context = context or 128
        if not 2 <= context <= 512:
            raise ValueError("Kronos-small context must be between 2 and 512")
    bars, at = context_at(pd.read_parquet(data), context, as_of)
    candles, metadata = (kronos_samples(bars, samples, seed) if model == "kronos"
                        else custom_samples(bars, samples, seed, checkpoint))
    quantiles = np.quantile(candles, [.1, .5, .9], axis=0)
    result = {"symbol": "BTCUSDT", "interval": "1m", "forecast_open_time": at.isoformat(),
        "forecast_close_time": (at + pd.Timedelta(minutes=1)).isoformat(),
        "context_candles": context, "last_observed_close": float(bars.close.iloc[-1]),
        "samples": samples, "seed": seed, "metadata": metadata,
        "point_candle": dict(zip(OHLC, quantiles[1].tolist())),
        "marginal_p10_p90": {name: [float(quantiles[0, i]), float(quantiles[2, i])] for i, name in enumerate(OHLC)},
        "sample_fraction_close_above_previous_close": float((candles[:, 3] > bars.close.iloc[-1]).mean()),
        "sample_fraction_green_body": float((candles[:, 3] > candles[:, 0]).mean()),
        "input_context_sha256": hashlib.sha256(bars.to_csv().encode()).hexdigest(),
        "note": "One-minute sampled forecast, not a measured confidence level. Intervals are marginal, not joint. Historical input produces a historical forecast, not a current market quote."}
    return result, candles


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data/next_candle/btc-2024-q1/BTCUSDT-1m.parquet"))
    parser.add_argument("--model", choices=["kronos", "custom"], default="kronos")
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--context", type=int)
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--as-of", help="UTC minute boundary, e.g. 2024-03-31T23:59:00+00:00")
    parser.add_argument("--output", type=Path, required=True, help="A new output directory")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Use a fresh forecast output directory")
    result, candles = predict(args.data, args.model, args.checkpoint, args.context, args.samples, args.seed, args.as_of)
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "forecast.json").write_text(json.dumps(result, indent=2, allow_nan=False))
    pd.DataFrame(candles, columns=OHLC).to_csv(args.output / "generated_candles.csv", index=False)
    print(json.dumps(result, indent=2, allow_nan=False))
