"""Verified public spot archives and past-only candle representations."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile

import numpy as np
import pandas as pd

OHLC = ["open", "high", "low", "close"]
FEATURES = ["gap_bps", "body_bps", "log_upper", "log_lower", "log_volume",
            "minute_sin", "minute_cos", "week_sin", "week_cos"]
BASE = "https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1m"


def validate(bars, now=None):
    """Reject gaps rather than fabricate candles. Index denotes UTC candle OPEN."""
    if len(bars) < 2 or not isinstance(bars.index, pd.DatetimeIndex) or bars.index.tz is None:
        raise ValueError("Need timestamped, timezone-aware minute candles")
    times = bars.index.tz_convert("UTC").as_unit("ns").asi8
    if times[0] % (60 * 10**9) or not np.all(np.diff(times) == 60 * 10**9):
        raise ValueError("Candles must be sorted, unique, aligned and consecutive minutes")
    values = bars[OHLC + ["volume"]].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values[:, :4] <= 0).any() or (values[:, 4] < 0).any():
        raise ValueError("Invalid prices or volume")
    o, h, l, c = values[:, :4].T
    if ((h < np.maximum(o, c)) | (l > np.minimum(o, c))).any():
        raise ValueError("Invalid OHLC ordering")
    now = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    if now.tzinfo is None:
        raise ValueError("now must include a timezone")
    if bars.index[-1] + pd.Timedelta(minutes=1) > now:
        raise ValueError("Last candle is not closed yet")


def encode(bars):
    """Candle t uses only its own OHLCV, timestamp and close at t-1."""
    o, h, l, c = bars[OHLC].to_numpy(dtype=np.float64).T
    prev = np.r_[c[0], c[:-1]]
    latent = np.column_stack([
        np.log(o / prev) * 1e4, np.log(c / o) * 1e4,
        np.log1p(np.maximum(0, np.log(h / np.maximum(o, c)) * 1e4)),
        np.log1p(np.maximum(0, np.log(np.minimum(o, c) / l) * 1e4)),
    ])
    utc = bars.index.tz_convert("UTC")
    minute = (utc.hour * 60 + utc.minute).to_numpy()
    week = utc.day_of_week.to_numpy() * 1440 + minute
    features = np.column_stack([latent, np.log1p(bars.volume.to_numpy()),
        np.sin(2 * np.pi * minute / 1440), np.cos(2 * np.pi * minute / 1440),
        np.sin(2 * np.pi * week / 10080), np.cos(2 * np.pi * week / 10080)])
    return features.astype(np.float32), latent.astype(np.float32)


def decode(latent, previous_close):
    """Convert sampled gap/body/wicks into valid, positive OHLC candles."""
    z = np.asarray(latent, dtype=np.float64)
    if z.shape[-1] != 4 or not np.isfinite(z).all():
        raise ValueError("Need four finite candle coordinates")
    previous_close = np.asarray(previous_close, dtype=np.float64)
    if not np.isfinite(previous_close).all() or (previous_close <= 0).any():
        raise ValueError("Need positive finite previous closes")
    # Numerical safety caps; clipping counts are recorded for generated forecasts.
    gap, body = np.clip(z[..., 0], -1000, 1000), np.clip(z[..., 1], -1000, 1000)
    upper, lower = np.expm1(np.clip(z[..., 2], 0, 7)), np.expm1(np.clip(z[..., 3], 0, 7))
    o = previous_close * np.exp(gap / 1e4)
    c = o * np.exp(body / 1e4)
    h = np.maximum(o, c) * np.exp(upper / 1e4)
    l = np.minimum(o, c) * np.exp(-lower / 1e4)
    return np.stack([o, h, l, c], axis=-1)


def parse_archive(content, month):
    name = f"BTCUSDT-1m-{month}.csv"
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        raw = pd.read_csv(archive.open(name), header=None)
    # Binance spot switched from milliseconds to microseconds in January 2025.
    unit = "us" if int(raw.iloc[0, 0]) >= 10**15 else "ms"
    bars = raw.iloc[:, 1:6].copy()
    bars.columns = OHLC + ["volume"]
    bars.index = pd.DatetimeIndex(pd.to_datetime(raw.iloc[:, 0], unit=unit, utc=True), name="timestamp")
    expected = pd.date_range(str(month), str(pd.Period(month, freq="M") + 1),
                             freq="min", inclusive="left", tz="UTC", name="timestamp")
    validate(bars)
    if not bars.index.equals(expected):
        raise ValueError(f"Archive does not contain the complete month {month}")
    return bars


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "next-candle-research/0.1"})
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read()


def download(start, end, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    destination = output / "BTCUSDT-1m.parquet"
    manifest = output / "manifest.json"
    if destination.exists() or manifest.exists():
        raise FileExistsError("Use a fresh output folder to preserve existing datasets")
    raw_dir = output / "raw"
    raw_dir.mkdir(exist_ok=True)
    parts, records = [], []
    months = pd.period_range(start, end, freq="M")
    if not len(months):
        raise ValueError("Choose at least one month")
    for month in months:
        name = f"BTCUSDT-1m-{month}.zip"
        url = f"{BASE}/{name}"
        path = raw_dir / name
        check = raw_dir / (name + ".CHECKSUM")
        content = path.read_bytes() if path.exists() else fetch(url)
        checksum = check.read_bytes() if check.exists() else fetch(url + ".CHECKSUM")
        digest = hashlib.sha256(content).hexdigest()
        if digest != checksum.decode().split()[0]:
            raise ValueError(f"Checksum mismatch: {name}")
        bars = parse_archive(content, str(month))
        path.write_bytes(content)
        check.write_bytes(checksum)
        parts.append(bars)
        records.append({"url": url, "sha256": digest, "rows": len(bars)})
        print(f"Verified {month}: {len(bars):,} candles", flush=True)
    combined = pd.concat(parts)
    validate(combined)
    combined.to_parquet(destination)
    manifest.write_text(json.dumps({"symbol": "BTCUSDT", "venue": "Binance spot", "interval": "1m",
        "timestamp_semantics": "UTC candle open; rows must be closed before inference",
        "archives": records, "rows": len(combined),
        "parquet_sha256": hashlib.sha256(destination.read_bytes()).hexdigest()}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2024-01")
    parser.add_argument("--end", default="2024-03")
    parser.add_argument("--output", type=Path, default=Path("data/next_candle/btc-2024-q1"))
    args = parser.parse_args()
    download(args.start, args.end, args.output)
