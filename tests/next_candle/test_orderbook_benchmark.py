"""Tests for the real-data order-book experiment's temporal contract."""
import importlib.util
import unittest

import numpy as np
import pandas as pd

from research.orderbook_benchmark.data import FIELDS, candidates, labels, select_cases, split_days

HAS_TORCH = importlib.util.find_spec("torch") is not None


def books():
    # Separate daily runs deliberately leave overnight gaps that must not be filled.
    index = pd.DatetimeIndex(np.concatenate([pd.date_range(f"2023-01-{d:02d}", periods=7200,
        freq="s", tz="UTC").to_numpy() for d in range(1, 13)]))
    rng = np.random.default_rng(10)
    mid = 20000 * np.exp(np.cumsum(rng.normal(0, .00001, len(index))))
    frame = pd.DataFrame(index=index)
    for i in range(1, 11):
        frame[f"ask{i}_price"] = mid + i * .1
        frame[f"bid{i}_price"] = mid - i * .1
        frame[f"ask{i}_size"] = rng.uniform(1, 5, len(index))
        frame[f"bid{i}_size"] = rng.uniform(1, 5, len(index))
    frame["mid"] = mid
    frame["imbalance"] = rng.uniform(-1, 1, len(index))
    frame["spread_bps"] = .1
    frame["depth"] = rng.uniform(10, 100, len(index))
    frame["snapshots"] = 4
    return frame


class TemporalTests(unittest.TestCase):
    def test_candidates_cannot_bridge_gaps_or_split_target_boundaries(self):
        book = books()
        split = candidates(book)
        val_at, test_at = split_days(book)
        self.assertTrue((book.index[split["train"]] + pd.Timedelta(seconds=60) < val_at).all())
        self.assertTrue((book.index[split["validation"]] >= val_at).all())
        self.assertTrue((book.index[split["validation"]] + pd.Timedelta(seconds=60) < test_at).all())
        for positions in split.values():
            self.assertTrue((book.index[positions + 60] - book.index[positions] == pd.Timedelta(seconds=60)).all())
            self.assertTrue((book.index[positions] - book.index[positions - 300] == pd.Timedelta(seconds=300)).all())

    def test_ten_cases_use_different_rules_and_separated_times(self):
        book = books()
        selected = select_cases(book, candidates(book)["test"])
        self.assertEqual(len({x["case"] for x in selected}), 10)
        self.assertEqual(len({x["position"] for x in selected}), 10)
        times = pd.DatetimeIndex([x["timestamp"] for x in selected]).sort_values()
        self.assertTrue((np.diff(times.as_unit("ns").asi8) >= 600 * 10**9).all())
        # Changing outcomes after the final candidate cannot change earlier measurements.
        from research.orderbook_benchmark.data import causal_measurements
        at = selected[0]["position"]
        before = causal_measurements(book).iloc[at]
        altered = book.copy()
        altered.iloc[at + 1:, altered.columns.get_loc("mid")] *= 10
        pd.testing.assert_series_equal(before, causal_measurements(altered).iloc[at])

    def test_labels_use_exact_60_second_future_and_fixed_flat_band(self):
        book = books().iloc[:600].copy()
        positions = np.array([300, 400, 500])
        book.iloc[positions, book.columns.get_loc("mid")] = 20000
        book.iloc[positions + 60, book.columns.get_loc("mid")] = [20004, 20000.5, 19996]
        np.testing.assert_array_equal(labels(book, positions), [0, 1, 2])


@unittest.skipUnless(HAS_TORCH, "Optional model environment required")
class ModelTests(unittest.TestCase):
    def test_window_excludes_future_states_and_ends_at_decision(self):
        from research.orderbook_benchmark.run import BookWindows
        book = books().iloc[:600]
        raw = book[FIELDS].to_numpy()
        dataset = BookWindows(raw, [300], [1], 1., 1.)
        before = dataset[0][0].numpy().copy()
        raw[301:] *= 10
        np.testing.assert_array_equal(before, dataset[0][0].numpy())
        self.assertEqual(before.shape, (128, 40))
        anchor = (raw[300, 0] + raw[300, 2]) / 2
        self.assertAlmostEqual(before[-1, 0], np.log(raw[300, 0] / anchor) * 1e4, places=5)

    def test_both_actual_author_models_have_finite_trainable_outputs(self):
        import torch
        from research.orderbook_benchmark.models import build_model, forward, log_probabilities
        from research.orderbook_benchmark.run import BookWindows
        torch.set_num_threads(2)
        raw = books().iloc[:600][FIELDS].to_numpy()
        dataset = BookWindows(raw, [300, 400], [0, 2], 1., 1.)
        x = torch.stack([dataset[i][0] for i in range(2)])
        for name in ("TLOB", "DeepLOB"):
            torch.manual_seed(42)
            model, probabilities, provenance = build_model(name)
            model.train()
            output = log_probabilities(forward(model, name, x), probabilities)
            self.assertEqual(output.shape, (2, 3))
            self.assertTrue(torch.isfinite(output).all())
            loss = torch.nn.functional.nll_loss(output, torch.tensor([0, 2]))
            loss.backward()
            self.assertTrue(all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None))
            self.assertGreater(provenance["parameters"], 100000)


if __name__ == "__main__":
    unittest.main()
