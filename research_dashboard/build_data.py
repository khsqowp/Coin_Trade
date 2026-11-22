#!/usr/bin/env python3
"""Build the static, read-only strategy research dashboard dataset."""
import argparse
import csv
import math
import json
import os
import re
import sqlite3
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

PROFILES = {
    "l5_4h": {"interval_ms": 14400000, "test_trades": 255, "test_days": 1.9 * 365.25, "minimum_trades": 30, "minimum_days": 90, "test_return_pct": 20.6},
    # The historical backtest period is not recorded, so its pace cannot be projected.
    "l5_12h": {"interval_ms": 43200000, "test_trades": 78, "test_days": None, "minimum_trades": 30, "minimum_days": 90, "test_return_pct": 48.8},
    "jbb_1h": {"interval_ms": 3600000, "test_trades": 885, "test_days": 1.9 * 365.25, "minimum_trades": 100, "minimum_days": 60, "test_return_pct": 13.8},
}
TESTS = ["null", "plateau", "adjusted", "A1", "B1", "B2", "B3", "B4", "B5", "B6", "execution_stress", "regime"]


def read_csv(path):
    try:
        with path.open(newline="", encoding="utf-8-sig") as stream:
            return list(csv.DictReader(stream))
    except (OSError, UnicodeError, csv.Error):
        return []


def truth(value):
    return str(value or "").strip().lower() in {"true", "1", "yes", "pass", "passed", "robust"}


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def verdict_value(value):
    return str(value or "").strip().upper()


def describe(spec):
    name = str(spec.get("name") or "This strategy").strip().rstrip(".")
    long_rule = re.sub(r"\s+", " ", str(spec.get("entry_long") or "")).strip().rstrip(".")
    short_rule = re.sub(r"\s+", " ", str(spec.get("entry_short") or "")).strip().rstrip(".")
    exit_rule = re.sub(r"\s+", " ", str(spec.get("exit") or "")).strip().rstrip(".")
    if long_rule:
        sentence = f"{name} enters long when {long_rule}"
        if short_rule:
            sentence += f" and short when {short_rule}"
        if exit_rule:
            sentence += f", then exits when {exit_rule}"
        return sentence + "."
    indicators = re.sub(r"\s+", " ", str(spec.get("indicators") or "")).strip().rstrip(".")
    return f"{name} uses {indicators}." if indicators else "Strategy description unavailable."


def infer_timeframes(spec):
    text = str(spec.get("instruments_timeframes_claimed") or "")
    matches = re.findall(r"(?<![A-Za-z0-9])(\d+\s*[mhdw]|\d+[mhdw])(?![A-Za-z0-9])", text, re.I)
    result = {re.sub(r"\s+", "", x).lower() for x in matches}
    lower = text.lower()
    if "daily" in lower or "1 day" in lower or "daily bars" in lower:
        result.add("1d")
    if "hourly" in lower or "1 hour" in lower:
        result.add("1h")
    for amount, unit in re.findall(r"\b(\d+)\s*[- ]?(minute|hour|day|week)s?\b", lower):
        result.add(amount + {"minute": "m", "hour": "h", "day": "d", "week": "w"}[unit])
    return sorted(result)


def symbol_class(spec):
    text = str(spec.get("instruments_timeframes_claimed") or "").lower()
    return "crypto" if any(x in text for x in ("btc", "crypto", "binance", "usdt")) else ("equity" if any(x in text for x in ("stock", "equity", "spx", "nasdaq")) else "other")


def side_of(spec):
    long = bool(spec.get("entry_long"))
    short = bool(spec.get("entry_short"))
    if long and short:
        return "both"
    if short:
        return "short"
    return "long" if long else "unknown"


def _status(ok, reason, present=True):
    if not present:
        return {"status": "not_run", "plain_reason": reason}
    return {"status": "passed" if ok else "failed", "plain_reason": reason}


def verification_depth(node):
    """Count passed verification flags only; deliberately excludes all return metrics."""
    return sum(test["status"] == "passed" for test in node["tests"])


def make_tests(strategy_id, timeframe, summary, a1, group_b, costs, regimes, candidate_timeframes):
    tests = {}
    pctl = number(summary.get("null_percentile"))
    tests["null"] = _status(pctl is not None and pctl >= 95, "Null comparison reached the 95th percentile." if pctl is not None and pctl >= 95 else ("Null comparison is below the 95th percentile." if pctl is not None else "No usable null percentile was recorded."), pctl is not None)
    plateau = str(summary.get("plateau") or "").strip().upper()
    tests["plateau"] = _status(plateau in {"PASS", "ROBUST", "TRUE", "YES"}, "Nearby parameter settings remained acceptable." if plateau in {"PASS", "ROBUST", "TRUE", "YES"} else ("Nearby parameter settings did not meet the recorded plateau rule." if plateau else "No plateau result was recorded."), bool(plateau))
    adjusted = verdict_value(summary.get("adjusted_verdict"))
    tests["adjusted"] = _status(adjusted == "PASS", "Passed the multiple-testing correction." if adjusted == "PASS" else ("Did not pass the multiple-testing correction." if adjusted else "No adjusted verdict was recorded."), bool(adjusted))

    row = next((r for r in a1 if r.get("strategy_id") == strategy_id and r.get("timeframe") == timeframe), None)
    val = verdict_value(row.get("A1")) if row else ""
    tests["A1"] = _status(val == "PASS", "Passed the family-wide statistical check." if val == "PASS" else ("Failed the family-wide statistical check." if val else "No A1 result was recorded."), bool(val))
    group_rows = [r for r in group_b if r.get("candidate") == strategy_id] if candidate_timeframes.get(strategy_id) == timeframe else []
    final_row = next((r for r in group_rows if r.get("scenario") == "FINAL"), None)
    final_tag = str((final_row or {}).get("tag") or "")
    for name in (f"B{i}" for i in range(1, 7)):
        rows = [r for r in group_rows if r.get("scenario") == name]
        if name in {"B1", "B2", "B3"} and final_row:
            failed = name in re.findall(r"B[1-3]", final_tag)
            tests[name] = _status(not failed, f"{name} passed the recorded Group B final gate." if not failed else f"{name} failed the recorded Group B final gate.")
        elif name == "B4" and rows:
            values = [number(r.get("walk_forward_pct")) for r in rows]
            values = [x for x in values if x is not None]
            tests[name] = _status(bool(values) and all(x > 0 for x in values), "Walk-forward results stayed above zero." if values and all(x > 0 for x in values) else "Walk-forward results did not stay above zero.", bool(values))
        elif name == "B5" and rows:
            outcomes = [verdict_value(r.get("status")) for r in rows if re.fullmatch(r"20\d\d", r.get("window", ""))]
            applicable = [x for x in outcomes if x in {"PASS", "FAIL"}]
            passed = bool(applicable) and applicable.count("FAIL") <= len(applicable) / 2
            tests[name] = _status(passed, "The yearly comparison rule passed." if passed else "The yearly comparison rule failed.", bool(applicable))
        elif name == "B6" and rows:
            val = verdict_value(rows[0].get("status"))
            tests[name] = _status(val == "PASS", "The source-convention check passed." if val == "PASS" else "The source-convention check did not pass.", val in {"PASS", "FAIL"})
        else:
            tests[name] = _status(False, f"No applicable {name} result was recorded.", False)
    stress_rows = [r for r in costs if r.get("strategy_id") == strategy_id and number(r.get("cost_multiple")) == 2] if candidate_timeframes.get(strategy_id) == timeframe else []
    if stress_rows:
        # A2's established stress rule is profitability at doubled costs.
        vals = [number(r.get("test_return")) for r in stress_rows]
        valid = [x for x in vals if x is not None]
        passed = bool(valid) and all(x > 0 for x in valid)
        tests["execution_stress"] = _status(passed, "Stayed profitable at twice the base trading cost." if passed else "Turned unprofitable at twice the base trading cost.")
    else:
        tests["execution_stress"] = _status(False, "No doubled-cost stress result was recorded.", False)
    rr = [r for r in regimes if r.get("candidate") == strategy_id and r.get("variant") in {"V1", "V2", "V3"} and r.get("timeframe") == timeframe]
    if rr:
        passed = any(truth(r.get("PASS")) for r in rr)
        tests["regime"] = _status(passed, "At least one recorded regime test passed." if passed else "No tested regime configuration passed its preregistered gates.")
    else:
        tests["regime"] = _status(False, "No regime result was recorded for this strategy.", False)
    files = {
        "null": "scratchpad/strategy_bt/results/slice_*/summary.csv",
        "plateau": "scratchpad/strategy_bt/results/slice_*/summary.csv",
        "adjusted": "scratchpad/strategy_bt/results/slice_*/summary.csv",
        "A1": "scratchpad/strategy_bt/verify2a/a1_results.csv",
        **{f"B{i}": "scratchpad/strategy_bt/verify2b/results/group_b.csv" for i in range(1, 7)},
        "execution_stress": "scratchpad/strategy_bt/verify/cost_stress.csv",
        "regime": "scratchpad/strategy_bt/regime/results/results.csv",
    }
    columns = {"null": "null_percentile >= 95", "plateau": "plateau", "adjusted": "adjusted_verdict == PASS", "A1": "A1 == PASS", "B1": "FINAL tag contains/omits B1; timeframe from verify/reproduce.csv", "B2": "FINAL tag contains/omits B2; timeframe from verify/reproduce.csv", "B3": "FINAL tag contains/omits B3; timeframe from verify/reproduce.csv", "B4": "walk_forward_pct > 0; timeframe from verify/reproduce.csv", "B5": "yearly status; failures <= half; timeframe from verify/reproduce.csv", "B6": "status == PASS; timeframe from verify/reproduce.csv", "execution_stress": "cost_multiple == 2; test_return > 0; timeframe from verify/reproduce.csv", "regime": "timeframe; variant in V1/V2/V3; PASS"}
    return [{"name": name, **tests[name], "source_file": files[name] if tests[name]["status"] != "not_run" else "" , "source_column": columns[name]} for name in TESTS]


def forward_decision(name, trades, days, net_return_pct, backtest_verdict):
    prof = PROFILES[name]
    enough = trades >= prof["minimum_trades"] and days >= prof["minimum_days"]
    backtest_known = backtest_verdict not in (None, "", "미판정", "미연결")
    confirmed = enough and net_return_pct > 0 and backtest_known and backtest_verdict != "탈락"
    return {
        "data_sufficient": enough,
        "confirmed": confirmed,
        "decision_label": "판정 가능" if enough else "데이터 부족",
        "confirmation_label": "확정" if confirmed else "확정 아님",
        "no_signals": trades == 0,
        "required_trades": prof["minimum_trades"],
        "trades_left": max(0, prof["minimum_trades"] - trades),
        "days_left": round(max(0, prof["minimum_days"] - days), 1),
    }


def copied_at(forward_dir):
    try:
        value = (Path(forward_dir) / "COPIED_AT.txt").read_text(encoding="utf-8").strip()
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (OSError, ValueError):
        return None


def copy_age_minutes(copy_time, now=None):
    if copy_time is None:
        return None
    now = now or datetime.now(timezone.utc)
    return max(0, int((now - copy_time).total_seconds() // 60))


def forward_status(db_path, name, copy_time=None, backtest_verdict=None):
    prof = PROFILES[name]
    project_root = str(Path(__file__).resolve().parents[1])
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    try:
        from forward_test.config import SYMBOLS, get_profile
        from forward_test.status import status_data

        profile = get_profile(name)
        book = "long_only" if name == "jbb_1h" else "combined"
        uri = db_path.resolve().as_uri() + "?mode=ro"
        with sqlite3.connect(uri, uri=True) as db:
            status = status_data(db, book=book, profile=profile)
            book_status = status["books"][book]
            realized = db.execute(
                "SELECT COALESCE(SUM(net_pnl),0) FROM trades WHERE book=?", (book,)
            ).fetchone()[0]
            curve_rows = db.execute(
                "SELECT ts,SUM(equity) FROM equity_snapshots WHERE book=? "
                "GROUP BY ts ORDER BY ts", (book,)
            ).fetchall()
        days = float(status["elapsed_days"])
        trades = int(status["progress"]["trades"])
        net_return = float(book_status["total_return_pct"])
        decision = forward_decision(name, trades, days, net_return, backtest_verdict)
        base_equity = profile.capital * len(SYMBOLS)
        step = max(1, math.ceil(len(curve_rows) / 40))
        curve = [
            {"ts": int(ts), "return_pct": round((float(equity) / base_equity - 1) * 100, 4)}
            for ts, equity in curve_rows[::step]
        ]
        reference_days = prof["test_days"]
        expected_trades = (
            prof["test_trades"] * days / reference_days
            if reference_days else None
        )
        expected_return = (
            prof["test_return_pct"] * days / reference_days
            if reference_days else None
        )
        copy_age = copy_age_minutes(copy_time)
        return {
            "profile": name, "loaded": True, "verdict": status["progress"]["verdict"], **decision,
            "trades": trades, "days_running": round(days, 2),
            "realized_pnl_pct": round(float(realized) / profile.capital * 100, 4),
            "net_return_pct": round(net_return, 4),
            "open_positions": len(book_status["open_positions"]),
            "equity_curve_points": len(curve_rows), "equity_curve": curve,
            "backtest_expectation_trades": round(expected_trades, 2) if expected_trades is not None else None,
            "backtest_expectation_return_pct": round(expected_return, 4) if expected_return is not None else None,
            "backtest_test_return_pct": prof["test_return_pct"],
            "backtest_test_days": reference_days,
            "backtest_verdict": backtest_verdict or "미연결",
            "last_candle_time": status["last_candle_time"],
            "last_update_time": status["last_run_time"],
            "stale": status["health"] == "STALE",
            "copied_at": copy_time.isoformat().replace("+00:00", "Z") if copy_time else None,
            "copy_age_minutes": copy_age,
            "bars_processed": status["bars_processed"],
        }
    except (sqlite3.Error, OSError, ValueError, KeyError, TypeError):
        return {"profile": name, "loaded": False, "verdict": "not loaded", "trades": None,
                "days_running": None, "equity_curve_points": None,
                "backtest_expectation_trades": None, "days_left": None, "trades_left": None}


def build(root, forward_db_dir=None):
    root = Path(root).resolve()
    archive_files = sorted((root / "strategy_archive").glob("*/strategies/*.json"))
    specs = {}
    for path in archive_files:
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
            if spec.get("id"):
                specs[str(spec["id"])] = spec
        except (OSError, ValueError):
            continue
    bt = root / "scratchpad/strategy_bt"
    summary_rows = []
    for path in sorted((bt / "results").glob("slice_*/summary.csv")):
        summary_rows.extend(read_csv(path))
    byid = {}
    for row in summary_rows:
        if row.get("strategy_id") and row.get("status") in {"DONE", "INELIGIBLE"}:
            key = (row["strategy_id"], row.get("timeframe") or "unknown")
            # Prefer an executed record when duplicate rows exist for a timeframe.
            if key not in byid or row.get("status") == "DONE":
                byid[key] = row
    ledger = read_csv(bt / "results/ledger.csv")
    a1 = read_csv(bt / "verify2a/a1_results.csv")
    group_b = read_csv(bt / "verify2b/results/group_b.csv")
    reproduce = read_csv(bt / "verify/reproduce.csv")
    candidate_timeframes = {r["strategy_id"]: r["timeframe"] for r in reproduce if r.get("strategy_id") and r.get("timeframe")}
    costs = read_csv(bt / "verify/cost_stress.csv")
    regimes = read_csv(bt / "regime/results/results.csv")
    nodes = []
    strategy_ids = set(specs) | {sid for sid, _tf in byid}
    for sid in sorted(strategy_ids):
        spec = specs.get(sid, {})
        summary_timeframes = {tf for candidate, tf in byid if candidate == sid}
        claimed_timeframes = set(infer_timeframes(spec)) if spec else set()
        timeframes = sorted(summary_timeframes | claimed_timeframes) or ["unknown"]
        for timeframe in timeframes:
            summary = byid.get((sid, timeframe), {})
            side = str(summary.get("side") or side_of(spec))
            tests = make_tests(sid, timeframe, summary, a1, group_b, costs, regimes, candidate_timeframes)
            tested = bool(summary or sid in {r.get("strategy_id") for r in ledger})
            raw = verdict_value(summary.get("raw_verdict"))
            adjusted = verdict_value(summary.get("adjusted_verdict"))
            if not tested:
                color_verdict = "not_tested"
            elif adjusted == "PASS":
                color_verdict = "adjusted_pass"
            elif raw == "PASS":
                color_verdict = "downgraded"
            elif summary and raw in {"FAIL", "FAILED"}:
                color_verdict = "failed"
            else:
                color_verdict = "not_tested"
            syms = sorted(set(re.findall(r"[A-Z]{2,10}USDT|\bSPX\b|\bBTC\b|\bETH\b", str(spec.get("instruments_timeframes_claimed") or ""))))
            nodes.append({"id": f"{sid}|{timeframe}|{side}", "strategy_id": sid, "timeframe": timeframe, "side": side, "name": spec.get("name", sid), "family": spec.get("family", "unknown"), "symbol_class": symbol_class(spec) if spec else "unknown", "symbols": syms, "description": describe(spec), "source_url": spec.get("source_url"), "spec_complete": bool(spec.get("mechanical_spec_complete")), "implemented": bool(summary), "verdict": color_verdict, "raw_verdict": raw or None, "adjusted_verdict": adjusted or None, "verification_depth": verification_depth({"tests": tests}), "tests": tests, "params": summary.get("params") or None, "train_return": number(summary.get("train_return")), "test_return": number(summary.get("test_return")), "null_percentile": number(summary.get("null_percentile")), "per_year": [], "forward": None})
    # Map B1 calendar-year rows for compact detail-card charts.
    for node in nodes:
        rows = [r for r in group_b if r.get("candidate") == node["strategy_id"] and r.get("scenario") == "B1" and re.fullmatch(r"20\d\d", r.get("window", ""))] if candidate_timeframes.get(node["strategy_id"]) == node["timeframe"] else []
        node["per_year"] = [{"year": int(r["window"]), "value": number(r.get("return_pct"))} for r in sorted(rows, key=lambda x: x["window"]) if number(r.get("return_pct")) is not None]
    for node in nodes:
        node["forward"] = None
    edges = []
    groups = defaultdict(list)
    for n in nodes:
        if n["symbols"]:
            groups[(n["family"], n["timeframe"], tuple(n["symbols"]), n["side"])].append(n["id"])
    for key in sorted(groups, key=str):
        ids = sorted(groups[key])
        # Chain connectivity keeps large shared-bet clusters visible without quadratic edges.
        for left, right in zip(ids, ids[1:]):
            edges.append({"source": left, "target": right, "edge_kind": "metadata_similarity", "label": "approximate (metadata similarity)", "weight": 1})
    # Optional empirical co-movement edges from the observed 12-strategy matrix.
    corr_path = bt / "verify/correlation.csv"
    try:
        with corr_path.open(newline="", encoding="utf-8-sig") as stream:
            matrix = list(csv.DictReader(stream))
        strategy_node = {}
        nodes_by_strategy = defaultdict(list)
        for node in nodes:
            nodes_by_strategy[node["strategy_id"]].append(node)
        for sid, timeframe in candidate_timeframes.items():
            match = next((node for node in nodes_by_strategy.get(sid, []) if node["timeframe"] == timeframe), None)
            if match:
                strategy_node[sid] = match["id"]
        for i, row in enumerate(matrix):
            left_id = row.get("") or row.get("strategy_id")
            if left_id not in strategy_node:
                continue
            for other in matrix[i + 1:]:
                right_id = other.get("") or other.get("strategy_id")
                corr = number(row.get(right_id)) if right_id else None
                if right_id in strategy_node and corr is not None and corr > 0.5:
                    edges.append({"source": strategy_node[left_id], "target": strategy_node[right_id], "edge_kind": "return_correlation", "label": "historical return correlation", "weight": corr, "correlation": corr, "source_file": "scratchpad/strategy_bt/verify/correlation.csv"})
    except (OSError, UnicodeError, csv.Error):
        pass
    forward = []
    if forward_db_dir:
        folder = Path(forward_db_dir)
        copy_time = copied_at(folder)
        for name in PROFILES:
            match = folder / name / "forward.db"
            matches = []
            if not match.is_file():
                matches = sorted(folder.glob(f"trading-forward-test*/forward.db"))
                match = next((p for p in matches if name in str(p.parent)), None)
            if match is None and len(matches) == 1:
                match = matches[0]
            node_id = "jesse_simple_bollinger" if name == "jbb_1h" else None
            node = next((n for n in nodes if n["strategy_id"] == node_id), None) if node_id else None
            backtest_verdict = (
                "탈락" if node and node["verdict"] in {"failed", "downgraded"}
                else "통과" if node and node["verdict"] == "adjusted_pass"
                else "미판정"
            ) if node_id else None
            forward.append(forward_status(match, name, copy_time, backtest_verdict) if match.is_file() else {
                "profile": name, "loaded": False, "verdict": "not loaded", "trades": None,
                "days_running": None, "equity_curve_points": None,
                "backtest_expectation_trades": None, "days_left": None, "trades_left": None,
                "test_return_pct": PROFILES[name]["test_return_pct"]})
    else:
        forward = [{"profile": name, "loaded": False, "verdict": "not loaded", "trades": None, "days_running": None, "equity_curve_points": None, "backtest_expectation_trades": None, "days_left": None, "trades_left": None, "test_return_pct": PROFILES[name]["test_return_pct"]} for name in PROFILES]
    fwd_by_name = {f["profile"]: f for f in forward}
    for node in nodes:
        # This profile's strategy identity is recorded in the backtest archive.
        if node["strategy_id"] == "jesse_simple_bollinger":
            node["forward"] = fwd_by_name["jbb_1h"]
            if node["forward"].get("loaded"):
                node["verdict"] = "forward_confirmed" if node["forward"].get("confirmed") else "forward_running"
    adjusted_nodes = [n for n in nodes if n["adjusted_verdict"]]
    raw_sums = [number(r.get("n_candidates_tested")) for r in ledger]
    trials = max((int(x) for x in raw_sums if x is not None), default=0)
    depth_sources = [{"test": name, "file": next((n["source_file"] for node in nodes for n in node["tests"] if n["name"] == name and n["source_file"]), ""), "column_or_rule": next((n["source_column"] for node in nodes for n in node["tests"] if n["name"] == name), "")} for name in TESTS]
    return {"generated_at": datetime.now(timezone.utc).isoformat(), "counts": {"total_archived": len(archive_files), "spec_complete": sum(bool(s.get("mechanical_spec_complete")) for s in specs.values()), "implemented_tested": len({sid for sid, _tf in byid}), "trials_counted": trials, "adjusted_passed": sum(n["adjusted_verdict"] == "PASS" for n in nodes), "adjusted_tested": sum(bool(n["adjusted_verdict"]) for n in nodes), "confirmed_real_winners": sum(n["verdict"] == "forward_confirmed" for n in nodes)}, "headline": f"Confirmed real winners: {sum(n['verdict'] == 'forward_confirmed' for n in nodes)}", "adjusted_sentence": f"{sum(n['adjusted_verdict'] == 'PASS' for n in nodes)} of {sum(bool(n['adjusted_verdict']) for n in nodes)} passed after multiple-testing correction", "depth_test_sources": depth_sources, "nodes": nodes, "edges": edges, "forward": forward}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="/Users/user/CODE/Coin_Trade")
    parser.add_argument("--out", default="dist/data.json")
    data_dir = Path(os.environ.get("TRADING_DATA_DIR", str(Path.home() / "CODE/trading_data")))
    parser.add_argument("--forward-db-dir", default=str(data_dir / "cache/forward"))
    args = parser.parse_args()
    data = build(args.root, args.forward_db_dir)
    out = Path(args.out)
    if not out.is_absolute():
        out = Path(__file__).resolve().parent / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Wrote {out} ({len(data['nodes'])} strategies)")


if __name__ == "__main__":
    main()
