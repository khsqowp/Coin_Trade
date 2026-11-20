import json
import subprocess
import sys
from pathlib import Path

from scripts.research.run_contract import validate_run_record


def valid_record(market="us"):
    return {
        "schema_version": 1,
        "run_id": "test-001",
        "market": market,
        "status": "complete",
        "frozen_at": "2025-01-01T00:00:00Z",
        "run_started_at": "2026-11-20T00:00:00Z",
        "preregistration_sha256": "a" * 64,
        "code_sha": "0123456789abcdef",
        "code_files": [{"ref": "scripts/research/run.py", "sha256": "c" * 64}],
        "inputs": [{"role": "daily-bars", "ref": "data/panel.csv", "sha256": "b" * 64}],
        "period": {"start": "2025-01-01T00:00:00Z", "end": "2026-01-01T00:00:00Z"},
        "splits": {
            "development": {"start": "2025-01-01T00:00:00Z", "end": "2025-06-01T00:00:00Z", "reused_for_tuning": False},
            "validation": {"start": "2025-06-01T00:00:00Z", "end": "2025-09-01T00:00:00Z", "reused_for_tuning": False},
            "sealed": {"start": "2025-09-01T00:00:00Z", "end": "2026-01-01T00:00:00Z", "reused_for_tuning": False},
        },
        "cost_scenarios": {"base": {"name": "base"}, "stress": {"name": "stress"}},
        "execution": {"fill_rule": "next close", "same_bar_rule": "stop first", "funding_rule": "not applicable"},
        "counts": {"oos_round_trips": 250},
        "metrics": {"cagr": 0.2, "mdd": 0.25, "sharpe": 1.1},
    }


def test_accepts_complete_equity_run_envelope():
    assert validate_run_record(valid_record()) == []


def test_accepts_crypto_specific_counts_and_metrics():
    record = valid_record("crypto")
    record["counts"] = {"oos_issued_signals": 320, "oos_nonoverlap_signals": 220}
    record["metrics"] = {"m2_target_first_rate": 0.81, "m2_wilson_95_low": 0.76,
                         "m2_wilson_95_high": 0.85, "m1_direction_accuracy": 0.57,
                         "net_expectancy": 0.03}
    assert validate_run_record(record) == []


def test_rejects_overlapping_splits_and_late_preregistration():
    record = valid_record()
    record["frozen_at"] = "2026-11-20T01:00:00Z"
    record["splits"]["validation"]["end"] = "2025-10-01T00:00:00Z"
    errors = validate_run_record(record)
    assert "development, validation, and sealed splits must not overlap" in errors
    assert "preregistration must be frozen before the run starts" in errors


def test_rejects_missing_cost_stress_and_invalid_input_fingerprint():
    record = valid_record()
    record["cost_scenarios"] = {"base": {"name": "base"}}
    record["inputs"][0]["sha256"] = "not-a-hash"
    errors = validate_run_record(record)
    assert "cost_scenarios must include base and stress" in errors
    assert "inputs[0].sha256 must be a lowercase SHA-256 digest" in errors


def test_rejects_market_specific_missing_sample_count():
    record = valid_record("crypto")
    record["counts"] = {"oos_issued_signals": 210}
    errors = validate_run_record(record)
    assert "counts.oos_nonoverlap_signals must be a non-negative integer" in errors


def test_cli_reports_structure_without_claiming_acceptance(tmp_path):
    fixture = tmp_path / "run.json"
    fixture.write_text(json.dumps(valid_record()), encoding="utf-8")
    script = Path(__file__).parents[1] / "scripts/research/run_contract.py"
    result = subprocess.run([sys.executable, str(script), str(fixture)], capture_output=True, text=True)
    assert result.returncode == 0
    assert "not a data, performance, or strategy approval" in result.stdout
