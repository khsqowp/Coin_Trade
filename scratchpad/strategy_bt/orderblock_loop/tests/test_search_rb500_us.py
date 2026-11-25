import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

import rb500_us_grid as grid
import search_rb500_us as r

ROOT = Path(__file__).resolve().parents[1]


def _flat(n=6, price=100.0):
    o = np.full(n, price)
    return o.copy(), o + 1, o - 1, o.copy()


class GridTests(unittest.TestCase):
    def test_exactly_500_unique_configs_with_fixed_hash(self):
        configs = grid.build_grid()
        self.assertEqual(len(configs), 500)
        self.assertEqual(len({tuple(sorted(c.items())) for c in configs}), 500)
        self.assertEqual(grid.grid_sha256(configs),
                         "41b901a96c2cda2121ec2d21595bf16f294fbc9b490a00f475109c3d8bc14b2c")


class SimulationTests(unittest.TestCase):
    def test_time_exit_next_open_entry_and_20bp_cost(self):
        o, h, l, c = _flat()
        o[1], c[2] = 100.0, 110.0
        sig = np.zeros(6, bool)
        sig[0] = True
        acc = r.simulate(sig, None, 0, 2, o, h, l, c, np.ones(6))
        self.assertEqual(acc[r.N], 1)
        self.assertAlmostEqual(acc[r.SUM], 110 / 100 - 1 - 0.0020)

    def test_stop_hit_intrabar_exits_at_stop_price(self):
        o, h, l, c = _flat()
        o[1] = 100.0
        l[1] = 97.0          # stop = 100 - 2*1 = 98
        sig = np.zeros(6, bool)
        sig[0] = True
        acc = r.simulate(sig, None, 2, 5, o, h, l, c, np.ones(6))
        self.assertAlmostEqual(acc[r.SUM], 98 / 100 - 1 - 0.0020)

    def test_gap_below_stop_exits_at_open(self):
        o, h, l, c = _flat()
        o[1], o[2] = 100.0, 95.0
        l[2] = 94.0
        sig = np.zeros(6, bool)
        sig[0] = True
        acc = r.simulate(sig, None, 2, 5, o, h, l, c, np.ones(6))
        self.assertAlmostEqual(acc[r.SUM], 95 / 100 - 1 - 0.0020)

    def test_rule_exit_fills_at_next_open(self):
        o, h, l, c = _flat()
        o[1], o[2] = 100.0, 104.0  # rule true at close of bar 1 -> exit at open of bar 2
        rule = np.zeros(6, bool)
        rule[1] = True
        sig = np.zeros(6, bool)
        sig[0] = True
        acc = r.simulate(sig, rule, 0, 5, o, h, l, c, np.ones(6))
        self.assertAlmostEqual(acc[r.SUM], 104 / 100 - 1 - 0.0020)

    def test_right_censored_trade_is_not_counted(self):
        o, h, l, c = _flat()
        sig = np.zeros(6, bool)
        sig[3] = True
        acc = r.simulate(sig, None, 0, 10, o, h, l, c, np.ones(6))
        self.assertEqual(acc[r.N], 0)
        self.assertEqual(acc[r.CENS], 1)


class CausalityTests(unittest.TestCase):
    def test_signals_at_or_before_t_do_not_change_when_future_bars_change(self):
        rng = np.random.default_rng(7)
        n = 400
        c = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, n)))
        o = c * (1 + rng.normal(0, 0.005, n))
        h = np.maximum(o, c) * 1.01
        l = np.minimum(o, c) * 0.99
        v = rng.uniform(1e5, 1e6, n)
        cfg = {"config_id": 1, "family": "F03_RSI2_PULLBACK", "rsi_thr": 10, "trend_sma": 100,
               "max_hold": 5, "stop_atr": 2}
        ind = r.symbol_indicators(o, h, l, c, v)
        base_sig, _, _, _ = r.build_signal(cfg, ind, 0, {"last_k": {}, "breadth_ok": None})
        t = 250
        c2, o2, h2, l2, v2 = c.copy(), o.copy(), h.copy(), l.copy(), v.copy()
        c2[t + 1:] *= 1.5
        o2[t + 1:] *= 0.5
        h2[t + 1:] *= 2
        l2[t + 1:] *= 0.3
        ind2 = r.symbol_indicators(o2, h2, l2, c2, v2)
        sig2, _, _, _ = r.build_signal(cfg, ind2, 0, {"last_k": {}, "breadth_ok": None})
        self.assertTrue(np.array_equal(base_sig[:t + 1], sig2[:t + 1]))


class LoaderCutoffTests(unittest.TestCase):
    def test_loader_never_returns_rows_after_cutoff(self):
        dates = pd.to_datetime(["2018-10-24", "2018-10-25", "2018-10-26", "2018-10-29", "2018-11-01"])
        df = pd.DataFrame({"ticker": "AAA", "date": dates, "open": 10.0, "high": 11.0, "low": 9.0,
                           "close": 10.5, "adj_close": 10.5, "volume": 1000.0})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "panel.parquet"
            df.to_parquet(path)
            with patch.object(r, "PARQUET", path):
                frames, failures = r.load_frames(["AAA"])
        self.assertIn("AAA", frames)
        self.assertLessEqual(frames["AAA"]["open_time"].max(),
                             pd.Timestamp("2018-10-26", tz="UTC").value // 10**6)
        self.assertEqual(len(frames["AAA"]), 3)


class LedgerTests(unittest.TestCase):
    def test_append_only_with_denominator_guard(self):
        header = ",".join(r.TRIAL_FIELDS) + "\n"
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "TRAIN_TRIALS.csv"
            ledger.write_text(header + "old,R0,US,t,{},h,c,p,{},,n\n", encoding="utf-8")
            runs = Path(tmp) / "runs"
            row = {k: "x" for k in r.TRIAL_FIELDS}
            with patch.object(r, "LEDGER", ledger), patch.object(r, "RUNS", runs):
                r.append_ledger([row, row], expected_before=1)
                self.assertEqual(r.ledger_rows_count(ledger), 3)
                with self.assertRaises(RuntimeError):
                    r.append_ledger([row], expected_before=1)
                self.assertEqual(r.ledger_rows_count(ledger), 3)
            text = ledger.read_text(encoding="utf-8")
            self.assertIn("old,R0", text)
            self.assertEqual(text.count("\n"), 4)  # header + old + 2 appended


if __name__ == "__main__":
    unittest.main()
