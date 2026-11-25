from __future__ import annotations

import csv
import os
import tempfile
import unittest
from pathlib import Path

import numpy as np

import search_crypto_rb500 as rb
from crypto import Bar, FundingEvent, Setup, Zone, simulate_trade


def synthetic_bars(n=1200, tf_ms=3_600_000, seed=7, start=1_577_836_800_000):
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 1.0, n)) + 5 * np.sin(np.arange(n) / 40)
    open_ = np.concatenate(([close[0]], close[:-1]))
    high = np.maximum(open_, close) + np.abs(rng.normal(0.5, 0.2, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0.5, 0.2, n))
    vol = rng.uniform(100, 300, n)
    return [Bar(start + i * tf_ms, float(open_[i]), float(high[i]), float(low[i]),
                float(close[i]), float(vol[i])) for i in range(n)]


def panel_from(bars, tf_ms=3_600_000, symbol="SYN"):
    return rb.Panel(symbol, bars, {}, tf_ms)


class GridTests(unittest.TestCase):
    def test_exactly_500_configs_with_family_quotas(self):
        grid = rb.build_grid()
        self.assertEqual(len(grid), 500)
        counts = {}
        for c in grid:
            counts[c["family"]] = counts.get(c["family"], 0) + 1
        self.assertEqual(sorted(counts.values()), sorted(q for *_, q in rb.FAMILY_SPECS))

    def test_grid_is_deterministic_and_unique(self):
        a, b = rb.build_grid(), rb.build_grid()
        self.assertEqual(rb.grid_sha256(a), rb.grid_sha256(b))
        keys = {tuple(sorted((k, str(v)) for k, v in c.items() if k != "config_id")) for c in a}
        self.assertEqual(len(keys), 500)

    def test_grid_hash_matches_prereg(self):
        self.assertEqual(rb.grid_sha256(rb.build_grid()),
                         "523c23707aae2eb8ad47b81b91a9326f1e04488ff26b11f0bd34e3d4eec45be2")


class LookaheadTests(unittest.TestCase):
    def test_every_family_signal_ignores_future_bars(self):
        bars = synthetic_bars()
        full = panel_from(bars)
        cut = 900
        short = panel_from(bars[:cut])
        for family in rb.DISPATCH:
            c = next(x for x in rb.GRID if x["family"] == family)
            with self.subTest(family=family):
                a = rb.DISPATCH[family](full, c)
                b = rb.DISPATCH[family](short, c)
                self.assertTrue(np.array_equal(a[:cut], b), family)

    def test_cross_sectional_rotation_ignores_future_bars(self):
        bars_by_sym = {s: synthetic_bars(seed=i + 1, tf_ms=rb.TF_MS["4h"]) for i, s in
                       enumerate(["BTCUSDT", "AAAUSDT", "BBBUSDT", "CCCUSDT"])}
        full = {s: panel_from(b, rb.TF_MS["4h"], s) for s, b in bars_by_sym.items()}
        cut = 700
        short = {s: panel_from(b[:cut], rb.TF_MS["4h"], s) for s, b in bars_by_sym.items()}
        c = {"top_k": 2, "rs_lookback_bars": 42, "regime_sma_bars": 50}
        a = rb._btc_regime_rs(full, c)
        b = rb._btc_regime_rs(short, c)
        for s in ("AAAUSDT", "BBBUSDT", "CCCUSDT"):
            self.assertTrue(np.array_equal(a[s][:cut - 1], b[s][:cut - 1]), s)


class TradeMechanicsTests(unittest.TestCase):
    def test_entry_is_next_bar_open_and_round_trip_cost_is_12bp(self):
        bars = synthetic_bars(n=200)
        p = panel_from(bars)
        i = 150
        dirs = np.zeros(len(bars), dtype=np.int8)
        dirs[i] = 1
        trades, stats = rb.simulate_symbol(p, dirs, {"horizon_bars": 24, "reward_r": 1.0,
                                                     "stop_atr": 2.0})
        self.assertEqual(len(trades), 0)  # signal inside warm-up is never traded
        # direct check: entry price equals next open and cost is 12bp round trip
        a = p.atr[i]
        entry = bars[i + 1].open
        setup = Setup(Zone(i, i, "long", entry - 2 * a, entry, a), i + 1, entry,
                      entry - 2 * a, entry + 2 * a)
        trade = simulate_trade(bars, setup, funding={}, max_holding_bars=24,
                               fee_bps_per_side=rb.FEE_BPS, slippage_bps_per_side=rb.SLIP_BPS,
                               bar_duration_ms=3_600_000, validated=True)
        self.assertIsNotNone(trade)
        self.assertAlmostEqual(trade.cost_bps, 12.0)
        self.assertEqual(trade.setup.entry_price, bars[i + 1].open)

    def test_funding_sign_long_pays_positive_rate(self):
        bars = synthetic_bars(n=200)
        ts = bars[101].timestamp + 1_000
        funding = {ts: FundingEvent(ts, 0.001, bars[101].open)}
        entry = bars[100].open
        setup = Setup(Zone(99, 99, "long", entry - 1, entry, 1.0), 100, entry, entry - 2, entry + 50)
        trade = simulate_trade(bars, setup, funding=funding, max_holding_bars=24,
                               fee_bps_per_side=0, slippage_bps_per_side=0,
                               bar_duration_ms=3_600_000, validated=True,
                               funding_order_policy="adverse_only")
        self.assertIsNotNone(trade)
        self.assertLess(trade.funding_return, 0)

    def test_no_overlapping_trades_per_symbol(self):
        bars = synthetic_bars(n=1600)
        p = panel_from(bars)
        dirs = np.zeros(len(bars), dtype=np.int8)
        dirs[600:1400] = 1  # many signals in a row
        c = {"horizon_bars": 24, "reward_r": 2.0, "stop_atr": 2.0}
        trades, stats = rb.simulate_symbol(p, dirs, c)
        self.assertGreater(stats["skipped_overlap"], 0)  # dense signals were suppressed
        accounted = (len(trades) + stats["skipped_overlap"] + stats["censored_no_exit"]
                     + stats["unscorable_funding"] + stats["reconcile_error"])
        self.assertEqual(accounted, 800)  # every one of the 800 signals is accounted for once


class LedgerTests(unittest.TestCase):
    def test_append_writes_all_rows_once_and_refuses_on_count_change(self):
        import search_crypto as common
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                csv.DictWriter(stream, fieldnames=common.FIELDS).writeheader()
            rec = {f: "" for f in common.FIELDS}
            rec.update({"trial_id": "t", "round": rb.ROUND, "metric": "{}"})
            n = rb.append_ledger_locked([rec, rec], 0, path)
            self.assertEqual(n, 2)
            self.assertEqual(rb._ledger_rows(path), 2)
            with self.assertRaises(RuntimeError):
                rb.append_ledger_locked([rec], 0, path)
            self.assertEqual(rb._ledger_rows(path), 2)


if __name__ == "__main__":
    unittest.main()
