import csv
import json
import tempfile
import unittest
from pathlib import Path

from ledger_summary import summarize


FIELDS = ["trial_id", "round", "market_group", "utc_timestamp", "definition",
          "parameter_grid_hash", "code_sha256", "train_period", "metric", "rank", "notes"]


class LedgerSummaryTests(unittest.TestCase):
    def test_groups_counts_handles_bad_metrics_and_orders_top_five(self):
        rows = []
        values = [3.0, -2.0, 7.0, 1.0, 5.0, 4.0]
        for index, expectancy in enumerate(values):
            rows.append({"trial_id": f"R3-KR-{index}", "round": "R3", "market_group": "KR",
                         "definition": json.dumps({"candidate": f"E3-{index}"}),
                         "metric": json.dumps({"expectancy_net_bps": expectancy,
                                                "trades": index + 10, "status": "TRAIN_ONLY_NOT_G"})})
        rows.append({"trial_id": "R3-KR-bad", "round": "R3", "market_group": "KR",
                     "definition": "{}", "metric": "{malformed"})
        rows.append({"trial_id": "R3-US-1", "round": "R3", "market_group": "US",
                     "definition": "{}", "metric": json.dumps({"expectancy_net_bps": 2, "status": "ok"})})
        rows.append({"trial_id": "R4-KR-1", "round": "R4", "market_group": "KR",
                     "definition": "{}", "metric": ""})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=FIELDS)
                writer.writeheader()
                for row in rows:
                    writer.writerow(row)
            groups = summarize(path)
            filtered = summarize(path, "R3", "US")
        kr = groups[("R3", "KR")]
        self.assertEqual(len(kr), 7)
        self.assertEqual(sum(row["expectancy"] is not None and row["expectancy"] > 0 for row in kr), 5)
        self.assertTrue(next(row for row in kr if row["trial_id"] == "R3-KR-bad")["no_metric"])
        top = sorted((row for row in kr if row["expectancy"] is not None),
                     key=lambda row: row["expectancy"], reverse=True)[:5]
        self.assertEqual([row["expectancy"] for row in top], [7.0, 5.0, 4.0, 3.0, 1.0])
        self.assertEqual(set(groups), {("R3", "KR"), ("R3", "US"), ("R4", "KR")})
        self.assertEqual(len(filtered[("R3", "US")]), 1)


if __name__ == "__main__":
    unittest.main()
