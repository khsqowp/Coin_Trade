"""Read-only SHA-256 verification for staged Binance USD-M archive ZIPs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


FILENAMES = {
    "klines_1h": lambda s, m: f"{s}-1h-{m}.zip",
    "mark_price_1h": lambda s, m: f"{s}-1h-{m}.zip",
    "funding": lambda s, m: f"{s}-fundingRate-{m}.zip",
}


def archive_path(root: Path, row: dict) -> Path | None:
    kind = row.get("kind")
    if kind not in FILENAMES:
        return None
    symbol, month = row.get("symbol"), row.get("month")
    if not isinstance(symbol, str) or not isinstance(month, str):
        return None
    return root / kind / symbol / FILENAMES[kind](symbol, month)


def verify(audit: dict, root: Path) -> dict:
    rows = audit.get("archive_rows")
    if not isinstance(rows, list):
        raise ValueError("audit metadata must contain archive_rows list")
    checked = missing = mismatch = malformed = 0
    mismatch_refs = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("sha256"), str):
            malformed += 1
            continue
        path = archive_path(root, row)
        if path is None:
            malformed += 1
            continue
        try:
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
        except OSError:
            missing += 1
            continue
        checked += 1
        if digest != row["sha256"]:
            mismatch += 1
            mismatch_refs.append({"kind": row.get("kind"), "symbol": row.get("symbol"),
                                  "month": row.get("month")})
    return {"audit_rows": len(rows), "checked": checked, "missing": missing,
            "sha256_mismatches": mismatch, "malformed_rows": malformed,
            "mismatch_refs": mismatch_refs,
            "status": "PASS" if checked == len(rows) and not missing and not mismatch and not malformed
            else "FAIL",
            "note": "hash equality proves file identity only, not source authenticity or time-series correctness"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audit_json", type=Path, help="audit JSON containing archive SHA-256 rows")
    parser.add_argument("archive_root", type=Path, help="root containing kind/symbol/month ZIPs")
    parser.add_argument("--output", type=Path, help="optional JSON result path")
    args = parser.parse_args()
    try:
        audit = json.loads(args.audit_json.read_text(encoding="utf-8"))
        result = verify(audit, args.archive_root)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        try:
            args.output.write_text(rendered, encoding="utf-8")
        except OSError as exc:
            print(json.dumps({"error": f"cannot write summary: {exc}"}, ensure_ascii=False))
            return 2
    else:
        print(rendered, end="")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
