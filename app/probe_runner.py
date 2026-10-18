"""후보 종목 스크리닝 프로브 공통 실행기.

kr_smallcap_probe.py 등 8개 프로브 스크립트가 반복하던 '토큰발급 → 순차 데이터수집 →
프로세스풀 백테스트 → 결과출력' 골격을 하나로 뽑았다. 각 프로브 스크립트는 이제 후보
리스트 + 아래 run_* 함수 호출 한 줄만 있으면 된다.

두 가지 스크리닝 방식을 지원한다:
- full_sweep: 기존 30전략 x 그리드서치 전체(app/stock_swing_search.py, app/us_swing_search.py 재사용)
  — 후보 수가 적을 때(수십개 이하)만 써야 한다. 많으면 optimize() 그리드서치가 폭발해 OOM 위험.
- ema_cross: 실거래봇이 실제로 쓰는 ema_cross 전략만 default 파라미터로 스크리닝 — 훨씬 가볍고
  대규모 후보군(수백개)에도 안전하다. app/kr_top200_probe.py, app/us_top500_probe.py가 이 방식.
"""
from __future__ import annotations

import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Callable, Sequence

import pandas as pd
from backtesting import Backtest

from app.kis_auth import issue_token
from app.more_indicators import add_ema_cross_indicators
from app.strategies import EmaCrossStrategy

MIN_USABLE_BARS = 250
MIN_PROFIT_FACTOR = 1.25
MAX_DRAWDOWN_PCT = 15.0
MIN_TRADES = 5
MAX_FETCH_RETRIES = 12


def _run_generic(
    candidates: Sequence[tuple],
    fetch_one: Callable[[tuple, str], pd.DataFrame | None],
    process_one: Callable[[tuple, pd.DataFrame], list[dict]],
    print_results: Callable[[list[dict]], None],
    max_workers_cap: int = 4,
) -> None:
    print("[1/3] 토큰 발급...")
    token = issue_token()
    print(f"[2/3] {len(candidates)}개 후보 일봉 수집...")
    frames: dict[tuple, pd.DataFrame] = {}
    for cand in candidates:
        frame = fetch_one(cand, token)
        if frame is not None:
            frames[cand] = frame

    available = [c for c in candidates if c in frames]
    print(f"[3/3] 백테스트 x 종목 {len(available)}개...")
    started = time.monotonic()
    rows: list[dict] = []
    max_workers = min(len(available) or 1, os.cpu_count() or 4, max_workers_cap)
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_one, cand, frames[cand]): cand for cand in available}
        for future in as_completed(futures):
            cand = futures[future]
            try:
                rows.extend(future.result())
            except Exception as exc:  # noqa: BLE001
                print(f"[오류] {cand}: {exc}")
    print(f"총 소요 {time.monotonic()-started:.0f}초")
    print_results(rows)


# ---------------------------------------------------------------------------
# full_sweep: 기존 30전략 x 그리드서치 (app/stock_swing_search.py, app/us_swing_search.py 재사용)
# ---------------------------------------------------------------------------

def _fetch_one_kr(cand: tuple[str, str], token: str, since: str) -> pd.DataFrame | None:
    from app.kis_data import fetch_ohlcv_kis
    symbol, name = cand
    try:
        frame = fetch_ohlcv_kis(symbol, token, since, None)
    except Exception as exc:  # noqa: BLE001
        print(f"  {name}({symbol}): 수집 실패 ({exc})")
        return None
    print(f"  {name}({symbol}): {len(frame)}봉")
    return frame


def _fetch_one_us(cand: tuple[str, str, str], token: str, since: str) -> pd.DataFrame | None:
    from app.kis_overseas_data import fetch_ohlcv_kis_overseas
    symbol, excd, name = cand
    try:
        frame = fetch_ohlcv_kis_overseas(symbol, excd, token, since, None)
    except Exception as exc:  # noqa: BLE001
        print(f"  {name}({symbol}): 수집 실패 ({exc})")
        return None
    print(f"  {name}({symbol}): {len(frame)}봉")
    return frame


# ProcessPoolExecutor는 워커 프로세스로 넘길 콜러블을 pickle해야 하므로, 클로저가 아니라
# 반드시 모듈 최상위 함수여야 한다(클로저는 "Can't get local object" 오류로 pickle 실패).
def _process_kr_full_sweep(cand: tuple[str, str], frame: pd.DataFrame) -> list[dict]:
    from app.stock_swing_search import _process_symbol
    symbol, name = cand
    return _process_symbol(symbol, name, frame, 10_000_000, 0.002, 12)


def _process_us_full_sweep(cand: tuple[str, str, str], frame: pd.DataFrame) -> list[dict]:
    from app.us_swing_search import _process_symbol
    symbol, _excd, name = cand
    return _process_symbol(symbol, name, frame, 10_000.0, 0.001, 12)


def run_kr_full_sweep_probe(candidates: list[tuple[str, str]], since: str = "2021-01-01") -> None:
    from app.stock_swing_search import DAILY_STRATEGIES, _print_ranked

    def fetch_one(cand: tuple[str, str], token: str) -> pd.DataFrame | None:
        return _fetch_one_kr(cand, token, since)

    print(f"전략 {len(DAILY_STRATEGIES)}개 x 종목 {len(candidates)}개 스윕 (국내)")
    _run_generic(candidates, fetch_one, _process_kr_full_sweep, _print_ranked)


def run_us_full_sweep_probe(candidates: list[tuple[str, str, str]], since: str = "2021-01-01") -> None:
    from app.us_swing_search import DAILY_STRATEGIES, _print_ranked

    def fetch_one(cand: tuple[str, str, str], token: str) -> pd.DataFrame | None:
        return _fetch_one_us(cand, token, since)

    print(f"전략 {len(DAILY_STRATEGIES)}개 x 종목 {len(candidates)}개 스윕 (미국)")
    _run_generic(candidates, fetch_one, _process_us_full_sweep, _print_ranked)


# ---------------------------------------------------------------------------
# ema_cross: 실거래봇이 쓰는 ema_cross(default 파라미터)만 스크리닝 — 대규모 후보군에 안전
# ---------------------------------------------------------------------------

def _ema_cross_backtest(symbol: str, name: str, frame: pd.DataFrame, cash: float, commission: float) -> dict | None:
    if frame.empty or len(frame) < MIN_USABLE_BARS:
        return None
    enriched = add_ema_cross_indicators(frame).dropna()
    if len(enriched) < MIN_USABLE_BARS:
        return None
    try:
        stats = Backtest(enriched, EmaCrossStrategy, cash=cash, commission=commission, exclusive_orders=True).run()
    except Exception as exc:  # noqa: BLE001
        print(f"  [오류] {name}({symbol}): {exc}")
        return None
    pf = stats.get("Profit Factor", float("nan"))
    mdd = abs(stats.get("Max. Drawdown [%]", float("inf")))
    trades = stats.get("# Trades", 0)
    buy_hold = stats.get("Buy & Hold Return [%]", float("nan"))
    hard_pass = pf == pf and pf >= MIN_PROFIT_FACTOR and mdd <= MAX_DRAWDOWN_PCT and trades >= MIN_TRADES
    return {
        "symbol": symbol, "name": name,
        "return_pct": stats.get("Return [%]", float("nan")),
        "buy_hold_pct": buy_hold, "profit_factor": pf, "max_drawdown_pct": mdd,
        "trades": trades, "gate_pass": hard_pass,
    }


def _print_ema_cross_ranked(rows: list[dict]) -> None:
    passed = [r for r in rows if r["gate_pass"]]
    passed.sort(key=lambda r: r["profit_factor"], reverse=True)
    print(f"\n게이트 통과(PF>={MIN_PROFIT_FACTOR}, MDD<={MAX_DRAWDOWN_PCT}%, 거래>={MIN_TRADES}건): {len(passed)}/{len(rows)}건\n")
    for r in passed:
        flag = "" if r["buy_hold_pct"] > 0 else "  [주의: 매수&보유 자체가 하락]"
        print(f"  {r['name']}({r['symbol']}): 수익률 {r['return_pct']:.1f}% PF {r['profit_factor']:.2f} "
              f"MDD {r['max_drawdown_pct']:.1f}% 거래 {r['trades']}건 B&H {r['buy_hold_pct']:.1f}%{flag}")


def _fetch_one_kr_with_retry(cand: tuple[str, str], token: str, since: str) -> pd.DataFrame | None:
    from app.kis_data import fetch_ohlcv_kis
    symbol, name = cand
    for attempt in range(MAX_FETCH_RETRIES):
        try:
            frame = fetch_ohlcv_kis(symbol, token, since, None)
            print(f"  {name}({symbol}): {len(frame)}봉")
            return frame
        except Exception as exc:  # noqa: BLE001
            if attempt == MAX_FETCH_RETRIES - 1:
                print(f"  {name}({symbol}): 수집 실패 ({exc})")
                return None
            time.sleep(1.0)
    return None


def _fetch_one_us_with_retry(cand: tuple[str, str, str], token: str, since: str) -> pd.DataFrame | None:
    from app.kis_overseas_data import fetch_ohlcv_kis_overseas
    symbol, excd, name = cand
    for attempt in range(MAX_FETCH_RETRIES):
        try:
            frame = fetch_ohlcv_kis_overseas(symbol, excd, token, since, None)
            print(f"  {name}({symbol}): {len(frame)}봉")
            return frame
        except Exception as exc:  # noqa: BLE001
            if attempt == MAX_FETCH_RETRIES - 1:
                print(f"  {name}({symbol}): 수집 실패 ({exc})")
                return None
            time.sleep(1.0)
    return None


def _process_kr_ema_cross(cand: tuple[str, str], frame: pd.DataFrame) -> list[dict]:
    symbol, name = cand
    result = _ema_cross_backtest(symbol, name, frame, 10_000_000, 0.002)
    return [result] if result else []


def _process_us_ema_cross(cand: tuple[str, str, str], frame: pd.DataFrame) -> list[dict]:
    symbol, _excd, name = cand
    result = _ema_cross_backtest(symbol, name, frame, 10_000.0, 0.001)
    return [result] if result else []


def run_kr_ema_cross_probe(candidates: list[tuple[str, str]], since: str = "2021-01-01") -> None:
    def fetch_one(cand: tuple[str, str], token: str) -> pd.DataFrame | None:
        return _fetch_one_kr_with_retry(cand, token, since)

    _run_generic(candidates, fetch_one, _process_kr_ema_cross, _print_ema_cross_ranked, max_workers_cap=8)


def run_us_ema_cross_probe(candidates: list[tuple[str, str, str]], since: str = "2021-01-01") -> None:
    def fetch_one(cand: tuple[str, str, str], token: str) -> pd.DataFrame | None:
        return _fetch_one_us_with_retry(cand, token, since)

    _run_generic(candidates, fetch_one, _process_us_ema_cross, _print_ema_cross_ranked, max_workers_cap=8)
