"""Validate supplier-provided KR point-in-time files without downloading data."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Iterator


DEFAULT_CUTOFF = date(2026, 5, 31)
BATCH_SIZE = 4096
MAX_ISSUES = 200
MARKET_ALIASES = {
    "KR": "KR",
    "KOSPI": "KR",
    "KOSDAQ": "KR",
    "KONEX": "KR",
    "KOSDAQ GLOBAL": "KR",
}
REQUIRED_COLUMNS = {
    "membership": {
        "security_id", "market", "symbol", "valid_from", "valid_through",
        "end_event", "source", "source_asof", "source_record_id",
    },
    "sessions": {"market", "session_date", "source"},
    "prices": {
        "security_id", "market", "symbol", "session_date", "open", "high",
        "low", "close", "volume", "source", "source_asof",
    },
    "actions": {
        "security_id", "effective_date", "action_type", "split_ratio",
        "cash_amount", "source", "source_asof",
    },
}
END_EVENTS = {"active", "delisted", "merger", "transfer"}
ACTION_TYPES = {"split", "cash_distribution", "merger", "delisting_settlement", "transfer"}


class ManifestInputError(ValueError):
    """Raised when a manifest or its file layout cannot be interpreted safely."""


def _day(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value[:10])
    except (TypeError, ValueError) as exc:
        raise ManifestInputError(f"invalid {field}: {value!r}") from exc


def _asof(value: str, cutoff: date, field: str) -> date:
    asof = _day(value, field)
    if asof > cutoff:
        raise ManifestInputError(f"{field} after cutoff: {asof} > {cutoff}")
    return asof


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _market(value: str) -> str:
    return MARKET_ALIASES.get(value.strip().upper(), value.strip().upper())


def _issue(report: dict[str, Any], code: str, detail: str) -> None:
    report["counts"][code] += 1
    if len(report["issues"]) < MAX_ISSUES:
        report["issues"].append({"code": code, "detail": detail})


def _dataset_path(dataset: dict[str, Any], root: Path, name: str) -> Path:
    raw = dataset.get("path")
    if not isinstance(raw, str) or not raw:
        raise ManifestInputError(f"{name}.path is required")
    path = (root / raw).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ManifestInputError(f"{name}.path escapes data_root")
    if not path.is_file():
        raise ManifestInputError(f"{name} file does not exist: {path}")
    return path


def _iter_rows(path: Path, dataset: dict[str, Any], required: set[str]) -> Iterator[dict[str, str]]:
    file_format = str(dataset.get("format", path.suffix.lstrip("."))).lower()
    if file_format == "csv":
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            fields = set(reader.fieldnames or [])
            missing = sorted(required - fields)
            if missing:
                raise ManifestInputError(f"{path.name} missing columns: {missing}")
            for row in reader:
                yield {str(key): str(value or "").strip() for key, value in row.items()}
        return
    if file_format != "parquet":
        raise ManifestInputError(f"unsupported format for {path.name}: {file_format}")
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ManifestInputError("pyarrow is required to stream parquet inputs") from exc
    parquet = pq.ParquetFile(path)
    fields = set(parquet.schema_arrow.names)
    missing = sorted(required - fields)
    if missing:
        raise ManifestInputError(f"{path.name} missing columns: {missing}")
    for batch in parquet.iter_batches(batch_size=BATCH_SIZE, columns=sorted(required)):
        columns = batch.to_pydict()
        for index in range(batch.num_rows):
            yield {key: str(columns[key][index] or "").strip() for key in columns}


def _read_membership(path: Path, dataset: dict[str, Any], cutoff: date,
                     report: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    rows: list[dict[str, Any]] = []
    by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for number, row in enumerate(_iter_rows(path, dataset, REQUIRED_COLUMNS["membership"]), start=2):
        try:
            start = _day(row["valid_from"], "valid_from")
            end = _day(row["valid_through"], "valid_through")
            _asof(row["source_asof"], cutoff, "source_asof")
        except ManifestInputError as exc:
            _issue(report, "invalid_membership_date", f"row {number}: {exc}")
            continue
        security_id = row["security_id"]
        market = _market(row["market"])
        symbol = row["symbol"]
        end_event = row["end_event"].lower()
        if not security_id or not symbol or not row["source"] or not row["source_record_id"]:
            _issue(report, "incomplete_membership_identity", f"row {number}")
            continue
        if market != "KR":
            _issue(report, "membership_market_mismatch", f"row {number}: {market}")
        if end_event not in END_EVENTS:
            _issue(report, "invalid_end_event", f"row {number}: {end_event}")
        if end_event == "active" and end != cutoff:
            _issue(report, "active_membership_short", f"row {number}: active interval ends {end}, cutoff {cutoff}")
        if start > end:
            _issue(report, "invalid_membership_interval", f"row {number}: {start}>{end}")
        if end > cutoff:
            _issue(report, "membership_after_cutoff", f"row {number}: {end}")
        item = {**row, "security_id": security_id, "market": market, "symbol": symbol,
                "valid_from_day": start, "valid_through_day": end, "end_event": end_event}
        rows.append(item)
        by_id[security_id].append(item)
    if not rows:
        _issue(report, "empty_membership", "no usable membership intervals")
    _check_intervals(rows, report)
    return rows, by_id


def _check_intervals(rows: list[dict[str, Any]], report: dict[str, Any]) -> None:
    for key_name in ("security_id", "symbol"):
        groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            value = row[key_name]
            groups[(row["market"], value)].append(row)
        for (market, value), group in groups.items():
            group.sort(key=lambda item: (item["valid_from_day"], item["valid_through_day"]))
            previous = None
            for current in group:
                if previous and current["valid_from_day"] <= previous["valid_through_day"]:
                    code = "overlapping_security_intervals" if key_name == "security_id" else "overlapping_symbol_intervals"
                    _issue(report, code, f"{market}/{value}: {previous['source_record_id']} overlaps {current['source_record_id']}")
                previous = current


def _read_sessions(path: Path, dataset: dict[str, Any], cutoff: date,
                   report: dict[str, Any]) -> dict[str, list[date]]:
    sessions: dict[str, set[date]] = defaultdict(set)
    for number, row in enumerate(_iter_rows(path, dataset, REQUIRED_COLUMNS["sessions"]), start=2):
        try:
            day = _day(row["session_date"], "session_date")
        except ManifestInputError as exc:
            _issue(report, "invalid_session_date", f"row {number}: {exc}")
            continue
        market = _market(row["market"])
        if market != "KR":
            _issue(report, "session_market_mismatch", f"row {number}: {market}")
        if not row["source"]:
            _issue(report, "session_source_missing", f"row {number}")
        if day > cutoff:
            _issue(report, "calendar_after_cutoff", f"row {number}: {day}")
            break
        if day in sessions[market]:
            _issue(report, "duplicate_session", f"row {number}: {market}/{day}")
        sessions[market].add(day)
    if not sessions.get("KR"):
        _issue(report, "empty_calendar", "no KR sessions")
    return {market: sorted(days) for market, days in sessions.items()}


def _read_actions(path: Path, dataset: dict[str, Any], cutoff: date,
                  membership_ids: set[str], report: dict[str, Any]) -> set[tuple[str, date]]:
    coverage = dataset.get("coverage", {})
    try:
        coverage_start = _day(coverage.get("start"), "actions.coverage.start")
        coverage_through = _day(coverage.get("through"), "actions.coverage.through")
    except ManifestInputError as exc:
        _issue(report, "action_coverage_unverified", str(exc))
        coverage_start, coverage_through = date.max, date.min
    if coverage.get("complete") is not True or coverage_start > min(
            (row["valid_from_day"] for row in report["membership_rows"]), default=cutoff):
        _issue(report, "action_coverage_unverified", "actions are not declared complete from first membership")
    if coverage_through < cutoff:
        _issue(report, "action_coverage_short", f"complete through {coverage_through}; cutoff {cutoff}")
    raw_event_types = coverage.get("event_types", [])
    declared_types = {str(value).lower() for value in raw_event_types} if isinstance(raw_event_types, list) else set()
    if not set(ACTION_TYPES).issubset(declared_types):
        _issue(report, "action_event_types_incomplete", f"declared event types: {sorted(declared_types)}")
    settlements: set[tuple[str, date]] = set()
    for number, row in enumerate(_iter_rows(path, dataset, REQUIRED_COLUMNS["actions"]), start=2):
        try:
            effective = _day(row["effective_date"], "effective_date")
        except ManifestInputError as exc:
            _issue(report, "invalid_action_record", f"row {number}: {exc}")
            continue
        if effective > cutoff:
            _issue(report, "action_after_cutoff", f"row {number}: {effective}")
            break
        try:
            split_ratio = float(row["split_ratio"] or "0")
            cash_amount = float(row["cash_amount"] or "0")
        except ValueError as exc:
            _issue(report, "invalid_action_record", f"row {number}: {exc}")
            continue
        action_type = row["action_type"].lower()
        security_id = row["security_id"]
        try:
            _asof(row["source_asof"], cutoff, "source_asof")
        except ManifestInputError as exc:
            _issue(report, "invalid_action_provenance", f"row {number}: {exc}")
        if not row["source"] or not row["source_asof"]:
            _issue(report, "action_row_provenance_missing", f"row {number}")
        if security_id not in membership_ids:
            _issue(report, "action_unknown_security", f"row {number}: {security_id}")
        elif not any(item["valid_from_day"] <= effective <= item["valid_through_day"]
                     for item in report["membership_rows"] if item["security_id"] == security_id):
            _issue(report, "action_outside_membership", f"row {number}: {security_id}/{effective}")
        if action_type not in ACTION_TYPES:
            _issue(report, "unknown_action_type", f"row {number}: {action_type}")
        if action_type == "split" and (not math.isfinite(split_ratio) or split_ratio <= 0):
            _issue(report, "invalid_split_ratio", f"row {number}: {split_ratio}")
        if action_type == "cash_distribution" and (not math.isfinite(cash_amount) or cash_amount < 0):
            _issue(report, "invalid_cash_distribution", f"row {number}: {cash_amount}")
        if action_type == "delisting_settlement":
            settlements.add((security_id, effective))
    return settlements


def _number(value: str, field: str, row_number: int, report: dict[str, Any]) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        _issue(report, "malformed_price_number", f"row {row_number}: {field}={value!r}")
        return None
    if not math.isfinite(number):
        _issue(report, "malformed_price_number", f"row {row_number}: {field} is non-finite")
        return None
    return number


def _expected_dates(security_rows: list[dict[str, Any]], sessions: list[date]) -> list[date]:
    intervals = [(row["valid_from_day"], row["valid_through_day"]) for row in security_rows]
    return [day for day in sessions if any(start <= day <= end for start, end in intervals)]


def _read_prices(path: Path, dataset: dict[str, Any], cutoff: date,
                 membership: dict[str, list[dict[str, Any]]], sessions_by_market: dict[str, list[date]],
                 settlements: set[tuple[str, date]], report: dict[str, Any]) -> None:
    previous_key: tuple[str, date] | None = None
    current_id: str | None = None
    expected: list[date] = []
    expected_index = 0
    seen_days: set[date] = set()

    def finish_security(security_id: str | None) -> None:
        nonlocal expected_index
        if not security_id:
            return
        missing = len(expected) - expected_index
        if missing > 0:
            _issue(report, "missing_price_sessions", f"{security_id}: {missing} expected sessions absent")
            report["counts"]["missing_price_session_count"] += missing
        for row in membership.get(security_id, []):
            if row["end_event"] in {"delisted", "merger", "transfer"}:
                terminal = row["valid_through_day"]
                if terminal not in seen_days and (security_id, terminal) not in settlements:
                    _issue(report, "missing_delisted_terminal_price", f"{security_id}/{terminal}")

    for row_number, row in enumerate(_iter_rows(path, dataset, REQUIRED_COLUMNS["prices"]), start=2):
        security_id = row["security_id"]
        if not security_id:
            _issue(report, "price_missing_security_id", f"row {row_number}")
            continue
        try:
            day = _day(row["session_date"], "session_date")
        except ManifestInputError as exc:
            _issue(report, "invalid_price_date", f"row {row_number}: {exc}")
            continue
        if day > cutoff:
            _issue(report, "price_after_cutoff", f"row {row_number}: {day}; stopped before parsing OHLC")
            report["cutoff_stop_row"] = row_number
            break
        key = (security_id, day)
        if previous_key and key < previous_key:
            _issue(report, "price_rows_not_sorted", f"row {row_number}: {key} follows {previous_key}")
        if previous_key == key:
            _issue(report, "duplicate_price_session", f"row {row_number}: {security_id}/{day}")
        previous_key = key
        if security_id != current_id:
            finish_security(current_id)
            current_id = security_id
            expected_index = 0
            seen_days = set()
            security_rows = membership.get(security_id)
            if not security_rows:
                _issue(report, "price_unknown_security", f"row {row_number}: {security_id}")
                expected = []
            else:
                markets = {row["market"] for row in security_rows}
                if len(markets) != 1:
                    _issue(report, "security_market_changes", security_id)
                market = next(iter(markets))
                expected = _expected_dates(security_rows, sessions_by_market.get(market, []))
        item_market = _market(row["market"])
        matching = [item for item in membership.get(security_id, [])
                    if item["valid_from_day"] <= day <= item["valid_through_day"]]
        if not matching:
            _issue(report, "price_outside_membership", f"row {row_number}: {security_id}/{day}")
        elif item_market != matching[0]["market"] or row["symbol"] != matching[0]["symbol"]:
            _issue(report, "price_membership_key_mismatch", f"row {row_number}: {item_market}/{row['symbol']}")
        if item_market != "KR":
            _issue(report, "price_market_mismatch", f"row {row_number}: {item_market}")
        try:
            _asof(row["source_asof"], cutoff, "source_asof")
        except ManifestInputError as exc:
            _issue(report, "invalid_price_provenance", f"row {row_number}: {exc}")
        if not row["source"] or not row["source_asof"]:
            _issue(report, "price_row_provenance_missing", f"row {row_number}")
        while expected_index < len(expected) and expected[expected_index] < day:
            expected_index += 1
            _issue(report, "missing_price_sessions", f"{security_id}: missing {expected[expected_index - 1]}")
            report["counts"]["missing_price_session_count"] += 1
        if expected_index < len(expected) and expected[expected_index] == day:
            expected_index += 1
        elif security_id in membership:
            if day not in seen_days:
                _issue(report, "price_not_on_trading_calendar", f"row {row_number}: {day}")
        seen_days.add(day)
        report["seen_security_ids"].add(security_id)
        report["counts"]["price_rows"] += 1
        values = {field: _number(row[field], field, row_number, report)
                  for field in ("open", "high", "low", "close", "volume")}
        if any(value is None for value in values.values()):
            continue
        opening, high, low, close, volume = (values[field] for field in ("open", "high", "low", "close", "volume"))
        if min(opening, high, low, close) <= 0:
            _issue(report, "zero_or_negative_price", f"row {row_number}: {security_id}/{day}")
        if low > high or not (low <= opening <= high) or not (low <= close <= high):
            _issue(report, "malformed_ohlc", f"row {row_number}: {security_id}/{day}")
        if volume < 0:
            _issue(report, "negative_volume", f"row {row_number}: {security_id}/{day}")
    finish_security(current_id)
    for security_id in membership:
        if security_id not in report["seen_security_ids"]:
            _issue(report, "security_without_prices", security_id)
            expected_missing = len(_expected_dates(membership[security_id],
                                                   sessions_by_market.get(membership[security_id][0]["market"], [])))
            if expected_missing:
                _issue(report, "missing_price_sessions", f"{security_id}: {expected_missing} expected sessions absent")
                report["counts"]["missing_price_session_count"] += expected_missing
            for item in membership[security_id]:
                if item["end_event"] in {"delisted", "merger", "transfer"} and \
                        (security_id, item["valid_through_day"]) not in settlements:
                    _issue(report, "missing_delisted_terminal_price", f"{security_id}/{item['valid_through_day']}")


def validate_manifest(manifest_path: Path, data_root: Path | None = None) -> dict[str, Any]:
    """Validate metadata and stream listed price rows; never writes or downloads."""
    manifest_path = manifest_path.resolve()
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestInputError(f"cannot read manifest: {exc}") from exc
    if manifest.get("schema_version") != 1:
        raise ManifestInputError("schema_version must equal 1")
    cutoff = _day(manifest.get("cutoff"), "cutoff")
    if cutoff != DEFAULT_CUTOFF:
        raise ManifestInputError(f"cutoff must be fixed at {DEFAULT_CUTOFF}")
    root = (data_root or manifest_path.parent).resolve()
    rights = manifest.get("rights", {})
    report: dict[str, Any] = {
        "schema_version": 1,
        "cutoff": cutoff.isoformat(),
        "manifest": str(manifest_path),
        "data_root": str(root),
        "manual_provenance_review_required": True,
        "rights_evidence_ref": rights.get("evidence_ref"),
        "status": "BLOCKED",
        "counts": defaultdict(int, {
            "membership_rows": 0,
            "calendar_sessions": 0,
            "price_rows": 0,
            "security_ids": 0,
            "missing_price_session_count": 0,
        }),
        "issues": [],
        "membership_rows": [],
        "seen_security_ids": set(),
    }
    if rights.get("research_use_permitted") is not True or not rights.get("evidence_ref"):
        _issue(report, "rights_unverified", "research permission and evidence_ref are required")
    datasets = manifest.get("datasets", {})
    missing_datasets = sorted(set(REQUIRED_COLUMNS) - set(datasets))
    if missing_datasets:
        raise ManifestInputError(f"datasets missing entries: {missing_datasets}")
    paths = {name: _dataset_path(datasets[name], root, name) for name in REQUIRED_COLUMNS}
    for name, dataset in datasets.items():
        digest = str(dataset.get("sha256", "")).lower()
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            _issue(report, "declared_sha256_missing", f"{name}.sha256 must be a 64-character hex digest")
        elif _sha256(paths[name]) != digest:
            _issue(report, "dataset_sha256_mismatch", f"{name} content differs from declared sha256")
        if not dataset.get("source_name"):
            _issue(report, "dataset_source_missing", f"{name}.source_name is required")
    if datasets["prices"].get("price_basis") != "raw_execution_prices":
        _issue(report, "price_basis_unverified", "prices.price_basis must be raw_execution_prices")
    membership_rows, membership = _read_membership(paths["membership"], datasets["membership"], cutoff, report)
    report["membership_rows"] = membership_rows
    report["counts"]["membership_rows"] = len(membership_rows)
    report["seen_security_ids"] = set()
    sessions = _read_sessions(paths["sessions"], datasets["sessions"], cutoff, report)
    report["counts"]["calendar_sessions"] = len(sessions.get("KR", []))
    settlements = _read_actions(paths["actions"], datasets["actions"], cutoff,
                                set(membership), report)
    _read_prices(paths["prices"], datasets["prices"], cutoff, membership, sessions, settlements, report)
    report["counts"]["security_ids"] = len(membership)
    report["counts"] = dict(report["counts"])
    report.pop("membership_rows", None)
    report.pop("seen_security_ids", None)
    if not report["issues"]:
        report["status"] = "MANIFEST_CHECKS_PASS_REQUIRES_HUMAN_SOURCE_REVIEW"
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--data-root", type=Path)
    args = parser.parse_args(argv)
    try:
        report = validate_manifest(args.manifest, args.data_root)
    except ManifestInputError as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, ensure_ascii=False), file=sys.stdout)
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] != "BLOCKED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
