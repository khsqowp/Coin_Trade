import unittest
import gzip
import json
import tempfile
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from pathlib import Path

from archive_store import ShadowArchiveStore
from core import process_snapshot, score_summary


class FixedForecaster:
    def __init__(self, delta: float = 1.0):
        self.delta = delta
        self.calls = []

    def forecast(self, symbol, bars, horizon):
        self.calls.append((symbol, len(bars), horizon))
        return [float(bars[-1]["close"]) + self.delta * step for step in range(1, horizon + 1)]


def make_bars(start: int, closes: list[float]):
    return [
        {"minute": start + i, "open": close, "high": close, "low": close, "close": close, "volume": 1.0}
        for i, close in enumerate(closes)
    ]


class ShadowCoreTests(unittest.TestCase):
    def test_forecast_failure_does_not_advance_failed_symbol_or_block_others(self):
        class FailOnceForecaster(FixedForecaster):
            def __init__(self):
                super().__init__()
                self.failed = False

            def forecast(self, symbol, bars, horizon):
                if symbol == "ETH" and not self.failed:
                    self.failed = True
                    raise RuntimeError("temporary forecast failure")
                return super().forecast(symbol, bars, horizon)

        forecaster = FailOnceForecaster()
        output = {}
        bars = make_bars(100, [100.0] * 30)
        state = {"updated_at": "a", "bars": {"BTC": bars, "ETH": bars, "SOL": bars}, "summary": {}}
        with self.assertLogs("shadow_predictor.core", level="WARNING") as logs:
            self.assertTrue(process_snapshot(state, output, forecaster))
        self.assertIn("ETH", logs.output[0])
        self.assertEqual(set(output["latest_forecasts"]), {"BTC", "SOL"})
        self.assertEqual(output["last_processed_minute"], {"BTC": 129, "SOL": 129})
        self.assertEqual(len(output["pending"]), 4)

        self.assertTrue(process_snapshot(state, output, forecaster))
        self.assertEqual(output["last_processed_minute"]["ETH"], 129)
        self.assertEqual(set(output["latest_forecasts"]), {"BTC", "ETH", "SOL"})
        self.assertEqual(len(output["pending"]), 6)
        self.assertEqual([call[0] for call in forecaster.calls], ["BTC", "SOL", "ETH"])

    def test_pending_before_oldest_bar_expires_and_updates_coverage(self):
        def pending(target_minute):
            return {
                "symbol": "BTC", "horizon": 1, "origin_minute": target_minute - 1,
                "target_minute": target_minute, "origin_close": 100.0,
                "predicted_close": 101.0, "base_close": 100.0,
            }

        output = {"pending": [pending(99), pending(100), pending(101)]}
        state = {"updated_at": "a", "bars": {"BTC": make_bars(100, [100.0])}, "summary": {}}
        self.assertTrue(process_snapshot(state, output, FixedForecaster()))
        self.assertEqual([row["target_minute"] for row in output["pending"]], [101])
        self.assertEqual(len(output["scores"]), 1)
        self.assertEqual(output["expired"], [{
            "symbol": "BTC", "horizon": 1, "origin_minute": 98,
            "target_minute": 99, "predicted_close": 101.0,
            "base_close": 100.0, "status": "expired",
        }])
        self.assertEqual(output["coverage"], {"scored": 1, "expired": 1, "pending": 1})
        self.assertFalse(process_snapshot(state, output, FixedForecaster()))
        self.assertEqual(output["coverage"], {"scored": 1, "expired": 1, "pending": 1})

    def test_forecasts_once_per_new_minute_and_settles_against_actual_bars(self):
        forecaster = FixedForecaster()
        output = {}
        bars = make_bars(100, [100.0] * 30)
        state = {"updated_at": "a", "bars": {"BTC": bars}, "summary": {}}
        self.assertTrue(process_snapshot(state, output, forecaster))
        self.assertEqual(len(forecaster.calls), 1)
        self.assertFalse(process_snapshot(state, output, forecaster))
        later = make_bars(100, [100.0] * 30 + [101.0] * 5)
        state2 = {"updated_at": "b", "bars": {"BTC": later}, "summary": {}}
        self.assertTrue(process_snapshot(state2, output, forecaster))
        rows = output["scores"]
        self.assertEqual({row["horizon"] for row in rows}, {1, 5})
        self.assertEqual(len(rows), 2)
        self.assertEqual(output["last_processed_minute"]["BTC"], 134)

    def test_strategy_conflict_is_recorded_only_as_review(self):
        output = {}
        state = {
            "updated_at": "a",
            "bars": {"BTC": make_bars(1, [100.0] * 30)},
            "summary": {"s1": {"name": "test", "equity": 100, "total_pnl": 1, "trades": 2,
                                 "open_positions": {"BTC": {"side": "short"}}}},
        }
        process_snapshot(state, output, FixedForecaster(delta=1))
        conflict = output["strategy_snapshot"]["s1"]["forecast_conflicts_review_only"]
        self.assertEqual(conflict, [{"symbol": "BTC", "position_side": "short", "forecast_side": "long"}])
        self.assertFalse(output["guardrails"]["orders_enabled"])
        self.assertFalse(output["guardrails"]["strategy_changes"])

    def test_summary_compares_model_with_random_walk_baseline(self):
        summary = score_summary([{
            "symbol": "BTC", "horizon": 1, "absolute_error_pct": 2.0,
            "baseline_absolute_error_pct": 1.0, "direction_hit": True,
        }])
        self.assertEqual(summary["ALL:1m"]["samples"], 1)
        self.assertEqual(summary["ALL:1m"]["direction_accuracy_pct"], 100.0)


class ShadowArchiveTests(unittest.TestCase):
    def test_output_events_are_idempotent_and_closed_day_is_verified_before_deletion(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ShadowArchiveStore(root / "spool.sqlite3")
            output = {
                "pending": [{"symbol": "BTC", "horizon": 1, "origin_minute": 100,
                             "target_minute": 101, "predicted_close": 101.0}],
                "scores": [{"symbol": "BTC", "horizon": 1, "origin_minute": 99,
                            "target_minute": 100, "actual_close": 100.0}],
                "expired": [],
                "latest_forecasts": {"BTC": {"origin_minute": 100, "predicted_close_1m": 101.0}},
                "strategy_snapshot": {"s1": {"equity": 100.0}},
                "source_updated_at": "source-1",
            }
            self.assertEqual(store.record_output(output), 4)
            self.assertEqual(store.record_output(output), 0)
            yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
            with store._connect() as db:
                db.execute("UPDATE events SET event_date=?", (yesterday,))

            nas = root / "nas" / "Trade"
            nas.mkdir(parents=True)
            result = store.flush_closed_days(nas, root, require_mount=False)
            self.assertEqual(result, {"days_exported": 1, "events_deleted_after_verification": 4})
            archives = list((nas / "shadow-predictor").rglob("*.jsonl.gz"))
            self.assertEqual(len(archives), 1)
            with gzip.open(archives[0], "rt", encoding="utf-8") as handle:
                records = [json.loads(line) for line in handle]
            self.assertEqual(len(records), 4)
            with store._connect() as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM events").fetchone()[0], 0)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM archived_batches").fetchone()[0], 1)

    def test_mount_check_fails_before_creating_nas_subfolder(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ShadowArchiveStore(root / "spool.sqlite3")
            store.record_output({"scores": [{"symbol": "BTC", "horizon": 1,
                                               "origin_minute": 1, "target_minute": 2}]})
            trade = root / "Trade"
            trade.mkdir()
            with self.assertRaisesRegex(RuntimeError, "not mounted"):
                store.flush_closed_days(trade, root)
            self.assertFalse((trade / "shadow-predictor").exists())
            with store._connect() as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM events").fetchone()[0], 1)

    def test_failed_remote_verification_keeps_spool_rows(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ShadowArchiveStore(root / "spool.sqlite3")
            store.record_output({"scores": [{"symbol": "BTC", "horizon": 1,
                                               "origin_minute": 1, "target_minute": 2}]})
            yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
            with store._connect() as db:
                db.execute("UPDATE events SET event_date=?", (yesterday,))
            nas = root / "Trade"
            nas.mkdir()
            with patch("archive_store._verify_gzip", side_effect=IOError("simulated readback failure")):
                with self.assertRaisesRegex(IOError, "simulated readback failure"):
                    store.flush_closed_days(nas, root, require_mount=False)
            with store._connect() as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM events").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
