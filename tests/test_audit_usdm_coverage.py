import json
import subprocess
import sys
from pathlib import Path

import scripts.research.audit_usdm_coverage as coverage
from scripts.research.audit_usdm_coverage import summarize


def test_continuous_coverage_requires_all_archive_types_and_clean_gaps():
    rows = []
    for month in ("2024-01", "2024-02", "2024-03", "2024-04", "2024-05"):
        for kind in ("klines_1h", "mark_price_1h", "funding"):
            rows.append({"symbol": "BTCUSDT", "month": month, "kind": kind,
                         "gap_count": 0, "missing_hours": 0,
                         "funding_interval_disagreement_count": 0})
    rows.append({"symbol": "BTCUSDT", "month": "2024-02", "kind": "mark_price_1h",
                 "gap_count": 1, "missing_hours": 24})
    result = summarize({"archive_rows": rows})
    btc = result["symbols"]["BTCUSDT"]
    assert btc == {"clean_consecutive_months": 3, "start_month": "2024-03", "end_month": "2024-05"}


def test_missing_archive_rows_fail_closed():
    try:
        summarize({})
    except ValueError as exc:
        assert "archive_rows" in str(exc)
    else:
        raise AssertionError("missing archive_rows should fail closed")


def test_cli_writes_only_to_explicit_output_path(tmp_path):
    source = tmp_path / "audit.json"
    output = tmp_path / "summary.json"
    source.write_text(json.dumps({"archive_rows": []}), encoding="utf-8")
    script = Path(coverage.__file__)
    result = subprocess.run([sys.executable, str(script), str(source), "--output", str(output)],
                            capture_output=True, text=True)
    assert result.returncode == 0
    assert json.loads(output.read_text(encoding="utf-8"))["symbols_with_valid_rows"] == 0
