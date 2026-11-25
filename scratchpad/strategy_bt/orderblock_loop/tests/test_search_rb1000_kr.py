import unittest
from datetime import date

import numpy as np

import search_rb1000_kr as m


class GridTests(unittest.TestCase):
    def test_grid_exact_200_unique(self):
        configs = m.build_configs()
        self.assertEqual(len(configs), 200)
        self.assertEqual(len({repr(sorted(c.items())) for c in configs}), 200)

    def test_family_counts(self):
        counts = {}
        for c in m.build_configs():
            counts[c["family"]] = counts.get(c["family"], 0) + 1
        self.assertEqual(counts, {"GAPUP": 48, "LIMIT": 16, "PREHOL": 8, "OPEXP": 16,
                                  "WKDAY": 4, "GAPDN": 24, "RGM": 48, "ETFTR": 36})


class JumpRuleTests(unittest.TestCase):
    def _arrays(self, closes, vols=None):
        n = len(closes)
        c = np.array(closes, dtype=float)
        t = np.arange(n, dtype=np.int64) * m.DAY_MS
        v = np.array(vols if vols is not None else [100.0] * n, dtype=float)
        return t, c.copy(), c.copy(), c.copy(), c.copy(), v

    def test_split_ratio_detection(self):
        self.assertEqual(m.split_ratio(0.5), 2)
        self.assertEqual(m.split_ratio(0.2), 5)
        self.assertEqual(m.split_ratio(2.0), 2)
        self.assertEqual(m.split_ratio(0.5556), 0)

    def test_split_is_back_adjusted_and_volume_scaled(self):
        t, o, h, l, c, v = self._arrays([100, 100, 100, 50, 51, 52], [10, 10, 10, 20, 20, 20])
        t2, o2, h2, l2, c2, v2, rep = m.adjust_corporate_actions(t, o, h, l, c, v)
        self.assertEqual(rep["split_adjusted"], 1)
        self.assertFalse(rep["truncated"])
        self.assertEqual(rep["residual_jumps"], 0)
        self.assertAlmostEqual(c2[2], 50.0)          # continuity at the split bar
        self.assertAlmostEqual(c2[0], 50.0)           # prefix scaled by 1/2
        self.assertAlmostEqual(v2[0], 20.0)           # volume doubled
        self.assertEqual(len(c2), 6)

    def test_unmatched_jump_truncates_history(self):
        t, o, h, l, c, v = self._arrays([100, 101, 102, 70, 71, 72, 73, 74])
        t2, o2, h2, l2, c2, v2, rep = m.adjust_corporate_actions(t, o, h, l, c, v)
        self.assertTrue(rep["truncated"])
        self.assertEqual(rep["rows_dropped"], 3)
        self.assertEqual(len(c2), 5)
        self.assertEqual(rep["residual_jumps"], 0)

    def test_small_moves_untouched(self):
        t, o, h, l, c, v = self._arrays([100, 105, 110, 99])
        _, _, _, _, c2, _, rep = m.adjust_corporate_actions(t, o, h, l, c, v)
        self.assertEqual(rep["jumps"], 0)
        np.testing.assert_allclose(c2, c)


class UnitTests(unittest.TestCase):
    def test_position_vec_costs_and_shape(self):
        O = np.array([10.0, 11.0, 12.0, 13.0])
        C = np.array([10.5, 11.5, 12.5, 13.5])
        vec, net = m.position_vec(O, C, 0, 2, m.BUY_COST, m.SELL_COST)
        self.assertEqual(len(vec), 3)
        self.assertAlmostEqual(net, 12 / 10 - 1 - m.ROUND_TRIP_COST)
        self.assertAlmostEqual(vec[0], 10.5 / 10 - 1 - m.BUY_COST)

    def test_position_vec_rejects_nan_path(self):
        O = np.array([10.0, 11.0, 12.0])
        C = np.array([10.0, np.nan, 12.0])
        self.assertIsNone(m.position_vec(O, C, 0, 2, 0.0, 0.0))

    def test_state_pairs_fill_next_bar(self):
        enter = np.array([False, True, False, False, False, False])
        exit_ = np.array([False, False, False, True, False, False])
        pairs, open_end = m.state_pairs(enter, exit_, 0, 6)
        self.assertEqual(pairs, [(2, 4)])
        self.assertFalse(open_end)
        pairs1, _ = m.state_pairs(enter, exit_, 1, 6)
        self.assertEqual(pairs1, [(3, 5)])

    def test_holiday_eve_and_option_expiry(self):
        # Thu 2018-05-24 is followed by Mon 2018-05-28: Fri 05-25 is a missing weekday (holiday)
        dates = np.array(["2018-05-22", "2018-05-23", "2018-05-24", "2018-05-28"], dtype="datetime64[D]")
        flags = m.holiday_eve_flags(dates)
        self.assertEqual(list(flags), [False, False, True, False])  # Fri 05-25 missing before Mon 05-28
        dates2 = np.array([np.datetime64(d) for d in
                           ["2018-06-13", "2018-06-14", "2018-06-15", "2018-06-18"]], dtype="datetime64[D]")
        self.assertEqual(list(m.holiday_eve_flags(dates2)), [False, False, False, False])
        # 2018-06: 1st Thursday 06-07, 2nd Thursday 06-14 -> expiry index of 06-14
        days = np.array([np.datetime64(x) for x in
                         ["2018-06-01", "2018-06-07", "2018-06-13", "2018-06-14", "2018-06-15"]],
                        dtype="datetime64[D]")
        self.assertEqual(m.option_expiry_indices(days), [3])
        # when 2nd Thursday is absent (holiday), expiry moves to prior trading day
        days2 = np.array([np.datetime64(x) for x in
                          ["2018-06-01", "2018-06-07", "2018-06-13", "2018-06-15"]], dtype="datetime64[D]")
        self.assertEqual(m.option_expiry_indices(days2), [2])



class SyntheticEvaluationTests(unittest.TestCase):
    """Runs every family's full evaluation path on a synthetic panel (no real data)."""

    def _panel(self):
        rng = np.random.default_rng(7)
        n_days, n_stocks = 900, 60
        start = np.datetime64("2012-01-02")
        day_ms = m.DAY_MS
        base_day = int(start.astype("datetime64[D]").astype(np.int64))
        t = (np.arange(base_day, base_day + n_days, dtype=np.int64)) * day_ms
        records = []
        for s in range(n_stocks):
            ret = rng.normal(0.0004, 0.02, n_days)
            ret[rng.random(n_days) < 0.01] += rng.choice([0.05, -0.06], 1)[0]
            close = 10000 * np.exp(np.cumsum(ret))
            open_ = close * (1 + rng.normal(0, 0.005, n_days))
            high = np.maximum(open_, close) * 1.01
            low = np.minimum(open_, close) * 0.99
            vol = rng.integers(1000, 5000, n_days).astype(float)
            records.append({"symbol": f"S{s:03d}", "t": t, "o": open_, "h": high, "l": low,
                            "c": close, "v": vol, "from_day": base_day,
                            "through_day": base_day + n_days + 10})
        idx_close = 2000 * np.exp(np.cumsum(rng.normal(0.0002, 0.01, n_days)))
        index_series = {code: {"t": t, "o": idx_close * 0.999, "c": idx_close}
                        for code in ("KS11", "KQ11", "KS200")}
        return m.Panel(records, index_series)

    def test_every_family_evaluates_without_error(self):
        P = self._panel()
        m.STATE = P
        seen = set()
        for i, cfg in enumerate(m.build_configs()):
            if cfg["family"] in seen:
                continue
            seen.add(cfg["family"])
            res = m.evaluate_config(i, cfg)
            self.assertEqual(res["status"], "ok", res)
            self.assertIn("checks", res)
        self.assertEqual(len(seen), 8)


if __name__ == "__main__":
    unittest.main()
