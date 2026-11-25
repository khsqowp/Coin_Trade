from __future__ import annotations

import csv
import os
import tempfile
import unittest
from pathlib import Path

import numpy as np

import search_crypto_rb1000_coina as coina
import search_crypto_rb500 as rb5
from crypto import Bar, FundingEvent

HOUR_MS = 3_600_000
START_MS = 1_577_836_800_000  # 2020-01-01T00:00Z


def synthetic_bars(n=900, tf_ms=HOUR_MS, seed=11, start=START_MS):
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 1.0, n)) + 6 * np.sin(np.arange(n) / 35)
    open_ = np.concatenate(([close[0]], close[:-1]))
    high = np.maximum(open_, close) + np.abs(rng.normal(0.5, 0.2, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0.5, 0.2, n))
    vol = rng.uniform(100, 300, n)
    return [Bar(start + i * tf_ms, float(open_[i]), float(high[i]), float(low[i]),
                float(close[i]), float(vol[i])) for i in range(n)]


def synthetic_funding(bars, tf_ms, seed=5, every=8):
    rng = np.random.default_rng(seed)
    out = {}
    for i in range(0, len(bars), every):
        ts = bars[i].timestamp
        out[ts] = FundingEvent(ts, float(rng.normal(0, 0.0006)), None)
    return out


def synthetic_raw(bars, tf_ms, seed=9):
    """Minute-level and 5-minute-level derivative arrays covering the bars (epoch ms)."""
    rng = np.random.default_rng(seed)
    n = len(bars)
    minutes = np.arange(n * (tf_ms // 60_000), dtype=np.int64) * 60_000 + bars[0].timestamp
    kl_v = rng.uniform(1, 5, len(minutes))
    kl_tb = kl_v * rng.uniform(0.2, 0.8, len(minutes))
    prem_c = rng.normal(0, 0.0004, len(minutes))
    snap_t = np.arange(n * (tf_ms // 300_000), dtype=np.int64) * 300_000 + bars[0].timestamp
    oi = 1e6 * np.exp(np.cumsum(rng.normal(0, 0.004, len(snap_t))))
    ratio_g = np.exp(rng.normal(0, 0.3, len(snap_t)))
    ratio_ta = np.exp(rng.normal(0, 0.3, len(snap_t)))
    ratio_tp = np.exp(rng.normal(0, 0.3, len(snap_t)))
    return {
        "oi_t": snap_t, "oi_v": oi,
        "count_long_short_ratio_t": snap_t, "count_long_short_ratio_v": ratio_g,
        "count_toptrader_long_short_ratio_t": snap_t, "count_toptrader_long_short_ratio_v": ratio_ta,
        "sum_toptrader_long_short_ratio_t": snap_t, "sum_toptrader_long_short_ratio_v": ratio_tp,
        "prem_t": minutes, "prem_v": prem_c,
        "kl_t": minutes, "kl_v": kl_v, "kl_tb": kl_tb,
    }


def truncate_raw(raw, cutoff_ms):
    """Keep only observations stamped strictly before cutoff_ms, per time/value pair."""
    out = {}
    for key, value in raw.items():
        if key.endswith("_t"):
            continue
        if key.endswith("_tb"):
            t_key = key[:-3] + "_t"
        else:
            t_key = key[:-2] + "_t"
        mask = raw[t_key] < cutoff_ms
        out[key] = value[mask]
        out[t_key] = raw[t_key][mask]
    return out


def make_panel(bars, funding, tf_ms=HOUR_MS, symbol="SYN"):
    return rb5.Panel(symbol, bars, funding, tf_ms)


def loader_from(raw):
    return lambda symbol: raw


class GridTests(unittest.TestCase):
    def test_exact_300_and_family_quotas(self):
        self.assertEqual(len(coina.GRID), 300)
        counts = {}
        for config in coina.GRID:
            counts[config["family"]] = counts.get(config["family"], 0) + 1
        for family, _variable, _fixed, quota in coina.FAMILY_SPECS:
            self.assertEqual(counts[family], quota, family)
        self.assertEqual(sum(counts.values()), 300)

    def test_ids_unique_and_hash_deterministic(self):
        ids = [c["config_id"] for c in coina.GRID]
        self.assertEqual(len(set(ids)), 300)
        again = coina.build_grid()
        self.assertEqual(rb5.grid_sha256(coina.GRID), rb5.grid_sha256(again))

    def test_every_family_has_a_signal_function(self):
        for family, *_ in coina.FAMILY_SPECS:
            self.assertIn(family, coina.SIGNALS)


class ExecutionTests(unittest.TestCase):
    def test_entry_is_next_bar_open(self):
        bars = synthetic_bars()
        panel = make_panel(bars, {})
        dirs = np.zeros(len(bars), dtype=np.int8)
        signal = 600
        dirs[signal] = 1
        config = {"horizon_bars": 24, "reward_r": 2.0, "stop_atr": 2.0}
        trades, _ = coina.simulate_variant(panel, dirs, config, 4.0, 2.0, 0, False)
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["entry_ts"], bars[signal + 1].timestamp)

    def test_delay_moves_entry_one_bar_later(self):
        bars = synthetic_bars()
        panel = make_panel(bars, {})
        dirs = np.zeros(len(bars), dtype=np.int8)
        dirs[600] = -1
        config = {"horizon_bars": 24, "reward_r": 2.0, "stop_atr": 2.0}
        base, _ = coina.simulate_variant(panel, dirs, config, 4.0, 2.0, 0, False)
        delayed, _ = coina.simulate_variant(panel, dirs, config, 4.0, 2.0, 1, False)
        self.assertEqual(base[0]["entry_ts"], bars[601].timestamp)
        self.assertEqual(delayed[0]["entry_ts"], bars[602].timestamp)

    def test_overlap_is_skipped_per_symbol(self):
        bars = synthetic_bars()
        panel = make_panel(bars, {})
        dirs = np.zeros(len(bars), dtype=np.int8)
        dirs[600] = 1
        dirs[601] = 1
        config = {"horizon_bars": 24, "reward_r": 2.0, "stop_atr": 2.0}
        trades, stats = coina.simulate_variant(panel, dirs, config, 4.0, 2.0, 0, False)
        self.assertEqual(len(trades), 1)
        self.assertGreaterEqual(stats["skipped_overlap"], 1)


class FeatureTests(unittest.TestCase):
    def test_minute_binning_boundaries(self):
        bar_open = np.array([0, HOUR_MS, 2 * HOUR_MS], dtype=np.int64)
        minutes = np.array([0, HOUR_MS - 60_000, HOUR_MS, 2 * HOUR_MS - 60_000], dtype=np.int64)
        idx, valid = coina._bin_index(bar_open, HOUR_MS, minutes)
        self.assertEqual(list(idx), [0, 0, 1, 1])
        self.assertTrue(valid.all())

    def test_funding_event_not_known_before_its_bar_close(self):
        bars = synthetic_bars(n=700)
        funding = {bars[300].timestamp + HOUR_MS: FundingEvent(bars[300].timestamp + HOUR_MS,
                                                               0.0020, None)}
        panel = make_panel(bars, funding)
        feats = coina.build_features(panel, synthetic_raw(bars, HOUR_MS))
        # event stamped at bar 301's open is known only from bar 301 close onward.
        self.assertFalse(np.isfinite(feats["f_last"][300]))
        self.assertTrue(np.isfinite(feats["f_last"][301]))
        self.assertTrue(bool(feats["f_new"][301]))

    def test_funding_contrarian_sign(self):
        bars = synthetic_bars(n=700)
        funding = {bars[300].timestamp: FundingEvent(bars[300].timestamp, 0.0010, None)}
        panel = make_panel(bars, funding)
        panel.feat = coina.build_features(panel, synthetic_raw(bars, HOUR_MS))
        config = {"family": "D1_FUNDING_CONTRARIAN_EXTREME", "timeframe": "1h",
                  "funding_threshold": 0.0005, "trigger": "event", "smoothing": "last",
                  "reward_r": 2.0, "horizon_bars": 24, "stop_atr": 2.0}
        dirs = coina.sig_d1(panel, config)
        # settlement stamped at bar 300 open is known at bar 300 close -> fade (short) there
        self.assertEqual(dirs[299], 0)
        self.assertEqual(dirs[300], -1)
        self.assertEqual(dirs[301], 0)  # 'event' trigger: no new event at bar 301

    def test_no_lookahead_truncation_all_families(self):
        bars = synthetic_bars(n=900)
        funding = synthetic_funding(bars, HOUR_MS)
        raw = synthetic_raw(bars, HOUR_MS)
        full = make_panel(bars, funding)
        full.feat = coina.build_features(full, raw)
        k = 700
        cutoff = bars[k].timestamp  # keep only data strictly before bar k open
        trunc_bars = bars[:k]
        trunc_funding = {t: e for t, e in funding.items() if t < cutoff}
        trunc = make_panel(trunc_bars, trunc_funding)
        trunc.feat = coina.build_features(trunc, truncate_raw(raw, cutoff))
        total_nonzero = 0
        for family, *_ in coina.FAMILY_SPECS:
            config = next(c for c in coina.GRID if c["family"] == family)
            if family == "D6_OI_FLUSH_REBOUND_LIQ_PROXY":
                config = {**config, "oi_drop_window_bars": 1, "oi_drop_threshold": 0.0}
            if family == "D7_COMPRESSION_OI_BREAKOUT":
                config = {**config, "compression_percentile": 30}
            if family == "D2_CROWD_LS_RATIO_FADE":
                config = {**config, "z_threshold": 0.5}
            if family == "D4_PREMIUM_BASIS_Z":
                config = {**config, "z_threshold": 0.5}
            if family == "D5_TAKER_FLOW_IMBALANCE":
                config = {**config, "z_threshold": 0.5}
            if family == "D3_OI_PRICE_BUILDUP":
                config = {**config, "oi_z_threshold": 0.5}
            full_dirs = coina.SIGNALS[family](full, config)
            trunc_dirs = coina.SIGNALS[family](trunc, config)
            total_nonzero += int(np.count_nonzero(full_dirs[:k]))
            np.testing.assert_array_equal(full_dirs[:k], trunc_dirs, err_msg=family)
        self.assertGreater(total_nonzero, 0)

    def test_empty_symbol_panel_is_skipped_by_run_variant(self):
        empty = make_panel([], {}, symbol="EMPTY")
        empty.feat = {}
        bars = synthetic_bars(n=900)
        full = make_panel(bars, {}, symbol="FULL")
        full.feat = coina.build_features(full, synthetic_raw(bars, HOUR_MS))
        panels = {"1h": {"EMPTY": empty, "FULL": full}, "4h": {}}
        config = next(c for c in coina.GRID if c["family"] == "D6_OI_FLUSH_REBOUND_LIQ_PROXY")
        trades, _ = coina.run_variant(config, panels, 4.0, 2.0, 0, False)
        self.assertTrue(all(t["symbol"] == "FULL" for t in trades))

    def test_non_positive_oi_is_missing(self):
        bars = synthetic_bars(n=700)
        raw = synthetic_raw(bars, HOUR_MS)
        # 5-minute snapshots: index 12*i+11 is the last snapshot before bar i+1 close
        raw["oi_v"][11:12 * 5:12] = 0.0
        feats = coina.build_features(make_panel(bars, {}), raw)
        self.assertTrue(np.isnan(feats["oi"]).any())
        self.assertFalse(np.any(feats["oi"] == 0))

    def test_create_time_parsing_is_utc_ms(self):
        import pandas as pd
        ms = coina._create_time_ms(pd.Series(["2021-01-01 00:05:00"]))
        self.assertEqual(int(ms[0]), 1_609_459_500_000)


class LedgerAndStatTests(unittest.TestCase):
    def test_ledger_append_refuses_row_count_change(self):
        import search_crypto as common
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "ledger.csv"
            with ledger.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=common.FIELDS)
                writer.writeheader()
            before = ledger.read_bytes()
            record = {field: "x" for field in common.FIELDS}
            with self.assertRaises(RuntimeError):
                rb5.append_ledger_locked([record], 5, ledger)  # wrong expected row count
            self.assertEqual(before, ledger.read_bytes())
            self.assertEqual(rb5.append_ledger_locked([record], 0, ledger), 1)
            self.assertEqual(rb5._ledger_rows(ledger), 1)

    def test_top_exclusion_removes_three_largest_symbols(self):
        trades = [{"symbol": s, "net": v} for s, v in
                  (("A", 0.05), ("B", 0.04), ("C", 0.03), ("D", 0.01), ("E", -0.02))]
        top, rest = coina._top_exclusion(trades)
        self.assertEqual(top, ["A", "B", "C"])
        self.assertEqual(sorted(rest), [-0.02, 0.01])

    def test_yearly_bear_rule(self):
        ts_2022 = 1_655_000_000_000  # 2022-06
        ts_2021 = 1_625_000_000_000  # 2021-06
        trades = ([{"entry_ts": ts_2021, "net": 0.002}] * 25
                  + [{"entry_ts": ts_2022, "net": -0.001}] * 25)
        _, passed, _ = coina._yearly(trades)
        self.assertFalse(passed)  # 2022 qualifies and is negative
        good = [{"entry_ts": ts_2021, "net": 0.002}] * 25 + [{"entry_ts": ts_2022, "net": 0.001}] * 25
        self.assertTrue(coina._yearly(good)[1])

    def test_cluster_p_uses_entry_day_clusters(self):
        day = 18_000 * DAY
        trades = [{"entry_ts": day, "net": 0.01}, {"entry_ts": day + 1000, "net": 0.01},
                  {"entry_ts": day + 2 * DAY, "net": -0.01}]
        p, clusters = coina._cluster_p(trades)
        self.assertEqual(clusters, 2)
        self.assertIsNotNone(p)


DAY = 86_400_000


if __name__ == "__main__":
    unittest.main()
