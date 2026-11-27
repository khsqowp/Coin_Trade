"""Metadata-only Binance Spot quote coverage gate for a frozen CMC cohort."""

from __future__ import annotations

import hashlib
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

try:
    from .research_paths import REPO_ROOT, require_trading_data_dir
except ImportError:  # Direct script execution from this directory.
    from research_paths import REPO_ROOT, require_trading_data_dir


PREREG_REL = Path(
    "scratchpad/strategy_bt/orderblock_loop/"
    "PREREG_BINANCE_SPOT_FIXED_QUOTE_FALLBACK_CMC201801_20261128.md"
)
PREREG_SHA256 = "bcf0e23a7212232b81b45403b5cef5681bc09a213f42f1d5399e9d4e652a1a5c"
ARCHIVE_ROOT = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision/"
ASSETS = (
    "XRP", "ETH", "BCH", "ADA", "LTC", "IOTA", "XEM", "XLM", "DASH",
    "XMR", "NEO", "EOS", "BTG", "QTUM", "NANO", "TRX", "ETC", "LSK",
    "BCC", "ICX", "XVG", "BTS", "OMG", "ZEC", "ARDR", "STRAT", "PPT",
    "USDT", "WAVES",
)
QUOTES = ("BTC", "USDT", "ETH", "BNB")
YEARS = (2018, 2022)
EXPECTED_MONTHS = frozenset(f"{month:02d}" for month in range(1, 13))
NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
KNOWN_COMPLETE_BTC = frozenset(
    "XRPBTC ETHBTC ADABTC LTCBTC IOTABTC XLMBTC DASHBTC XMRBTC NEOBTC EOSBTC QTUMBTC".split()
)
KNOWN_INCOMPLETE_BTC = frozenset("BCHBTC XEMBTC BTGBTC NANOBTC".split())
SEED_COMPLETE_BTC = frozenset("TRXBTC".split())
UNRESOLVED_BASES = frozenset({"BCC"})
REQUEST_INTERVAL_SECONDS = 1.0
REQUEST_TIMEOUT_SECONDS = 20


@dataclass(frozen=True)
class ListingResult:
    status: str
    zip_months: frozenset[str] = frozenset()
    checksum_months: frozenset[str] = frozenset()

    @property
    def complete(self) -> bool:
        return (
            self.status == "http_200"
            and self.zip_months == EXPECTED_MONTHS
            and self.checksum_months == EXPECTED_MONTHS
        )


def year_prefix(pair: str, year: int) -> str:
    if year not in YEARS or not re.fullmatch(r"[A-Z0-9]+", pair):
        raise ValueError("pair or historical year is outside the preregistered scope")
    return f"data/spot/monthly/klines/{pair}/1h/{pair}-1h-{year}-"


def parse_listing(xml_body: bytes, prefix: str) -> ListingResult:
    try:
        root = ET.fromstring(xml_body)
    except ET.ParseError:
        return ListingResult("unverified_xml")
    expected_root = f"{{{NS['s3']}}}ListBucketResult"
    if root.tag != expected_root:
        return ListingResult("unverified_xml")
    truncated = root.findtext("s3:IsTruncated", default="true", namespaces=NS)
    if truncated.lower() != "false":
        return ListingResult("unverified_truncated")

    zip_months: set[str] = set()
    checksum_months: set[str] = set()
    for key_node in root.findall("s3:Contents/s3:Key", NS):
        key = key_node.text or ""
        if not key.startswith(prefix):
            continue
        suffix = key[len(prefix):]
        zip_match = re.fullmatch(r"(\d{2})\.zip", suffix)
        checksum_match = re.fullmatch(r"(\d{2})\.zip\.CHECKSUM", suffix)
        if zip_match:
            zip_months.add(zip_match.group(1))
        elif checksum_match:
            checksum_months.add(checksum_match.group(1))
    return ListingResult("http_200", frozenset(zip_months), frozenset(checksum_months))


class MetadataClient:
    def __init__(self) -> None:
        no_redirect = type(
            "NoRedirect",
            (urllib.request.HTTPRedirectHandler,),
            {"redirect_request": lambda self, req, fp, code, msg, headers, newurl: None},
        )
        self.opener = urllib.request.build_opener(no_redirect)
        self.last_request_at = 0.0
        self.request_count = 0

    def list_year(self, pair: str, year: int) -> ListingResult:
        elapsed = time.monotonic() - self.last_request_at
        if self.last_request_at and elapsed < REQUEST_INTERVAL_SECONDS:
            time.sleep(REQUEST_INTERVAL_SECONDS - elapsed)
        prefix = year_prefix(pair, year)
        query = urllib.parse.urlencode({"list-type": "2", "prefix": prefix})
        request = urllib.request.Request(
            ARCHIVE_ROOT + "?" + query,
            headers={"User-Agent": "Coin_Trade historical metadata audit"},
        )
        self.last_request_at = time.monotonic()
        self.request_count += 1
        try:
            with self.opener.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                if response.status != 200:
                    return ListingResult(f"http_{response.status}")
                return parse_listing(response.read(), prefix)
        except urllib.error.HTTPError as exc:
            return ListingResult(f"http_{exc.code}")
        except (urllib.error.URLError, TimeoutError, OSError):
            return ListingResult("unverified_network")


def verify_prereg() -> None:
    path = REPO_ROOT / PREREG_REL
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != PREREG_SHA256:
        raise RuntimeError("preregistration hash changed; stop before any request")


def probe_asset(base: str, client: MetadataClient) -> tuple[str, str]:
    if base in UNRESOLVED_BASES:
        return "-", "identity_unresolved"

    for quote in QUOTES:
        if base == quote:
            continue
        pair = base + quote
        if pair in KNOWN_COMPLETE_BTC or pair in SEED_COMPLETE_BTC:
            if quote == "BTC":
                return pair, "complete_reused"
        if pair in KNOWN_INCOMPLETE_BTC:
            if quote == "BTC":
                continue
        year_results: list[ListingResult] = []
        for year in YEARS:
            result = client.list_year(pair, year)
            year_results.append(result)
            if not result.complete:
                break
        if len(year_results) == len(YEARS) and all(r.complete for r in year_results):
            return pair, "complete_new"
    return "-", "no_confirmed_complete_pair"


def main() -> int:
    require_trading_data_dir(os.environ.get("TRADING_DATA_DIR"))
    verify_prereg()
    client = MetadataClient()
    completed = len(KNOWN_COMPLETE_BTC | SEED_COMPLETE_BTC)
    print("source=Binance Vision official bucket; scope=CMC 2018 fixed cohort; years=2018,2022")
    for base in ASSETS:
        pair, status = probe_asset(base, client)
        if status == "complete_new":
            completed += 1
        print(f"asset={base} pair={pair} status={status}")
    print(f"confirmed_complete={completed}/29 required=25 requests={client.request_count}")
    print("price_zip_downloads=0 price_rows_opened=0 ledger_access=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
