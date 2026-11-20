"""Read-only audit of research-registry document/artifact references."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def audit(root: Path) -> dict:
    registry = root / "docs/research/registry.jsonl"
    rows = [json.loads(line) for line in registry.read_text(encoding="utf-8").splitlines() if line.strip()]
    verdicts = Counter(row.get("verdict", "MISSING") for row in rows)
    missing_docs = []
    directory_docs = []
    file_docs = 0
    missing_artifacts = []
    without_artifacts = []
    artifact_rows = 0
    for row in rows:
        doc_ref = row.get("doc_ref")
        if not isinstance(doc_ref, str) or not (root / doc_ref).exists():
            missing_docs.append(row.get("id"))
        elif (root / doc_ref).is_dir():
            directory_docs.append(row.get("id"))
        else:
            file_docs += 1
        artifacts = row.get("artifacts") or []
        if not artifacts:
            without_artifacts.append(row.get("id"))
            continue
        artifact_rows += 1
        for reference in artifacts:
            if not isinstance(reference, str) or not reference.strip():
                missing_artifacts.append({"id": row.get("id"), "reference": reference})
                continue
            # Registry entries may append a variant/CLI annotation after the path.
            path = reference.strip().split()[0]
            if not (root / path).is_file():
                missing_artifacts.append({"id": row.get("id"), "reference": reference})
    return {
        "rows": len(rows),
        "verdict_counts": dict(sorted(verdicts.items())),
        "doc_refs_resolved": len(rows) - len(missing_docs),
        "doc_refs_to_files": file_docs,
        "doc_refs_to_directories": directory_docs,
        "missing_doc_refs": missing_docs,
        "rows_with_artifacts": artifact_rows,
        "rows_without_artifacts": without_artifacts,
        "missing_artifact_refs": missing_artifacts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    try:
        result = audit(args.root.resolve())
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["missing_doc_refs"] or result["missing_artifact_refs"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
