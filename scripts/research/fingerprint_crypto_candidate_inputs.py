"""Fingerprint the frozen spot/perpetual files named by a prior archive audit."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import stat


DATASETS = ("spot_klines_1m", "um_klines_1m")


def _digest_stable(path: Path) -> tuple[str, int, int]:
    before = path.stat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError(f"not a regular file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    after = path.stat()
    identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if identity_before != identity_after:
        raise RuntimeError(f"file changed while hashing: {path}")
    return digest.hexdigest(), before.st_size, before.st_mtime_ns


def fingerprint(root: Path, audit_path: Path) -> dict:
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if audit.get("ohlc_values_checked") is not True:
        raise ValueError("source audit must include OHLC validation")
    if audit.get("start_month") != "2024-10" or audit.get("end_month") != "2026-10":
        raise ValueError("source audit period does not match frozen preregistration")
    if audit.get("complete_file_cohort_symbol_count") != 32 or audit.get("complete_file_cohort_month_count") != 25:
        raise ValueError("source audit cohort dimensions do not match frozen preregistration")
    symbols = audit.get("complete_file_cohort", [])
    if len(symbols) != 32 or len(set(symbols)) != 32:
        raise ValueError("source audit symbol list is not the frozen 32-symbol cohort")

    expected = {}
    for dataset in DATASETS:
        files = audit.get("datasets", {}).get(dataset, {}).get("files", [])
        selected = {item["symbol"] + "/" + item["month"]: item
                    for item in files if item.get("symbol") in symbols
                    and "2024-10" <= item.get("month", "") <= "2026-10"}
        if len(selected) != 32 * 25:
            raise ValueError(f"{dataset}: expected 800 audit records, got {len(selected)}")
        for key, item in selected.items():
            if item.get("status") != "PASS":
                raise ValueError(f"{dataset}/{key}: audit status is {item.get('status')}")
            expected[f"{dataset}/{key}.parquet"] = item

    files = []
    for relative, audited in sorted(expected.items()):
        path = root / relative
        digest, size, mtime_ns = _digest_stable(path)
        if size != audited.get("size_bytes") or mtime_ns != audited.get("mtime_ns"):
            raise RuntimeError(f"file changed since OHLC audit: {relative}")
        files.append({"path": relative, "size_bytes": size, "mtime_ns": mtime_ns,
                      "sha256": digest})

    identity = {
        "root": str(root.resolve()),
        "audit_sha256": hashlib.sha256(audit_path.read_bytes()).hexdigest(),
        "start_month": audit["start_month"],
        "end_month": audit["end_month"],
        "symbols": symbols,
        "files": files,
    }
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    return {**identity, "file_count": len(files), "total_bytes": sum(x["size_bytes"] for x in files),
            "aggregate_sha256": hashlib.sha256(canonical).hexdigest(),
            "all_files_stable": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--audit-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.root.is_dir():
        parser.error(f"input root does not exist: {args.root}")
    if args.output.resolve().is_relative_to(args.root.resolve()):
        parser.error("output must be outside the read-only input root")
    result = fingerprint(args.root, args.audit_json)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in
                      ("file_count", "total_bytes", "aggregate_sha256", "all_files_stable")},
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
