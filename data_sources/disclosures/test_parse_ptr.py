"""PTR 파서의 합성 입력 회귀 검사."""
import unittest

from parse_ptr import parse_document


class ParsePtrTests(unittest.TestCase):
    def test_extracts_common_fields_and_uses_index_disclosure_date(self):
        text = """name: Jane Doe State/District: CA12 transactions owner asset transaction type date notification date amount
        SP Apple Inc. (AAPL) [ST] P 06/13/2022 06/19/2022 $1,001 - $15,000"""
        row, = parse_document("123", text, {"member_name": "Jane Doe", "district": "CA12", "notification_date": "2022-06-19"}, "markitdown")
        self.assertEqual((row["member_name"], row["district"], row["holder"]), ("Jane Doe", "CA12", "SP"))
        self.assertEqual((row["ticker"], row["asset_code"], row["transaction_type"]), ("AAPL", "ST", "P"))
        self.assertEqual((row["trade_date"], row["notification_date"]), ("2022-06-13", "2022-06-19"))
        self.assertEqual((row["amount_low"], row["amount_high"], row["source"]), (1001, 15000, "markitdown"))

    def test_ocr_confidence_is_lower_and_partial_sale_is_recognized(self):
        text = "JT Microsoft Corp (MSFT) [ST] S (partial) 1/2/2020 1/5/2020 $50,001 - $100,000"
        row, = parse_document("456", text, {"notification_date": "2020-01-05"}, "ocr")
        self.assertEqual(row["transaction_type"], "S(partial)")
        self.assertEqual(row["ticker"], "MSFT")
        self.assertLess(row["confidence"], 0.84)


if __name__ == "__main__":
    unittest.main()
