import unittest
import csv
import hashlib
import json
from pathlib import Path

import pandas as pd

from data_quality import SymbolQualityError, filter_equity_bars, tick_size


def bars(count=100):
    return pd.DataFrame({
        "open_time": range(count), "open": [10.0] * count,
        "high": [11.0] * count, "low": [9.0] * count,
        "close": [10.5] * count, "volume": [100.0] * count,
    })


class EquityDataQualityTests(unittest.TestCase):
    def test_drops_single_nonpositive_ohlc_row(self):
        frame = bars()
        frame.loc[3, "close"] = 0
        filtered, stats = filter_equity_bars(frame, "TEST")
        self.assertEqual(len(filtered), 99)
        self.assertEqual(stats["invalid_ohlc"], 0)
        self.assertEqual(stats["halt_bars"], 1)
        self.assertNotIn(3, filtered["open_time"].tolist())

    def test_drops_invalid_range_and_close_outside_range(self):
        frame = bars()
        frame.loc[1, "high"] = 8
        frame.loc[4, "close"] = 13
        filtered, stats = filter_equity_bars(frame, "TEST")
        self.assertEqual(len(filtered), 98)
        self.assertEqual(stats["invalid_ohlc"], 2)

    def test_drops_nonfinite_and_open_outside_range(self):
        frame = bars()
        frame.loc[1, "open"] = float("inf")
        frame.loc[4, "open"] = 13
        filtered, stats = filter_equity_bars(frame, "TEST")
        self.assertEqual(len(filtered), 98)
        self.assertEqual(stats["invalid_ohlc"], 1)
        self.assertEqual(stats["halt_bars"], 1)

    def test_rejects_symbol_when_bad_rows_are_concentrated(self):
        frame = bars()
        frame.loc[2:4, "close"] = 0
        filtered, stats = filter_equity_bars(frame, "HALT-ONLY")
        self.assertEqual(len(filtered), 97)
        self.assertEqual(stats["invalid_ohlc"], 0)
        self.assertEqual(stats["halt_bars"], 3)

    def test_many_zero_ohlc_rows_do_not_trigger_quality_caps(self):
        frame = bars()
        frame.loc[:, ["open", "high", "low", "close"]] = 0
        filtered, stats = filter_equity_bars(frame, "HALT-ONLY")
        self.assertTrue(filtered.empty)
        self.assertEqual(stats["invalid_ohlc"], 0)
        self.assertEqual(stats["halt_bars"], 100)

    def test_krx_tick_table_and_close_high_one_tick_tolerance(self):
        self.assertEqual([tick_size(p) for p in (999, 1000, 5000, 10000, 50000, 100000, 500000)],
                         [1, 5, 10, 50, 100, 500, 1000])
        for high, tick in ((500, 1), (2000, 5), (7000, 10), (20000, 50),
                           (70000, 100), (200000, 500), (700000, 1000)):
            frame = bars(1)
            frame.loc[0, ["open", "low", "high", "close"]] = [high, high - tick, high, high + tick]
            filtered, stats = filter_equity_bars(frame, "TICK")
            self.assertEqual(len(filtered), 1, f"high={high}")
            self.assertEqual(stats["invalid_ohlc"], 0, f"high={high}")

    def test_one_tick_row_is_clamped_and_consistent_rows_are_unchanged(self):
        frame = bars(2)
        original = frame.iloc[1].copy()
        frame.loc[0, ["open", "high", "low", "close"]] = [2000, 2000, 1900, 2005]
        filtered, stats = filter_equity_bars(frame, "TICK")
        self.assertEqual(stats["tick_corrected"], 1)
        self.assertEqual(stats["invalid_ohlc"], 0)
        self.assertEqual(filtered.loc[0, "high"], 2005)
        self.assertEqual(filtered.loc[0, "low"], 1900)
        pd.testing.assert_series_equal(filtered.iloc[1], original, check_names=False)

    def test_already_consistent_row_is_not_tick_corrected(self):
        frame = bars(1)
        before = frame.copy(deep=True)
        filtered, stats = filter_equity_bars(frame, "CLEAN")
        self.assertEqual(stats["tick_corrected"], 0)
        pd.testing.assert_frame_equal(filtered, before)

    def test_two_tick_close_high_violation_is_rejected(self):
        frame = bars(100)
        frame.loc[0, ["open", "low", "high", "close"]] = [2000, 1900, 2000, 2010]
        filtered, stats = filter_equity_bars(frame, "TWO-TICK")
        self.assertEqual(len(filtered), 99)
        self.assertEqual(stats["invalid_ohlc"], 1)

    def test_tick_tolerance_at_band_boundary_uses_smaller_tick(self):
        frame = bars(100)
        frame.loc[0, ["open", "low", "high", "close"]] = [999, 999, 999, 1001]
        filtered, stats = filter_equity_bars(frame, "BOUNDARY")
        self.assertEqual(len(filtered), 99)
        self.assertEqual(stats["invalid_ohlc"], 1)

    def test_real_us_train_filter_is_unchanged_from_prechange_baseline(self):
        from search_equities_r3 import _load_train

        root = Path(__file__).resolve().parents[1]
        data_dir = Path("/Users/user/CODE/trading_data")
        split_file = data_dir / "cache/orderblock/equities_splits.json"
        baseline = {
            "AAL": {"kept": 3295, "invalid_ohlc": 0, "halt_bars": 0,
                    "sha256": "6d7b07f9843019eb57df89585107209a5ab592a70adb2d346d83abb96c860800"},
            "AAMRQ": {"kept": 0, "invalid_ohlc": 0, "halt_bars": 0,
                      "sha256": "a8f73c5747f51fb2a4ecffbd3bbf53b19d88842ed698f87393c920d86fd45eb4"},
            "AAPL": {"kept": 9552, "invalid_ohlc": 0, "halt_bars": 0,
                     "sha256": "9864d7410eda9cba281b2b89a489d80f11884ecb77a678f0b7d516be9027f9e7"},
            "ABI": {"kept": 0, "invalid_ohlc": 0, "halt_bars": 0,
                    "sha256": "a8f73c5747f51fb2a4ecffbd3bbf53b19d88842ed698f87393c920d86fd45eb4"},
            "ABS": {"kept": 0, "invalid_ohlc": 0, "halt_bars": 0,
                    "sha256": "a8f73c5747f51fb2a4ecffbd3bbf53b19d88842ed698f87393c920d86fd45eb4"},
            "ABT": {"kept": 9740, "invalid_ohlc": 0, "halt_bars": 0,
                    "sha256": "d6a60f610ba41ce93054531fe3155e0b5607d6dd7c1075cabe8cbf63116a686a"},
            "ABX": {"kept": 0, "invalid_ohlc": 0, "halt_bars": 0,
                    "sha256": "a8f73c5747f51fb2a4ecffbd3bbf53b19d88842ed698f87393c920d86fd45eb4"},
            "ACKH": {"kept": 0, "invalid_ohlc": 0, "halt_bars": 0,
                     "sha256": "a8f73c5747f51fb2a4ecffbd3bbf53b19d88842ed698f87393c920d86fd45eb4"},
        }
        with (root / "universe/US.csv").open(newline="") as handle:
            rows = list(csv.DictReader(handle))[:8]
        observed = {}
        for row in rows:
            symbol = row["symbol"]
            frame = _load_train(Path(row["daily_path"]), symbol, row["market"], split_file)
            kept, stats = filter_equity_bars(frame, symbol)
            csv_bytes = kept.to_csv(index=False, lineterminator="\n").encode()
            observed[symbol] = {"kept": len(kept), "invalid_ohlc": stats["invalid_ohlc"],
                                "halt_bars": stats["halt_bars"],
                                "tick_corrected": stats["tick_corrected"],
                                "sha256": hashlib.sha256(csv_bytes).hexdigest()}
        self.assertEqual({k: {x: v for x, v in val.items() if x != "tick_corrected"}
                          for k, val in observed.items()}, baseline)
        self.assertEqual({symbol: val["tick_corrected"] for symbol, val in observed.items()},
                         {symbol: 0 for symbol in baseline})

    def test_real_us_train_r3_bars_match_original_prechange_baseline(self):
        from search_equities_r3 import _bars, _load_train

        root = Path(__file__).resolve().parents[1]
        split_file = Path("/Users/user/CODE/trading_data/cache/orderblock/equity_splits_r3.json")
        baseline = {
            "AAL": (3295, "0465810c448040fbca1f9656d47af557c3c8d3046e8cb2680db774f68edc03e2"),
            "AAPL": (9552, "14daa6f4faad8073800627f3143e639983af4c546bd71886308e89264176d965"),
            "ABT": (9740, "81d305c2183fcebd91db227fa0cc726ffa2897eb3c0cc21a31f303cb0eb25cfb"),
        }
        with (root / "universe/US.csv").open(newline="") as handle:
            rows = {row["symbol"]: row for row in csv.DictReader(handle)
                    if row["symbol"] in baseline}
        self.assertEqual(set(rows), set(baseline))
        for symbol, row in rows.items():
            frame = _load_train(Path(row["daily_path"]), symbol, row["market"], split_file)
            stats = {}
            result = _bars(frame, symbol, stats)
            payload = [(bar.timestamp, bar.open, bar.high, bar.low, bar.close, bar.complete)
                       for bar in result]
            encoded = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode()
            self.assertEqual(len(result), baseline[symbol][0], symbol)
            self.assertEqual(hashlib.sha256(encoded).hexdigest(), baseline[symbol][1], symbol)
            self.assertEqual(stats["invalid_ohlc"], 0, symbol)
            self.assertEqual(stats["halt_bars"], 0, symbol)

    def test_drops_five_day_zero_volume_halt_run(self):
        frame = bars()
        frame.loc[1:5, "volume"] = 0
        filtered, stats = filter_equity_bars(frame, "HALTED")
        self.assertEqual(filtered["open_time"].tolist(), [0, *range(6, 100)])
        self.assertEqual(stats["halt_bars"], 5)

    def test_keeps_isolated_zero_volume_rows(self):
        frame = bars()
        frame.loc[2, "volume"] = 0
        filtered, stats = filter_equity_bars(frame, "THIN")
        self.assertEqual(len(filtered), 100)
        self.assertEqual(stats["halt_bars"], 0)


if __name__ == "__main__":
    unittest.main()
