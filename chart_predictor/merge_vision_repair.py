"""Create a separately identified repaired snapshot without editing inputs."""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

DEFAULT_SOURCE = Path(__file__).parent / "data" / "vision_dev.sqlite"
DEFAULT_PATCH = Path(__file__).parent / "data" / "vision_gap_repair.sqlite"
DEFAULT_OUTPUT = Path(__file__).parent / "data" / "vision_dev_repaired.sqlite"


def merge(source: str | Path = DEFAULT_SOURCE, patch: str | Path = DEFAULT_PATCH,
          output: str | Path = DEFAULT_OUTPUT) -> dict:
    source, patch, output = Path(source).resolve(), Path(patch).resolve(), Path(output).resolve()
    if output in {source, patch}:
        raise ValueError("output must be separate from source and patch")
    if not source.exists() or not patch.exists():
        raise FileNotFoundError("source and patch databases must both exist")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing snapshot: {output}")

    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    dst = sqlite3.connect(output)
    try:
        src.backup(dst)
        dst.execute("ATTACH DATABASE ? AS repair", (str(patch),))
        overlap = dst.execute(
            "SELECT COUNT(*) FROM repair.candles r JOIN candles c "
            "ON c.symbol=r.symbol AND c.open_ms=r.open_ms"
        ).fetchone()[0]
        if overlap:
            raise ValueError(f"patch contains {overlap} keys already present in source")
        source_rows = dst.execute("SELECT COUNT(*) FROM candles").fetchone()[0]
        patch_rows = dst.execute("SELECT COUNT(*) FROM repair.candles").fetchone()[0]
        dst.execute("INSERT INTO candles SELECT * FROM repair.candles")
        dst.execute("CREATE TABLE repair_pages AS SELECT * FROM repair.repair_pages")
        dst.commit()
        merged_rows = dst.execute("SELECT COUNT(*) FROM candles").fetchone()[0]
        coverage = dst.execute("""
            SELECT symbol, COUNT(*), MIN(open_ms), MAX(open_ms)
            FROM candles GROUP BY symbol ORDER BY symbol
        """).fetchall()
        gaps = []
        for symbol, count, first, last in coverage:
            expected = (last - first) // 60_000 + 1
            if expected != count:
                gaps.append({"symbol": symbol, "expected": expected, "observed": count,
                             "missing": expected - count})
        if merged_rows != source_rows + patch_rows or gaps:
            raise RuntimeError(f"merged snapshot failed verification: rows={merged_rows}, gaps={gaps}")
        return {"status": "complete", "source": str(source), "patch": str(patch),
                "output": str(output), "source_rows": source_rows, "patch_rows": patch_rows,
                "merged_rows": merged_rows, "source_patch_overlap": overlap,
                "symbol_count": len(coverage), "observed_span_gaps": gaps,
                "retained_repair_pages": dst.execute("SELECT COUNT(*) FROM repair_pages").fetchone()[0],
                "output_bytes": output.stat().st_size}
    except Exception:
        dst.close()
        output.unlink(missing_ok=True)
        raise
    finally:
        try:
            dst.close()
        except sqlite3.Error:
            pass
        src.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--patch", type=Path, default=DEFAULT_PATCH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(merge(args.source, args.patch, args.output), indent=2))


if __name__ == "__main__":
    main()
