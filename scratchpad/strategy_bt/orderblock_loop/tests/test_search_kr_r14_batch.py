import csv
import io
import tempfile
import unittest
from pathlib import Path

import numpy as np

import search_crypto as ledger_common
import search_kr_r14_batch as m


def make_symbol(n=400, seed=1, alive=None):
    rng = np.random.default_rng(seed)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    o = np.r_[c[0], c[:-1]] * (1 + rng.normal(0, 0.002, n))
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.005, n)))
    l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.005, n)))
    v = rng.integers(1000, 5000, n).astype(float)
    t = (np.arange(n) + 10_000) * m.DAY_MS
    alive = np.ones(n, bool) if alive is None else alive
    bar = np.arange(n, dtype=np.int64)
    return m.SymbolBars("000001", "x", t, o, h, l, c, v, bar, alive, bar)


class Trials(unittest.TestCase):
    def test_grid_is_exactly_500_and_deterministic(self):
        configs = m.build_configs()
        self.assertEqual(len(configs), 500)
        self.assertEqual(m.grid_sha256(configs), m.grid_sha256(m.build_configs()))

    def test_kr_round_trip_cost_is_31bp(self):
        self.assertAlmostEqual(m.ROUND_TRIP_COST, 0.0031)
        self.assertEqual(m.BONFERRONI_N, m.EXPECTED_LEDGER_ROWS + 500)


class Engine(unittest.TestCase):
    def test_entry_is_next_open_and_time_exit_at_hold(self):
        s = make_symbol()
        entry = np.zeros(s.n, bool)
        entry[50] = True
        trades, cens, gaps = m.simulate(s, m._spec(entry, hold=5))
        self.assertEqual(len(trades), 1)
        tr = trades[0]
        self.assertEqual((tr.e, tr.x), (51, 56))
        self.assertEqual(tr.entry_px, s.o[51])
        self.assertEqual(tr.exit_px, s.o[56])
        self.assertAlmostEqual(tr.net, s.o[56] / s.o[51] - 1 - m.ROUND_TRIP_COST)

    def test_daily_pnl_sums_to_net_trade_return(self):
        s = make_symbol()
        entry = np.zeros(s.n, bool)
        entry[50] = True
        trades, _, _ = m.simulate(s, m._spec(entry, hold=7))
        vec = m.trade_daily_pnl(s, trades[0])
        self.assertAlmostEqual(vec.sum(), trades[0].net, places=12)

    def test_stop_fills_at_min_of_open_and_level(self):
        s = make_symbol(n=60)
        s.l[:] = s.c * 0.999
        s.l[53] = 1.0  # forced gap-through stop on bar 53
        s.o[53] = 50.0
        entry = np.zeros(s.n, bool)
        entry[50] = True
        spec = m._spec(entry, hold=10)
        spec["atr"] = np.full(s.n, 2.0)
        spec["stop_atr"] = 1.0
        trades, _, _ = m.simulate(s, spec)
        self.assertEqual(trades[0].reason, "stop")
        self.assertEqual(trades[0].x, 53)
        self.assertEqual(trades[0].exit_px, 50.0)

    def test_gap_when_exit_day_not_alive_and_censor_at_data_end(self):
        s = make_symbol(n=120)
        s.alive[60:] = False
        entry = np.zeros(s.n, bool)
        entry[50] = True
        trades, cens, gaps = m.simulate(s, m._spec(entry, hold=15))
        self.assertEqual((len(trades), gaps), (0, 1))
        entry2 = np.zeros(s.n, bool)
        entry2[115] = True
        trades2, cens2, _ = m.simulate(make_symbol(n=120), m._spec(entry2, hold=10))
        self.assertEqual((len(trades2), cens2), (0, 1))  # hold runs past data end: censored
        entry3 = np.zeros(s.n, bool)
        entry3[100] = True
        s2 = make_symbol(n=120)
        trades3, cens3, _ = m.simulate(s2, m._spec(entry3, hold=30))
        self.assertEqual((len(trades3), cens3), (0, 1))


class Causality(unittest.TestCase):
    def test_time_series_signals_ignore_future_bars(self):
        full = make_symbol(n=500, seed=3)
        cut = 300
        prefix = make_symbol(n=cut, seed=3)
        prefix.c, prefix.o, prefix.h, prefix.l, prefix.v = (
            full.c[:cut], full.o[:cut], full.h[:cut], full.l[:cut], full.v[:cut])
        st = m.BatchState(symbols=[], universe_n=1, gt=np.arange(500), index_close=np.linspace(100, 200, 500),
                          index_sma={w: np.full(500, np.nan) for w in (60, 120, 200)},
                          close_panel=None, high_panel=None, alive_panel=None,
                          gyear=np.zeros(500, int), accounting={}, input_sha256="")
        st.index_sma = {w: np.full(500, np.nan) for w in (60, 120, 200)}
        st.index_sma[60] = m.pd.Series(st.index_close).rolling(60, min_periods=60).mean().to_numpy()
        st.index_close = st.index_close
        prefix_st = st
        cases = [
            {"family": "REV", "params": {"lookback": 5, "drop_pct": 5, "trend_sma": 200, "hold": 5, "stop_atr": 2}},
            {"family": "VOLSURGE", "params": {"mult": 2, "up_day": True, "hold": 3, "stop_atr": None}},
            {"family": "MATREND", "params": {"sma_n": 20, "regime_sma": 60, "exit_sma": 10, "stop_atr": 3}},
            {"family": "DONCH", "params": {"breakout": 20, "trail_atr": 2, "regime_sma": None, "max_hold": 60}},
            {"family": "VBRK", "params": {"k": 0.5, "trend_sma": 20, "hold": 3, "stop_atr": 2}},
        ]
        for cfg in cases:
            a = m.build_spec(cfg, full, st)["entry"][:cut]
            b = m.build_spec(cfg, prefix, prefix_st)["entry"]
            np.testing.assert_array_equal(a, b, err_msg=cfg["family"])

    def test_future_mutation_does_not_change_past_entries(self):
        base = make_symbol(n=400, seed=9)
        mutated = make_symbol(n=400, seed=9)
        mutated.c[300:] *= 3.0
        mutated.h[300:] *= 3.0
        st = m.BatchState(symbols=[], universe_n=1, gt=np.arange(400), index_close=np.ones(400),
                          index_sma={w: np.ones(400) for w in (60, 120, 200)}, close_panel=None,
                          high_panel=None, alive_panel=None, gyear=np.zeros(400, int),
                          accounting={}, input_sha256="")
        cfg = {"family": "TOM", "params": {"days_remaining": 2, "exit_day": 1, "regime_sma": None}}
        a = m.build_spec(cfg, base, st)["entry"][:300]
        b = m.build_spec(cfg, mutated, st)["entry"][:300]
        np.testing.assert_array_equal(a, b)


class LedgerAppend(unittest.TestCase):
    def _make_ledger(self, rows):
        tmp = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="")
        writer = csv.writer(tmp)
        writer.writerow(ledger_common.FIELDS)
        for i in range(rows):
            writer.writerow([f"x{i}"] + [""] * (len(ledger_common.FIELDS) - 1))
        tmp.close()
        return Path(tmp.name)

    def test_append_adds_rows_and_refuses_on_count_mismatch(self):
        path = self._make_ledger(3)
        rec = [{k: "v" for k in ledger_common.FIELDS}]
        m.append_ledger(rec, expected_rows=3, path=path)
        self.assertEqual(m.ledger_rows(path), 4)
        with self.assertRaises(RuntimeError):
            m.append_ledger(rec, expected_rows=3, path=path)
        self.assertEqual(m.ledger_rows(path), 4)


if __name__ == "__main__":
    unittest.main()
