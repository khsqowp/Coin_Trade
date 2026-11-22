import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from data_access import (EQUITY_COMMON_SPLIT_MS, UTC_CUTOFF_MS, _settlement_bar_ms, iter_train_bars,
                         load_bars, split_timestamp)


class DataAccessTests(unittest.TestCase):
    def test_sixty_forty_split_uses_last_train_timestamp(self):
        frame = pd.DataFrame({"open_time": range(10)})
        self.assertEqual(split_timestamp(frame), 5)

    def test_split_rejects_duplicate_or_unsorted_times(self):
        with self.assertRaises(ValueError):
            split_timestamp(pd.DataFrame({"open_time": [1, 1, 2]}))
        with self.assertRaises(ValueError):
            split_timestamp(pd.DataFrame({"open_time": [2, 1, 3]}))

    def test_funding_settlement_millisecond_jitter_maps_to_minute_bar(self):
        self.assertEqual(_settlement_bar_ms(1683331200009), 1683331200000)

    def test_post_cutoff_request_requires_explicit_freeze(self):
        with self.assertRaises(ValueError):
            load_bars("unused.parquet", window="test", split_file="split.json",
                      end_ms=UTC_CUTOFF_MS + 1)

    def test_train_and_test_are_disjoint_and_split_timestamp_persists(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "bars.parquet"
            split = root / "split.json"
            rows = pd.DataFrame({"open_time": range(10), "close": range(10)})
            rows.to_parquet(source)
            train = load_bars(source, window="train", split_file=split)
            test = load_bars(source, window="test", split_file=split)
            self.assertEqual(list(train.open_time), list(range(6)))
            self.assertEqual(list(test.open_time), list(range(6, 10)))
            self.assertTrue(set(train.open_time).isdisjoint(test.open_time))
            saved = json.loads(split.read_text())
            self.assertEqual(next(iter(saved.values()))["split_timestamp"], 5)

    def test_fixed_common_split_is_persisted_and_shared_despite_symbol_length(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            split = root / "split.json"
            outputs = []
            for symbol, count in (("SHORT", 8), ("LONG", 15)):
                source = root / f"{symbol}.parquet"
                pd.DataFrame({"open_time": range(count), "ticker": [symbol] * count,
                              "open": [10.0] * count, "high": [11.0] * count,
                              "low": [9.0] * count, "close": [10.0] * count}).to_parquet(source)
                outputs.append(load_bars(source, window="train", split_file=split,
                                         symbol=symbol, fixed_split_ms=5))
            self.assertEqual([list(frame.open_time) for frame in outputs],
                             [list(range(6)), list(range(6))])
            saved = json.loads(split.read_text())
            self.assertEqual({item["split_timestamp"] for item in saved.values()}, {5})
            self.assertTrue(all(item["fixed"] is True for item in saved.values()))

    def test_fixed_common_split_rejects_conflicting_cached_split(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "bars.parquet"
            split = root / "split.json"
            pd.DataFrame({"open_time": range(10), "close": range(10)}).to_parquet(source)
            load_bars(source, window="train", split_file=split)
            with self.assertRaisesRegex(ValueError, "conflicts with preregistered fixed split"):
                load_bars(source, window="train", split_file=split, fixed_split_ms=4)

    def test_crypto_bar_cutoff_excludes_bar_closing_after_freeze(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "bars.parquet"
            split = root / "split.json"
            cutoff = UTC_CUTOFF_MS
            pd.DataFrame({"open_time": [cutoff - 29 * 60_000,
                                         cutoff - 14 * 60_000],
                          "close": [10.0, 11.0]}).to_parquet(source)
            frame = load_bars(source, window="test", split_file=split,
                              fixed_split_ms=cutoff - 60 * 60_000,
                              bar_duration_ms=15 * 60_000)
            self.assertEqual(list(frame.open_time), [cutoff - 29 * 60_000])

    def test_equity_common_cutoff_is_frozen_preregistered_timestamp(self):
        self.assertEqual(pd.to_datetime(EQUITY_COMMON_SPLIT_MS, unit="ms", utc=True),
                         pd.Timestamp("2018-10-26 23:59:00", tz="UTC"))

    def test_crypto_loader_yields_one_symbol_train_only_and_lagged_funding_mark(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            start = int(pd.Timestamp("2020-01-01", tz="UTC").timestamp() * 1000)
            bars_dir = base / "cache/orderblock/bars/15m"
            bars_dir.mkdir(parents=True)
            bar_rows = pd.DataFrame({
                "open_time": [start + i * 900_000 for i in range(10)],
                "open": [100.0] * 10, "high": [101.0] * 10,
                "low": [99.0] * 10, "close": [100.0] * 10,
                "volume": [5.0] * 10, "complete": [True] * 10,
            })
            pq.write_table(pa.Table.from_pandas(bar_rows, preserve_index=False),
                           bars_dir / "BTCUSDT.parquet")

            funding_ts = start + 3 * 900_000 + 9
            funding_dir = base / "external/crypto/binance/um_fundingRate/BTCUSDT"
            funding_dir.mkdir(parents=True)
            pq.write_table(pa.table({"calc_time": [funding_ts],
                                     "last_funding_rate": [0.001]}),
                           funding_dir / "2020-01.parquet")
            future = base / "external/crypto/binance/um_fundingRate/BTCUSDT"
            pq.write_table(pa.table({"not_a_funding_schema": [1]}),
                           future / "2026-06.parquet")

            mark_dir = base / "external/crypto/binance/um_markPriceKlines_1m/BTCUSDT"
            mark_dir.mkdir(parents=True)
            mark_ts = funding_ts - 9 - 60_000
            pq.write_table(pa.table({"open_time": [mark_ts], "close": [99.5]}),
                           mark_dir / "2020-01.parquet")

            result = list(iter_train_bars("15m", data_dir=base, common_split_ms=None))
            self.assertEqual(len(result), 1)
            symbol, train_bars, funding = result[0]
            self.assertEqual(symbol, "BTCUSDT")
            self.assertEqual(len(train_bars), 6)
            self.assertTrue(all(bar.timestamp <= train_bars[-1].timestamp for bar in train_bars))
            normalized_ts = funding_ts - 9
            self.assertEqual(funding[normalized_ts].mark_price, 99.5)

    def test_crypto_loader_keeps_symbol_with_no_pre_cutoff_bars_as_empty(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            start = int(pd.Timestamp("2020-01-01", tz="UTC").timestamp() * 1000)
            bars_dir = base / "cache/orderblock/bars/15m"
            bars_dir.mkdir(parents=True)
            rows = pd.DataFrame({"open_time": [start + i * 900_000 for i in range(4)],
                                 "open": [100.0] * 4, "high": [101.0] * 4,
                                 "low": [99.0] * 4, "close": [100.0] * 4,
                                 "volume": [5.0] * 4, "complete": [True] * 4})
            pq.write_table(pa.Table.from_pandas(rows, preserve_index=False),
                           bars_dir / "NEWCOINUSDT.parquet")
            result = list(iter_train_bars("15m", data_dir=base,
                                          common_split_ms=start - 1))
            self.assertEqual(result, [("NEWCOINUSDT", [], {})])

    def test_crypto_loader_preserves_funding_event_when_mark_is_missing(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            start = int(pd.Timestamp("2020-01-01", tz="UTC").timestamp() * 1000)
            bars_dir = base / "cache/orderblock/bars/15m"
            bars_dir.mkdir(parents=True)
            rows = pd.DataFrame({"open_time": [start + i * 900_000 for i in range(10)],
                                 "open": [100.0] * 10, "high": [101.0] * 10,
                                 "low": [99.0] * 10, "close": [100.0] * 10,
                                 "volume": [5.0] * 10, "complete": [True] * 10})
            pq.write_table(pa.Table.from_pandas(rows, preserve_index=False),
                           bars_dir / "BTCUSDT.parquet")
            funding_ts = start + 3 * 900_000
            funding_dir = base / "external/crypto/binance/um_fundingRate/BTCUSDT"
            funding_dir.mkdir(parents=True)
            pq.write_table(pa.table({"calc_time": [funding_ts],
                                     "last_funding_rate": [0.001]}),
                           funding_dir / "2020-01.parquet")
            marks = base / "external/crypto/binance/um_markPriceKlines_1m/BTCUSDT"
            marks.mkdir(parents=True)
            result = list(iter_train_bars("15m", data_dir=base, common_split_ms=None))
            event = result[0][2][funding_ts]
            self.assertIsNone(event.mark_price)


if __name__ == "__main__":
    unittest.main()
