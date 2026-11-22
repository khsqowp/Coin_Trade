"""House periodic-transaction-report (PTR) fetcher and Markdown converter.

Read-only public source: disclosures-clerk.house.gov (no login). Resumable, 1 request/second.
Per filing: PDF -> Microsoft markitdown -> Markdown. If markitdown yields (almost) no text the
PDF is a scan, so it is rendered with pymupdf and OCR'd with tesseract; those files are
flagged in manifest `method=ocr`.

Outputs under $TRADING_DATA_DIR/external/disclosures/house/ (default ~/CODE/trading_data):
  ptr_pdf/<year>/<docid>.pdf   ptr_md/<year>/<docid>.md   ptr_manifest.csv

Run (inside the venv at ~/CODE/trading_data/cache/disclosures/venv):
  nice -n 10 python fetch_house_ptr.py [--years 2021 2022] [--limit N]
"""
import argparse
import csv
import hashlib
import io
import os
import re
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import pytesseract  # needs the tesseract binary (brew install tesseract)

BASE = Path(os.environ.get("TRADING_DATA_DIR", Path.home() / "CODE/trading_data"))
ROOT = BASE / "external/disclosures/house"
URL = "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{y}/{d}.pdf"
UA = "research-client/1.0"
MIN_TEXT = 200  # fewer extracted characters than this -> treat as scan, run OCR
FIELDS = ["year", "docid", "pdf_sha256", "pdf_bytes", "md_chars", "method", "status"]


def ptr_ids(year):
    """(docid, filing_date, name) of type-P filings from the downloaded index."""
    xml = zipfile.ZipFile(ROOT / f"{year}FD.zip").read(f"{year}FD.xml").decode("utf8", "ignore")
    for blk in re.findall(r"<Member>.*?</Member>", xml, re.S):
        if "<FilingType>P</FilingType>" in blk:
            yield re.search(r"<DocID>(\d+)</DocID>", blk).group(1)


def download(year, docid, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    r = subprocess.run(
        ["curl", "-s", "-m", "90", "-A", UA, "-o", str(tmp), "-w", "%{http_code}", URL.format(y=year, d=docid)],
        capture_output=True, text=True,
    )
    code = r.stdout.strip()
    if code != "200" or tmp.stat().st_size < 500:
        tmp.unlink(missing_ok=True)
        return f"http_{code or 'err'}"
    tmp.rename(dest)
    return "ok"


def pdf_to_md(pdf, converter):
    text = converter.convert(str(pdf)).text_content or ""
    if len(text.strip()) >= MIN_TEXT:
        return text, "markitdown"
    return ocr_pdf(pdf), "ocr"


def ocr_pdf(pdf):
    import pymupdf
    from PIL import Image

    parts = []
    with pymupdf.open(pdf) as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            parts.append(_best_rotation_text(img))
    return "\n\n".join(parts)


def _mean_conf(img):
    data = pytesseract.image_to_data(img, config="--psm 6", output_type=pytesseract.Output.DICT)
    conf = [float(c) for c, t in zip(data["conf"], data["text"]) if t.strip() and float(c) >= 0]
    return sum(conf) / len(conf) if conf else 0.0


def _best_rotation_text(img):
    """Scanned pages are often landscape-rotated: keep the rotation tesseract is most sure about."""
    best, best_conf = img, _mean_conf(img)
    if best_conf < 60:
        for angle in (90, 270, 180):
            rot = img.rotate(angle, expand=True)
            c = _mean_conf(rot)
            if c > best_conf:
                best, best_conf = rot, c
    return pytesseract.image_to_string(best, config="--psm 6")


def load_done():
    f = ROOT / "ptr_manifest.csv"
    if not f.exists():
        return set()
    with open(f) as fh:
        return {(r["year"], r["docid"]) for r in csv.DictReader(fh) if r["status"] == "ok"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", nargs="*", type=int, default=list(range(2015, 2027)))
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    from markitdown import MarkItDown

    conv = MarkItDown()
    done = load_done()
    mf = ROOT / "ptr_manifest.csv"
    new = not mf.exists()
    n = 0
    with open(mf, "a", newline="") as fh:
        w = csv.DictWriter(fh, FIELDS)
        if new:
            w.writeheader()
        for y in args.years:
            for d in ptr_ids(y):
                if (str(y), d) in done:
                    continue
                if args.limit and n >= args.limit:
                    return
                n += 1
                pdf = ROOT / f"ptr_pdf/{y}/{d}.pdf"
                st = "ok" if pdf.exists() else download(y, d, pdf)
                row = dict(year=y, docid=d, pdf_sha256="", pdf_bytes=0, md_chars=0, method="", status=st)
                if st == "ok":
                    row["pdf_bytes"] = pdf.stat().st_size
                    row["pdf_sha256"] = hashlib.sha256(pdf.read_bytes()).hexdigest()
                    try:
                        md, method = pdf_to_md(pdf, conv)
                        out = ROOT / f"ptr_md/{y}/{d}.md"
                        out.parent.mkdir(parents=True, exist_ok=True)
                        out.write_text(md, encoding="utf8")
                        row.update(md_chars=len(md), method=method)
                    except Exception as e:  # keep going; failure is recorded, not hidden
                        row.update(status=f"convert_error:{type(e).__name__}")
                w.writerow(row)
                fh.flush()
                time.sleep(1.0)


if __name__ == "__main__":
    sys.exit(main())
