from __future__ import annotations

import unittest

import numpy as np

import search_coinb_rb1000 as cb
import search_crypto_rb500 as rb
from crypto import Bar

HOUR = 3_600_000
H4 = 14_400_000
T0 = 1_577_836_800_000  # 2020-01-01T00:00Z


def bars_from(close, tf_ms, start=T0, vol=None, seed=0):
    rng = np.random.default_rng(seed)
    n = len(close)
    open_ = np.concatenate(([close[0]], close[:-1]))
    high = np.maximum(open_, close) + np.abs(rng.normal(0.4, 0.1, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0.4, 0.1, n))
    vol = rng.uniform(100, 300, n) if vol is None else vol
    return [Bar(start + i * tf_ms, float(open_[i]), float(high[i]), float(low[i]),
                float(close[i]), float(vol[i])) for i in range(n)]


def random_close(n, seed, drift=0.0):
    rng = np.random.default_rng(seed)
    return 100 * np.exp(np.cumsum(rng.normal(drift, 0.01, n)))


def panels_for(symbols, n, tf_ms, seed0=1):
    out = {}
    for i, s in enumerate(symbols):
        b = bars_from(random_close(n, seed0 + i), tf_ms, seed=seed0 + i)
        out[s] = rb.Panel(s, b, {}, tf_ms)
    return out


SYMS_4H = ["BTCUSDT", "ETHUSDT"] + [f"S{i:02d}USDT" for i in range(12)]


class GridTests(unittest.TestCase):
    def test_exactly_300_configs_with_family_quotas(self):
        grid = cb.build_grid()
        self.assertEqual(len(grid), 300)
        counts = {}
        for c in grid:
            counts[c["family"]] = counts.get(c["family"], 0) + 1
        self.assertEqual(counts, {f: q for f, _v, _x, q in cb.FAMILY_SPECS})

    def test_deterministic_unique_and_hash_matches_prereg(self):
        a, b = cb.build_grid(), cb.build_grid()
        self.assertEqual(cb.grid_sha256(a), cb.grid_sha256(b))
        keys = {tuple(sorted((k, str(v)) for k, v in c.items() if k != "config_id")) for c in a}
        self.assertEqual(len(keys), 300)
        self.assertEqual(cb.grid_sha256(a),
                         "a7d1622f539965b55f96b0b5e7b24e178c0e365f7a3b44730e57b34215245adf")

    def test_horizons_are_only_24_or_48_and_denominator_constants(self):
        for c in cb.build_grid():
            self.assertIn(c["horizon_bars"], (24, 48))
        self.assertEqual(cb.PRIOR_EXPLORE_ROWS, 429)
        self.assertEqual(cb.LANE_TOTAL_CONFIGS, 1000)


class LookaheadTests(unittest.TestCase):
    def test_per_symbol_families_ignore_future_bars(self):
        bars = bars_from(random_close(1400, 5), HOUR, seed=5)
        full = rb.Panel("X", bars, {}, HOUR)
        cut = 1000
        short = rb.Panel("X", bars[:cut], {}, HOUR)
        for fam in ("C6", "C7", "C8"):
            c = next(x for x in cb.build_grid() if x["family"].startswith(fam))
            with self.subTest(family=fam):
                a = cb.PER_SYMBOL[fam](full, c)
                b = cb.PER_SYMBOL[fam](short, c)
                self.assertTrue(np.array_equal(a[:cut], b))

    def test_cross_sectional_pair_and_leadlag_ignore_future_bars(self):
        for family, tf_ms, n, cut in (("C1", H4, 1400, 900), ("C2", H4, 1400, 900),
                                       ("C3", H4, 1400, 900), ("C4", H4, 1400, 900),
                                       ("C5", HOUR, 2400, 1700)):
            c = next(x for x in cb.build_grid() if x["family"].startswith(family))
            full = panels_for(SYMS_4H, n, tf_ms)
            short = {s: rb.Panel(s, p.bars[:cut], {}, tf_ms) for s, p in full.items()}
            panels_full = {c["timeframe"]: full}
            panels_short = {c["timeframe"]: short}
            with self.subTest(family=family):
                a = cb.dirs_for_config(c, panels_full)
                b = cb.dirs_for_config(c, panels_short)
                for s in full:
                    self.assertTrue(np.array_equal(a[s][:cut - 1], b[s][:cut - 1]), (family, s))


class MechanicsTests(unittest.TestCase):
    def test_base_entry_is_next_open_delay_two_is_open_after_that(self):
        bars = bars_from(random_close(1200, 9), HOUR, seed=9)
        p = rb.Panel("X", bars, {}, HOUR)
        dirs = np.zeros(len(bars), dtype=np.int8)
        dirs[600] = 1
        c = {"horizon_bars": 24, "reward_r": 50.0, "stop_atr": 2.0}
        base, _ = cb.simulate_symbol(p, dirs, c)
        d2, _ = cb.simulate_symbol(p, dirs, c, delay=2)
        self.assertEqual(len(base), 1)
        self.assertEqual(base[0]["entry_ts"], bars[601].timestamp)
        self.assertEqual(d2[0]["entry_ts"], bars[602].timestamp)

    def test_cost_two_adds_exactly_12bp_per_trade_without_funding(self):
        bars = bars_from(random_close(1200, 11), HOUR, seed=11)
        p = rb.Panel("X", bars, {}, HOUR)
        dirs = np.zeros(len(bars), dtype=np.int8)
        dirs[700] = -1
        c = {"horizon_bars": 24, "reward_r": 50.0, "stop_atr": 2.0}
        base, _ = cb.simulate_symbol(p, dirs, c, want_daily=True)
        c2, _ = cb.simulate_symbol(p, dirs, c, fee_bps=cb.COST2_FEE_BPS, slip_bps=cb.COST2_SLIP_BPS)
        self.assertEqual(len(base), 1)
        self.assertAlmostEqual(base[0]["net"] - c2[0]["net"], 0.0012, places=9)

    def test_dense_signals_are_suppressed_and_fully_accounted(self):
        bars = bars_from(random_close(1600, 13), HOUR, seed=13)
        p = rb.Panel("X", bars, {}, HOUR)
        dirs = np.zeros(len(bars), dtype=np.int8)
        dirs[600:1400] = 1
        c = {"horizon_bars": 24, "reward_r": 50.0, "stop_atr": 2.0}
        trades, stats = cb.simulate_symbol(p, dirs, c)
        self.assertGreater(stats["skipped_overlap"], 0)
        total = (len(trades) + stats["skipped_overlap"] + stats["censored_no_exit"]
                 + stats["unscorable_funding"] + stats["reconcile_error"])
        self.assertEqual(total, 800)

    def test_cross_sectional_cadence_has_no_overlap_skips(self):
        c = {"family": "C2_CS_MOMENTUM_LS", "timeframe": "4h", "reward_r": 50.0,
             "side": "momentum", "lookback_days": 7, "top_k": 2, "horizon_bars": 24,
             "stop_atr": 1000.0}
        panels = {"4h": panels_for(SYMS_4H, 1200, H4)}
        dirs = cb.dirs_for_config(c, panels)
        ref = dirs["BTCUSDT"]
        signal_rows = np.flatnonzero(ref)
        self.assertTrue(len(signal_rows) > 0)
        self.assertTrue(all(i % 25 == 0 for i in signal_rows))
        total_trades, totals = 0, {"skipped_overlap": 0}
        for s, p in panels["4h"].items():
            t, st = cb.simulate_symbol(p, dirs[s], c)
            total_trades += len(t)
            totals["skipped_overlap"] += st["skipped_overlap"]
        self.assertEqual(totals["skipped_overlap"], 0)
        self.assertGreater(total_trades, 0)

    def test_cross_sectional_long_short_counts_and_neutrality(self):
        c = {"family": "C1_CS_SHORT_REVERSAL_LS", "timeframe": "4h", "side": "reversal",
             "lookback_days": 2, "top_k": 3, "horizon_bars": 24}
        panels = {"4h": panels_for(SYMS_4H, 1200, H4)}
        dirs = cb.dirs_for_config(c, panels)
        stacked = np.array([dirs[s] for s in SYMS_4H])
        for t in np.flatnonzero(np.any(stacked != 0, axis=0)):
            longs = int(np.sum(stacked[:, t] == 1))
            shorts = int(np.sum(stacked[:, t] == -1))
            self.assertEqual((longs, shorts), (3, 3))


class SignalDirectionTests(unittest.TestCase):
    def test_pair_spread_jump_goes_short_eth_long_btc(self):
        n = 400
        base = np.full(n, 100.0)
        eth = base.copy()
        eth[300:] = 100 * 1.25  # ETH spread jumps up sharply at bar 300
        btc = base.copy()
        panels = {"4h": {"BTCUSDT": rb.Panel("BTCUSDT", bars_from(btc, H4, seed=2), {}, H4),
                         "ETHUSDT": rb.Panel("ETHUSDT", bars_from(eth, H4, seed=3), {}, H4)}}
        c = {"family": "C4_BTC_ETH_SPREAD_REVERSION", "timeframe": "4h", "window_bars": 30,
             "entry_z": 2.0, "horizon_bars": 24, "stop_atr": 3.0, "reward_r": 50.0}
        dirs = cb.dirs_for_config(c, panels)
        self.assertTrue(np.any(dirs["ETHUSDT"][300:310] == -1))
        self.assertTrue(np.any(dirs["BTCUSDT"][300:310] == 1))
        self.assertFalse(np.any(dirs["ETHUSDT"][:300] != 0))

    def test_settlement_signal_fires_on_bar_before_entry_hour(self):
        n = 200
        bars = bars_from(random_close(n, 21), HOUR, seed=21)
        p = rb.Panel("X", bars, {}, HOUR)
        c = {"offset_hours": 2, "direction": "long", "settle_hour_utc": 8}
        d = cb._settle_signal(p, c)
        for i in np.flatnonzero(d):
            self.assertEqual(((p.T[i + 1] // HOUR) % 24), 6)
        self.assertTrue(np.any(d))

    def test_settlement_signal_handles_symbol_without_bars(self):
        empty = rb.Panel("EMPTY", [], {}, HOUR)
        d = cb._settle_signal(empty, {"offset_hours": 1, "direction": "long", "settle_hour_utc": 0})
        self.assertEqual(len(d), 0)

    def test_leadlag_follows_btc_shock_into_lagging_alts(self):
        n = 800
        rng = np.random.default_rng(31)
        btc = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
        btc[600:] *= 1.08  # BTC up shock at bar 600
        lag = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
        lag[600:] *= 1.01  # alt lags the shock
        lead = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
        lead[600:] *= 1.09  # alt moved as much as BTC: not lagging
        panels = {"1h": {"BTCUSDT": rb.Panel("BTCUSDT", bars_from(btc, HOUR, seed=1), {}, HOUR),
                         "LAGUSDT": rb.Panel("LAGUSDT", bars_from(lag, HOUR, seed=2), {}, HOUR),
                         "LEADUSDT": rb.Panel("LEADUSDT", bars_from(lead, HOUR, seed=3), {}, HOUR)}}
        c = {"family": "C5_BTC_SHOCK_ALT_LAG_FOLLOW", "timeframe": "1h", "lag_bars": 3,
             "shock_z": 2.0, "horizon_bars": 24, "stop_atr": 2.0, "reward_r": 1.5}
        dirs = cb.dirs_for_config(c, panels)
        self.assertTrue(np.any(dirs["LAGUSDT"][600:605] == 1))
        self.assertFalse(np.any(dirs["LEADUSDT"][600:605] == 1))


class SupplementaryAndLedgerTests(unittest.TestCase):
    def test_supplementary_fails_closed_without_delayed_trades(self):
        base = [{"symbol": "A", "entry_ts": T0 + i * 86_400_000, "entry_year": 2020,
                 "net": 0.01, "exit_reason": "time"} for i in range(5)]
        s = cb.supplementary(base, [], [], 5000)
        self.assertFalse(s["delay1"]["pass"])
        self.assertFalse(s["all_pass"])

    def test_record_carries_round_label_and_denominator(self):
        result = {"config_id": "CB-000", "family": "x", "status": "failed"}
        rec = cb._ledger_record(result, "g", "c", "f", 4618, "p", "m", 3189)
        self.assertEqual(rec["round"], "RB1000-COINB")
        self.assertIn('"bonferroni_denominator":4618', rec["metric"])
        self.assertTrue(rec["trial_id"].startswith("RB1000-COINB-CB-000-"))


if __name__ == "__main__":
    unittest.main()
