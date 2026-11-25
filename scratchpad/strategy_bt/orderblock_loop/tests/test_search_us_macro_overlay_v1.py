import csv
import hashlib
import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import search_us_macro_overlay_v1 as us_macro
from search_us_macro_overlay_v1 import (
    Trial,
    build_cot_signals,
    build_vix_signals,
    evaluate_train,
    frozen_trials,
    LEDGER_ROUND,
    run_train_grid,
    expected_train_rows,
    validate_cot_rows,
    validate_spy_rows,
    validate_vx_rows,
    write_train_results,
)


class SearchUsMacroOverlayV1Tests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self._old_manifest_hash = us_macro.EXPECTED_SOURCE_MANIFEST_SHA256
        self.addCleanup(setattr, us_macro, "EXPECTED_SOURCE_MANIFEST_SHA256",
                        self._old_manifest_hash)
        self.data_root = Path(self._temp.name) / "trading_data"
        self.data_root.mkdir()
        self._data_root_patcher = patch.dict(
            os.environ, {"TRADING_DATA_DIR": str(self.data_root)},
        )
        self._data_root_patcher.start()
        self.addCleanup(self._data_root_patcher.stop)

    @staticmethod
    def calendar_for(rows):
        return {date.fromisoformat(str(row["date"])[:10]): row["session_close_at"]
                for row in rows}

    def source_metadata(self, normalized_sha256=None):
        normalized_sha256 = normalized_sha256 or {}
        source_dir = self.data_root / "sources"
        source_dir.mkdir(exist_ok=True)
        frozen_dir = self.data_root / "frozen_2026-05-31"
        frozen_dir.mkdir(exist_ok=True)
        manifest_sources = {}
        transform_paths = {}
        for name in ("spy", "vix", "cot", "calendar"):
            source_path = source_dir / f"{name}_original.csv"
            snapshot_path = frozen_dir / f"{name}.csv"
            snapshot_bytes = b"date,value\n2026-01-05,1\n"
            if snapshot_path.exists():
                snapshot_path.chmod(0o644)
            snapshot_path.write_bytes(snapshot_bytes)
            snapshot_path.chmod(0o444)
            snapshot_stat = snapshot_path.stat()
            transform_path = source_dir / f"{name}_transform.py"
            transform_path.write_text("# synthetic transform\n", encoding="utf-8")
            transform_paths[name] = transform_path.resolve()
            manifest_sources[name] = {
                "source_path": str(source_path.resolve()),
                "snapshot_path": str(snapshot_path.resolve()),
                "snapshot_stat": {"device": snapshot_stat.st_dev,
                                  "inode": snapshot_stat.st_ino,
                                  "mtime_ns": snapshot_stat.st_mtime_ns,
                                  "size": snapshot_stat.st_size,
                                  "mode": snapshot_stat.st_mode},
                "rows": 1, "bytes": len(snapshot_bytes),
                "sha256": hashlib.sha256(snapshot_bytes).hexdigest(),
                "schema": ["date", "value"],
                "date_min": "2026-01-05", "date_max": "2026-01-05",
                "normalized_sha256": normalized_sha256.get(name, "0" * 64),
                "rights_status": "confirmed",
                "transform_sha256": us_macro._file_sha256(transform_path),
            }
        manifest_path = source_dir / "cutoff_manifest.json"
        manifest = {"schema_version": 1, "snapshot_kind": "cutoff_only",
                    "freeze_cutoff": "2026-05-31", "sources": manifest_sources}
        manifest_bytes = us_macro._canonical_json(manifest).encode()
        manifest_path.write_bytes(manifest_bytes)
        manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
        us_macro.EXPECTED_SOURCE_MANIFEST_SHA256 = manifest_hash
        result = {}
        for name in ("spy", "vix", "cot", "calendar"):
            result[name] = {
                "manifest_path": str(manifest_path.resolve()),
                "manifest_sha256": manifest_hash,
                "normalized_sha256": manifest_sources[name]["normalized_sha256"],
                "transform_path": str(transform_paths[name]),
                "transform_sha256": manifest_sources[name]["transform_sha256"],
            }
        return result

    def source_metadata_for_eval(self, spy_rows, signals, hypothesis, session_calendar):
        spy = validate_spy_rows(spy_rows, session_calendar=session_calendar)
        signal_source = "vix" if hypothesis == "vix_curve" else "cot"
        hashes = {"spy": us_macro._json_sha256(spy),
                  "calendar": us_macro._json_sha256(us_macro._calendar_rows(session_calendar)),
                  signal_source: us_macro._json_sha256(us_macro._signal_rows(signals))}
        return self.source_metadata(hashes)

    def source_metadata_for_grid(self, spy_rows, vix, cot, session_calendar):
        spy = validate_spy_rows(spy_rows, session_calendar=session_calendar)
        hashes = {"spy": us_macro._json_sha256(spy),
                  "calendar": us_macro._json_sha256(us_macro._calendar_rows(session_calendar)),
                  "vix": us_macro._json_sha256(us_macro._signal_rows(vix)),
                  "cot": us_macro._json_sha256(us_macro._signal_rows(cot))}
        return self.source_metadata(hashes)

    @staticmethod
    def repin_manifest(metadata, manifest_path):
        digest = hashlib.sha256(Path(manifest_path).read_bytes()).hexdigest()
        us_macro.EXPECTED_SOURCE_MANIFEST_SHA256 = digest
        for source in metadata.values():
            source["manifest_sha256"] = digest

    def test_manifest_hash_tampering_is_rejected(self):
        metadata = self.source_metadata()
        manifest_path = Path(metadata["spy"]["manifest_path"])
        manifest_path.write_bytes(manifest_path.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "does not match preregistered hash"):
            us_macro._validate_source_metadata(metadata)

    def test_post_cutoff_append_is_rejected_without_opening_snapshot(self):
        metadata = self.source_metadata()
        manifest_path = Path(metadata["spy"]["manifest_path"])
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        snapshot_path = Path(manifest["sources"]["spy"]["snapshot_path"])
        snapshot_path.chmod(0o644)
        with snapshot_path.open("ab") as handle:
            handle.write(b"2026-06-01,2\n")
        snapshot_path.chmod(0o444)
        original_open = Path.open

        def no_snapshot_open(path, *args, **kwargs):
            if path.resolve() == snapshot_path.resolve():
                raise AssertionError("validator read post-cutoff snapshot bytes")
            return original_open(path, *args, **kwargs)

        with patch.object(Path, "open", no_snapshot_open):
            with self.assertRaisesRegex(ValueError, "snapshot stat mismatch"):
                us_macro._validate_source_metadata(metadata)

    def test_snapshot_content_hash_is_checked_against_pinned_manifest(self):
        metadata = self.source_metadata()
        manifest_path = Path(metadata["spy"]["manifest_path"])
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        source = manifest["sources"]["spy"]
        snapshot_path = Path(source["snapshot_path"])
        snapshot_path.chmod(0o644)
        original = snapshot_path.read_bytes()
        tampered = original.replace(b",1\n", b",2\n")
        self.assertEqual(len(original), len(tampered))
        snapshot_path.write_bytes(tampered)
        snapshot_path.chmod(0o444)
        stat = snapshot_path.stat()
        source["snapshot_stat"] = {"device": stat.st_dev, "inode": stat.st_ino,
                                   "mtime_ns": stat.st_mtime_ns,
                                   "size": stat.st_size, "mode": stat.st_mode}
        manifest_path.write_text(us_macro._canonical_json(manifest), encoding="utf-8")
        self.repin_manifest(metadata, manifest_path)
        with self.assertRaisesRegex(ValueError, "content hash mismatch"):
            us_macro._validate_source_metadata(metadata)

    def test_pinned_manifest_post_cutoff_range_is_rejected(self):
        metadata = self.source_metadata()
        manifest_path = Path(metadata["spy"]["manifest_path"])
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["sources"]["spy"]["date_max"] = "2026-06-01"
        manifest_path.write_text(us_macro._canonical_json(manifest), encoding="utf-8")
        self.repin_manifest(metadata, manifest_path)
        with self.assertRaisesRegex(ValueError, "outside cutoff"):
            us_macro._validate_source_metadata(metadata)

    def test_normalized_train_hash_must_match_frozen_manifest(self):
        rows = self.spy_rows(6)
        calendar = self.calendar_for(rows)
        spy = validate_spy_rows(rows, session_calendar=calendar)
        signals = {row["date"]: 0.0 for row in spy}
        expected = {"spy": us_macro._json_sha256(spy),
                    "calendar": us_macro._json_sha256(us_macro._calendar_rows(calendar)),
                    "vix": us_macro._json_sha256(us_macro._signal_rows(signals))}
        metadata = self.source_metadata(expected)
        actual = dict(expected, vix="f" * 64)
        with self.assertRaisesRegex(ValueError, "does not match frozen vix snapshot"):
            us_macro._validate_source_metadata(metadata, normalized_sha256=actual)

    def result_fixture(self):
        source_metadata = self.source_metadata(
            {"spy": "e" * 64, "vix": "f" * 64,
             "cot": "0" * 64, "calendar": "9" * 64})
        return {"trial_id": "US-VIX-01", "window": "train",
                "parameters": {"hypothesis": "vix_curve", "threshold": 0.0,
                               "persistence": 1},
                "common_rows": 10, "train_rows": 6,
                "train_first_signal_date": "2026-01-05",
                "train_last_signal_date": "2026-01-12",
                "common_dates_sha256": "c" * 64, "train_prefix_sha256": "d" * 64,
                "sessions": 1, "strategy_annualized_simple_return_on_initial_capital": 0.0,
                "strategy_total_return": 0.0, "strategy_yearly_returns": {},
                "buy_hold_total_return": 0.0, "active_return": 0.0,
                "annualized_sharpe": None, "max_drawdown": 0.0,
                "daily_path": [{"date": "2026-01-07", "strategy_nav": 1.0,
                                "buy_hold_nav": 1.0}],
                "candidate_status": "exploratory_challenger_not_G_eligible",
                "input_sha256": {"spy_normalized": "e" * 64,
                                 "macro_normalized": "f" * 64,
                                 "calendar_normalized": "9" * 64},
                "source_metadata": source_metadata,
                "transform_sha256": {key: source_metadata[key]["transform_sha256"] for key in
                                      ("spy", "vix", "cot", "calendar")},
                "code_sha256": "a" * 64, "preregistration_sha256": "9" * 64}

    @staticmethod
    def split_metadata(common_rows, train_rows, all_rows):
        common_dates = [str(row["date"])[:10] for row in all_rows]
        prefix_dates = common_dates[:len(train_rows)]
        common_hash = hashlib.sha256(json.dumps(common_dates, separators=(",", ":"),
                                        sort_keys=True).encode()).hexdigest()
        prefix_hash = hashlib.sha256(json.dumps(prefix_dates, separators=(",", ":"),
                                        sort_keys=True).encode()).hexdigest()
        return {"common_rows": common_rows, "train_rows": len(train_rows),
                "train_first_date": train_rows[0]["date"],
                "train_last_date": train_rows[-1]["date"],
                "common_session_dates": common_dates,
                "common_dates_sha256": common_hash,
                "train_prefix_sha256": prefix_hash}

    @staticmethod
    def write_synthetic_ledger(path, trials):
        module_dir = Path(__file__).resolve().parents[1]
        code_hash = hashlib.sha256((module_dir / "search_us_macro_overlay_v1.py").read_bytes()).hexdigest()
        prereg_hash = hashlib.sha256((module_dir / "PREREG_US_MACRO_OVERLAY_V1.md").read_bytes()).hexdigest()
        fields = ["trial_id", "round", "market_group", "definition",
                  "parameter_grid_hash", "code_sha256"]
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for trial in trials:
                writer.writerow({"trial_id": trial.trial_id, "round": LEDGER_ROUND,
                                 "market_group": "US",
                                 "definition": json.dumps({"hypothesis": trial.hypothesis,
                                                            "threshold": trial.threshold,
                                                            "persistence": trial.persistence},
                                                           sort_keys=True, separators=(",", ":")),
                                 "parameter_grid_hash": prereg_hash,
                                 "code_sha256": code_hash})
        return path

    @staticmethod
    def weekdays(start, count):
        days = []
        current = start
        while len(days) < count:
            if current.weekday() < 5:
                days.append(current)
            current += timedelta(days=1)
        return days

    @classmethod
    def spy_rows(cls, count=12, opens=None):
        days = cls.weekdays(date(2026, 1, 5), count)
        prices = opens or [100.0 + i for i in range(count)]
        return [{"date": day.isoformat(), "session_close_at": f"{day.isoformat()}T21:00:00+00:00",
                 "open": prices[i], "close": prices[i], "dividends": 0.0,
                 "stock_splits": 0.0, "capital_gains": 0.0}
                for i, day in enumerate(days)]

    @classmethod
    def cot_rows(cls, count=56):
        rows = []
        report_date = date(2024, 12, 24)
        for index in range(count):
            release = report_date + timedelta(days=3)
            rows.append({"report_date": report_date.isoformat(),
                         "published_at": f"{release.isoformat()}T20:30:00+00:00",
                         "market": "S&P 500 Consolidated",
                         "leveraged_long": 1000 + index * 10,
                         "leveraged_short": 500,
                         "open_interest": 5000})
            report_date += timedelta(days=7)
        return rows

    @classmethod
    def vx_rows(cls, spy_rows, *, available_at="20:00:00+00:00"):
        rows = []
        for source in spy_rows:
            day = date.fromisoformat(str(source["date"])[:10])
            for expiry, settle in ((day + timedelta(days=30), 20.0),
                                   (day + timedelta(days=60), 21.0)):
                rows.append({"trade_date": day.isoformat(), "expiry_date": expiry.isoformat(),
                             "settle": settle,
                             "available_at": f"{day.isoformat()}T{available_at}"})
        return rows

    def test_frozen_grid_has_twelve_unique_trial_ids(self):
        trials = frozen_trials()
        self.assertEqual(len(trials), 12)
        self.assertEqual(len({trial.trial_id for trial in trials}), 12)
        self.assertEqual([trial.trial_id for trial in trials[:6]],
                         [f"US-VIX-{index:02d}" for index in range(1, 7)])
        self.assertEqual([trial.trial_id for trial in trials[6:]],
                         [f"US-COT-{index:02d}" for index in range(1, 7)])

    def test_post_cutoff_rows_and_missing_corporate_actions_fail_closed(self):
        rows = self.spy_rows(6)
        rows[-1]["date"] = "2026-06-01"
        with self.assertRaisesRegex(ValueError, "post-cutoff"):
            validate_spy_rows(rows, session_calendar=self.calendar_for(rows))
        incomplete = self.spy_rows(6)
        del incomplete[2]["dividends"]
        with self.assertRaisesRegex(ValueError, "missing required fields"):
            validate_spy_rows(incomplete, session_calendar=self.calendar_for(incomplete))

    def test_verified_nyse_calendar_blocks_wrong_regular_or_early_close(self):
        rows = self.spy_rows(6)
        calendar = self.calendar_for(rows)
        calendar[date.fromisoformat(rows[4]["date"])] = "2026-01-09T18:00:00+00:00"
        with self.assertRaisesRegex(ValueError, "disagrees with NYSE calendar"):
            validate_spy_rows(rows, session_calendar=calendar)

    def test_cot_release_after_anchor_close_cannot_change_earlier_signal(self):
        raw_spy = self.spy_rows(6)
        spy = validate_spy_rows(raw_spy, session_calendar=self.calendar_for(raw_spy))
        cot = validate_cot_rows([row for row in self.cot_rows()
                                 if row["published_at"] <= raw_spy[-1]["session_close_at"]])
        base = build_cot_signals(spy, cot, session_calendar=self.calendar_for(raw_spy))
        later = dict(cot[-1])
        later["report_date"] = "2026-01-07"
        later["published_at"] = "2026-01-07T20:30:00+00:00"
        later["leveraged_long"] = 100000
        later["leveraged_short"] = 0
        later["open_interest"] = 1000
        changed = build_cot_signals(spy, validate_cot_rows(cot + [later]),
                                    session_calendar=self.calendar_for(raw_spy))
        self.assertEqual(base[spy[1]["date"]], changed[spy[1]["date"]])

    def test_cot_release_after_nyse_early_close_is_not_used_that_day(self):
        raw_spy = self.spy_rows(6)
        early_day = date.fromisoformat(raw_spy[4]["date"])
        raw_spy[4]["session_close_at"] = f"{early_day.isoformat()}T18:00:00+00:00"
        calendar = self.calendar_for(raw_spy)
        spy = validate_spy_rows(raw_spy, session_calendar=calendar)
        reports = [row for row in self.cot_rows()
                   if row["published_at"] <= raw_spy[-1]["session_close_at"]]
        release_report_date = (early_day - timedelta(days=3)).isoformat()
        before_report = [dict(row) for row in reports
                         if row["report_date"] != release_report_date]
        after_close_report = [dict(row) for row in reports]
        for row in after_close_report:
            if row["report_date"] == release_report_date:
                row["published_at"] = f"{early_day.isoformat()}T18:30:00+00:00"
                row["leveraged_long"] = 0
                row["leveraged_short"] = 1000
        base = build_cot_signals(spy, validate_cot_rows(before_report),
                                 session_calendar=calendar)
        changed = build_cot_signals(spy, validate_cot_rows(after_close_report),
                                    session_calendar=calendar)
        self.assertEqual(base[early_day], changed[early_day])
        self.assertNotEqual(base[spy[5]["date"]], changed[spy[5]["date"]])

    def test_cot_missing_or_naive_publication_time_is_rejected(self):
        missing = self.cot_rows()
        del missing[0]["published_at"]
        with self.assertRaisesRegex(ValueError, "normalized fields"):
            validate_cot_rows(missing)
        naive = self.cot_rows()
        naive[0]["published_at"] = "2025-01-03T20:30:00"
        with self.assertRaisesRegex(ValueError, "timezone"):
            validate_cot_rows(naive)
        mixed_market = self.cot_rows()
        mixed_market[0]["market"] = "E-MINI S&P 500"
        with self.assertRaisesRegex(ValueError, "exactly the preregistered"):
            validate_cot_rows(mixed_market)

    def test_cot_rows_after_train_boundary_are_rejected(self):
        raw_spy = self.spy_rows(6)
        train = validate_spy_rows(raw_spy[:5],
                                  session_calendar=self.calendar_for(raw_spy[:5]))
        future = validate_cot_rows(self.cot_rows(57))
        with self.assertRaisesRegex(ValueError, "beyond the frozen TRAIN boundary"):
            build_cot_signals(train, future,
                              session_calendar=self.calendar_for(raw_spy[:5]))

    def test_vx_needs_two_unexpired_contracts_available_by_spy_close(self):
        raw_spy = self.spy_rows(6)
        spy = validate_spy_rows(raw_spy, session_calendar=self.calendar_for(raw_spy))
        valid = validate_vx_rows(self.vx_rows(spy))
        self.assertEqual(len(build_vix_signals(spy, valid,
                                               session_calendar=self.calendar_for(raw_spy))), len(spy))
        too_late = validate_vx_rows(self.vx_rows(spy, available_at="22:00:00+00:00"))
        with self.assertRaisesRegex(ValueError, "missing two point-in-time"):
            build_vix_signals(spy, too_late, session_calendar=self.calendar_for(raw_spy))

    def test_expired_vx_contract_is_rejected(self):
        row = {"trade_date": "2026-01-05", "expiry_date": "2026-01-05",
               "settle": 20, "available_at": "2026-01-05T20:00:00Z"}
        with self.assertRaisesRegex(ValueError, "expired"):
            validate_vx_rows([row])

    def test_vx_backdated_release_and_post_train_rows_are_rejected(self):
        raw = self.spy_rows(6)
        spy = validate_spy_rows(raw, session_calendar=self.calendar_for(raw))
        backdated = self.vx_rows(spy)
        backdated[0]["available_at"] = "2026-01-04T20:00:00+00:00"
        with self.assertRaisesRegex(ValueError, "cannot precede"):
            validate_vx_rows(backdated)
        train = spy[:5]
        with self.assertRaisesRegex(ValueError, "beyond the frozen TRAIN boundary"):
            build_vix_signals(train, validate_vx_rows(self.vx_rows(spy)),
                              session_calendar=self.calendar_for(raw[:5]))

    def test_sixty_forty_split_loads_only_train_prefix_count(self):
        self.assertEqual(expected_train_rows(10), 6)
        self.assertEqual(expected_train_rows(16), 9)
        with self.assertRaisesRegex(ValueError, "at least five"):
            expected_train_rows(4)

    def test_later_slice_with_expected_row_count_fails_prefix_hash(self):
        full_spy = self.spy_rows(10)
        later_slice = full_spy[1:7]
        spy = validate_spy_rows(later_slice,
                                session_calendar=self.calendar_for(later_slice))
        signals = {row["date"]: 0.0 for row in spy}
        trial = frozen_trials()[0]
        with tempfile.TemporaryDirectory() as temp:
            ledger = self.write_synthetic_ledger(Path(temp) / "synthetic.csv", [trial])
            with patch("search_us_macro_overlay_v1.SHARED_LEDGER_PATH", ledger):
                with self.assertRaisesRegex(ValueError, "exact beginning"):
                    evaluate_train(spy, signals, trial,
                                   session_calendar=self.calendar_for(later_slice),
                                   split_metadata=self.split_metadata(10, later_slice, full_spy),
                                   source_metadata=self.source_metadata_for_eval(
                                       spy, signals, trial.hypothesis,
                                       self.calendar_for(later_slice)))

    def test_next_session_open_fill_and_unregistered_trial_block(self):
        raw = self.spy_rows(12, [100, 100, 100, 200, 200, 200, 200, 200, 200, 200, 200, 200])
        train = raw[:expected_train_rows(12)]
        spy = validate_spy_rows(train, session_calendar=self.calendar_for(train))
        signals = {row["date"]: (0.10 if index >= 1 else -0.10)
                   for index, row in enumerate(spy)}
        trial = Trial("US-VIX-01", "vix_curve", 0.0, 1)
        with tempfile.TemporaryDirectory() as temp:
            ledger = self.write_synthetic_ledger(Path(temp) / "synthetic.csv", [trial])
            with patch("search_us_macro_overlay_v1.SHARED_LEDGER_PATH", ledger):
                result = evaluate_train(spy, signals, trial,
                                        session_calendar=self.calendar_for(train),
                                        split_metadata=self.split_metadata(12, train, raw),
                                        source_metadata=self.source_metadata_for_eval(
                                            spy, signals, trial.hypothesis,
                                            self.calendar_for(train)))
        self.assertEqual(result["fills"][0]["signal_date"], spy[1]["date"].isoformat())
        self.assertEqual(result["fills"][0]["execution_date"], spy[2]["date"].isoformat())
        self.assertGreater(result["strategy_total_return"], 0)

    def test_cost_stress_and_buy_hold_use_same_price_window(self):
        raw_spy = self.spy_rows(16)
        train = raw_spy[:expected_train_rows(16)]
        spy = validate_spy_rows(train, session_calendar=self.calendar_for(train))
        vix = {row["date"]: (0.10 if index % 4 in (2, 3) else -0.10)
               for index, row in enumerate(spy)}
        cot = {row["date"]: (0.95 if index % 4 in (2, 3) else 0.20)
               for index, row in enumerate(spy)}
        with tempfile.TemporaryDirectory() as temp:
            ledger = self.write_synthetic_ledger(Path(temp) / "synthetic.csv", frozen_trials())
            with patch("search_us_macro_overlay_v1.SHARED_LEDGER_PATH", ledger):
                outputs = run_train_grid(train, vix, cot,
                                         session_calendar=self.calendar_for(train),
                                         split_metadata=self.split_metadata(16, train, raw_spy),
                                         source_metadata=self.source_metadata_for_grid(
                                             train, vix, cot, self.calendar_for(train)))
        self.assertEqual(len(outputs), 36)
        base = outputs[0]
        double_cost = outputs[1]
        self.assertLess(double_cost["buy_hold_total_return"], base["buy_hold_total_return"])
        self.assertEqual(base["window"], "train")
        self.assertTrue(all(row["sessions"] > 0 for row in outputs))
        self.assertIn("strategy_yearly_returns", base)
        self.assertEqual(len(base["daily_path"]), base["sessions"])
        self.assertEqual(set(base["input_sha256"]),
                         {"spy_normalized", "macro_normalized", "calendar_normalized"})
        self.assertEqual(set(base["transform_sha256"]), {"spy", "vix", "cot", "calendar"})
        self.assertTrue(base["source_metadata"]["spy"]["snapshot"]["snapshot_path"].endswith("spy.csv"))
        previous_nav = 1.0
        for point in base["daily_path"]:
            self.assertAlmostEqual(point["strategy_daily_return_on_prior_nav"],
                                   point["strategy_nav"] / previous_nav - 1.0)
            previous_nav = point["strategy_nav"]
        year = next(iter(base["strategy_yearly_returns"]))
        self.assertAlmostEqual(base["strategy_yearly_returns"][year],
                               base["daily_path"][-1]["strategy_nav"] - 1.0)

    def test_buy_hold_reflects_dividend_cashflow_and_split_ratio(self):
        prices = [100.0] * 12
        prices[3] = 50.0
        raw = self.spy_rows(12, prices)
        raw[2]["dividends"] = 1.0
        raw[2]["capital_gains"] = 0.5
        raw[3]["stock_splits"] = 2.0
        train = raw[:expected_train_rows(12)]
        spy = validate_spy_rows(train, session_calendar=self.calendar_for(train))
        signals = {row["date"]: -0.10 for row in spy}
        trial = Trial("US-VIX-01", "vix_curve", 0.0, 1)
        with tempfile.TemporaryDirectory() as temp:
            ledger = self.write_synthetic_ledger(Path(temp) / "synthetic.csv", [trial])
            with patch("search_us_macro_overlay_v1.SHARED_LEDGER_PATH", ledger):
                result = evaluate_train(spy, signals, trial,
                                        session_calendar=self.calendar_for(train),
                                        split_metadata=self.split_metadata(12, train, raw),
                                        source_metadata=self.source_metadata_for_eval(
                                            spy, signals, trial.hypothesis,
                                            self.calendar_for(train)))
        self.assertGreater(result["buy_hold_total_return"], 0.012)
        self.assertAlmostEqual(result["strategy_total_return"], 0.0, places=6)

    def test_distributions_remain_cash_when_strategy_reenters_spy(self):
        prices = [100.0] * 20
        raw = self.spy_rows(20, prices)
        raw[3]["dividends"] = 100.0
        raw[6]["open"] = 200.0
        train = raw[:expected_train_rows(20)]
        spy = validate_spy_rows(train, session_calendar=self.calendar_for(train))
        signals = {row["date"]: (0.1 if index < 2 or index >= 4 else -0.1)
                   for index, row in enumerate(spy)}
        # A later doubling gains only on the deployed capital; the earlier cash
        # distribution stays outside the position when the strategy reenters.
        trial = frozen_trials()[0]
        with tempfile.TemporaryDirectory() as temp:
            ledger = self.write_synthetic_ledger(Path(temp) / "synthetic.csv", [trial])
            with patch("search_us_macro_overlay_v1.SHARED_LEDGER_PATH", ledger):
                with_distribution = evaluate_train(
                    spy, signals, trial, session_calendar=self.calendar_for(train),
                    split_metadata=self.split_metadata(20, train, raw),
                    source_metadata=self.source_metadata_for_eval(
                        spy, signals, trial.hypothesis, self.calendar_for(train)))
                train_no_distribution = [dict(row, dividends=0.0) for row in train]
                no_distribution = evaluate_train(
                    train_no_distribution, signals, trial,
                    session_calendar=self.calendar_for(train_no_distribution),
                    split_metadata=self.split_metadata(20, train_no_distribution, raw),
                    source_metadata=self.source_metadata_for_eval(
                        train_no_distribution, signals, trial.hypothesis,
                        self.calendar_for(train_no_distribution)))
        self.assertAlmostEqual(
            with_distribution["strategy_total_return"] - no_distribution["strategy_total_return"],
            100.0 * 0.999 / 100.0, places=6)
        year = next(iter(with_distribution["strategy_yearly_returns"]))
        self.assertAlmostEqual(
            with_distribution["strategy_yearly_returns"][year]
            - no_distribution["strategy_yearly_returns"][year],
            100.0 * 0.999 / 100.0, places=6)

    def test_incomplete_trial_registration_blocks_full_grid(self):
        full_spy = self.spy_rows(10)
        train = full_spy[:expected_train_rows(10)]
        signals = {row["date"]: 0.0 for row in
                   validate_spy_rows(train, session_calendar=self.calendar_for(train))}
        with tempfile.TemporaryDirectory() as temp:
            ledger = self.write_synthetic_ledger(Path(temp) / "synthetic.csv", frozen_trials()[:1])
            with patch("search_us_macro_overlay_v1.SHARED_LEDGER_PATH", ledger):
                with self.assertRaisesRegex(ValueError, "absent from the shared trial ledger"):
                    run_train_grid(train, signals, signals,
                                   session_calendar=self.calendar_for(train),
                                   split_metadata=self.split_metadata(10, train, full_spy),
                                   source_metadata=self.source_metadata())

    def test_trial_registration_hash_and_parameters_are_checked(self):
        trial = frozen_trials()[0]
        with tempfile.TemporaryDirectory() as temp:
            ledger = self.write_synthetic_ledger(Path(temp) / "synthetic.csv", [trial])
            with ledger.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
                fields = rows[0].keys()
            rows[0]["definition"] = "{}"
            with ledger.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            full_spy = self.spy_rows(10)
            train = full_spy[:expected_train_rows(10)]
            spy = validate_spy_rows(train, session_calendar=self.calendar_for(train))
            signals = {row["date"]: 0.0 for row in spy}
            with patch("search_us_macro_overlay_v1.SHARED_LEDGER_PATH", ledger):
                with self.assertRaisesRegex(ValueError, "ledger registration does not match"):
                    evaluate_train(spy, signals, trial,
                                   session_calendar=self.calendar_for(train),
                                   split_metadata=self.split_metadata(10, train, full_spy),
                                   source_metadata=self.source_metadata())

    def test_preregistration_and_code_hashes_are_checked_in_synthetic_ledger(self):
        trial = frozen_trials()[0]
        full_spy = self.spy_rows(10)
        train = full_spy[:expected_train_rows(10)]
        spy = validate_spy_rows(train, session_calendar=self.calendar_for(train))
        signals = {row["date"]: 0.0 for row in spy}
        for field in ("parameter_grid_hash", "code_sha256"):
            with tempfile.TemporaryDirectory() as temp:
                ledger = self.write_synthetic_ledger(Path(temp) / "synthetic.csv", [trial])
                with ledger.open(newline="", encoding="utf-8") as handle:
                    rows = list(csv.DictReader(handle))
                    fields = rows[0].keys()
                rows[0][field] = "c" * 64
                with ledger.open("w", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(handle, fieldnames=fields)
                    writer.writeheader()
                    writer.writerows(rows)
                with patch("search_us_macro_overlay_v1.SHARED_LEDGER_PATH", ledger):
                    with self.assertRaisesRegex(ValueError, "ledger registration does not match"):
                        evaluate_train(spy, signals, trial,
                                       session_calendar=self.calendar_for(train),
                                       split_metadata=self.split_metadata(10, train, full_spy),
                                       source_metadata=self.source_metadata())

    def test_result_artifact_is_written_under_data_root_without_overwrite(self):
        target = self.data_root / "cache" / "orderblock" / "us_macro_overlay_v1" / "train.json"
        with self.assertRaisesRegex(ValueError, "missing required provenance"):
            write_train_results([{"trial_id": "US-VIX-01"}],
                                output_path=str(target))
        valid_result = self.result_fixture()
        written = write_train_results([valid_result], output_path=str(target))
        with self.assertRaises(FileExistsError):
            write_train_results([valid_result], output_path=str(target))
        payload = json.loads(Path(written).read_text(encoding="utf-8"))
        self.assertEqual(payload["window"], "train")
        self.assertEqual(payload["results"][0]["trial_id"], "US-VIX-01")

    def test_result_path_cannot_escape_data_root(self):
        with tempfile.TemporaryDirectory() as temp:
            outside = Path(temp) / "outside.json"
            with self.assertRaisesRegex(ValueError, "below TRADING_DATA_DIR"):
                write_train_results([self.result_fixture()], output_path=str(outside))


if __name__ == "__main__":
    unittest.main()
