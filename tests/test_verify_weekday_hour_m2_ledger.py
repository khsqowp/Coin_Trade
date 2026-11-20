import csv
import json

from scripts.research.verify_weekday_hour_m2_ledger import audit, _wilson


def write_fixture(tmp_path, net_base="0.009"):
    ledger = tmp_path / "event_ledger.csv"
    fields = ["symbol", "side", "signal_time_ms", "entry_time_ms", "exit_time_ms", "entry",
              "stop", "target", "exit_price", "m2_hit", "m1_hit", "reason", "gross_return",
              "funding_cost", "net_base", "net_stress"]
    row = {"symbol": "BTCUSDT", "side": "long", "signal_time_ms": 0,
           "entry_time_ms": 0, "exit_time_ms": 3_600_000, "entry": 100,
           "stop": 99, "target": 101, "exit_price": 101, "m2_hit": True,
           "m1_hit": True, "reason": "TARGET", "gross_return": 0.01,
           "funding_cost": 0, "net_base": net_base, "net_stress": "0.007"}
    with ledger.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerow(row)
    interval = _wilson(1, 1)
    summary = {
        "metric": {
            "signals": 1, "m2_hits": 1, "m2_rate": 1.0, "m2_wilson_95": interval,
            "symbols": 1, "market_time_nonoverlap_events": 1, "exit_reasons": {"TARGET": 1},
            "m1_direction_accuracy": 1.0, "coverage_pct": 100.0, "eligible_anchors": 1,
            "gross_mean": 0.01, "net_mean_base": 0.009, "net_mean_stress": 0.007,
            "funding_cost_mean": 0.0, "frozen_baseline_side": "short",
        },
        "by_symbol": {"BTCUSDT": {"eligible_anchors": 1,
                                    "raw_directional_forecasts": 1,
                                    "suppressed_open_position": 0}},
    }
    summary_path = tmp_path / "summary.json"
    summary_path.write_text(json.dumps(summary))
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps({"frozen_baseline_side": "short"}))
    return ledger, summary_path, baseline_path


def test_independent_ledger_audit_accepts_consistent_event(tmp_path):
    paths = write_fixture(tmp_path)
    result, per_symbol = audit(*paths)
    assert result["status"] == "PASS"
    assert result["checks"]["ledger_rows"] == 1
    assert per_symbol[0]["m2_rate"] == 1.0


def test_independent_ledger_audit_rejects_bad_net_formula(tmp_path):
    paths = write_fixture(tmp_path, net_base="0.5")
    result, _ = audit(*paths)
    assert result["status"] == "FAIL"
    assert any("base-cost arithmetic mismatch" in message for message in result["problems"])
