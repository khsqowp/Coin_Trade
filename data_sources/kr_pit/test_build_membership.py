"""Synthetic tests for the local KR membership builder."""
from __future__ import annotations

import csv
import tempfile
import unittest
from datetime import date
from pathlib import Path

from data_sources.kr_pit.build_membership import MEMBERSHIP_COLUMNS, STATUS, build, validate_intervals


class BuildMembershipTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.delist = self.root / 'delisting_list.csv'
        self.output = self.root / 'nested' / 'membership.csv'
        self._write(self.delist, ['Symbol', 'Market', 'ListingDate', 'DelistingDate'], [
            {'Symbol': '000001', 'Market': 'KOSPI', 'ListingDate': '2000-01-01', 'DelistingDate': '2020-01-01'},
            {'Symbol': '000002', 'Market': 'KOSDAQ', 'ListingDate': '', 'DelistingDate': '2020-01-01'},
        ])

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def _write(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
        with path.open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)

    @staticmethod
    def _rows(path: Path) -> list[dict[str, str]]:
        with path.open(newline='', encoding='utf-8') as handle:
            return list(csv.DictReader(handle))

    def test_missing_listing_date_is_excluded_and_reported(self) -> None:
        counts = build(self.delist, self.output, today=date(2026, 11, 23))
        self.assertEqual(counts['excluded_missing_listing_date'], 1)
        self.assertEqual(self._rows(self.output.with_name('excluded_missing_listing_date.csv')),
                         [{'symbol': '000002', 'reason': 'missing ListingDate'}])

    def test_overlapping_current_symbol_excludes_both_records(self) -> None:
        current = self.root / 'current.csv'
        self._write(current, ['market', 'symbol', 'listing_date'], [
            {'market': 'KOSDAQ', 'symbol': '000001', 'listing_date': '2010-01-01'}])
        counts = build(self.delist, self.output, current, date(2026, 11, 23))
        self.assertEqual(counts['overlap_conflicts'], 1)
        self.assertEqual(self._rows(self.output), [])
        self.assertEqual(self._rows(self.output.with_name('conflicts.csv'))[0]['symbol'], '000001')

    def test_non_overlapping_current_symbol_is_separate_membership(self) -> None:
        current = self.root / 'current.csv'
        self._write(current, ['market', 'symbol', 'listing_date', 'source'], [
            {'market': 'KOSPI', 'symbol': '000003', 'listing_date': '2021-04-05', 'source': 'FDR KRX'}])
        build(self.delist, self.output, current, date(2026, 11, 23))
        rows = self._rows(self.output)
        self.assertEqual(len(rows), 2)
        current_row = next(row for row in rows if row['symbol'] == '000003')
        self.assertEqual(current_row['alive_through'], '2026-05-31')
        self.assertEqual(current_row['source'], 'FDR KRX')

    def test_no_current_listing_runs_delisted_only(self) -> None:
        counts = build(self.delist, self.output, today=date(2026, 11, 23))
        rows = self._rows(self.output)
        self.assertEqual(counts['membership_rows'], 1)
        self.assertEqual([row['symbol'] for row in rows], ['000001'])

    def test_column_order_and_status_are_exact(self) -> None:
        build(self.delist, self.output, today=date(2026, 11, 23))
        with self.output.open(newline='', encoding='utf-8') as handle:
            reader = csv.DictReader(handle)
            self.assertEqual(reader.fieldnames, MEMBERSHIP_COLUMNS)
            rows = list(reader)
        self.assertEqual(rows[0]['status'], STATUS)
        self.assertEqual(rows[0]['source_asof'], '2026-11-23')

    def test_duplicate_delisting_symbol_is_excluded_defensively(self) -> None:
        rows = self._rows(self.delist)
        self._write(self.delist, ['Symbol', 'Market', 'ListingDate', 'DelistingDate'],
                    rows + [dict(rows[0])])
        counts = build(self.delist, self.output, today=date(2026, 11, 23))
        self.assertEqual(counts['duplicate_symbols'], 1)
        self.assertEqual(self._rows(self.output), [])
        self.assertEqual(self._rows(self.output.with_name('conflicts.csv'))[0]['reason'],
                         'duplicate Symbol in delisting_list.csv')

    def test_current_listing_after_cutoff_is_excluded_and_reported(self) -> None:
        current = self.root / 'current.csv'
        self._write(current, ['market', 'symbol', 'listing_date'], [
            {'market': 'KOSDAQ', 'symbol': '0209J0', 'listing_date': '2026-09-22'}])
        counts = build(self.delist, self.output, current, date(2026, 11, 23))
        self.assertEqual(counts['excluded_after_cutoff'], 1)
        self.assertNotIn('0209J0', [row['symbol'] for row in self._rows(self.output)])
        self.assertEqual(self._rows(self.output.with_name('excluded_after_cutoff.csv')),
                         [{'symbol': '0209J0', 'market': 'KOSDAQ', 'listing_date': '2026-09-22',
                           'reason': 'listing_date after 2026-05-31 cutoff'}])

    def test_current_listing_on_cutoff_is_kept(self) -> None:
        current = self.root / 'current.csv'
        self._write(current, ['market', 'symbol', 'listing_date'], [
            {'market': 'KOSPI', 'symbol': '000004', 'listing_date': '2026-05-31'}])
        build(self.delist, self.output, current, date(2026, 11, 23))
        row = next(row for row in self._rows(self.output) if row['symbol'] == '000004')
        self.assertEqual(row['alive_from'], '2026-05-31')
        self.assertEqual(row['alive_through'], '2026-05-31')

    def test_interval_defensive_check_rejects_inverted_interval(self) -> None:
        with self.assertRaisesRegex(ValueError, 'alive_from <= alive_through check FAIL: 1'):
            validate_intervals([{'symbol': '0209J0', 'alive_from': '2026-09-22',
                                 'alive_through': '2026-05-31'}])


if __name__ == '__main__':
    unittest.main()
