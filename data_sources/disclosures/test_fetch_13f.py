"""13F 수집기의 네트워크 없는 기본 검증."""
import hashlib
import io
import tempfile
import unittest
from pathlib import Path
import zipfile

import pandas as pd

from fetch_13f import apply_acceptance_times, extract_acceptance_datetime, extract_bulk_urls, manifest_row, parse_dataset_zip
from sec_common import RateLimiter


class Fetch13FTests(unittest.TestCase):
    def test_acceptance_datetime_from_synthetic_sgml_headers(self):
        headers = [
            "<SEC-HEADER>\n<ACCEPTANCE-DATETIME>20241114160532</ACCEPTANCE-DATETIME>\n</SEC-HEADER>",
            "<acceptance-datetime>20230201090107</acceptance-datetime>",
        ]
        self.assertEqual(extract_acceptance_datetime(headers[0]), "20241114160532")
        self.assertEqual(extract_acceptance_datetime(headers[1]), "20230201090107")

    def test_acceptance_datetime_missing_is_explicit(self):
        with self.assertRaisesRegex(ValueError, "태그가 없습니다"):
            extract_acceptance_datetime("<SEC-HEADER>no acceptance field</SEC-HEADER>")

    def test_pit_timestamp_is_separate_from_report_period(self):
        source = pd.DataFrame([{"accession_number": "0000000001-24-000001", "period_of_report": "2024-09-30"}])
        result = apply_acceptance_times(source, {"0000000001-24-000001": "20241114160532"})
        self.assertEqual(result.loc[0, "period_of_report"], "2024-09-30")
        self.assertEqual(result.loc[0, "accepted_at"], "20241114160532")

    def test_synthetic_dataset_zip_joins_submission_cover_and_holding(self):
        accession = "0000000001-24-000001"
        files = {
            "SUBMISSION.tsv": f"ACCESSION_NUMBER\tCIK\n{accession}\t1234\n",
            "COVERPAGE.tsv": f"ACCESSION_NUMBER\tPERIODOFREPORT\n{accession}\t2024-09-30\n",
            "INFOTABLE.tsv": f"ACCESSION_NUMBER\tCUSIP\tVALUE\n{accession}\t123456789\t100\n",
        }
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for filename, contents in files.items():
                archive.writestr(filename, contents)
        result, raw_files = parse_dataset_zip(buffer.getvalue())
        self.assertEqual(len(result), 1)
        self.assertEqual(result.loc[0, "period_of_report"], "2024-09-30")
        self.assertEqual(result.loc[0, "cik"], "1234")
        self.assertEqual(result.loc[0, "CUSIP"], "123456789")
        self.assertEqual(set(raw_files), {"SUBMISSION.TSV", "COVERPAGE.TSV", "INFOTABLE.TSV"})

    def test_rate_limiter_sleeps_only_for_remaining_interval(self):
        now = [10.0]
        sleeps = []

        def clock():
            return now[0]

        def sleep(seconds):
            sleeps.append(seconds)
            now[0] += seconds

        limiter = RateLimiter(interval=1.0, clock=clock, sleeper=sleep)
        limiter.wait()
        limiter.wait()
        self.assertEqual(sleeps, [1.0])

    def test_manifest_row_has_file_hash_size_and_row_count(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.tsv"
            path.write_bytes(b"a\tb\n1\t2\n")
            row = manifest_row(path, "raw/sample.tsv", 1, "https://source.invalid/sample.zip", "2024Q3")
        self.assertEqual(row["rows"], 1)
        self.assertEqual(row["bytes"], len(b"a\tb\n1\t2\n"))
        self.assertEqual(row["sha256"], hashlib.sha256(b"a\tb\n1\t2\n").hexdigest())

    def test_bulk_links_are_taken_from_page_markup(self):
        page = '<a href="/files/structureddata/data/13f-data-sets/2024q3_form13f.zip">download</a>'
        self.assertEqual(extract_bulk_urls(page), ["https://www.sec.gov/files/structureddata/data/13f-data-sets/2024q3_form13f.zip"])
        self.assertEqual(extract_bulk_urls("<html>no files</html>"), [])


if __name__ == "__main__":
    unittest.main()
