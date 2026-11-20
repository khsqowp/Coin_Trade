"""Independent raw-ZIP spot audit of deterministic Pine M2 ledger rows."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from datetime import datetime, timezone
from pathlib import Path
import zipfile

HOUR = 3_600_000


def _month(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m")


def _read(path: Path) -> list[dict[str, str]]:
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.endswith(".csv")]
        if len(names) != 1:
            raise ValueError(f"expected one CSV member: {path}")
        with archive.open(names[0]) as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
            first = text.readline()
            names = ["open_time", "open", "high", "low", "close", "volume",
                     "close_time", "quote_volume", "count", "taker_buy_volume",
                     "taker_buy_quote_volume", "ignore"]
            return list(csv.DictReader([first, *text], fieldnames=names if first[:1].isdigit() else None))


def audit(archive_root: Path, ledger_path: Path, sample_size: int = 100) -> dict:
    events = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines() if line]
    events.sort(key=lambda row: hashlib.sha256(
        f"pine-regime-audit-v1|{row['symbol']}|{row['signal_close_ms']}".encode()
    ).digest())
    selected = events[:sample_size]
    checked = mismatches = 0
    details = []
    cache: dict[tuple[str, str, str], list[dict[str, str]]] = {}

    def rows(symbol: str, kind: str, month: str) -> list[dict[str, str]]:
        key = (symbol, kind, month)
        if key not in cache:
            filename = f"{symbol}-1h-{month}.zip" if kind == "klines_1h" else f"{symbol}-fundingRate-{month}.zip"
            cache[key] = _read(archive_root / kind / symbol / filename)
        return cache[key]

    for event in selected:
        symbol, entry_time = event["symbol"], int(event["entry_open_ms"])
        months = sorted({_month(entry_time + i * HOUR) for i in range(21)})
        candle_map = {}
        funding_rows = []
        for month in months:
            for row in rows(symbol, "klines_1h", month):
                stamp = int(row["open_time"])
                if entry_time <= stamp < entry_time + 20 * HOUR:
                    candle_map[stamp] = row
            funding_rows.extend(rows(symbol, "funding", month))
        candles = [candle_map.get(entry_time + i * HOUR) for i in range(20)]
        if any(row is None for row in candles):
            raise ValueError(f"audit sample has missing outcome candle: {symbol} {entry_time}")
        side = event["side"]
        sign = 1 if side == "LONG" else -1
        entry, risk = float(event["entry"]), float(event["risk"])
        stop = entry - sign * risk
        target = entry + sign * 2 * risk
        reason, exit_price, exit_idx = "TIMEOUT", float(candles[-1]["close"]), 19
        for idx, row in enumerate(candles):
            op, high, low = (float(row[k]) for k in ("open", "high", "low"))
            if (low <= stop if sign > 0 else high >= stop):
                reason = "STOP_GAP" if (op < stop if sign > 0 else op > stop) else "STOP"
                exit_price, exit_idx = (op if reason == "STOP_GAP" else stop), idx
                break
            if high >= target if sign > 0 else low <= target:
                reason, exit_price, exit_idx = "TARGET", target, idx
                break
        entry_close = entry_time
        exit_bar_open = entry_time + exit_idx * HOUR
        exit_close = exit_bar_open + HOUR
        funding_cost = 0.0
        for row in funding_rows:
            timestamp = int(row["calc_time"])
            if entry_close < timestamp <= exit_close:
                cost = sign * float(row["last_funding_rate"])
                if timestamp >= exit_bar_open:
                    cost = max(cost, 0.0)
                funding_cost += cost
        gross = sign * (exit_price - entry) / entry
        base, stress = gross - 0.001 - funding_cost, gross - 0.003 - funding_cost
        expected = (event["reason"], float(event["exit_price"]),
                    float(event["net_base"]), float(event["net_stress"]))
        actual = (reason, exit_price, base, stress)
        same = expected[0] == actual[0] and all(math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-12)
                                                for a, b in zip(expected[1:], actual[1:]))
        checked += 1
        mismatches += not same
        details.append({"symbol": symbol, "signal_close_ms": event["signal_close_ms"], "match": same})
    return {"status": "PASS" if checked == len(selected) and mismatches == 0 else "FAIL",
            "selection": "SHA256(pine-regime-audit-v1|symbol|signal_close_ms), ascending",
            "ledger_rows": len(events), "sample_requested": sample_size, "checked": checked,
            "mismatches": mismatches, "sample": details}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.archive_root, args.ledger)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "sample"}, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
