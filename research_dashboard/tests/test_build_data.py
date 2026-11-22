import copy
import csv
import json
import random
import tempfile
import unittest
from pathlib import Path

import build_data
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).parent / "fixtures/tree"


def validate_data(data):
    assert set(data) == {"generated_at", "counts", "headline", "adjusted_sentence", "depth_test_sources", "nodes", "edges", "forward"}
    assert isinstance(data["generated_at"], str)
    assert isinstance(data["nodes"], list) and isinstance(data["edges"], list)
    for field in ("total_archived", "spec_complete", "implemented_tested", "trials_counted", "adjusted_passed", "adjusted_tested", "confirmed_real_winners"):
        assert isinstance(data["counts"][field], int)
    for node in data["nodes"]:
        for field, typ in (("id", str), ("strategy_id", str), ("timeframe", str), ("side", str), ("family", str), ("verdict", str), ("verification_depth", int), ("tests", list)):
            assert isinstance(node[field], typ), (field, node)
        for test in node["tests"]:
            assert test["status"] in {"passed", "failed", "not_run"}
            assert all(isinstance(test[k], str) for k in ("name", "source_file", "plain_reason"))
        assert node["verification_depth"] == sum(t["status"] == "passed" for t in node["tests"])
        assert isinstance(node["symbols"], list) and isinstance(node["per_year"], list)
        assert node["source_url"] is None or isinstance(node["source_url"], str)
    node_ids = {node["id"] for node in data["nodes"]}
    for edge in data["edges"]:
        assert edge["source"] in node_ids and edge["target"] in node_ids
        assert edge["edge_kind"] in {"metadata_similarity", "return_correlation"}
        assert isinstance(edge["weight"], (int, float))
    assert [f["profile"] for f in data["forward"]] == ["l5_4h", "l5_12h", "jbb_1h"]
    assert all(isinstance(row["test"], str) and isinstance(row["file"], str) and isinstance(row["column_or_rule"], str) for row in data["depth_test_sources"])


class BuildDataTests(unittest.TestCase):
    def test_fixture_snapshot(self):
        actual = build_data.build(ROOT)
        actual.pop("generated_at")
        expected = json.loads((Path(__file__).parent / "fixtures/expected.json").read_text())
        self.assertEqual(actual, expected)

    def test_schema(self):
        validate_data(build_data.build(ROOT))

    def test_node_size_uses_only_verification_depth_fields(self):
        node = {"tests": [{"status": "passed"}, {"status": "failed"}, {"status": "not_run"}], "train_return": 2, "test_return": 5, "secondary_return": 10}
        expected = build_data.verification_depth(node)
        rng = random.Random(12)
        for key in ("train_return", "test_return", "secondary_return"):
            node[key] = rng.uniform(-1e9, 1e9)
        self.assertEqual(build_data.verification_depth(node), expected)
        import inspect
        source = inspect.getsource(build_data.verification_depth)
        self.assertNotIn("train_return", source)
        self.assertNotIn("test_return", source)
        self.assertNotIn("secondary_return", source)
        self.assertIn('test["status"]', source)

        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp) / "tree"
            import shutil
            shutil.copytree(ROOT, tree)
            summary = tree / "scratchpad/strategy_bt/results/slice_0/summary.csv"
            with summary.open() as stream:
                rows = list(csv.DictReader(stream))
            original_depth = build_data.build(tree)["nodes"][0]["verification_depth"]
            for key in ("train_return", "test_return"):
                rows[0][key] = str(rng.uniform(-1e8, 1e8))
            with summary.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            mutated_depth = build_data.build(tree)["nodes"][0]["verification_depth"]
            self.assertEqual(mutated_depth, original_depth)

    def test_forward_decision_thresholds_and_confirmation(self):
        empty = build_data.forward_decision("l5_4h", 0, 2, 0, "통과")
        self.assertFalse(empty["data_sufficient"])
        self.assertFalse(empty["confirmed"])
        self.assertTrue(empty["no_signals"])
        self.assertEqual(empty["decision_label"], "데이터 부족")
        self.assertEqual(empty["trades_left"], 30)
        self.assertEqual(empty["days_left"], 88)

        short_by_one_trade = build_data.forward_decision("l5_4h", 29, 90, 3, "통과")
        self.assertFalse(short_by_one_trade["data_sufficient"])
        short_by_one_day = build_data.forward_decision("jbb_1h", 100, 59.9, 3, "통과")
        self.assertFalse(short_by_one_day["data_sufficient"])

        exact_but_zero = build_data.forward_decision("l5_4h", 30, 90, 0, "통과")
        self.assertTrue(exact_but_zero["data_sufficient"])
        self.assertFalse(exact_but_zero["confirmed"])
        exact_and_profitable = build_data.forward_decision("l5_4h", 30, 90, 0.01, "통과")
        self.assertTrue(exact_and_profitable["confirmed"])
        rejected = build_data.forward_decision("jbb_1h", 100, 60, 0.01, "탈락")
        self.assertFalse(rejected["confirmed"])
        unknown = build_data.forward_decision("jbb_1h", 100, 60, 0.01, "미판정")
        self.assertFalse(unknown["confirmed"])

    def test_copy_age_uses_copy_timestamp(self):
        now = datetime(2026, 11, 22, 0, 0, tzinfo=timezone.utc)
        copied = now - timedelta(minutes=17, seconds=59)
        self.assertEqual(build_data.copy_age_minutes(copied, now), 17)
        self.assertIsNone(build_data.copy_age_minutes(None, now))


if __name__ == "__main__":
    unittest.main()
