import csv
import json
import tempfile
import unittest
from argparse import Namespace
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import gate_check
from metrics import ROBUSTNESS_REQUIRED_KEYS


class GateCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.trades = self.root / "trades.csv"
        with self.trades.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["symbol", "entry_date", "exit_date", "net_return"])
            start = date(2018, 1, 1)
            for index in range(100):
                day = start + timedelta(days=index * 3)
                value = "0.03" if index < 90 else "-0.01"
                writer.writerow(["AAA", day.isoformat(), (day + timedelta(days=1)).isoformat(), value])
        self.daily = self.root / "daily.csv"
        with self.daily.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["date", "net_return"])
            start = date(2018, 1, 1)
            for index in range(100):
                writer.writerow([(start + timedelta(days=index)).isoformat(),
                                 "0.011" if index % 2 else "0.009"])

    def tearDown(self):
        self.temp.cleanup()

    def args(self, **overrides):
        values = dict(oos_trades=str(self.trades), daily_pnl=str(self.daily), market="crypto",
                      train_trials_count=10, frozen_test_count=5, grid_returns=None,
                      winner_config=None, family_daily_returns=None, cost_2x_trades=None,
                      delay_1bar_trades=None, untouched_symbol_trades=None,
                      reimplementation_return=None, bars=None, cutoff_ms=None,
                      source_fingerprint=None, funding_complete=False, source_unchanged=False)
        values.update(overrides)
        return Namespace(**values)

    def write_trade_companion(self, name, rows=None):
        path = self.root / name
        with path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["symbol", "entry_date", "exit_date", "net_return"])
            writer.writerows(rows or [["AAA", "2020-01-01", "2020-01-02", "0.02"]] * 20)
        return str(path)

    def test_core_eight_automatic_evidence_and_unknowns(self):
        result = gate_check.evaluate(self.args())
        self.assertEqual(set(result["core"]), {
            "sample", "net_return", "profit_factor", "expectancy",
            "wilson_vs_breakeven", "drawdown", "sharpe", "solvency"})
        self.assertEqual(set(result["core"].values()), {"pass"})
        for key in ("monte_carlo", "walk_forward", "regime_2018"):
            self.assertEqual(result["gates"][key], "pass", key)
        self.assertEqual(result["gates"]["profit_concentration"], "fail")
        self.assertEqual(result["gates"]["regime_2022"], "undetermined")
        for key in ("plateau", "reality_check", "spa", "cost_stress_2x", "delay_1_bar",
                    "untouched_symbols", "independent_reimplementation", "data_integrity"):
            self.assertEqual(result["gates"][key], "undetermined", key)
        self.assertEqual(result["gates"]["random_entry"], "undetermined")
        self.assertEqual(result["gates"]["circular_shift"], "undetermined")
        self.assertEqual(result["final"], "incomplete")

    def test_companion_inputs_create_measured_evidence(self):
        grid = self.root / "grid.csv"
        configs = [{"x": x} for x in (1, 2, 3)]
        with grid.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["definition_json", "net_return"])
            writer.writerows([[json.dumps(config), 0.08 if config["x"] == 2 else 0.06]
                              for config in configs])
        winner = self.root / "winner.json"
        winner.write_text(json.dumps({"x": 2}))
        family = self.root / "family.csv"
        with family.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["date", "candidate_id", "net_return"])
            for index in range(100):
                day = date(2020, 1, 1) + timedelta(days=index)
                for candidate in ("a", "b"):
                    writer.writerow([day.isoformat(), candidate, "0.01"])
        bars = self.root / "bars.csv"
        bars.write_text("timestamp,open,high,low,close,volume\n1,10,11,9,10,2\n2,10,11,9,10,3\n")
        args = self.args(grid_returns=str(grid), winner_config=str(winner),
                         family_daily_returns=str(family),
                         cost_2x_trades=self.write_trade_companion("cost.csv"),
                         delay_1bar_trades=self.write_trade_companion("delay.csv"),
                         untouched_symbol_trades=self.write_trade_companion("untouched.csv"),
                         reimplementation_return=1.0, bars=str(bars), cutoff_ms=2,
                         source_fingerprint="a" * 64, funding_complete=True, source_unchanged=True)
        with patch.object(gate_check, "reality_check", return_value={"p_value": 0.001, "method": "synthetic"}), \
             patch.object(gate_check, "hansen_spa", return_value={"p_value": 0.001, "method": "synthetic"}):
            result = gate_check.evaluate(args)
        for key in ("plateau", "reality_check", "spa", "cost_stress_2x", "delay_1_bar",
                    "untouched_symbols", "independent_reimplementation", "data_integrity"):
            self.assertEqual(result["gates"][key], "pass", key)
            self.assertNotIn(key, result["unknown_reasons"])
        self.assertTrue(set(ROBUSTNESS_REQUIRED_KEYS).issubset(result["gates"]))

    def test_official_reality_and_spa_import_failure_stays_unknown(self):
        family = self.root / "family.csv"
        family.write_text("date,candidate_id,net_return\n2020-01-01,a,0.01\n")
        with patch.object(gate_check, "reality_check", side_effect=RuntimeError("arch.bootstrap.RealityCheck is required by PREREG")), \
             patch.object(gate_check, "hansen_spa", side_effect=RuntimeError("arch.bootstrap.SPA is required by PREREG")):
            result = gate_check.evaluate(self.args(family_daily_returns=str(family)))
        self.assertEqual(result["gates"]["reality_check"], "undetermined")
        self.assertEqual(result["gates"]["spa"], "undetermined")
        self.assertIn("arch.bootstrap", result["statistical_details"]["reality_check"]["unavailable"])

    def test_cli_writes_json_and_markdown_summary(self):
        output = self.root / "result.json"
        argv = ["--oos-trades", str(self.trades), "--daily-pnl", str(self.daily),
                "--market", "crypto", "--train-trials-count", "10",
                "--frozen-test-count", "5", "--out", str(output)]
        self.assertEqual(gate_check.main(argv), 0)
        result = json.loads(output.read_text())
        self.assertEqual(result["final"], "incomplete")
        self.assertIn("random_entry", result["unknown_reasons"])
        summary = output.with_suffix(".md").read_text()
        self.assertIn("CORE 8항목", summary)
        self.assertIn("UNKNOWN", summary)

    def test_full_gate_incomplete_and_complete_call_paths(self):
        incomplete = gate_check.evaluate(self.args())
        self.assertEqual(incomplete["final"], "incomplete")
        self.assertFalse(incomplete["full_gate_complete"])
        grid = self.root / "complete_grid.csv"
        grid.write_text('definition_json,net_return\n{"x":1},0.06\n{"x":2},0.08\n{"x":3},0.06\n')
        winner = self.root / "complete_winner.json"
        winner.write_text('{"x":2}')
        family = self.root / "complete_family.csv"
        with family.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["date", "candidate_id", "net_return"])
            for index in range(100):
                day = date(2020, 1, 1) + timedelta(days=index)
                for candidate in ("a", "b"):
                    writer.writerow([day.isoformat(), candidate, "0.01"])
        bars = self.root / "complete_bars.csv"
        bars.write_text("timestamp,open,high,low,close,volume\n1,10,11,9,10,2\n")
        args = self.args(grid_returns=str(grid), winner_config=str(winner),
                         family_daily_returns=str(family),
                         cost_2x_trades=self.write_trade_companion("complete_cost.csv"),
                         delay_1bar_trades=self.write_trade_companion("complete_delay.csv"),
                         untouched_symbol_trades=self.write_trade_companion("complete_symbols.csv"),
                         reimplementation_return=1.0, bars=str(bars), cutoff_ms=1,
                         source_fingerprint="a" * 64, funding_complete=True, source_unchanged=True)
        with patch.object(gate_check, "reality_check", return_value={"p_value": 0.001, "method": "synthetic"}), \
             patch.object(gate_check, "hansen_spa", return_value={"p_value": 0.001, "method": "synthetic"}), \
             patch.object(gate_check, "deflated_sharpe", return_value=0.99), \
             patch.object(gate_check, "full_gate", return_value=False):
            complete = gate_check.evaluate(args)
        self.assertFalse(complete["full_gate_complete"])
        self.assertEqual(complete["final"], "incomplete")
        self.assertEqual(complete["gates"]["random_entry"], "undetermined")
        self.assertEqual(complete["gates"]["circular_shift"], "undetermined")

        measured = {key: gate_check._evidence(True, "synthetic fixture", 1, {"fixture": True})
                    for key in ROBUSTNESS_REQUIRED_KEYS}
        core = {key: True for key in gate_check.CORE_REQUIRED_KEYS}
        final, is_complete = gate_check._final_gate(core, measured)
        self.assertTrue(is_complete)
        self.assertTrue(final)
        failed_core = dict(core, sample=False)
        self.assertFalse(gate_check._final_gate(failed_core, measured)[0])


if __name__ == "__main__":
    unittest.main()
