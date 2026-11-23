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

    def test_2024_glued_dates_and_nul_labels(self):
        text = """P\x00\x00\x00\x00\x00\x00\x00 T\x00\x00\x00\x00\x00\x00\x00\x00\x00 R\x00\x00\x00\x00\x00Clerk of the House of Representatives • Legislative Resource Center • B81 Cannon Building • Washington, DC 20515F\x00\x00\x00\x00 I\x00\x00\x00\x00\x00\x00\x00\x00\x00Name:Hon. Marjorie Taylor Mrs GreeneStatus:MemberState/District:GA14T\x00\x00\x00\x00\x00\x00\x00IDOwnerAssetTransactionTypeDateNotificationDateAmountCap.Gains >$200?ASML Holding N.V. - New YorkRegistry Shares (ASML) [ST]P10/21/202410/22/2024$1,001 - $15,000F\x00\x00\x00\x00\x00 S\x00\x00\x00\x00\x00: New"""
        row, = parse_document("20026059", text, {"member_name": "Marjorie Taylor Greene", "district": "GA14"}, "markitdown")
        self.assertTrue(all("\x00" not in value for value in row.values() if isinstance(value, str)))
        self.assertEqual(row["trade_date"], "2024-10-21")

    def test_2026_spaced_dates_and_nul_labels(self):
        text = """P\x00\x00\x00\x00\x00\x00\x00 T\x00\x00\x00\x00\x00\x00\x00\x00\x00 R\x00\x00\x00\x00\x00Clerk of the House of Representatives • Legislative Resource Center • B81 Cannon Building • Washington, DC 20515F\x00\x00\x00\x00 I\x00\x00\x00\x00\x00\x00\x00\x00\x00Name:Hon. Gilbert CisnerosStatus:MemberState/District:CA31T\x00\x00\x00\x00\x00\x00\x00IDOwnerAssetTransactionTypeDateNotificationDateAmountCap.Gains >$200?Advanced Micro Devices, Inc. (AMD)[ST]S (partial)08/18/2026 09/04/2026$1,001 - $15,000F\x00\x00\x00\x00\x00 S\x00\x00\x00\x00\x00: New"""
        row, = parse_document("20035390", text, {"member_name": "Gilbert Cisneros", "district": "CA31"}, "markitdown")
        self.assertTrue(all("\x00" not in value for value in row.values() if isinstance(value, str)))
        self.assertEqual(row["trade_date"], "2026-08-18")

    def test_2025_glued_dates_and_nul_labels(self):
        text = """P\x00\x00\x00\x00\x00\x00\x00 T\x00\x00\x00\x00\x00\x00\x00\x00\x00 R\x00\x00\x00\x00\x00Clerk of the House of Representatives • Legislative Resource Center • B81 Cannon Building • Washington, DC 20515F\x00\x00\x00\x00 I\x00\x00\x00\x00\x00\x00\x00\x00\x00Name:Hon. Robert B. AderholtStatus:MemberState/District:AL04T\x00\x00\x00\x00\x00\x00\x00IDOwnerAssetTransactionTypeDateNotificationDateAmountCap.Gains >$200?GSK plc American Depositary Shares(GSK) [ST]S07/28/202508/11/2025$1,001 - $15,000F\x00\x00\x00\x00\x00 S\x00\x00\x00\x00\x00: New"""
        row, = parse_document("20032062", text, {"member_name": "Robert B. Aderholt", "district": "AL04"}, "markitdown")
        self.assertTrue(all("\x00" not in value for value in row.values() if isinstance(value, str)))
        self.assertEqual(row["trade_date"], "2025-07-28")


if __name__ == "__main__":
    unittest.main()
