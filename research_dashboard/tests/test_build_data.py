import copy
import csv
import json
import random
import tempfile
import unittest
from pathlib import Path

import build_data

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


if __name__ == "__main__":
    unittest.main()
