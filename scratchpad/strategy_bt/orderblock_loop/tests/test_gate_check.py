import csv
import json
import tempfile
import unittest
from argparse import Namespace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import gate_check
from metrics import ROBUSTNESS_REQUIRED_KEYS


class GateCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.write_ledgers(train_rows=2, frozen_rows=1)
        self.trades = self.root / "trades.csv"
        with self.trades.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["symbol", "entry_date", "exit_date", "net_return", "signal_id"])
            start = date(2018, 1, 1)
            for index in range(100):
                day = start + timedelta(days=index * 3)
                value = "0.03" if index < 90 else "-0.01"
                writer.writerow(["AAA", day.isoformat(), (day + timedelta(days=1)).isoformat(),
                                 value, f"s{index}"])
        self.m2_events = self.root / "m2-events.csv"
        with self.m2_events.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["signal_id", "symbol", "entry_timestamp_ms",
                             "exit_end_timestamp_ms", "target_first"])
            for index in range(100):
                day = date(2018, 1, 1) + timedelta(days=index * 3)
                timestamp = int(datetime.combine(
                    day, datetime.min.time(), timezone.utc
                ).timestamp() * 1000)
                writer.writerow([f"s{index}", "AAA", timestamp,
                                 timestamp + 86_400_000, "true" if index < 90 else "false"])
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
        values = dict(oos_trades=str(self.trades), m2_events=str(self.m2_events),
                      daily_pnl=str(self.daily), market="crypto",
                      ledger_dir=self.root, grid_returns=None,
                      winner_config=None, family_daily_returns=None, cost_2x_trades=None,
                      delay_1bar_trades=None, untouched_symbol_trades=None,
                      reimplementation_return=None, bars=None, cutoff_ms=None,
                      source_fingerprint=None, funding_complete=False, source_unchanged=False)
        values.update(overrides)
        return Namespace(**values)

    def write_ledgers(self, train_rows=2, frozen_rows=1):
        train = self.root / "TRAIN_TRIALS.csv"
        train.write_text("trial_id\n" + "same-config\n" * train_rows)
        frozen = self.root / "FROZEN_TEST_CANDIDATES.csv"
        lines = ["candidate_id,round,market,timeframe,prereg_sha256,freeze_utc,status,notes"]
        for index in range(frozen_rows):
            lines.append(f"c{index},R1,crypto,4h,{'a' * 64},2026-11-24T00:00:00Z,frozen,")
        frozen.write_text("\n".join(lines) + "\n")

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
        self.assertEqual(result["gates"]["m2_target_first"], "pass")
        self.assertEqual(result["gates"]["m2_nonoverlap_sample"], "fail")
        self.assertEqual(result["counts"]["m2_signals"], 100)
        self.assertEqual(result["counts"]["m2_nonoverlap_signals"], 100)
        self.assertEqual(result["final"], "incomplete")

    def test_m2_requires_80_percent_and_200_nonoverlap_signals(self):
        rows = [{"signal_id": f"s{i}", "symbol": "AAA", "entry_timestamp_ms": str(i * 2000),
                 "exit_end_timestamp_ms": str(i * 2000 + 1000),
                 "target_first": "true" if i < 160 else "false"}
                for i in range(200)]
        target, sample = gate_check._m2_evidence(rows, "crypto")
        self.assertTrue(target.passed)
        self.assertTrue(sample.passed)
        self.assertEqual(target.diagnostics["rate"], 0.8)
        self.assertEqual(sample.diagnostics["nonoverlap_signals"], 200)

        target, sample = gate_check._m2_evidence(rows[:199], "crypto")
        self.assertTrue(target.passed)
        self.assertFalse(sample.passed)

        below = [dict(row, target_first="true" if i < 159 else "false")
                 for i, row in enumerate(rows)]
        target, sample = gate_check._m2_evidence(below, "crypto")
        self.assertFalse(target.passed)
        self.assertTrue(sample.passed)

    def test_nonoverlap_uses_maximum_cardinality_not_longest_first(self):
        rows = [
            {"signal_id": "long", "symbol": "AAA", "entry_timestamp_ms": "0",
             "exit_end_timestamp_ms": "100", "target_first": "false"},
            {"signal_id": "short1", "symbol": "AAA", "entry_timestamp_ms": "1",
             "exit_end_timestamp_ms": "2", "target_first": "true"},
            {"signal_id": "short2", "symbol": "AAA", "entry_timestamp_ms": "3",
             "exit_end_timestamp_ms": "4", "target_first": "true"},
        ]
        _, sample = gate_check._m2_evidence(rows, "crypto")
        self.assertEqual(sample.diagnostics["nonoverlap_signals"], 2)
        self.assertEqual(sample.diagnostics["nonoverlap_target_first"], 2)

    def test_statistical_denominators_come_from_ledgers(self):
        train, frozen = gate_check._authoritative_trial_counts(self.root)
        self.assertEqual(train, 2)
        self.assertEqual(frozen, 1)
        self.write_ledgers(train_rows=4, frozen_rows=2)
        train, frozen = gate_check._authoritative_trial_counts(self.root)
        self.assertEqual((train, frozen), (4, 2))

    def test_ledgers_fail_closed_on_missing_frozen_candidates(self):
        self.write_ledgers(train_rows=2, frozen_rows=0)
        with self.assertRaisesRegex(ValueError, "no frozen candidate"):
            gate_check._authoritative_trial_counts(self.root)

    def test_ledgers_fail_closed_on_duplicate_candidate_id(self):
        self.write_ledgers(train_rows=2, frozen_rows=2)
        path = self.root / "FROZEN_TEST_CANDIDATES.csv"
        lines = path.read_text().splitlines()
        lines[2] = lines[1].replace("c1,", "c0,")
        path.write_text("\n".join(lines) + "\n")
        with self.assertRaisesRegex(ValueError, "duplicate candidate_id"):
            gate_check._authoritative_trial_counts(self.root)

    def test_crypto_gate_requires_m2_events_and_equities_mark_not_applicable(self):
        legacy = self.root / "legacy-trades.csv"
        legacy.write_text("symbol,entry_date,exit_date,net_return\nAAA,2020-01-01,2020-01-02,0.01\n")
        result = gate_check.evaluate(self.args(m2_events=None))
        self.assertEqual(result["gates"]["m2_target_first"], "undetermined")
        self.assertEqual(result["final"], "incomplete")

        result = gate_check.evaluate(self.args(market="US", oos_trades=str(legacy)))
        self.assertEqual(result["gates"]["m2_target_first"], "pass")
        self.assertEqual(result["evidence"]["m2_target_first"]["diagnostics"]["not_applicable"], True)

        bad_schema = self.root / "bad-m2.csv"
        bad_schema.write_text("signal_id,symbol\ns1,AAA\n")
        with self.assertRaisesRegex(ValueError, "entry_timestamp_ms"):
            gate_check.evaluate(self.args(m2_events=str(bad_schema)))

    def test_m2_failure_forces_final_false_even_if_base_gate_passes(self):
        events = self.root / "m2-below.csv"
        with events.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["signal_id", "symbol", "entry_timestamp_ms",
                             "exit_end_timestamp_ms", "target_first"])
            for index in range(200):
                if index < 100:
                    day = date(2018, 1, 1) + timedelta(days=index * 3)
                    signal_id = f"s{index}"
                    start = int(datetime.combine(
                        day, datetime.min.time(), timezone.utc
                    ).timestamp() * 1000)
                    hit = index < 90
                else:
                    signal_id = f"extra-{index}"
                    start = 1_900_000_000_000 + (index - 100) * 2_000
                    hit = index < 169
                writer.writerow([f"s{index}", "AAA", start, start + 1000,
                                 "true" if hit else "false"])
        with patch.object(gate_check, "_final_gate", return_value=(True, True)):
            result = gate_check.evaluate(self.args(m2_events=str(events)))
        self.assertTrue(result["full_gate_complete"])
        self.assertFalse(result["final"])
        self.assertEqual(result["gates"]["m2_target_first"], "fail")

    def test_crypto_scored_trade_must_match_m2_signal(self):
        mismatched = self.root / "m2-mismatch.csv"
        with self.m2_events.open(newline="") as source, mismatched.open("w", newline="") as target:
            rows = list(csv.reader(source))
            rows[1][1] = "OTHER"
            csv.writer(target).writerows(rows)
        with self.assertRaisesRegex(ValueError, "matching M2 event"):
            gate_check.evaluate(self.args(m2_events=str(mismatched)))

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
        argv = ["--oos-trades", str(self.trades), "--m2-events", str(self.m2_events),
                "--daily-pnl", str(self.daily),
                "--market", "crypto", "--out", str(output)]
        with patch.object(gate_check, "LEDGER_DIR", self.root):
            self.assertEqual(gate_check.main(argv), 0)
        result = json.loads(output.read_text())
        self.assertEqual(result["final"], "incomplete")
        self.assertIn("random_entry", result["unknown_reasons"])
        summary = output.with_suffix(".md").read_text()
        self.assertIn("CORE 8항목", summary)
        self.assertIn("UNKNOWN", summary)

    def test_cli_does_not_accept_user_supplied_denominators(self):
        with self.assertRaises(SystemExit) as caught:
            gate_check._parser().parse_args([
                "--oos-trades", "trades.csv", "--daily-pnl", "daily.csv",
                "--market", "crypto", "--train-trials-count", "1",
                "--frozen-test-count", "1", "--out", "result.json",
            ])
        self.assertEqual(caught.exception.code, 2)

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
