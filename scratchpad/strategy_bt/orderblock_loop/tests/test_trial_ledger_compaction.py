import hashlib
import unittest

from trial_ledger_compaction import compact_id_list


class TrialLedgerCompactionTests(unittest.TestCase):
    def test_empty_list_has_empty_string_digest(self):
        self.assertEqual(
            compact_id_list([]),
            {"count": 0, "sha256": hashlib.sha256(b"").hexdigest()},
        )

    def test_duplicates_are_preserved_and_counted(self):
        result = compact_id_list(["trade-b", "trade-a", "trade-a"])
        expected = hashlib.sha256(b"trade-a\ntrade-a\ntrade-b").hexdigest()
        self.assertEqual(result, {"count": 3, "sha256": expected})

    def test_input_order_does_not_change_digest(self):
        first = compact_id_list(["trade-c", "trade-a", "trade-b"])
        second = compact_id_list(["trade-b", "trade-c", "trade-a"])
        self.assertEqual(first["sha256"], second["sha256"])

    def test_count_matches_input_length(self):
        ids = ["x", "x", "y", "z", "z"]
        self.assertEqual(compact_id_list(ids)["count"], len(ids))


if __name__ == "__main__":
    unittest.main()
