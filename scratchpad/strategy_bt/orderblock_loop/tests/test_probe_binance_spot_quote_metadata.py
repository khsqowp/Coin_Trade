import unittest

from scratchpad.strategy_bt.orderblock_loop.probe_binance_spot_quote_metadata import (
    EXPECTED_MONTHS,
    parse_listing,
    year_prefix,
)


NS = "http://s3.amazonaws.com/doc/2006-03-01/"


def listing_xml(prefix, months, include_checksums=True, truncated="false"):
    entries = []
    for month in months:
        entries.append(f"<Contents><Key>{prefix}{month}.zip</Key></Contents>")
        if include_checksums:
            entries.append(f"<Contents><Key>{prefix}{month}.zip.CHECKSUM</Key></Contents>")
    return (
        f'<ListBucketResult xmlns="{NS}"><IsTruncated>{truncated}</IsTruncated>'
        + "".join(entries)
        + "</ListBucketResult>"
    ).encode()


class QuoteMetadataTests(unittest.TestCase):
    def test_prefix_is_fixed_to_preregistered_year_and_interval(self):
        self.assertEqual(
            year_prefix("TRXBTC", 2018),
            "data/spot/monthly/klines/TRXBTC/1h/TRXBTC-1h-2018-",
        )
        with self.assertRaises(ValueError):
            year_prefix("TRXBTC", 2026)
        with self.assertRaises(ValueError):
            year_prefix("../TRXBTC", 2018)

    def test_complete_requires_all_zip_and_checksum_months(self):
        prefix = year_prefix("TRXBTC", 2022)
        months = [f"{month:02d}" for month in range(1, 13)]
        result = parse_listing(listing_xml(prefix, months), prefix)
        self.assertEqual(result.status, "http_200")
        self.assertEqual(result.zip_months, EXPECTED_MONTHS)
        self.assertEqual(result.checksum_months, EXPECTED_MONTHS)
        self.assertTrue(result.complete)

    def test_missing_checksum_prevents_complete(self):
        prefix = year_prefix("TRXBTC", 2022)
        months = [f"{month:02d}" for month in range(1, 13)]
        result = parse_listing(listing_xml(prefix, months, include_checksums=False), prefix)
        self.assertEqual(len(result.zip_months), 12)
        self.assertEqual(len(result.checksum_months), 0)
        self.assertFalse(result.complete)

    def test_partial_year_does_not_pass(self):
        prefix = year_prefix("TRXBTC", 2018)
        months = [f"{month:02d}" for month in range(1, 12)]
        self.assertFalse(parse_listing(listing_xml(prefix, months), prefix).complete)

    def test_truncated_or_malformed_listing_fails_closed(self):
        prefix = year_prefix("TRXBTC", 2018)
        months = [f"{month:02d}" for month in range(1, 13)]
        truncated = parse_listing(listing_xml(prefix, months, truncated="true"), prefix)
        malformed = parse_listing(b"<not-xml", prefix)
        self.assertEqual(truncated.status, "unverified_truncated")
        self.assertEqual(malformed.status, "unverified_xml")
        self.assertFalse(truncated.complete)
        self.assertFalse(malformed.complete)

    def test_wrong_prefix_keys_do_not_inflate_coverage(self):
        prefix = year_prefix("TRXBTC", 2018)
        months = [f"{month:02d}" for month in range(1, 13)]
        xml_body = listing_xml(prefix, months).replace(
            f"{prefix}01.zip".encode(),
            b"data/spot/monthly/klines/OTHERBTC/1h/OTHERBTC-1h-2018-01.zip",
        )
        result = parse_listing(xml_body, prefix)
        self.assertEqual(len(result.zip_months), 11)
        self.assertFalse(result.complete)


if __name__ == "__main__":
    unittest.main()
