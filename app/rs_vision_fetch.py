"""공개 데이터 덤프(data.binance.vision)에서 1h 선물 klines + 펀딩 이력을 직렬 수집해 공용 캐시에 저장.

REST API(fapi.binance.com)를 전혀 쓰지 않으므로 IP 레이트리밋/밴과 무관하다 — 라이브 봇과 충돌하지 않는다.
리서치 에이전트들은 이 캐시만 읽는다: trading/.rs_cache/vision/{klines_1h,funding}/{BASE}USDT.csv.gz
"""
from __future__ import annotations

import csv
import gzip
import io
import sys
import time
import zipfile
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1] / ".rs_cache" / "vision"
BASE_URL = "https://data.binance.vision/data/futures/um"
START = date(2021, 6, 1)
SLEEP = 0.15


def _universe() -> list[str]:
    # 모듈 import는 ccxt를 끌어오므로(네트워크 객체 생성 위험) 소스를 AST로만 읽는다.
    import ast
    src = (Path(__file__).resolve().parent / "momentum_rotation_loop.py").read_text()
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "UNIVERSE" for t in node.targets):
            return list(ast.literal_eval(node.value))
    raise RuntimeError("UNIVERSE 정의를 찾지 못함")


def _months(today: date) -> list[tuple[int, int]]:
    out, y, m = [], START.year, START.month
    while (y, m) <= (today.year, today.month):
        out.append((y, m))
        y, m = (y, m + 1) if m < 12 else (y + 1, 1)
    return out


def _get(url: str) -> bytes | None:
    for attempt in range(3):
        try:
            with urlopen(url, timeout=30) as r:
                return r.read()
        except HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(2 * (attempt + 1))
        except URLError:
            time.sleep(2 * (attempt + 1))
    return None


def _rows(zbytes: bytes) -> list[list[str]]:
    with zipfile.ZipFile(io.BytesIO(zbytes)) as z:
        text = z.read(z.namelist()[0]).decode()
    rows = list(csv.reader(io.StringIO(text)))
    return [r for r in rows if r and r[0].isdigit()]  # 헤더 행 제거


def _fetch_symbol(kind: str, sym: str, today: date) -> list[list[str]]:
    path = "klines" if kind == "klines_1h" else "fundingRate"
    rows: list[list[str]] = []
    for y, m in _months(today):
        tag = f"{y}-{m:02d}"
        fname = f"{sym}-1h-{tag}.zip" if kind == "klines_1h" else f"{sym}-fundingRate-{tag}.zip"
        sub = f"{sym}/1h" if kind == "klines_1h" else sym
        z = _get(f"{BASE_URL}/monthly/{path}/{sub}/{fname}")
        if z is not None:
            rows += _rows(z)
        elif (y, m) == (today.year, today.month):
            # 이번 달은 월간 파일이 아직 없음 — 일간 파일로 어제까지 채운다.
            d = date(y, m, 1)
            while d < today:
                dname = (f"{sym}-1h-{d.isoformat()}.zip" if kind == "klines_1h"
                         else f"{sym}-fundingRate-{d.isoformat()}.zip")
                dz = _get(f"{BASE_URL}/daily/{path}/{sub}/{dname}")
                if dz is not None:
                    rows += _rows(dz)
                d += timedelta(days=1)
                time.sleep(SLEEP)
        time.sleep(SLEEP)
    return rows


def main() -> None:
    today = date.today()
    for kind in ("klines_1h", "funding"):
        (ROOT / kind).mkdir(parents=True, exist_ok=True)
    syms = [f"{b}USDT" for b in _universe()]
    print(f"수집 시작: {len(syms)}종목 × (klines_1h, funding), {START}~{today}", flush=True)
    for i, sym in enumerate(syms, 1):
        for kind in ("klines_1h", "funding"):
            out = ROOT / kind / f"{sym}.csv.gz"
            if out.exists() and out.stat().st_size > 0:
                continue
            rows = _fetch_symbol(kind, sym, today)
            rows.sort(key=lambda r: int(r[0]))
            with gzip.open(out, "wt", newline="") as f:
                csv.writer(f).writerows(rows)
            print(f"[{i}/{len(syms)}] {kind} {sym}: {len(rows)}행", flush=True)
    (ROOT / "READY").write_text(today.isoformat())
    print("완료", flush=True)


if __name__ == "__main__":
    main()
