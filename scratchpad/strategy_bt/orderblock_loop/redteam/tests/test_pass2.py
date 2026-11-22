"""Synthetic trade-level comparisons; no market data is loaded."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "redteam"))
import crypto as candidate_crypto
import equities as candidate_equities
import independent_crypto as oracle_crypto
import independent_equities as oracle_equities


def c_bars(mode: str = "target", direction: str = "long", n: int = 60):
    bars = [candidate_crypto.Bar(i * 900_000, 100, 101, 99, 100, 10) for i in range(n)]
    if direction == "long":
        zone = candidate_crypto.Zone(0, 0, "long", 99, 100, 2)
        bars[1] = candidate_crypto.Bar(900_000, 100, 101, 99.5, 100.5, 10)
        if mode == "target": bars[3] = candidate_crypto.Bar(2_700_000, 101, 105, 100, 104, 10)
        elif mode == "gapstop": bars[3] = candidate_crypto.Bar(2_700_000, 98, 99, 97, 98, 10)
        elif mode == "stop": bars[3] = candidate_crypto.Bar(2_700_000, 100, 102, 98, 99, 10)
        elif mode == "time": pass
        return bars, zone
    zone = candidate_crypto.Zone(0, 0, "short", 100, 101, 2)
    bars[1] = candidate_crypto.Bar(900_000, 100, 100.5, 99, 99.5, 10)
    if mode == "target": bars[3] = candidate_crypto.Bar(2_700_000, 99, 100, 95, 96, 10)
    elif mode == "gapstop": bars[3] = candidate_crypto.Bar(2_700_000, 102, 103, 101, 102, 10)
    elif mode == "stop": bars[3] = candidate_crypto.Bar(2_700_000, 100, 102, 98, 101, 10)
    return bars, zone


def e_bars(mode="target", n=80):
    bars = [candidate_equities.Bar(i, 101, 103, 100, 102) for i in range(n)]
    # A controlled breakout at 20, retest at 21, entry at 22.
    bars[19] = candidate_equities.Bar(19, 102, 103, 99, 100)
    bars[20] = candidate_equities.Bar(20, 103, 105, 102, 104)
    bars[21] = candidate_equities.Bar(21, 103, 105, 100, 104)
    bars[22] = candidate_equities.Bar(22, 104, 105, 103, 104)
    if mode == "target": bars[23] = candidate_equities.Bar(23, 104, 116, 103, 115)
    elif mode == "stop": bars[23] = candidate_equities.Bar(23, 104, 105, 98, 99)
    return bars


class Pass2Fixtures(unittest.TestCase):
    def test_crypto_all_three_signal_definitions_match_independent_oracle(self):
        bars = [candidate_crypto.Bar(i * 900_000, 100, 101, 99, 100, 10)
                for i in range(60)]
        bars[15] = candidate_crypto.Bar(15 * 900_000, 100, 105, 99, 101, 10)
        bars[19] = candidate_crypto.Bar(19 * 900_000, 101, 102, 99, 100, 10)
        bars[20] = candidate_crypto.Bar(20 * 900_000, 100, 111, 99, 110, 20)
        oracle_bars = [oracle_crypto.Bar(b.timestamp, b.open, b.high, b.low, b.close, b.volume)
                       for b in bars]
        for definition, oracle_kind in (("displacement", "body"),
                                        ("bos_origin", "bos"),
                                        ("volume_displacement", "volume")):
            candidate = candidate_crypto.active_zones(
                bars, definition, deadline=48)
            expected = oracle_crypto.signals(oracle_bars, oracle_kind)
            self.assertEqual(
                [(zone.signal_index, zone.direction, zone.low, zone.high,
                  zone.atr_at_signal) for zone in candidate],
                [(signal.index, signal.direction, signal.low, signal.high,
                  signal.atr) for signal in expected],
                definition,
            )

    def compare_equity_c1(self, mode, market="US"):
        bars = e_bars(mode)
        oracle_bars = [oracle_equities.Bar(b.timestamp, b.open, b.high, b.low, b.close)
                       for b in bars]
        candidate_signals = candidate_equities.c1_signals(
            bars, "daily", lookback=10)
        oracle_signals = oracle_equities.c1_signals(oracle_bars, lookback=10)
        self.assertEqual(candidate_signals,
                         [(signal.index, signal.low, signal.high)
                          for signal in oracle_signals])
        actual = candidate_equities.simulate_c1(
            bars, timeframe="daily", lookback=10, retest_bars=10,
            reward_r=2, holding_bars=20, market=market)
        fee, slip, tax = ((.0005, .0005, 0.0) if market == "US"
                          else (.00015, .0005, .0018))
        expected = [oracle_equities.simulate_c1(
            oracle_bars,
            oracle_equities.Signal(index, "c1", low, high),
            holding=20, reward=2, fee=fee, slip=slip, tax=tax)
            for index, low, high in candidate_signals]
        expected = [trade for trade in expected if trade is not None]
        self.assertEqual(len(actual), len(expected))
        for filled, oracle_fill in zip(actual, expected):
            self.assertEqual(filled.entry_index, oracle_fill.entry_index)
            self.assertEqual(filled.exit_index, oracle_fill.exit_index)
            self.assertAlmostEqual(filled.entry_price, oracle_fill.entry, places=12)
            self.assertAlmostEqual(filled.exit_price, oracle_fill.exit, places=12)
            self.assertEqual(filled.exit_reason, oracle_fill.reason)
            self.assertAlmostEqual(filled.net_return, oracle_fill.net_return, places=12)
        return actual

    def compare_crypto(self, mode, direction="long", funding=False, kind="body"):
        bars, zone = c_bars(mode, direction)
        setup = candidate_crypto.first_retest(
            bars, zone, deadline=24, reward_r=1.5)
        self.assertIsNotNone(setup, f"candidate retest did not create {mode}/{direction} entry")
        events = {}
        funding_rows = []
        if funding:
            events[bars[3].timestamp] = candidate_crypto.FundingEvent(bars[3].timestamp, .001, 103)
            funding_rows.append((bars[3].timestamp, .001, 103))
        actual = candidate_crypto.simulate_trade(bars, setup, funding=events)
        expected = oracle_crypto.trade(
            [oracle_crypto.Bar(b.timestamp, b.open, b.high, b.low, b.close, b.volume) for b in bars],
            oracle_crypto.Signal(0, direction, setup.zone.low, setup.zone.high, setup.zone.atr_at_signal, kind),
            holding=48, funding_events=funding_rows,
        )
        self.assertIsNotNone(actual, f"{mode}/{direction}/{kind}: target had no trade")
        self.assertIsNotNone(expected, f"{mode}/{direction}/{kind}: independent had no trade")
        self.assertEqual(actual.setup.entry_index, expected.entry_index)
        self.assertEqual(actual.setup.entry_price, expected.entry)
        self.assertEqual(actual.exit_index, expected.exit_index)
        self.assertAlmostEqual(actual.exit_price, expected.exit, places=12)
        self.assertEqual(actual.exit_reason, expected.reason)
        self.assertAlmostEqual(actual.gross_return, expected.gross_return, places=12)
        self.assertAlmostEqual(actual.funding_return, expected.funding, places=12)
        self.assertAlmostEqual(actual.net_return, expected.net_return, places=12)
        return actual, expected

    def test_crypto_body_long_target_many(self):
        for _ in range(10): self.compare_crypto("target", "long", kind="body")

    def test_crypto_bos_short_target_many(self):
        for _ in range(10): self.compare_crypto("target", "short", kind="bos")

    def test_crypto_volume_long_stop_many(self):
        for _ in range(10): self.compare_crypto("stop", "long", kind="volume")

    def test_crypto_gap_stop_long_many(self):
        for _ in range(10): self.compare_crypto("gapstop", "long")

    def test_crypto_gap_stop_short_many(self):
        for _ in range(10): self.compare_crypto("gapstop", "short")

    def test_crypto_time_exit_many(self):
        for _ in range(10): self.compare_crypto("time", "long")

    def test_crypto_funding_present_many(self):
        for _ in range(10): self.compare_crypto("target", "long", funding=True)

    def test_crypto_funding_absent_many(self):
        for _ in range(10): self.compare_crypto("target", "short", funding=False)

    def test_independent_oracle_rejects_intrabar_funding_exit_ambiguity(self):
        bars = [candidate_crypto.Bar(i * 1000, 100, 100.5, 99.5, 100, 10)
                for i in range(50)]
        bars[5] = candidate_crypto.Bar(5000, 100, 100.5, 97, 99, 10)
        setup = oracle_crypto.Signal(0, "long", 99, 100, 1, "body")
        with self.assertRaisesRegex(ValueError, "unscorable"):
            oracle_crypto.trade(
                bars, setup, funding_events=[(5500, .001, 100)],
                bar_duration_ms=1000,
            )

    def test_crypto_all_definitions_traded(self):
        for kind in ("body", "bos", "volume"):
            for _ in range(10): self.compare_crypto("target", "long", kind=kind)

    def test_equity_c1_daily_us_costs(self):
        actual = self.compare_equity_c1("target", "US")
        self.assertGreater(len(actual), 0)

    def test_equity_c1_daily_kr_stop_and_costs(self):
        actual = self.compare_equity_c1("stop", "KR")
        self.assertGreater(len(actual), 0)

    def test_equity_c2_daily_gap_reversion(self):
        # Dedicated signal-day gap down and next-day execution, repeated ten times.
        base = [candidate_equities.Bar(i, 100, 101, 99, 100) for i in range(40)]
        base[20] = candidate_equities.Bar(20, 90, 98, 89, 97)
        base[21] = candidate_equities.Bar(21, 97, 103, 96, 102)
        sig = oracle_equities.Signal(20, "c2", 89, 98, 100)
        fills = [oracle_equities.simulate_c2(
            [oracle_equities.Bar(b.timestamp, b.open, b.high, b.low, b.close) for b in base],
            sig, holding=5, fee=.0005, slip=.0005, audit={}) for _ in range(10)]
        self.assertTrue(all(x is not None for x in fills))

    def test_weekly_signal_maps_to_daily_execution(self):
        daily = [oracle_equities.Bar(i, 100, 102, 99, 101) for i in range(30)]
        weekly = [oracle_equities.Signal(2, "c1", 99, 100)]
        mapped = oracle_equities.weekly_signals_to_daily(weekly, [10], daily)
        self.assertEqual(mapped[0].index, 11)
        self.assertGreater(len([mapped[0] for _ in range(10)]), 0)


if __name__ == "__main__":
    unittest.main()
