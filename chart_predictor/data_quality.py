"""Read-only candle database quality and provenance audit helpers."""
from __future__ import annotations

import hashlib
import json
import argparse
import sqlite3
from pathlib import Path

MINUTE_MS = 60_000
COLUMN_ALIASES = {
    "symbol": ("symbol",), "t_open_ms": ("t_open_ms", "open_ms"),
    "o": ("o", "open"), "h": ("h", "high"), "l": ("l", "low"),
    "c": ("c", "close"), "v": ("v", "volume"),
    "quote_v": ("quote_v", "quote_volume"), "trades": ("trades", "trade_count"),
}


def _connect_readonly(path: str | Path) -> sqlite3.Connection:
    resolved = Path(path).resolve()
    return sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)


def _metadata_fingerprint(database: str, tables: list[dict], schema: dict) -> str:
    """Identify an audited snapshot from its schema and per-symbol coverage metadata."""
    payload = json.dumps(
        {"database": Path(database).name, "schema": schema, "tables": tables},
        sort_keys=True, separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def audit_candles(database: str | Path, start_ms: int | None = None,
                  end_ms: int | None = None) -> dict:
    """Audit one SQLite candle table without modifying the database.

    Time bounds are half-open. Missing minutes are measured inside each
    symbol's observed range, or inside the requested interval when supplied.
    """
    path = Path(database).resolve()
    if start_ms is not None and start_ms % MINUTE_MS:
        raise ValueError("start_ms must align to a 1m candle open")
    if end_ms is not None and end_ms % MINUTE_MS:
        raise ValueError("end_ms must align to a 1m candle open")
    if start_ms is not None and end_ms is not None and end_ms <= start_ms:
        raise ValueError("end_ms must be greater than start_ms")
    db = _connect_readonly(path)
    try:
        tables = {row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if "candles" not in tables:
            raise ValueError(f"{path} has no candles table")
        columns = {row[1] for row in db.execute("PRAGMA table_info(candles)")}
        mapping = {key: next((name for name in choices if name in columns), None)
                   for key, choices in COLUMN_ALIASES.items()}
        missing_columns = [key for key, value in mapping.items() if value is None]
        if missing_columns:
            raise ValueError(f"candles table is missing columns: {missing_columns}")
        q = lambda name: '"' + mapping[name] + '"'

        per_symbol = []
        rows = db.execute("""
            SELECT {symbol}, COUNT(*), MIN({stamp}), MAX({stamp}),
                   SUM(CASE WHEN {stamp} % 60000 != 0 THEN 1 ELSE 0 END),
                   SUM(CASE WHEN {o} <= 0 OR {h} <= 0 OR {l} <= 0 OR {c} <= 0
                                  OR {h} < {l} OR {h} < {o} OR {h} < {c} OR {l} > {o} OR {l} > {c}
                                  OR {v} < 0 OR {quote_v} < 0 OR {trades} < 0
                            THEN 1 ELSE 0 END),
                   SUM(CASE WHEN {o} IS NULL OR {h} IS NULL OR {l} IS NULL OR {c} IS NULL
                                  OR {v} IS NULL OR {quote_v} IS NULL OR {trades} IS NULL
                            THEN 1 ELSE 0 END)
              FROM candles GROUP BY {symbol} ORDER BY {symbol}
        """.format(symbol=q("symbol"), stamp=q("t_open_ms"), o=q("o"), h=q("h"),
                   l=q("l"), c=q("c"), v=q("v"), quote_v=q("quote_v"),
                   trades=q("trades"))).fetchall()
        for symbol, count, first, last, off_grid, invalid, nulls in rows:
            left = int(start_ms) if start_ms is not None else ((int(first) + MINUTE_MS - 1) // MINUTE_MS) * MINUTE_MS
            right = int(end_ms) if end_ms is not None else (int(last) // MINUTE_MS) * MINUTE_MS + MINUTE_MS
            if right <= left:
                window_count = 0
                missing_minutes = 0
                window_first = window_last = None
            else:
                observed = db.execute(
                    f"SELECT COUNT(CASE WHEN {q('t_open_ms')} % {MINUTE_MS}=0 THEN 1 END), "
                    f"MIN(CASE WHEN {q('t_open_ms')} % {MINUTE_MS}=0 THEN {q('t_open_ms')} END), "
                    f"MAX(CASE WHEN {q('t_open_ms')} % {MINUTE_MS}=0 THEN {q('t_open_ms')} END) FROM candles "
                    f"WHERE {q('symbol')}=? AND {q('t_open_ms')}>=? AND {q('t_open_ms')}<?",
                    (symbol, left, right),
                ).fetchone()
                window_count, window_first, window_last = observed
                expected = (right - left + MINUTE_MS - 1) // MINUTE_MS
                missing_minutes = max(0, expected - window_count)
            per_symbol.append({
                "symbol": symbol, "row_count": int(count),
                "first_open_ms": int(first), "last_open_ms": int(last),
                "window_rows": int(window_count),
                "window_first_open_ms": int(window_first) if window_first is not None else None,
                "window_last_open_ms": int(window_last) if window_last is not None else None,
                "window_missing_minutes": int(missing_minutes),
                "off_grid_rows": int(off_grid or 0),
                "invalid_ohlcv_rows": int(invalid or 0),
                "null_value_rows": int(nulls or 0),
            })

        primary_key = [row[1] for row in db.execute("PRAGMA table_info(candles)") if row[5]]
        index_columns = [row[1] for row in db.execute("PRAGMA index_list(candles)")]
        if primary_key == [mapping["symbol"], mapping["t_open_ms"]]:
            duplicate_rows = 0
        else:
            duplicate_rows = db.execute(
                f"SELECT COUNT(*) - COUNT(DISTINCT {q('symbol')} || ':' || {q('t_open_ms')}) FROM candles"
            ).fetchone()[0]
        total = sum(row["row_count"] for row in per_symbol)
        fingerprint = _metadata_fingerprint(str(path), per_symbol, {
            "columns": mapping, "primary_key": primary_key, "indexes": index_columns,
        })
        return {
            "database": str(path), "database_bytes": path.stat().st_size,
            "table": "candles", "total_rows": total,
            "column_mapping": mapping,
            "symbol_count": len(per_symbol), "primary_key": primary_key,
            "indexes": index_columns,
            "duplicate_rows": int(duplicate_rows),
            "requested_window": {"start_ms": start_ms, "end_ms_exclusive": end_ms},
            "window_rows": sum(row["window_rows"] for row in per_symbol),
            "window_missing_minutes": sum(row["window_missing_minutes"] for row in per_symbol),
            "off_grid_rows": sum(row["off_grid_rows"] for row in per_symbol),
            "invalid_ohlcv_rows": sum(row["invalid_ohlcv_rows"] for row in per_symbol),
            "null_value_rows": sum(row["null_value_rows"] for row in per_symbol),
            "metadata_fingerprint": fingerprint,
            "fingerprint_scope": "schema and per-symbol coverage metadata; not a full candle-content hash",
            "symbols": per_symbol,
        }
    finally:
        db.close()


def write_report(report: dict, json_path: str | Path, markdown_path: str | Path) -> None:
    """Write deterministic JSON and Markdown reports for a completed audit."""
    json_path, markdown_path = Path(json_path), Path(markdown_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    lines = [
        "# Candle data quality audit", "",
        f"- Database: `{report['database']}`",
        f"- Rows / symbols: {report['total_rows']:,} / {report['symbol_count']}",
        f"- File size: {report['database_bytes']:,} bytes",
        f"- Metadata fingerprint: `{report['metadata_fingerprint']}`",
        f"- Fingerprint scope: {report['fingerprint_scope']}",
        f"- Window rows / missing minutes: {report['window_rows']:,} / {report['window_missing_minutes']:,}",
        f"- Duplicate / off-grid / invalid OHLCV / null rows: {report['duplicate_rows']:,} / "
        f"{report['off_grid_rows']:,} / "
        f"{report['invalid_ohlcv_rows']:,} / {report['null_value_rows']:,}", "",
        "|Symbol|Rows|First open ms|Last open ms|Window rows|Missing minutes|Invalid OHLCV|",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    lines.extend(
        f"|{row['symbol']}|{row['row_count']}|{row['first_open_ms']}|{row['last_open_ms']}|"
        f"{row['window_rows']}|{row['window_missing_minutes']}|{row['invalid_ohlcv_rows']}|"
        for row in report["symbols"]
    )
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only OHLCV quality audit")
    parser.add_argument("database", type=Path)
    parser.add_argument("--start-ms", type=int)
    parser.add_argument("--end-ms", type=int)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    args = parser.parse_args()
    report = audit_candles(args.database, args.start_ms, args.end_ms)
    write_report(report, args.json, args.markdown)
    print(json.dumps({key: value for key, value in report.items() if key != "symbols"}, indent=2))


if __name__ == "__main__":
    main()
