#!/usr/bin/env python3
"""Create a metadata-only inventory of Coin_Trade and Ochestration trading files.

The command is read-only with respect to source repositories and data. It skips
secret-like files, Git internals, virtual environments, and agent worktree contents.
It records paths, stat metadata, Git tracking, and conservative category hints; it
does not open data-file contents or calculate checksums.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path


COIN_ROOT = Path("/home/noroot/CODE/Coin_Trade")
ORCH_ROOT = Path("/Users/user/CODE/Ochestration")
SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache",
}
SECRET_PARTS = {".env", ".env.local", "secrets", "credentials"}
SECRET_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}
YEAR_RE = re.compile(r"^(?:19|20)\d{2}$")
DATE_RE = re.compile(r"(?<!\d)(20\d{2})[-_]?([01]\d)[-_]?([0-3]\d)(?!\d)")


def git_lines(root: Path, *args: str) -> set[str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), *args], check=True,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return set()
    return {item.decode("utf-8", "surrogateescape") for item in proc.stdout.split(b"\0") if item}


def safe_path(path: Path) -> bool:
    parts = {part.lower() for part in path.parts}
    return not (parts & SECRET_PARTS or path.suffix.lower() in SECRET_SUFFIXES)


def relative_parts(path: Path) -> tuple[str, ...]:
    parts = path.parts
    for marker in ("Coin_Trade", "Ochestration"):
        if marker in parts:
            return parts[parts.index(marker) + 1 :]
    return parts


def infer_market(path: Path) -> tuple[str, str]:
    parts = relative_parts(path)
    lower = "/".join(part.lower() for part in parts)
    name = path.name.lower()
    if "chart_predictor" in lower or ".rs_cache" in lower or "crypto" in lower or "coin" in lower:
        return "crypto", "path/name hint"
    kr = name == "kr.jsonl" or bool(re.search(r"(?:^|[_/-])kr(?:[_/.-]|$)", lower))
    us = name == "us.jsonl" or bool(re.search(r"(?:^|[_/-])us(?:[_/.-]|$)", lower)) or "usa" in lower
    if kr and us:
        return "kr_us_shared", "path/name hint"
    if kr:
        return "kr", "path/name hint"
    if us:
        return "us", "path/name hint"
    if "equity" in lower or "stock" in lower or "etf" in lower:
        return "kr_us_shared", "equity path/name hint; market unresolved"
    if "trading-tick-archive" in lower or "scratchpad" in lower or "research" in lower:
        return "unclassified", "requires report/experiment provenance"
    return "shared_or_unclassified", "no reliable market marker"


def infer_kind(path: Path) -> str:
    lower = "/".join(part.lower() for part in relative_parts(path))
    suffix = path.suffix.lower()
    if "trading-tick-archive" in lower or ".rs_cache" in lower or "chart_predictor/data" in lower:
        return "market_data_or_derived_data"
    if "/docs/" in lower or "docs/" in lower:
        if suffix in {".md", ".pdf", ".html"}:
            return "research_document_or_spec"
        if suffix in {".csv", ".json", ".jsonl", ".parquet", ".sqlite", ".db"}:
            return "research_result_or_dataset"
        return "documentation_asset"
    if "/scripts/" in lower or suffix in {".py", ".sh", ".sql", ".pine"}:
        return "code_or_script"
    if "runtime" in lower or "paper-state" in lower:
        return "runtime_or_paper_state"
    if suffix in {".sqlite", ".db", ".csv", ".jsonl", ".parquet"}:
        return "data_or_result_unclassified"
    return "other_work_product"


def date_hint(path: Path) -> str:
    candidates: list[str] = []
    for part in path.parts:
        if re.fullmatch(r"20\d{2}-[01]\d-[0-3]\d", part):
            candidates.append(part)
        elif YEAR_RE.fullmatch(part):
            candidates.append(part)
        match = DATE_RE.search(part)
        if match:
            candidates.append("-".join(match.groups()))
    return candidates[-1] if candidates else ""


def git_file_sets(root: Path) -> tuple[set[str], set[str]]:
    tracked = git_lines(root, "ls-files", "-z")
    ignored = git_lines(root, "ls-files", "--others", "--ignored", "--exclude-standard", "-z")
    return tracked, ignored


def status_of(rel: str, tracked: set[str], ignored: set[str]) -> str:
    if rel in tracked:
        return "tracked"
    if rel in ignored:
        return "ignored"
    return "untracked"


def scan_tree(root: Path, relative: str, tracked: set[str], ignored: set[str]) -> list[dict[str, object]]:
    start = root / relative
    if not start.exists():
        return []
    result: list[dict[str, object]] = []
    for current, dirs, files in os.walk(start, followlinks=False):
        current_path = Path(current)
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and d != "worktrees"]
        for name in files:
            path = current_path / name
            if not safe_path(path):
                continue
            try:
                stat = path.lstat()
            except OSError:
                continue
            if not path.is_file() or path.is_symlink():
                continue
            rel = path.relative_to(root).as_posix()
            market, reason = infer_market(path)
            result.append({
                "repository": root.name,
                "market": market,
                "artifact_type": infer_kind(path),
                "path": f"{root.name}/{rel}",
                "relative_path": rel,
                "file_count": 1,
                "bytes": stat.st_size,
                "modified_utc": dt.datetime.fromtimestamp(stat.st_mtime, dt.timezone.utc).isoformat(timespec="seconds"),
                "path_date_hint": date_hint(path),
                "git_status": status_of(rel, tracked, ignored),
                "classification_basis": reason,
                "sha256": "not_computed_read_only_inventory",
            })
    return result


def scan_aggregate(root: Path, relative: str) -> list[dict[str, object]]:
    """Summarize a very large untracked tree without exposing every file name."""
    start = root / relative
    if not start.exists():
        return []
    count = size = 0
    newest = 0.0
    for current, dirs, files in os.walk(start, followlinks=False):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            path = Path(current) / name
            if path.is_symlink() or not safe_path(path):
                continue
            try:
                stat = path.lstat()
            except OSError:
                continue
            if not path.is_file():
                continue
            count += 1
            size += stat.st_size
            newest = max(newest, stat.st_mtime)
    if not count:
        return []
    market, reason = infer_market(start)
    rel = start.relative_to(root).as_posix()
    return [{
        "repository": root.name,
        "market": market,
        "artifact_type": "aggregated_unclassified_work_tree",
        "path": f"{root.name}/{rel}/[aggregate]",
        "relative_path": rel,
        "file_count": count,
        "bytes": size,
        "modified_utc": dt.datetime.fromtimestamp(newest, dt.timezone.utc).isoformat(timespec="seconds"),
        "path_date_hint": "",
        "git_status": "untracked_or_ignored",
        "classification_basis": f"directory aggregate only; {reason}",
        "sha256": "not_computed_read_only_inventory",
    }]


def worktree_rows(root: Path) -> list[dict[str, object]]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "worktree", "list", "--porcelain"],
            check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    rows: list[dict[str, object]] = []
    current: dict[str, str] = {}
    for line in [*proc.stdout.splitlines(), ""]:
        if not line:
            if current:
                worktree_path = Path(current.get("worktree", ""))
                try:
                    display_path = f"{root.name}/{worktree_path.relative_to(root).as_posix()}"
                except ValueError:
                    display_path = f"external/{worktree_path.name}"
                rows.append({
                    "repository": root.name,
                    "path": display_path,
                    "head": current.get("HEAD", ""),
                    "branch": current.get("branch", ""),
                    "locked": "yes" if "locked" in current else "no",
                    "prunable": "yes" if "prunable" in current else "no",
                })
            current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    return rows


def registry_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    rows: list[dict[str, str]] = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            import json

            record = json.loads(line)
            track = str(record.get("track", "unknown"))
            scope_text = " ".join(str(record.get(k, "")) for k in ("title", "scope", "doc_ref")).lower()
            if track == "coin":
                market = "crypto"
            elif track == "stock":
                tags = []
                if re.search(r"\bkr\b|korea|한국|국장|대한민국", scope_text):
                    tags.append("kr")
                if re.search(r"\bus\b|united states|미장|미국", scope_text):
                    tags.append("us")
                market = "+".join(tags) if tags else "stock_market_unspecified"
            else:
                market = "unclassified"
            rows.append({
                "id": str(record.get("id", "")),
                "date": str(record.get("ts", "")),
                "track": track,
                "market_hint": market,
                "phase": str(record.get("phase", "")),
                "title": str(record.get("title", "")),
                "scope": str(record.get("scope", "")),
                "headline_metric": str(record.get("headline_metric", "")),
                "verdict": str(record.get("verdict", "")),
                "bar": str(record.get("bar", "")),
                "artifacts": ";".join(record.get("artifacts", []) or []),
                "doc_ref": str(record.get("doc_ref", "")),
                "note": str(record.get("note", "") or ""),
            })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coin-root", type=Path, default=COIN_ROOT)
    parser.add_argument("--orch-root", type=Path, default=ORCH_ROOT)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    roots = [(args.coin_root, ["docs/research", "docs/chart_predictor", "chart_predictor", "app", "scripts", "tests", ".kis-cache-local"]),
             (args.orch_root, ["trading-tick-archive", "trading/.rs_cache", "trading/shadow_predictor", "trading-crypto-paper-state", "trading/docs/research", "trading/scripts", "trading/app", "trading/data", "trading/agent_sandbox", "trading/tests"])]
    entries: list[dict[str, object]] = []
    worktrees: list[dict[str, object]] = []
    for root, paths in roots:
        if not root.is_dir():
            print(f"missing repository root: {root}", file=sys.stderr)
            return 2
        tracked, ignored = git_file_sets(root)
        worktrees.extend(worktree_rows(root))
        for relative in paths:
            entries.extend(scan_tree(root, relative, tracked, ignored))
        if root == args.orch_root:
            entries.extend(scan_aggregate(root, "trading/scratchpad"))

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    manifest = args.out_dir / f"market_artifacts_{stamp}.csv"
    fields = ["repository", "market", "artifact_type", "path", "relative_path", "file_count", "bytes", "modified_utc", "path_date_hint", "git_status", "classification_basis", "sha256"]
    with manifest.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(entries)
    wt_file = args.out_dir / f"git_worktrees_{stamp}.csv"
    with wt_file.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["repository", "path", "head", "branch", "locked", "prunable"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(worktrees)

    experiments = registry_rows(args.coin_root / "docs/research/registry.jsonl")
    experiment_file = args.out_dir / f"research_registry_{stamp}.csv"
    exp_fields = ["id", "date", "track", "market_hint", "phase", "title", "scope", "headline_metric", "verdict", "bar", "artifacts", "doc_ref", "note"]
    with experiment_file.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=exp_fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(experiments)

    totals: dict[tuple[str, str, str], list[int]] = defaultdict(lambda: [0, 0])
    for row in entries:
        key = (str(row["repository"]), str(row["market"]), str(row["artifact_type"]))
        totals[key][0] += int(row["file_count"])
        totals[key][1] += int(row["bytes"])
    summary = args.out_dir / f"market_artifacts_{stamp}.md"
    with summary.open("w", encoding="utf-8") as stream:
        stream.write(f"# Market artifact inventory — {stamp}\n\n")
        stream.write("Metadata-only scan. Source files were not opened, moved, deleted, or hashed. "
                     "Market labels are conservative path/name hints and require review.\n\n")
        stream.write("| Repository | Market hint | Type | Files | Bytes |\n|---|---|---|---:|---:|\n")
        for (repo, market, kind), (count, size) in sorted(totals.items()):
            stream.write(f"| {repo} | {market} | {kind} | {count} | {size} |\n")
        stream.write(f"\nDetailed manifest: `{manifest.name}`. Experiment registry snapshot: `{experiment_file.name}`. Git worktree inventory: `{wt_file.name}`.\n")
        stream.write("\nThis report is not a deletion authorization, backup verification, data-rights finding, "
                     "or proof that files are inactive.\n")
    print(f"manifest={manifest}")
    print(f"summary={summary}")
    print(f"worktrees={wt_file}")
    print(f"experiments={experiment_file}")
    print(f"files={len(entries)} experiments={len(experiments)} worktrees={len(worktrees)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
