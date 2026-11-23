import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock
import pandas as pd
import collector

class CollectorTests(unittest.TestCase):
    def test_month_ends_has_exact_cutoff(self):
        self.assertEqual(collector.month_ends(date(2026,4,1), date(2026,5,31)), [date(2026,4,30), date(2026,5,31)])

    def test_membership_and_snapshot_resume(self):
        stock = Mock(); stock.get_market_ticker_list.return_value = ['5930']
        with tempfile.TemporaryDirectory() as tmp:
            df = collector.fetch_membership(stock, [date(2026,4,30),date(2026,5,31)], sleep=lambda _:None, snapshot_dir=tmp)
            self.assertEqual(list(df.columns), collector.MEMBERSHIP_COLUMNS)
            self.assertEqual(df.iloc[0].symbol, '005930')
            self.assertEqual(stock.get_market_ticker_list.call_count, 4)
            stock.reset_mock()
            collector.fetch_membership(stock, [date(2026,4,30),date(2026,5,31)], sleep=lambda _:None, snapshot_dir=tmp)
            stock.get_market_ticker_list.assert_not_called()

    def test_delistings_cutoff_and_reuse_key(self):
        fdr = Mock(); fdr.StockListing.return_value = pd.DataFrame({'Symbol':['000001','000001','000002'], 'ListingDate':['2001-01-01','2010-01-01','2026-06-01'], 'DelistingDate':['2005-01-01','2020-01-01','2026-06-30'], 'Reason':['일반','합병','일반']})
        rows = collector.fetch_delistings(fdr)
        self.assertEqual(len(rows), 2); self.assertEqual(rows.instrument_key.nunique(), 2)
        self.assertTrue(collector._is_merger(rows.iloc[1]))

    def test_price_cutoff_merger_and_empty_guard(self):
        class Stock:
            def get_market_ohlcv_by_date(self, start, end, code):
                return pd.DataFrame({'시가':[10,11,12], '고가':[11,12,13], '저가':[9,10,11], '종가':[10,11,12], '거래량':[1,1,1]}, index=['2026-05-29','2026-05-31','2026-06-01'])
        rows = pd.DataFrame([{'code':'000001','listing_date':date(2020,1,1),'delisting_date':date(2026,5,31),'instrument_key':'000001:2020-01-01','Reason':'합병'}])
        prices, _ = collector.fetch_delisted_prices(rows, Stock(), sleep=lambda _:None, rate_seconds=0)
        self.assertEqual(len(prices), 2); self.assertTrue((prices.date <= collector.CUTOFF).all()); self.assertTrue(prices.merger_delisting.all())
        with self.assertRaises(ValueError): collector.write_table(pd.DataFrame(), Path('/tmp/no.csv'))

if __name__ == '__main__': unittest.main()
