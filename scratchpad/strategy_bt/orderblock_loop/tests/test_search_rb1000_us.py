"""Synthetic and guard tests for the RB1000-US runner (PREREG_RB1000_US.md section 8)."""
from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import rb1000_us_grid as grid  # noqa: E402
import search_rb1000_us as rb  # noqa: E402
import search_rb500_us as base  # noqa: E402


def _bars(opens, highs, lows, closes):
    return (np.asarray(opens, float), np.asarray(highs, float), np.asarray(lows, float),
            np.asarray(closes, float))


class GridTests(unittest.TestCase):
    def test_exactly_200_configs_with_expected_family_counts(self):
        configs = grid.build_grid()
        self.assertEqual(len(configs), 200)
        counts = {}
        for c in configs:
            counts[c["family"]] = counts.get(c["family"], 0) + 1
        self.assertEqual(counts, grid.EXPECTED_COUNTS)

    def test_grid_hash_matches_prereg(self):
        self.assertEqual(grid.grid_sha256(), rb.PREREG_GRID_SHA256)


class SimulationRuleTests(unittest.TestCase):
    def setUp(self):
        # bar index: 0..6; signal at 0 -> entry at open of bar 1
        self.o, self.h, self.l, self.c = _bars(
            opens=[10, 10, 11, 12, 12, 12, 12],
            highs=[10, 12, 13, 13, 13, 13, 13],
            lows=[9, 9.5, 10.5, 11.5, 11.5, 11.5, 11.5],
            closes=[10, 11, 12, 12.5, 12.5, 12.5, 12.5])
        self.atr = np.full(7, 1.0)
        self.rc = rb.COST_RT

    def test_entry_is_next_bar_open_and_time_exit_at_close(self):
        sig = np.zeros(7, bool)
        sig[0] = True
        E, X, NET, counts = rb.simulate_trades(sig, None, 0, 2, self.o, self.h, self.l, self.c, self.atr)
        self.assertEqual(E.tolist(), [1])
        self.assertEqual(X.tolist(), [2])  # hold 2 bars: entry bar 1, exit close of bar 2
        self.assertAlmostEqual(NET[0], self.c[2] / self.o[1] - 1 - self.rc)

    def test_cost_is_twenty_bp_round_trip(self):
        self.assertAlmostEqual(rb.COST_RT, 0.0020)

    def test_rule_exit_fills_next_open(self):
        sig = np.zeros(7, bool)
        sig[0] = True
        rule = np.zeros(7, bool)
        rule[2] = True  # close of bar 2 -> exit at open of bar 3
        E, X, NET, _ = rb.simulate_trades(sig, rule, 0, 10, self.o, self.h, self.l, self.c, self.atr)
        self.assertEqual(X.tolist(), [3])
        self.assertAlmostEqual(NET[0], self.o[3] / self.o[1] - 1 - self.rc)

    def test_stop_gap_exits_at_open_and_intrabar_at_stop(self):
        o = np.array([10, 10, 9.0, 10, 10, 10, 10.0])
        h = np.array([10, 10.5, 9.2, 10.5, 10.5, 10.5, 10.5])
        l = np.array([10, 9.5, 8.0, 9.5, 9.5, 9.5, 9.5])
        c = np.array([10, 10, 9.0, 10, 10, 10, 10.0])
        atr = np.full(7, 1.0)
        sig = np.zeros(7, bool)
        sig[0] = True
        # stop = entry(10) - 1*1 = 9. Bar 2 opens at 9.0 (<= stop) -> gap exit at 9.0
        _, X, NET, _ = rb.simulate_trades(sig, None, 1, 5, o, h, l, c, atr)
        self.assertEqual(X.tolist(), [2])
        self.assertAlmostEqual(NET[0], 9.0 / 10.0 - 1 - self.rc)
        # intrabar stop: open above stop, low through stop -> exit at stop price
        o2 = np.array([10, 10, 9.5, 10, 10, 10, 10.0])
        l2 = np.array([10, 9.5, 8.5, 9.5, 9.5, 9.5, 9.5])
        _, X2, NET2, _ = rb.simulate_trades(sig, None, 1, 5, o2, h, l2, c, atr)
        self.assertEqual(X2.tolist(), [2])
        self.assertAlmostEqual(NET2[0], 9.0 / 10.0 - 1 - self.rc)

    def test_entry_at_or_below_stop_is_ignored(self):
        o = np.array([10, 8.5, 9, 10, 10, 10, 10.0])
        sig = np.zeros(7, bool)
        sig[0] = True
        # degenerate ATR of zero puts the stop at the entry price -> entry <= stop -> ignored
        _, X, _, counts = rb.simulate_trades(sig, None, 1, 2, o, o + 0.5, o - 0.5, o, np.zeros(7))
        self.assertEqual(X.size, 0)
        self.assertEqual(counts[2], 1)

    def test_matches_rb500_engine_on_random_bars(self):
        rng = np.random.default_rng(7)
        T = 400
        c = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, T)))
        o = c * np.exp(rng.normal(0, 0.003, T))
        h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.004, T)))
        l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.004, T)))
        atr = pd.Series(h - l).rolling(14, min_periods=14).mean().to_numpy()
        sig = rng.random(T) < 0.05
        rule = rng.random(T) < 0.03
        for stop_k, hold, rl in ((0, 5, None), (2, 10, rule), (3, 1000, rule)):
            E, X, NET, _ = rb.simulate_trades(sig, rl, stop_k, hold, o, h, l, c, atr)
            acc = base.simulate(sig, rl, stop_k, hold, o, h, l, c, atr)
            self.assertEqual(int(acc[base.N]), NET.size)
            self.assertAlmostEqual(float(acc[base.SUM]), float(NET.sum()), places=9)


class CausalityTests(unittest.TestCase):
    def test_vix_state_signal_unchanged_by_future_values(self):
        T = 400
        rng = np.random.default_rng(3)
        vix = 15 + np.abs(np.cumsum(rng.normal(0, 0.8, T)))
        W = {"spy": 0, "vix": vix.copy()}
        cfg = {"mode": "pct80", "confirm_d": 3}
        before = rb.legs_l06(cfg, {**W, "vix": vix})[0][0]
        cut = 250
        vix2 = vix.copy()
        vix2[cut + 1:] = 1000.0
        after = rb.legs_l06(cfg, {**W, "vix": vix2})[0][0]
        self.assertTrue(np.array_equal(before[: cut + 1], after[: cut + 1]))

    def test_spike_reversal_uses_only_current_and_prior_close(self):
        vix = np.array([20, 31, 28, 26, 40.0])
        W = {"spy": 0, "vix": vix}
        sig, _, _, _ = rb.legs_l07({"vix_thr": 25, "hold_d": 5}, W)[0]
        self.assertEqual(np.flatnonzero(sig).tolist(), [2, 3])

    def test_vix_missing_day_turns_regime_off(self):
        vix = np.array([10, 10, np.nan, 10, 10.0])
        W = {"spy": 0, "vix": vix}
        sig, rule, _, _ = rb.legs_l06({"mode": "level20", "confirm_d": 1}, W)[0]
        self.assertTrue(rule[2])  # NaN -> rule exit (conservative)
        self.assertEqual(np.flatnonzero(sig).tolist(), [0, 3])


class CalendarTests(unittest.TestCase):
    def test_third_friday_selected_and_holiday_shift(self):
        days = pd.bdate_range("2018-01-01", "2018-12-31")
        idx = rb.third_fridays(pd.DatetimeIndex(days))
        dec = [days[i] for i in idx if days[i].year == 2018 and days[i].month == 12]
        self.assertEqual(dec[0], pd.Timestamp("2018-12-21"))
        # remove the 3rd Friday (holiday) -> expiry is the prior trading day
        holiday = pd.Timestamp("2018-12-21")
        trading = pd.DatetimeIndex([d for d in days if d != holiday])
        idx2 = rb.third_fridays(trading)
        dec2 = [trading[i] for i in idx2 if trading[i].year == 2018 and trading[i].month == 12]
        self.assertEqual(dec2[0], pd.Timestamp("2018-12-20"))

    def test_opex_leg_enters_pre_days_before_expiry(self):
        dates = pd.DatetimeIndex(pd.bdate_range("2017-01-02", "2017-06-30"))
        C = np.linspace(100, 200, len(dates))[None, :]
        W = {"C": C, "spy": 0, "opex": rb.third_fridays(dates)}
        cfg = {"pre_days": 3, "hold_d": 2, "trend": "none"}
        sig, rule, stop_k, hold = rb.legs_l02(cfg, W)[0]
        self.assertIsNone(rule)
        self.assertEqual(hold, 2)
        # opex 2017-03-17 (third Friday); entry = opex - 3 trading days; signal the bar before entry
        o_idx = dates.get_loc(pd.Timestamp("2017-03-17"))
        self.assertTrue(sig[o_idx - 3 - 1])
        self.assertFalse(sig[o_idx - 3])

    def test_yearend_excludes_cut_year(self):
        dates = pd.DatetimeIndex(pd.bdate_range("2017-06-01", "2018-10-26"))
        C = np.linspace(100, 200, len(dates))[None, :]
        W = {"C": C, "spy": 0, "dates": dates}
        sig, _, _, _ = rb.legs_l12({"entry_before_ye": 2, "hold_d": 10, "trend": "none"}, W)[0]
        signalled = dates[np.flatnonzero(sig)]
        self.assertEqual(len(signalled), 1)  # only the 2017 year-end (2018 is partial)
        self.assertEqual(signalled[0].year, 2017)


class StatisticsTests(unittest.TestCase):
    def test_top3_exclusion_removes_largest_contributors(self):
        sym = np.array([0] * 10 + [1] * 10 + [2] * 10 + [3] * 10 + [4] * 10)
        net = np.concatenate([np.full(10, 0.05), np.full(10, 0.04), np.full(10, 0.03),
                              np.full(10, 0.02), np.full(10, -0.01)])
        stats, names = rb.top3_check(sym, net, ["A", "B", "C", "D", "E"])
        self.assertEqual(names, ["A", "B", "C"])
        self.assertEqual(stats["n"], 20)

    def test_single_instrument_top3_is_not_applicable(self):
        stats, names = rb.top3_check(np.zeros(100, int), np.full(100, 0.01), ["SPY"])
        self.assertIsNone(stats)
        self.assertEqual(names, [])

    def test_cluster_p_collapses_same_entry_dates(self):
        E = np.repeat(np.arange(10), 20)
        net = np.repeat(np.linspace(-0.01, 0.02, 10), 20)
        p = rb.cluster_p(E, net)
        self.assertIsNotNone(p)
        self.assertGreater(p, 0.0)

    def test_evaluate_applies_bonferroni_denominator(self):
        rec = {
            "base": {"n": 200, "pf": 1.6, "expectancy_bp": 80.0, "wilson_lower": 0.5, "breakeven": 0.4,
                     "p_raw": 1e-7},
            "delay": {"n": 200, "pf": 1.6, "expectancy_bp": 80.0, "wilson_lower": 0.5, "breakeven": 0.4,
                      "p_raw": 1e-7},
            "cost2x": {"n": 200, "pf": 1.6, "expectancy_bp": 80.0, "wilson_lower": 0.5, "breakeven": 0.4,
                       "p_raw": 1e-7},
            "top3": {"n": 200, "pf": 1.6, "expectancy_bp": 80.0, "wilson_lower": 0.5, "breakeven": 0.4,
                     "p_raw": 1e-7},
            "p_cluster": 0.01, "year": {"year_pass": True},
        }
        ok = rb.evaluate(rec, 4618)
        self.assertTrue(ok["candidate"])
        self.assertAlmostEqual(ok["bonferroni_thr"], 0.05 / 4618)
        rec["base"]["p_raw"] = 0.05 / 4618 * 2
        self.assertFalse(rb.evaluate(rec, 4618)["screen_pass"])
        rec["base"]["p_raw"] = 1e-7
        rec["top3"] = None
        self.assertFalse(rb.evaluate(rec, 4618)["candidate"])

    def test_beta_recovers_known_slope(self):
        rng = np.random.default_rng(11)
        m = rng.normal(0, 0.01, 300)
        r = 2.0 * m[None, :]
        beta = rb._beta(r, np.broadcast_to(m, r.shape), 60)
        self.assertTrue(np.allclose(beta[0, 60:], 2.0, atol=1e-9))


class LedgerAndDataTests(unittest.TestCase):
    def test_append_ledger_is_append_only_and_uses_locked_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            ledger = tmp / "TRAIN_TRIALS.csv"
            with ledger.open("w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(rb.TRIAL_FIELDS)
                w.writerow(["x"] * len(rb.TRIAL_FIELDS))
            with mock.patch.object(rb, "LEDGER", ledger), mock.patch.object(rb, "RUNS", tmp / "runs"):
                seen = {}

                def make(count):
                    seen["count"] = count
                    return [{k: "y" for k in rb.TRIAL_FIELDS}]

                got = rb.append_ledger(make)
                self.assertEqual(got, 1)
                self.assertEqual(seen["count"], 1)
                self.assertEqual(rb.ledger_rows_count(ledger), 2)
                # original row untouched
                lines = ledger.read_text().splitlines()
                self.assertTrue(lines[1].startswith("x,"))

    def test_real_loaders_never_return_post_cutoff_rows(self):
        etf = rb.ETF_PARQUET
        fred = rb.FRED_PARQUET
        if not (etf.exists() and fred.exists()):
            self.skipTest("external data not present")
        frames, _ = rb.load_etf_frames(["SPY"])
        self.assertIn("SPY", frames)
        self.assertLessEqual(frames["SPY"]["open_time"].max() // 1, pd.Timestamp(rb.CUTOFF).value // 10**6)
        f = rb.load_fred()
        self.assertLessEqual(f["VIXCLS"].index.max(), rb.CUTOFF)
        self.assertLessEqual(f["T10Y2Y"].index.max(), rb.CUTOFF)


if __name__ == "__main__":
    unittest.main()
