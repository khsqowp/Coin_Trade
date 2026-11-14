import sys, unittest
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from us.common import topk_mask, var_exit_events, month_turn_days, fixed_events, COST
from lib import data


def toy_panel(close, high=None, low=None, open_=None):
    T, N = close.shape
    dates = pd.bdate_range("2020-01-01", periods=T)
    c = close.astype(float)
    return data.Panel(dates, [f"S{i}" for i in range(N)], [f"S{i}" for i in range(N)], np.array(["US"] * N, dtype=object),
                      c if open_ is None else open_, c if high is None else high, c if low is None else low, c,
                      np.full((T, N), 1e6), c, "us")


class T(unittest.TestCase):
    def test_topk(self):
        v = np.array([[1.0, 5.0, 3.0, 4.0, np.nan]])
        self.assertEqual(topk_mask(v, 2).tolist(), [[False, True, False, True, False]])

    def test_var_exit_first_hit_and_default(self):
        c = np.array([[100, 100], [100, 100], [110, 100], [120, 100], [130, 100], [140, 100], [150, 100]], float)
        P = toy_panel(c)
        mask = np.zeros(c.shape, bool); mask[0, 0] = mask[0, 1] = True
        cond = lambda ti, ci, k: (k == 2) & (ci == 0)   # col 0 exits at k=2, col 1 runs to H=4
        ev = var_exit_events(P, mask, 4, cond)
        got = {int(ci): g for ci, g in zip(ev.ci, ev.gross)}
        self.assertAlmostEqual(got[0], 0.10)     # close[2]/close[0]
        self.assertAlmostEqual(got[1], 0.0)      # col 1 flat to t+4
        self.assertTrue(np.all(ev.x_slot > ev.e_slot))

    def test_var_exit_drops_past_end(self):
        c = np.full((5, 1), 100.0)
        P = toy_panel(c)
        mask = np.zeros(c.shape, bool); mask[3, 0] = True
        self.assertEqual(len(var_exit_events(P, mask, 3, lambda ti, ci, k: np.zeros(len(ti), bool))), 0)

    def test_month_turn(self):
        d = pd.bdate_range("2021-01-01", "2021-04-30")
        idx = month_turn_days(d, 2)
        self.assertEqual([str(d[i].date()) for i in idx], ["2021-01-28", "2021-02-25", "2021-03-30", "2021-04-29"])

    def test_fixed_events_open_close_same_day(self):
        o = np.array([[100.0], [90.0], [100.0]]); c = np.array([[100.0], [99.0], [100.0]])
        P = toy_panel(c, open_=o)
        mask = np.zeros(c.shape, bool); mask[1, 0] = True
        ev = fixed_events(P, mask, ("open", 0), ("close", 0))
        self.assertAlmostEqual(ev.gross[0], 0.10)
        self.assertAlmostEqual(ev.cost[0], COST.roundtrip())


if __name__ == "__main__":
    unittest.main()
