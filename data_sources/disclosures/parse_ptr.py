"""Parse House PTR Markdown into reviewable event rows and yearly Parquet files."""
from __future__ import annotations

import argparse
import csv
import hashlib
import re
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

DATA = Path.home() / "CODE/Coin_Trade/trading_data/external/disclosures/house"
OUT = DATA / "events"
FIELDS = ["docid", "member_name", "district", "holder", "asset_name", "ticker",
          "asset_code", "transaction_type", "trade_date", "notification_date",
          "amount_low", "amount_high", "confidence", "source"]
AMOUNT = re.compile(r"\$\s*(\d[\d,]*)\s*(?:-|to)\s*\$?\s*(\d[\d,]*)", re.I)
# Dates can be glued together with no separator, so word boundaries miss the first one.
DATE = re.compile(r"(\d{1,2}/\d{1,2}/\d{4})")
CODE = re.compile(r"\[([A-Z]{1,5})\]")
TICKER = re.compile(r"\(([A-Z][A-Z0-9.\-]{0,9})\)")
TRADE = re.compile(r"(?<![A-Z])(S\s*\(\s*partial\s*\)|P|S|E)(?![A-Z])", re.I)


def index_metadata(year: int) -> dict[str, dict[str, str]]:
    with zipfile.ZipFile(DATA / f"{year}FD.zip") as zf:
        rows = zf.read(f"{year}FD.txt").decode("utf-8-sig", "replace").splitlines()
    if not rows:
        return {}
    result = {}
    for row in csv.DictReader(rows, delimiter="\t"):
        if row.get("FilingType") == "P":
            result[row["DocID"]] = {
                "member_name": " ".join(x for x in (row.get("First", "").strip(), row.get("Last", "").strip(), row.get("Suffix", "").strip()) if x),
                "district": row.get("StateDst", ""),
                "notification_date": parse_date(row.get("FilingDate", "")),
            }
    return result


def parse_date(value: str) -> str | None:
    try:
        return datetime.strptime(value.strip(), "%m/%d/%Y").date().isoformat()
    except (ValueError, AttributeError):
        return None


def parse_document(docid: str, text: str, metadata: dict[str, str], source: str) -> list[dict]:
    text = text.replace("\x00", "")
    flat = re.sub(r"\s+", " ", text).strip()
    name = metadata.get("member_name") or _extract_member(flat)
    district = metadata.get("district")
    events = []
    matches = list(AMOUNT.finditer(flat))
    for i, amount in enumerate(matches):
        start = matches[i - 1].end() if i else 0
        segment = flat[start:amount.end()]
        dates = DATE.findall(segment)
        tr = _last_match(TRADE, segment)
        code = _last_match(CODE, segment)
        ticker = _last_match(TICKER, segment)
        asset = _asset(segment, amount.group(0), ticker)
        holder = _holder(segment)
        confidence = 0.84 if tr and dates and code else 0.62 if tr and dates else 0.30
        if source == "ocr":
            confidence *= 0.75
        events.append({
            "docid": str(docid), "member_name": name, "district": district,
            "holder": holder, "asset_name": asset,
            "ticker": ticker.group(1) if ticker else _asset_ticker(asset),
            "asset_code": code.group(1) if code else None,
            "transaction_type": _normalize_trade(tr.group(1)) if tr else None,
            "trade_date": parse_date(dates[0]) if dates else None,
            "notification_date": parse_date(dates[1]) if len(dates) > 1 else metadata.get("notification_date"),
            "amount_low": int(amount.group(1).replace(",", "")),
            "amount_high": int(amount.group(2).replace(",", "")),
            "confidence": round(confidence, 2), "source": source,
        })
    return events


def _extract_member(text: str) -> str | None:
    m = re.search(r"name:\s*([A-Z][A-Z .,'-]{3,60})\s+(?:office|telephone|filing)", text, re.I)
    return m.group(1).strip(" .") if m else None


def _normalize_trade(value: str) -> str:
    v = re.sub(r"\s+", "", value).upper()
    return "S(partial)" if "PARTIAL" in v else v


def _last_match(pattern, text):
    found = list(pattern.finditer(text))
    return found[-1] if found else None


def _holder(text: str) -> str:
    found = re.findall(r"\b(SP|DC|JT)\b", text)
    return found[-1] if found else ""


def _asset(text: str, amount: str, ticker_match) -> str | None:
    before = text[:ticker_match.start()] if ticker_match else text.split(amount, 1)[0]
    holders = list(re.finditer(r"\b(?:SP|DC|JT)\b", before))
    if holders:
        before = before[holders[-1].end():]
    before = re.sub(r"\b(?:P|S|E)\b", " ", before, flags=re.I)
    before = DATE.sub(" ", before)
    before = re.sub(r"\b(?:name|status|transactions|owner|asset|type|date|notification|amount|filing status)\b", " ", before, flags=re.I)
    value = re.sub(r"\s+", " ", before).strip(" |;,.-")
    return value[-100:] or None


def _asset_ticker(asset: str | None) -> str | None:
    if not asset:
        return None
    m = re.search(r"\b([A-Z]{1,5})\b\s*$", asset)
    return m.group(1) if m else None


def process_year(year: int) -> tuple[list[dict], Counter]:
    metadata = index_metadata(year)
    manifest = DATA / "ptr_manifest.csv"
    methods = {}
    if manifest.exists():
        with manifest.open(newline="") as fh:
            methods = {r["docid"]: r["method"] for r in csv.DictReader(fh) if r["year"] == str(year) and r["status"] == "ok"}
    rows, counts = [], Counter()
    for docid, meta in metadata.items():
        path = DATA / "ptr_md" / str(year) / f"{docid}.md"
        if not path.is_file() or docid not in methods:
            counts["missing"] += 1
            continue
        source = "ocr" if methods[docid] == "ocr" else "markitdown"
        counts["documents"] += 1
        counts[source] += 1
        parsed = parse_document(docid, path.read_text(encoding="utf-8", errors="replace"), meta, source)
        counts["events"] += len(parsed)
        if not parsed:
            counts["failed"] += 1
        rows.extend(parsed)
    return rows, counts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--years", nargs="+", type=int, default=list(range(2014, 2027)))
    args = ap.parse_args()
    manifest_path = OUT / "MANIFEST_sha256.csv"
    manifest_rows = {}
    if manifest_path.exists():
        with manifest_path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                manifest_rows[int(row["year"])] = row
    for year in args.years:
        rows, counts = process_year(year)
        if not rows:
            print(f"{year}: 이벤트 없음; parquet 저장 생략; 집계={dict(counts)}")
            continue
        OUT.mkdir(parents=True, exist_ok=True)
        table = pa.Table.from_pylist(rows).select(FIELDS)
        pq.write_table(table, OUT / f"{year}.parquet", compression="zstd")
        output = OUT / f"{year}.parquet"
        manifest_rows[year] = {"year": year, "rows": len(rows), "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}
        print(f"{year}: rows={len(rows)} docs={counts['documents']} failed={counts['failed']} missing={counts['missing']} ocr={counts['ocr']}")
    if manifest_rows:
        with manifest_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=["year", "rows", "sha256"])
            writer.writeheader()
            writer.writerows(manifest_rows[year] for year in sorted(manifest_rows))


if __name__ == "__main__":
    main()
