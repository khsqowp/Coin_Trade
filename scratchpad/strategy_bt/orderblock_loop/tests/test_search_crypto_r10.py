"""Synthetic-only boundary tests for the preregistered R10 state machine."""
import unittest
import csv
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from crypto import Bar, FundingEvent, Zone
import search_crypto_r10 as r10

H = r10.HOUR_MS
F = r10.FOUR_HOUR_MS


def bar(ts, *, o=105.0, h=108.0, l=102.0, c=105.0):
    return Bar(ts, o, h, l, c, 1.0)


def quiet(ts):
    return bar(ts, o=115, h=117, l=113, c=115)


class R10IdentityAndClockTests(unittest.TestCase):
    def test_ids_include_symbol_segment_timestamp_direction_and_role(self):
        ids = {r10.stable_id(sym, seg, ts, direction, role)
               for sym in ("BTCUSDT", "ETHUSDT")
               for seg in (0, 100 * H)
               for ts in (24 * H, 124 * H)
               for direction in ("long", "short")
               for role in ("parent", "child", "trade")}
        self.assertEqual(len(ids), 2 * 2 * 2 * 2 * 3)
        self.assertNotEqual(r10.stable_id("BTC", 0, 0, "long", "parent"),
                            r10.stable_id("BTC", 100, 0, "long", "parent"))

    def test_segment_gap_splits_without_compressing_local_clock(self):
        data = [bar(0), bar(H), bar(3*H), bar(4*H)]
        self.assertEqual(r10.segments(data, H), [(0, 2), (2, 4)])

    def test_duplicate_or_unaligned_time_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            r10.segments([bar(0), bar(0)], H)
        with self.assertRaisesRegex(ValueError, "UTC boundaries"):
            r10.segments([bar(0), bar(H+1)], H)

    def test_parent_same_timestamp_opposing_signals_are_both_dropped(self):
        zs = [Zone(2, 0, "long", 100, 110, 1),
              Zone(2, 1, "short", 100, 110, 1),
              Zone(3, 2, "long", 100, 110, 1)]
        self.assertEqual(r10.choose_parent_candidates(zs), {3: zs[2]})

    def test_child_must_close_strictly_after_parent_retest_and_fit(self):
        parent = Zone(0, 0, "long", 100, 110, 2)
        self.assertFalse(r10._eligible_child(parent, 8*H,
                                             Zone(8, 2, "long", 101, 109, 1), 8*H))
        self.assertTrue(r10._eligible_child(parent, 8*H,
                                            Zone(8, 2, "long", 101, 109, 1), 9*H))
        self.assertFalse(r10._eligible_child(parent, 8*H,
                                             Zone(8, 2, "long", 99, 109, 1), 9*H))
        self.assertFalse(r10._eligible_child(parent, 8*H,
                                             Zone(8, 2, "long", 101, 109, 1), 8*H))
        self.assertFalse(r10._eligible_child(parent, 8*H,
                                             Zone(8, 2, "short", 101, 109, 1), 9*H))

    def test_train_adapter_requests_only_both_train_timeframes_and_exact_universe(self):
        calls = []
        symbols = sorted(r10._expected_symbols())
        pbar = [bar(0)]
        cbar = [bar(i*H) for i in range(4)]
        def iterator(*, timeframe):
            calls.append(timeframe)
            bars = pbar if timeframe == "4h" else cbar
            return [(symbol, list(bars), {}) for symbol in symbols]
        rows = r10._load_train_barsets(loader=SimpleNamespace(iter_train_bars=iterator))
        self.assertEqual(calls, ["4h", "1h"])
        self.assertEqual(len(rows), 35)
        self.assertEqual({r[0] for r in rows}, set(symbols))

    def test_synthetic_train_adapter_writes_external_cache_and_trial_record(self):
        symbols=sorted(r10._expected_symbols())
        p=[bar(0)]
        c=[bar(i*H) for i in range(4)]
        def iterator(*,timeframe,**kwargs):
            bars=p if timeframe=="4h" else c
            return [(symbol,list(bars),{}) for symbol in symbols]
        with tempfile.TemporaryDirectory(prefix="r10-synthetic-") as tmp:
            ledger=Path(tmp)/"TRAIN_TRIALS.csv"
            cache=Path(tmp)/"external-cache"
            with patch.object(r10,"TRIAL_CSV_PATH",ledger):
                result=r10._run_train_once(cache_dir=cache,
                    loader=SimpleNamespace(iter_train_bars=iterator))
            self.assertEqual(result["eligible_symbols"],35)
            event_path=Path(result["event_file"])
            self.assertTrue(event_path.is_file())
            self.assertNotIn(str(r10.HERE),str(event_path))
            with ledger.open(newline="",encoding="utf-8") as stream:
                rows=list(csv.DictReader(stream))
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]["round"],"R10-coin")

    def test_only_30_cross_timeframe_eligible_symbols_are_scorable(self):
        p = [bar(0)]
        c = [bar(i*H) for i in range(4)]
        eligible = [(f"S{i}", p, c, {}) for i in range(30)]
        with patch.object(r10, "simulate_symbol", return_value=([], [], {})):
            self.assertEqual(r10.run_symbols(eligible)["status"], "completed")
            self.assertEqual(r10.run_symbols(eligible[:29])["status"], "unscorable")


class R10SequenceTests(unittest.TestCase):
    def test_48th_parent_retest_is_funnel_only_no_child(self):
        p = [quiet(i*F) for i in range(50)]
        p[0] = bar(0, h=120, l=90)
        p[48] = bar(48*F, h=109, l=105)
        c = [quiet(i*H) for i in range(200)]
        zone = Zone(0, 0, "long", 100, 110, 2)
        with patch.object(r10, "r4_zones", return_value=[]):
            _, events, counts = r10.simulate_symbol("BTC", p, c,
                parent_zones=[zone], child_zones=[])
        self.assertTrue(any(e["status"] == "parent_expired_on_retest" for e in events))
        self.assertEqual(counts["children"], 0)

    def test_unclosed_4h_wick_does_not_cancel_child_entry(self):
        p = [quiet(i*F) for i in range(8)]
        p[0] = bar(0, h=120, l=90)
        p[1] = bar(F, h=109, l=105)
        # During the 4h bar containing the child signal/retest, this 1h wick is
        # below the parent's distal edge. It is not itself a completed 4h event.
        c = [quiet(i*H) for i in range(65)]
        c[9] = bar(9*H, h=109, l=103)
        c[10] = bar(10*H, h=108, l=99)
        pz = Zone(0, 0, "long", 100, 110, 2)
        cz = Zone(8, 2, "long", 102, 108, 1)
        with patch.object(r10, "r4_zones", return_value=[]), \
             patch.object(r10, "simulate_trade", return_value=None) as sim:
            _, events, _ = r10.simulate_symbol("BTC", p, c, parent_zones=[pz],
                child_zones=[cz], cutoff_ms=100*H)
        sim.assert_called_once()
        self.assertFalse(any(e["status"] == "parent_invalidated_before_entry" for e in events))

    def test_synthetic_completed_trade_reconciles_cost_m2_and_funding_fields(self):
        p = [quiet(i*F) for i in range(20)]
        p[0] = bar(0, h=120, l=90)
        p[1] = bar(F, h=109, l=105)
        c = [quiet(i*H) for i in range(80)]
        c[8] = bar(8*H, h=109, l=103)
        c[9] = bar(9*H, h=109, l=103)
        c[10] = bar(10*H, o=105, h=112, l=103, c=110)
        pz = Zone(0, 0, "long", 100, 110, 2)
        cz = Zone(8, 2, "long", 102, 108, 1)
        trades, events, _ = r10.simulate_symbol("BTC", p, c, {},
            parent_zones=[pz], child_zones=[cz], cutoff_ms=100*H)
        entered = next(e for e in events if e["status"] == "entered")
        self.assertEqual(len(trades), 1)
        self.assertEqual(entered["entry_timestamp"], 10*H)
        self.assertEqual(entered["exit_reason"], "target")
        self.assertAlmostEqual(entered["cost_bps"], 12.0)
        self.assertTrue(entered["m2_included"])
        self.assertTrue(entered["m2_target_hit"])
        self.assertEqual(entered["funding_event_count"], 0)
        self.assertIsNotNone(entered["daily_pnl"])

    def test_unscorable_funding_keeps_completed_price_path_in_m2(self):
        p=[quiet(i*F) for i in range(20)]
        p[0]=bar(0,h=120,l=90)
        p[1]=bar(F,h=109,l=105)
        c=[quiet(i*H) for i in range(80)]
        c[8]=bar(8*H,h=109,l=103)
        c[9]=bar(9*H,h=109,l=103)
        c[10]=bar(10*H,o=105,h=112,l=103,c=110)
        pz=Zone(0,0,"long",100,110,2)
        cz=Zone(8,2,"long",102,108,1)
        settlement=10*H+30*60_000
        funding={settlement:FundingEvent(settlement,0.0005,105.0,coverage_gap=True)}
        trades,events,_=r10.simulate_symbol("BTC",p,c,funding,
            parent_zones=[pz],child_zones=[cz],cutoff_ms=100*H)
        entered=next(e for e in events if e["status"]=="entered")
        self.assertEqual(len(trades),1)
        self.assertTrue(entered["funding_unscorable"])
        self.assertTrue(entered["m2_included"])
        self.assertTrue(entered["m2_target_hit"])
        self.assertIsNone(entered["net_return"])
        self.assertEqual(entered["funding_event_count"],1)

    def test_parent_close_invalidation_cancels_same_timestamp_entry(self):
        p = [quiet(i*F) for i in range(5)]
        p[0] = bar(0, h=120, l=90)
        p[1] = bar(F, h=109, l=105)
        p[2] = bar(2*F, h=108, l=99)
        c = [quiet(i*H) for i in range(15)]
        c[9] = quiet(9*H)
        c[11] = bar(11*H, h=108, l=103)
        pz, cz = Zone(0, 0, "long", 100, 110, 2), Zone(8, 2, "long", 102, 108, 1)
        with patch.object(r10, "r4_zones", return_value=[]), \
             patch.object(r10, "simulate_trade", return_value=None) as sim:
            _, events, _ = r10.simulate_symbol("BTC", p, c, parent_zones=[pz],
                child_zones=[cz], cutoff_ms=100*H)
        sim.assert_not_called()
        self.assertTrue(any(e["status"] == "parent_invalidated" and
                            e.get("parent_close") == 12*H for e in events))

    def test_parent_expiry_at_child_close_timestamp_preempts_child(self):
        p = [quiet(i*F) for i in range(49)]
        p[1] = bar(F, h=109, l=105)
        c = [quiet(i*H) for i in range(196)]
        pz = Zone(0, 0, "long", 100, 110, 2)
        cz = Zone(195, 193, "long", 102, 108, 1)
        with patch.object(r10, "r4_zones", return_value=[]):
            _, events, counts = r10.simulate_symbol("BTC", p, c,
                parent_zones=[pz], child_zones=[cz], cutoff_ms=300*H)
        self.assertEqual(counts["parent_expired"], 1)
        self.assertTrue(any(e["status"] == "parent_expired"
                            and e.get("parent_close") == 196*H for e in events))
        self.assertFalse(any(e["status"] == "child_selected" for e in events))

    def test_prefix_invariance_of_confirmed_sequence_and_entry(self):
        p = [quiet(i*F) for i in range(8)]
        p[1] = bar(F, h=109, l=105)
        c = [quiet(i*H) for i in range(32)]
        c[9] = bar(9*H, h=109, l=103)
        pz = Zone(0, 0, "long", 100, 110, 2)
        cz = Zone(8, 2, "long", 102, 108, 1)
        changed_p = list(p)
        for i in range(2, len(changed_p)):
            changed_p[i] = bar(i*F, h=108, l=99, c=101)
        changed_c = list(c)
        for i in range(11, len(changed_c)):
            changed_c[i] = bar(i*H, o=90, h=91, l=88, c=89)

        def decision_prefix(parent_bars, child_bars):
            with patch.object(r10, "r4_zones", return_value=[]):
                _, rows, _ = r10.simulate_symbol("BTC", parent_bars, child_bars,
                    parent_zones=[pz], child_zones=[cz], cutoff_ms=100*H)
            keys = {
                "parent_created": ("parent_signal_close",),
                "parent_retested": ("parent_retest_close",),
                "child_selected": ("child_signal_close", "child_low", "child_high"),
                "child_retested": ("child_retest_close",),
                "entered": ("entry_timestamp", "entry_price", "stop", "target"),
            }
            decided = [(row["status"], tuple(row.get(k) for k in keys[row["status"]]))
                       for row in rows if row["status"] in keys
                       and row["status"] != "entered"]
            entries = [(row["trade_id"], row["entry_timestamp"], row["entry_price"],
                        row["stop"], row["target"])
                       for row in rows if row.get("entry_occurred")
                       or row.get("status") == "entered"]
            return decided, entries

        self.assertEqual(decision_prefix(p, c),
                         decision_prefix(changed_p, changed_c))

    def test_nonzero_parent_signal_index_uses_local_age_not_segment_age(self):
        p = [quiet(i*F) for i in range(72)]
        p[55] = bar(55*F, h=120, l=90)
        p[56] = bar(56*F, h=109, l=105)
        c = [quiet(i*H) for i in range(280)]
        c[228] = bar(228*H, h=109, l=103)
        pz = Zone(55, 50, "long", 100, 110, 2)
        cz = Zone(228, 220, "long", 102, 108, 1)
        with patch.object(r10, "r4_zones", return_value=[]), \
             patch.object(r10, "simulate_trade", return_value=None):
            _, events, _ = r10.simulate_symbol("BTC", p, c,
                parent_zones=[pz], child_zones=[cz], cutoff_ms=1000*H)
        self.assertTrue(any(e["status"] == "child_selected" for e in events))

    def test_child_in_later_1h_segment_is_rejected_after_intervening_gap(self):
        p = [quiet(i*F) for i in range(12)]
        p[0] = bar(0, h=120, l=90)
        p[1] = bar(F, h=109, l=105)
        c = [quiet(i*H) for i in range(10)] + [quiet(12*H+i*H) for i in range(30)]
        pz = Zone(0, 0, "long", 100, 110, 2)
        # Index 10 is the first bar after the missing 10h and 11h interval.
        cz = Zone(10, 4, "long", 102, 108, 1)
        with patch.object(r10, "r4_zones", return_value=[]):
            _, events, counts = r10.simulate_symbol("BTC", p, c,
                parent_zones=[pz], child_zones=[cz], cutoff_ms=1000*H)
        self.assertEqual(counts["children"], 0)
        self.assertTrue(any(e["status"] == "sequence_gap_terminated" for e in events))

    def test_parent_wick_invalidation_after_retest_precedes_child_retest(self):
        p = [quiet(i*F) for i in range(10)]
        p[0] = bar(0, h=120, l=90)
        p[1] = bar(F, h=109, l=105)
        p[2] = bar(2*F, h=108, l=99)
        c = [quiet(i*H) for i in range(25)]
        c[8] = bar(8*H, h=109, l=103)   # child close 9h, after 8h parent retest close
        c[13] = bar(13*H, h=108, l=103) # retest would occur after 12h parent invalidation
        pz = Zone(0, 0, "long", 100, 110, 2)
        cz = Zone(8, 2, "long", 102, 108, 1)
        with patch.object(r10, "r4_zones", return_value=[]), \
             patch.object(r10, "simulate_trade") as sim:
            _, events, _ = r10.simulate_symbol("BTC", p, c,
                parent_zones=[pz], child_zones=[cz], cutoff_ms=1000*H)
        sim.assert_not_called()
        self.assertTrue(any(e["status"] == "parent_invalidated" and
                            e.get("parent_close") == 12*H for e in events))
        self.assertFalse(any(e["status"] == "child_retested" for e in events))

    def test_cutoff_entry_and_gap_boundary_have_distinct_funnel_status(self):
        p = [quiet(i*F) for i in range(8)]
        p[0] = bar(0, h=120, l=90)
        p[1] = bar(F, h=109, l=105)
        pz = Zone(0, 0, "long", 100, 110, 2)
        cz = Zone(8, 2, "long", 102, 108, 1)
        cutoff_bars = [quiet(i*H) for i in range(10)]
        cutoff_bars[8] = bar(8*H, h=109, l=103)
        cutoff_bars[9] = bar(9*H, h=108, l=103)
        gap_bars = cutoff_bars + [quiet(11*H+i*H) for i in range(5)]
        for child_bars, expected in ((cutoff_bars, "cutoff_entry_censored"),
                                     (gap_bars, "sequence_gap_terminated")):
            with self.subTest(expected=expected), patch.object(r10, "r4_zones", return_value=[]):
                _, events, counts = r10.simulate_symbol("BTC", p, child_bars,
                    parent_zones=[pz], child_zones=[cz], cutoff_ms=100*H)
                self.assertTrue(any(e["status"] == expected for e in events))
                self.assertEqual(counts["cutoff_entry_censored"],
                                 int(expected == "cutoff_entry_censored"))

    def test_child_retest_window_includes_24_excludes_25(self):
        child = Zone(0, 0, "long", 100, 110, 2)
        bars24 = [quiet(i*H) for i in range(26)]
        bars24[24] = bar(24*H, h=109, l=105)
        self.assertEqual(r10.first_child_retest(bars24, child), ("retested", 24))
        bars25 = [quiet(i*H) for i in range(27)]
        bars25[25] = bar(25*H, h=109, l=105)
        self.assertEqual(r10.first_child_retest(bars25, child), ("expired", None))

    def test_child_retest_cannot_cross_gap_segment(self):
        data = [quiet(i*H) for i in range(25)] + [quiet(26*H), quiet(27*H)]
        zone = Zone(0, 0, "long", 100, 110, 2)
        data[26] = bar(26*H, h=109, l=105)
        left_segment = data[:12]
        local_zone = Zone(0, 0, "long", 100, 110, 2)
        self.assertEqual(r10.first_child_retest(left_segment, local_zone),
                         ("right_censored", None))

    def test_later_child_is_not_selected_after_first_eligible_child_fails(self):
        p = [quiet(i*F) for i in range(8)]
        p[0] = bar(0, h=120, l=90)
        p[1] = bar(F, h=109, l=105)
        c = [quiet(i*H) for i in range(70)]
        c[9] = bar(9*H, h=109, l=99)  # first child invalidated at first contact
        c[11] = bar(11*H, h=109, l=101)  # later child is never substituted
        pz = Zone(0, 0, "long", 100, 110, 2)
        cz1 = Zone(8, 2, "long", 102, 108, 1)
        cz2 = Zone(10, 3, "long", 102, 108, 1)
        with patch.object(r10, "r4_zones", return_value=[]):
            _, events, counts = r10.simulate_symbol("BTC", p, c,
                parent_zones=[pz], child_zones=[cz1, cz2], cutoff_ms=100*H)
        self.assertEqual(counts["children"], 1)
        self.assertEqual(counts["child_failed"], 1)
        self.assertFalse(any(e["status"] == "entered" for e in events))

    def test_cutoff_blocks_next_open_entry_for_both_directions(self):
        for direction in ("long", "short"):
            with self.subTest(direction=direction):
                p = [quiet(i*F) for i in range(5)]
                p[0] = bar(0, h=120, l=90)
                p[1] = bar(F, h=109, l=105)
                c = [quiet(i*H) for i in range(12)]
                zone = Zone(0, 0, direction, 100, 110, 2)
                child = Zone(8, 2, direction, 102, 108, 1)
                c[9] = (bar(9*H, h=109, l=103) if direction == "long"
                        else bar(9*H, h=107, l=103))
                with patch.object(r10, "r4_zones", return_value=[]):
                    _, events, counts = r10.simulate_symbol("BTC", p, c,
                        parent_zones=[zone], child_zones=[child], cutoff_ms=10*H)
                self.assertEqual(counts["cutoff_entry_censored"], 1)
                self.assertTrue(any(e["status"] == "cutoff_entry_censored" for e in events))


if __name__ == "__main__":
    unittest.main()
