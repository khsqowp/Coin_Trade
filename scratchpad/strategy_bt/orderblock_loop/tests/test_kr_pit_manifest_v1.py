from __future__ import annotations

import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))

from data_sources.kr_pit.validate_pit_manifest_v1 import validate_manifest


class KrPitManifestTests(unittest.TestCase):
    membership_columns = [
        "security_id", "market", "symbol", "valid_from", "valid_through",
        "end_event", "source", "source_asof", "source_record_id",
    ]
    session_columns = ["market", "session_date", "source"]
    price_columns = [
        "security_id", "market", "symbol", "session_date", "open", "high",
        "low", "close", "volume", "source", "source_asof",
    ]
    action_columns = [
        "security_id", "effective_date", "action_type", "split_ratio",
        "cash_amount", "source", "source_asof",
    ]
    action_types = ["split", "cash_distribution", "merger", "delisting_settlement", "transfer"]

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.manifest_path = self.root / "manifest.json"
        self._write_csv("membership.csv", self.membership_columns, [self._member()])
        self._write_csv("sessions.csv", self.session_columns, [
            self._session("2020-01-02"), self._session("2020-01-03"), self._session("2020-01-06")])
        self._write_csv("prices.csv", self.price_columns, [
            self._price("2020-01-02"), self._price("2020-01-03"), self._price("2020-01-06")])
        self._write_csv("actions.csv", self.action_columns, [])
        self._write_manifest()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _member(self, **updates: str) -> dict[str, str]:
        row = {
            "security_id": "issuer-1", "market": "KOSPI", "symbol": "000001",
            "valid_from": "2020-01-02", "valid_through": "2026-05-31",
            "end_event": "active", "source": "synthetic", "source_asof": "2026-05-31",
            "source_record_id": "membership-1",
        }
        return {**row, **updates}

    @staticmethod
    def _session(day: str, market: str = "KOSPI") -> dict[str, str]:
        return {"market": market, "session_date": day, "source": "synthetic-calendar"}

    @staticmethod
    def _price(day: str, **updates: str) -> dict[str, str]:
        row = {
            "security_id": "issuer-1", "market": "KR", "symbol": "000001",
            "session_date": day, "open": "100", "high": "110", "low": "90",
            "close": "105", "volume": "1000", "source": "synthetic-prices",
            "source_asof": "2026-05-31",
        }
        return {**row, **updates}

    def _write_csv(self, name: str, columns: list[str], rows: list[dict[str, str]]) -> None:
        with (self.root / name).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)

    def _write_manifest(self, **overrides: object) -> None:
        names = ("membership.csv", "sessions.csv", "prices.csv", "actions.csv")
        datasets = {}
        for name in names:
            datasets[name.split(".")[0] if name != "prices.csv" else "prices"] = {
                "path": name,
                "format": "csv",
                "source_name": "synthetic fixture",
                "sha256": hashlib.sha256((self.root / name).read_bytes()).hexdigest(),
            }
        datasets["actions"]["coverage"] = {
            "complete": True,
            "start": "2020-01-02",
            "through": "2026-05-31",
            "event_types": self.action_types,
        }
        datasets["prices"]["price_basis"] = "raw_execution_prices"
        manifest = {
            "schema_version": 1,
            "cutoff": "2026-05-31",
            "rights": {"research_use_permitted": True, "evidence_ref": "synthetic-test-only"},
            "datasets": datasets,
            **overrides,
        }
        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    def _replace_prices(self, rows: list[dict[str, str]]) -> None:
        self._write_csv("prices.csv", self.price_columns, rows)
        self._write_manifest()

    def _replace_membership(self, rows: list[dict[str, str]]) -> None:
        self._write_csv("membership.csv", self.membership_columns, rows)
        self._write_manifest()

    def test_inclusive_interval_boundaries_and_matching_calendar_pass(self) -> None:
        result = validate_manifest(self.manifest_path)
        self.assertEqual(result["status"], "MANIFEST_CHECKS_PASS_REQUIRES_HUMAN_SOURCE_REVIEW")
        self.assertEqual(result["counts"]["price_rows"], 3)
        self.assertEqual(result["counts"]["missing_price_session_count"], 0)
        self.assertTrue(result["manual_provenance_review_required"])

    def test_reused_symbol_with_nonoverlapping_stable_ids_is_accepted(self) -> None:
        self._replace_membership([
            self._member(valid_through="2020-01-03", end_event="delisted", source_record_id="old"),
            self._member(security_id="issuer-2", valid_from="2020-01-06",
                         valid_through="2020-01-06", source_record_id="reused"),
        ])
        self._replace_prices([
            self._price("2020-01-02"), self._price("2020-01-03"),
            self._price("2020-01-06", security_id="issuer-2"),
        ])
        result = validate_manifest(self.manifest_path)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertNotIn("overlapping_symbol_intervals", codes)
        self.assertNotIn("price_membership_key_mismatch", codes)
        self.assertNotIn("missing_delisted_terminal_price", codes)

    def test_missing_delisted_terminal_price_is_blocked(self) -> None:
        self._replace_membership([self._member(end_event="delisted")])
        self._replace_prices([self._price("2020-01-02"), self._price("2020-01-03")])
        result = validate_manifest(self.manifest_path)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("missing_delisted_terminal_price", codes)
        self.assertIn("missing_price_sessions", codes)

    def test_market_mismatch_is_blocked(self) -> None:
        self._replace_prices([self._price(day, market="US") for day in
                              ("2020-01-02", "2020-01-03", "2020-01-06")])
        result = validate_manifest(self.manifest_path)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("price_market_mismatch", {issue["code"] for issue in result["issues"]})

    def test_zero_price_and_malformed_ohlc_are_blocked(self) -> None:
        rows = [self._price("2020-01-02", close="0"),
                self._price("2020-01-03"), self._price("2020-01-06")]
        self._replace_prices(rows)
        result = validate_manifest(self.manifest_path)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("zero_or_negative_price", codes)
        self.assertIn("malformed_ohlc", codes)

    def test_cutoff_stops_before_parsing_post_cutoff_ohlc(self) -> None:
        self._replace_membership([self._member(valid_from="2026-05-29", valid_through="2026-05-31")])
        self._write_csv("sessions.csv", self.session_columns, [self._session("2026-05-29")])
        self._replace_prices([
            self._price("2026-05-29"),
            self._price("2026-06-01", open="bad", high="bad", low="bad", close="bad"),
        ])
        result = validate_manifest(self.manifest_path)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("price_after_cutoff", codes)
        self.assertNotIn("malformed_price_number", codes)
        self.assertEqual(result["counts"]["price_rows"], 1)

    def test_price_row_without_source_asof_is_blocked(self) -> None:
        rows = [self._price("2020-01-02", source_asof=""),
                self._price("2020-01-03"), self._price("2020-01-06")]
        self._replace_prices(rows)
        result = validate_manifest(self.manifest_path)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("price_row_provenance_missing", {issue["code"] for issue in result["issues"]})

    def test_future_price_source_asof_is_blocked(self) -> None:
        rows = [self._price("2020-01-02", source_asof="2026-06-01"),
                self._price("2020-01-03"), self._price("2020-01-06")]
        self._replace_prices(rows)
        result = validate_manifest(self.manifest_path)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("invalid_price_provenance", {issue["code"] for issue in result["issues"]})

    def test_future_membership_source_asof_is_blocked(self) -> None:
        self._replace_membership([self._member(source_asof="2026-06-01")])
        result = validate_manifest(self.manifest_path)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("invalid_membership_date", {issue["code"] for issue in result["issues"]})

    def test_future_action_source_asof_is_blocked(self) -> None:
        self._write_csv("actions.csv", self.action_columns, [{
            "security_id": "issuer-1", "effective_date": "2020-01-03",
            "action_type": "cash_distribution", "split_ratio": "0", "cash_amount": "1",
            "source": "synthetic-actions", "source_asof": "2026-06-01",
        }])
        self._write_manifest()
        result = validate_manifest(self.manifest_path)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("invalid_action_provenance", {issue["code"] for issue in result["issues"]})

    def test_dataset_digest_mismatch_is_blocked(self) -> None:
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        manifest["datasets"]["prices"]["sha256"] = "0" * 64
        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        result = validate_manifest(self.manifest_path)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("dataset_sha256_mismatch", {issue["code"] for issue in result["issues"]})

    def test_post_cutoff_action_payload_is_not_parsed(self) -> None:
        self._write_csv("actions.csv", self.action_columns, [{
            "security_id": "issuer-1", "effective_date": "2026-06-01",
            "action_type": "split", "split_ratio": "not-a-number", "cash_amount": "",
            "source": "synthetic-actions", "source_asof": "2026-05-31",
        }])
        self._write_manifest()
        result = validate_manifest(self.manifest_path)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("action_after_cutoff", codes)
        self.assertNotIn("invalid_action_record", codes)

    def test_incomplete_distribution_action_provenance_is_blocked(self) -> None:
        self._write_manifest()
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        manifest["datasets"]["actions"]["coverage"]["event_types"].remove("cash_distribution")
        manifest["datasets"]["actions"]["coverage"]["complete"] = False
        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        result = validate_manifest(self.manifest_path)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("action_coverage_unverified", codes)
        self.assertIn("action_event_types_incomplete", codes)


if __name__ == "__main__":
    unittest.main()
