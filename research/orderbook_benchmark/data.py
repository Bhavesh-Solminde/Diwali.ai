"""Actual L2 snapshots, causal features and fixed contrasting example selection."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

import numpy as np
import pandas as pd

ROOT = Path("data/orderbook_benchmark")
FIELDS = [f"{side}{level}_{kind}" for level in range(1, 11)
          for side, kind in [("ask", "price"), ("ask", "size"), ("bid", "price"), ("bid", "size")]]
CLASSES = ["up", "flat", "down"]
CONTEXT = 128
HORIZON = 60
THRESHOLD_BPS = 1.0


def prepare_archive():
    destination = ROOT / "seconds.parquet"
    if destination.exists():
        return pd.read_parquet(destination)
    source = ROOT / "btc-orderbook.zip"
    parts, last_stamp, out_of_order, rows = [], None, 0, 0
    with zipfile.ZipFile(source) as archive:
        member = archive.infolist()[0]
        if member.filename != "1-09-1-20.csv" or member.file_size != 1195785420:
            raise ValueError("Unexpected BTC archive schema/size")
        # Original fields 2..21 are bids, 22..41 asks. Preserve all ten levels.
        order = [str(i) for level in range(10) for i in (22 + 2 * level, 23 + 2 * level,
                                                       2 + 2 * level, 3 + 2 * level)]
        for raw in pd.read_csv(archive.open(member), usecols=["0"] + order, dtype="float64", chunksize=150000):
            stamps = raw["0"].to_numpy(dtype=np.int64)
            out_of_order += int((np.diff(stamps) < 0).sum())
            if last_stamp is not None:
                out_of_order += int(stamps[0] < last_stamp)
            last_stamp = stamps[-1]
            # The observation is available at this second boundary, strictly after its event time.
            at = pd.to_datetime(stamps, unit="ms", utc=True).floor("s") + pd.Timedelta(seconds=1)
            book = raw[order].copy()
            book.columns = FIELDS
            book.index = pd.DatetimeIndex(at, name="state_at")
            group = book.groupby(level=0, sort=True)
            part = group.last()
            part["snapshots"] = group.size()
            parts.append(part)
            rows += len(raw)
            print(f"Read {rows:,} real order-book snapshots", flush=True)
    if out_of_order:
        raise ValueError("Source timestamps are out of order; investigate before use")
    combined = pd.concat(parts)
    counts = combined.snapshots.groupby(level=0).sum()
    book = combined.groupby(level=0, sort=True).last()
    book["snapshots"] = counts
    values = book[FIELDS].to_numpy()
    if not np.isfinite(values).all() or (values[:, 0::2] <= 0).any() or (values[:, 1::2] < 0).any():
        raise ValueError("Invalid book prices/sizes")
    asks, bids = values[:, 0::4], values[:, 2::4]
    bad = ((asks[:, 0] <= bids[:, 0]) | (np.diff(asks, axis=1) <= 0).any(axis=1)
           | (np.diff(bids, axis=1) >= 0).any(axis=1))
    # Dropped invalid states create explicit gaps and cannot enter continuous windows.
    removed = int(bad.sum())
    book = book.loc[~bad].copy()
    book["mid"] = (book.ask1_price + book.bid1_price) / 2
    book["spread_bps"] = (book.ask1_price - book.bid1_price) / book.mid * 1e4
    book["bid_depth"] = book[[f"bid{i}_size" for i in range(1, 11)]].sum(axis=1)
    book["ask_depth"] = book[[f"ask{i}_size" for i in range(1, 11)]].sum(axis=1)
    book["depth"] = book.bid_depth + book.ask_depth
    if (book.depth <= 0).any():
        raise ValueError("Empty combined depth")
    book["imbalance"] = (book.bid_depth - book.ask_depth) / book.depth
    book.to_parquet(destination)
    manifest = {"dataset": "siavashraz/bitcoin-perpetualbtcusdtp-limit-order-book-data",
        "url": "https://www.kaggle.com/datasets/siavashraz/bitcoin-perpetualbtcusdtp-limit-order-book-data",
        "instrument": "BTCUSDT perpetual (dataset provider description)",
        "venue": "not independently verified from source files",
        "archive_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "parquet_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        "raw_snapshots": rows, "sampled_seconds": len(book), "invalid_seconds_removed": removed,
        "first": book.index[0].isoformat(), "last": book.index[-1].isoformat(),
        "missing_second_intervals": int((np.diff(book.index.as_unit("ns").asi8) != 10**9).sum()),
        "timestamp": "Last snapshot strictly before UTC second boundary; epoch milliseconds authoritative"}
    (ROOT / "dataset-manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2), flush=True)
    return book


def split_days(book):
    dates = book.index.normalize().unique()
    a, b = int(len(dates) * .8), int(len(dates) * .8) + int(len(dates) * .1)
    if a < 2 or b >= len(dates):
        raise ValueError("Need enough distinct dates for train/validation/test")
    return dates[a], dates[b]


def candidates(book, context=CONTEXT, horizon=HORIZON):
    ns = book.index.as_unit("ns").asi8
    # Need five minutes of real preceding history for case classification.
    # This stricter common grid applies to training, validation and test alike.
    lookback = max(context - 1, 300)
    positions = np.arange(lookback, len(book) - horizon)
    gap = np.r_[0, np.cumsum(np.diff(ns) != 10**9)]
    continuous = gap[positions + horizon] == gap[positions - lookback]
    aligned = ns[positions] % (60 * 10**9) == 0
    positions = positions[continuous & aligned]
    val_start, test_start = split_days(book)
    at = book.index[positions]
    end = at + pd.Timedelta(seconds=horizon)
    return {
        "train": positions[end < val_start],
        "validation": positions[(at >= val_start) & (end < test_start)],
        "test": positions[at >= test_start],
    }


def causal_measurements(book):
    ns = book.index.as_unit("ns").asi8
    # Rolling rows are used only at candidates verified to have uninterrupted seconds.
    returns = np.log(book.mid).diff() * 1e4
    return pd.DataFrame({
        "trend_5m_bps": np.log(book.mid / book.mid.shift(300)) * 1e4,
        "volatility_5m_bps": returns.rolling(300).std(ddof=0),
        "imbalance": book.imbalance,
        "spread_1m_bps": book.spread_bps.rolling(60).mean(),
        "depth_btc": book.depth,
        "recorded_snapshots_1m": book.snapshots.rolling(60).sum(),
        "midpoint_changes_1m": book.mid.diff().ne(0).astype(float).rolling(60).sum(),
    }, index=book.index)


def select_cases(book, positions):
    measurements = causal_measurements(book).iloc[positions]
    rules = [
        ("rising", "Rising price", "trend_5m_bps", "max"),
        ("falling", "Falling price", "trend_5m_bps", "min"),
        ("sideways", "Sideways price", "trend_5m_bps", "abs_min"),
        ("high_volatility", "High volatility", "volatility_5m_bps", "max"),
        ("low_volatility", "Low volatility", "volatility_5m_bps", "min"),
        ("bid_imbalance", "Buy-side imbalance", "imbalance", "max"),
        ("ask_imbalance", "Sell-side imbalance", "imbalance", "min"),
        ("wide_spread", "Wide spread", "spread_1m_bps", "max"),
        ("thin_liquidity", "Thin liquidity", "depth_btc", "min"),
        ("high_activity", "Rapid midpoint updates", "midpoint_changes_1m", "max"),
    ]
    chosen, times = [], []
    for key, title, feature, rule in rules:
        eligible = np.ones(len(measurements), dtype=bool)
        for at in times:
            eligible &= np.abs((measurements.index - at).total_seconds()) >= 600
        available = measurements.iloc[np.flatnonzero(eligible)]
        if available.empty:
            raise ValueError("Cannot select ten separated cases")
        score = available[feature].abs() if rule == "abs_min" else available[feature]
        at = score.idxmax() if rule == "max" else score.idxmin()
        times.append(at)
        chosen.append({"case": key, "title": title, "timestamp": at.isoformat(),
            "position": int(book.index.get_loc(at)), "rule": f"{rule} {feature}",
            "measurements": {k: float(v) for k, v in measurements.loc[at].items()}})
    return chosen


def labels(book, positions, horizon=HORIZON):
    mid = book.mid.to_numpy()
    change = np.log(mid[positions + horizon] / mid[positions]) * 1e4
    return np.where(change > THRESHOLD_BPS, 0, np.where(change < -THRESHOLD_BPS, 2, 1)).astype(np.int64)


def prepare():
    book = prepare_archive()
    splits = candidates(book)
    cases = select_cases(book, splits["test"])
    freeze = {"protocol_sha256": hashlib.sha256(Path(__file__).with_name("PROTOCOL.md").read_bytes()).hexdigest(),
        "context_seconds": CONTEXT, "horizon_seconds": HORIZON, "threshold_bps": THRESHOLD_BPS,
        "cases": cases, "split_counts": {k: len(v) for k, v in splits.items()},
        "split_boundaries": [s.isoformat() for s in split_days(book)],
        "selection_uses_future_prices": False}
    dest = ROOT / "frozen-cases.json"
    if dest.exists() and json.loads(dest.read_text()) != freeze:
        raise ValueError("Frozen cases changed")
    dest.write_text(json.dumps(freeze, indent=2))
    np.savez_compressed(ROOT / "splits.npz", **splits)
    print(json.dumps(freeze, indent=2), flush=True)


if __name__ == "__main__":
    prepare()
