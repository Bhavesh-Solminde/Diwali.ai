"""Causality, split isolation, candle validity and a real save/load training check."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from research.next_candle.data import OHLC, decode, encode, validate
from research.next_candle.predict import context_at

HAS_TORCH = importlib.util.find_spec("torch") is not None


def fixture(n=800):
    rng = np.random.default_rng(11)
    close = 40000 * np.exp(np.cumsum(rng.normal(0, .0002, n)))
    o = np.r_[close[0], close[:-1]]
    return pd.DataFrame({"open": o, "close": close,
        "high": np.maximum(o, close) * 1.0001, "low": np.minimum(o, close) / 1.0002,
        "volume": rng.uniform(1, 100, n)}, index=pd.date_range("2024-01-01", periods=n, freq="min", tz="UTC"))


class CandleDataTests(unittest.TestCase):
    def test_encoding_is_past_only_and_roundtrips(self):
        bars = fixture()
        features, targets = encode(bars)
        changed = bars.copy()
        changed.loc[changed.index[400]:, OHLC] *= 10
        after, _ = encode(changed)
        np.testing.assert_array_equal(features[:400], after[:400])
        np.testing.assert_allclose(decode(targets[1:], bars.close.to_numpy()[:-1]),
                                   bars[OHLC].to_numpy()[1:], rtol=1e-7)

    def test_decode_extreme_coordinates_stays_valid(self):
        z = np.random.default_rng(1).normal(size=(200, 4)) * 1e5
        candles = decode(z, 40000)
        self.assertTrue(np.isfinite(candles).all())
        self.assertTrue((candles > 0).all())
        self.assertTrue((candles[:, 1] >= candles.max(axis=1)).all())
        self.assertTrue((candles[:, 2] <= candles.min(axis=1)).all())

    def test_rejects_missing_duplicate_unclosed_and_bad_prices(self):
        bars = fixture()
        for bad in [bars.drop(bars.index[10]), pd.concat([bars.iloc[:10], bars.iloc[9:]])]:
            with self.assertRaises(ValueError):
                validate(bad)
        with self.assertRaises(ValueError):
            validate(bars, now=bars.index[-1] + pd.Timedelta(seconds=30))
        for column, value in [("high", 1), ("low", 1e9), ("volume", -1), ("close", np.nan)]:
            bad = bars.copy()
            bad.loc[bad.index[10], column] = value
            with self.assertRaises(ValueError):
                validate(bad)

    def test_asof_excludes_open_and_future_candles(self):
        bars = fixture()
        at = bars.index[400]
        before, _ = context_at(bars, 64, at)
        bars.loc[at:, OHLC] = 999999
        after, _ = context_at(bars, 64, at)
        pd.testing.assert_frame_equal(before, after)
        self.assertEqual(before.index[-1] + pd.Timedelta(minutes=1), at)
        with self.assertRaises(ValueError):
            context_at(bars, 64, bars.index[-1] + pd.Timedelta(minutes=2))
        with self.assertRaises(ValueError):
            context_at(bars, 64, "2024-01-01T06:40:00")


@unittest.skipUnless(HAS_TORCH, "Custom transformer tests require the optional Torch environment")
class TransformerTests(unittest.TestCase):
    def test_future_tokens_cannot_change_prior_outputs(self):
        import torch
        from research.next_candle.model import CandleTransformer, Config
        torch.set_num_threads(2)
        torch.manual_seed(10)
        model = CandleTransformer(Config(context=16, width=16, heads=2, layers=1, dropout=0)).eval()
        x = torch.randn(2, 16, 9)
        with torch.inference_mode():
            before = model(x)[0]
            x[:, 8:] = 100
            after = model(x)[0]
        torch.testing.assert_close(before[:, :8], after[:, :8], rtol=0, atol=0)

    def test_scalers_and_training_windows_do_not_see_holdouts(self):
        from research.next_candle.train import prepare
        from research.next_candle.model import Windows
        bars = fixture()
        x, y, scalers, (train_end, _) = prepare(bars, 16)
        changed = bars.copy()
        changed.loc[changed.index[train_end]:, OHLC] *= 10
        _, _, changed_scalers, _ = prepare(changed, 16)
        for key in scalers:
            np.testing.assert_array_equal(scalers[key], changed_scalers[key])
        window = Windows(x, y, [train_end - 1, train_end], 16)
        np.testing.assert_array_equal(window[0][0].numpy(), x[train_end - 17:train_end - 1])
        np.testing.assert_array_equal(window[0][1].numpy(), y[train_end - 1])

    def test_train_checkpoint_and_inference_roundtrip(self):
        from research.next_candle.model import Config
        from research.next_candle.train import train
        from research.next_candle.predict import predict
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data = root / "btc.parquet"
            fixture().to_parquet(data)
            report = train(data, root / "run", epochs=1, stride=8, batch_size=32,
                           config=Config(context=16, width=16, heads=2, layers=1, dropout=0))
            self.assertEqual(report["test"]["rows"], 120)
            kwargs = {"data": data, "model": "custom", "checkpoint": root / "run/model.pt"}
            result, candles = predict(**kwargs)
            again, repeat = predict(**kwargs)
            np.testing.assert_array_equal(candles, repeat)
            self.assertEqual(result, again)
            point = result["point_candle"]
            self.assertGreaterEqual(point["high"], max(point.values()))
            self.assertLessEqual(point["low"], min(point.values()))
            self.assertEqual(result["forecast_open_time"], "2024-01-01T13:20:00+00:00")


if __name__ == "__main__":
    unittest.main()
