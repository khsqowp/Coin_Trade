"""SEC 공식 13F 구조화 데이터셋 수집 및 parquet 변환기."""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import os
import re
import sys
import time
import zipfile
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests

try:
    from . import sec_common
except ImportError:  # 직접 스크립트 실행
    import sec_common

TRADING_DATA_DIR = Path(os.environ.get("TRADING_DATA_DIR", "/Users/user/CODE/Coin_Trade/trading_data"))
ROOT = TRADING_DATA_DIR / "external/disclosures/13f"
DATASET_PAGE = "https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets"
# 알려진 것으로 추정되는 경로 형식: /files/structureddata/data/13f-data-sets/YYYYqQ_form13f.zip.
# 확인 안 됨(추정): 안내 페이지에서 링크를 검증하기 전에는 이 경로를 조합하거나 다운로드에 사용하지 않는다.
MANIFEST_FIELDS = ["path", "rows", "bytes", "sha256", "source_url", "date_range"]
ACCEPTANCE_RE = re.compile(r"<ACCEPTANCE-DATETIME>\s*(\d{14})\s*</ACCEPTANCE-DATETIME>", re.I)


def extract_acceptance_datetime(header_text: str) -> str:
    """SGML 제출 헤더의 14자리 SEC 접수 시각을 원문 그대로 반환한다."""
    match = ACCEPTANCE_RE.search(header_text)
    if not match:
        raise ValueError("ACCEPTANCE-DATETIME 태그가 없습니다")
    value = match.group(1)
    return value


def extract_bulk_urls(page_html: str, page_url: str = DATASET_PAGE) -> list[str]:
    """안내 페이지에 실제로 게시된 분기별 13F zip 링크만 반환한다."""
    links = re.findall(r"href\s*=\s*['\"]([^'\"]+\.zip(?:\?[^'\"]*)?)['\"]", page_html, re.I)
    return sorted({urljoin(page_url, html.unescape(link)) for link in links if "13f" in link.lower()})


def accession_txt_url(cik: str, accession: str) -> str:
    dashed = accession if "-" in accession else f"{accession[:10]}-{accession[10:12]}-{accession[12:]}"
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{dashed.replace('-', '')}/{dashed}.txt"


def fetch_text(url: str, session: requests.Session, limiter: sec_common.RateLimiter) -> str:
    limiter.wait()
    response = session.get(url, headers={"User-Agent": sec_common.SEC_USER_AGENT}, timeout=30)
    response.raise_for_status()
    return response.text


def fetch_bytes(url: str, session: requests.Session, limiter: sec_common.RateLimiter) -> bytes:
    limiter.wait()
    response = session.get(url, headers={"User-Agent": sec_common.SEC_USER_AGENT}, timeout=90)
    response.raise_for_status()
    return response.content


def _column(frame: pd.DataFrame, *candidates: str) -> str:
    columns = {str(name).strip().upper(): name for name in frame.columns}
    for candidate in candidates:
        if candidate.upper() in columns:
            return columns[candidate.upper()]
    raise ValueError(f"필수 열을 찾을 수 없습니다: {', '.join(candidates)}")


def parse_dataset_zip(payload: bytes) -> tuple[pd.DataFrame, dict[str, bytes]]:
    """공식 zip의 SUBMISSION/COVERPAGE/INFOTABLE TSV를 제출별 보유행으로 합친다."""
    raw_files = {}
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for name in archive.namelist():
            leaf = Path(name).name
            if leaf.upper() in {"SUBMISSION.TSV", "COVERPAGE.TSV", "INFOTABLE.TSV"}:
                raw_files[leaf.upper()] = archive.read(name)
    required = {"SUBMISSION.TSV", "COVERPAGE.TSV", "INFOTABLE.TSV"}
    if not required.issubset(raw_files):
        raise ValueError(f"13F zip 필수 파일 누락: {sorted(required - raw_files.keys())}")
    frames = {name: pd.read_csv(io.BytesIO(data), sep="\t", dtype=str, keep_default_na=False) for name, data in raw_files.items()}
    sub, cover, info = (frames["SUBMISSION.TSV"], frames["COVERPAGE.TSV"], frames["INFOTABLE.TSV"])
    sub_acc, cover_acc, info_acc = _column(sub, "ACCESSION_NUMBER"), _column(cover, "ACCESSION_NUMBER"), _column(info, "ACCESSION_NUMBER")
    period_col = _column(cover, "PERIODOFREPORT", "PERIOD_OF_REPORT")
    cik_col = _column(sub, "CIK")
    metadata = sub[[sub_acc, cik_col]].rename(columns={sub_acc: "accession_number", cik_col: "cik"})
    cover_meta = cover[[cover_acc, period_col]].rename(columns={cover_acc: "accession_number", period_col: "period_of_report"})
    merged = info.rename(columns={info_acc: "accession_number"}).merge(cover_meta, on="accession_number", how="left", validate="many_to_one")
    merged = merged.merge(metadata, on="accession_number", how="left", validate="many_to_one")
    return merged, raw_files


def manifest_row(path: Path, relative_path: str, rows: int, source_url: str, date_range: str) -> dict:
    content = path.read_bytes()
    return {"path": relative_path, "rows": rows, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(),
            "source_url": source_url, "date_range": date_range}


def apply_acceptance_times(frame: pd.DataFrame, accepted: dict[str, str]) -> pd.DataFrame:
    """공시 기준 시각을 별도 열로 붙이고 보고 기간 열은 보존한다."""
    result = frame.copy()
    result["accepted_at"] = result["accession_number"].map(accepted)
    if result["accepted_at"].isna().any():
        raise ValueError("accepted_at 누락 제출이 있어 parquet 저장을 중단합니다")
    return result


def write_manifest(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if path.exists():
        with path.open(newline="", encoding="utf-8") as handle:
            existing = {row["path"]: row for row in csv.DictReader(handle)}
    existing.update({row["path"]: row for row in rows})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(existing[key] for key in sorted(existing))


def _read_acceptance(accessions: pd.DataFrame, session: requests.Session, limiter: sec_common.RateLimiter,
                     raw_dir: Path) -> dict[str, str]:
    result = {}
    accession_col, cik_col = _column(accessions, "accession_number"), _column(accessions, "cik")
    for row in accessions[[accession_col, cik_col]].drop_duplicates().itertuples(index=False, name=None):
        accession, cik = row
        url = accession_txt_url(cik, accession)
        text = fetch_text(url, session, limiter)
        raw_path = raw_dir / f"{accession}.txt"
        raw_path.write_text(text, encoding="utf-8")
        result[accession] = extract_acceptance_datetime(text)
    return result


def process_quarter(url: str, session: requests.Session, limiter: sec_common.RateLimiter) -> int:
    raw_root, parquet_dir = ROOT / "raw", ROOT / "parquet"
    raw_root.mkdir(parents=True, exist_ok=True)
    parquet_dir.mkdir(parents=True, exist_ok=True)
    payload = fetch_bytes(url, session, limiter)
    zip_path = raw_root / url.rsplit("/", 1)[-1].split("?", 1)[0]
    raw_dir = raw_root / zip_path.stem
    raw_dir.mkdir(parents=True, exist_ok=True)
    zip_path.write_bytes(payload)
    frame, raw_files = parse_dataset_zip(payload)
    manifest = [manifest_row(zip_path, f"raw/{zip_path.name}", len(frame), url, "")]
    for name, data in raw_files.items():
        output = raw_dir / name.lower()
        output.write_bytes(data)
        row_count = max(0, data.count(b"\n") - 1)
        manifest.append(manifest_row(output, f"raw/{zip_path.stem}/{output.name}", row_count, url, ""))
    # 백테스트 체결은 accepted_at 기준으로만 해야 하고 period_of_report는 참고용이다.
    accepted = _read_acceptance(frame[["accession_number", "cik"]], session, limiter, raw_dir)
    for accession in accepted:
        txt_path = raw_dir / f"{accession}.txt"
        source_url = accession_txt_url(str(frame.loc[frame["accession_number"] == accession, "cik"].iloc[0]), accession)
        manifest.append(manifest_row(txt_path, f"raw/{zip_path.stem}/{txt_path.name}", 1, source_url, ""))
    frame = apply_acceptance_times(frame, accepted)
    date_range = f"{frame['period_of_report'].min()}..{frame['period_of_report'].max()}"
    output = parquet_dir / (zip_path.stem + ".parquet")
    frame.to_parquet(output, compression="zstd", index=False)
    manifest.append(manifest_row(output, f"parquet/{output.name}", len(frame), url, date_range))
    write_manifest(manifest, ROOT / "MANIFEST_sha256.csv")
    return len(frame)


def run(session=None, limiter=None) -> int:
    session = session or requests.Session()
    limiter = limiter or sec_common.RateLimiter(1.0)
    page = fetch_text(DATASET_PAGE, session, limiter)
    urls = extract_bulk_urls(page)
    if not urls:
        raise ValueError("안내 페이지에서 실제 분기 zip 링크를 찾지 못했습니다; URL 패턴 확인 안 됨")
    return process_quarter(urls[-1], session, limiter)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", action="store_true", help="안내 페이지에서 확인된 최신 zip 한 분기만 처리")
    parser.parse_args()
    expected = "/Users/user/CODE/Coin_Trade/trading_data"
    if str(TRADING_DATA_DIR) != expected:
        raise ValueError("TRADING_DATA_DIR은 저장소 내부 trading_data 경로여야 합니다")
    try:
        rows = run()
    except requests.HTTPError as exc:
        response = exc.response
        print(f"SEC 요청 실패: HTTP {response.status_code if response is not None else 'unknown'}", file=sys.stderr)
        return 2
    except requests.RequestException as exc:
        print(f"SEC 요청 실패: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    except (ValueError, zipfile.BadZipFile) as exc:
        print(f"수집 중단: {exc}", file=sys.stderr)
        return 2
    print(f"저장 행 수: {rows}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
