"""Meaningful checks for causal features, ambiguous outcomes and event auditing."""
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('analysis', Path(__file__).with_name('analyze-flow.py'))
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


class ResearchAnalysisTests(unittest.TestCase):
    def test_both_barriers_in_same_candle_remain_ambiguous(self):
        rows = [dict(open=10000, high=10000, low=10000, close=10000, volume=1) for _ in range(31)]
        rows[1].update(high=10020, low=9980)
        self.assertEqual(analysis.outcome(rows, 0, 1)['first_outcome'], 'ambiguous')
        self.assertEqual(analysis.outcome(rows, 0, -1)['first_outcome'], 'ambiguous')

    def test_timeout_and_signed_short_target(self):
        rows = [dict(open=10000, high=10000, low=10000, close=10000, volume=1) for _ in range(31)]
        self.assertEqual(analysis.outcome(rows, 0, 1)['first_outcome'], 'timeout')
        rows[5].update(low=9980, close=9980)
        self.assertEqual(analysis.outcome(rows, 0, -1)['first_outcome'], 'target')
        self.assertEqual(analysis.outcome(rows, 0, 1)['first_outcome'], 'stop')
        self.assertEqual(analysis.outcome(rows, 0, -1)['first_outcome_candle'], 5)

    def test_pattern_features_do_not_read_future(self):
        rows = [dict(open=10000+i, high=10010+i, low=9990+i, close=10000+i, volume=1) for i in range(180)]
        before = analysis.patterns(rows, 125, [1.]*99)
        for r in rows[126:]:
            r.update(high=999999, low=1, close=500000)
        self.assertEqual(before, analysis.patterns(rows, 125, [1.]*99))

    def test_neutral_band_boundaries(self):
        self.assertEqual(analysis.sign(1), 0)
        self.assertEqual(analysis.sign(-1), 0)
        self.assertEqual(analysis.sign(1.01), 1)
        self.assertEqual(analysis.sign(-1.01), -1)


if __name__ == '__main__':
    unittest.main()
