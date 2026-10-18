"""크립토 추세추종(ema_cross) 스크리닝 — 시가총액 상위/거래량 많은 '인지도 있는' 코인
50개로 제한(잡코인 급락 리스크 회피, KR 워치리스트 확장 때와 같은 원칙). 바이낸스 스팟
공개 API(app/data.py, API 키 불필요)로 일봉 수집, 실거래봇과 동일한 ema_cross(default
파라미터)만 스크리닝한다 — app/probe_runner.py의 ema_cross 방식과 동일 이유(대규모
후보군에서 30전략 그리드서치가 폭발하는 문제 회피).

펀딩비 차익거래(paper_funding_arb.py)와는 별개의 '방향성 스팟 매매' 아이디어 검증용.
"""
from __future__ import annotations

import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import pandas as pd
from backtesting import Backtest

from app.data import fetch_ohlcv
from app.more_indicators import add_ema_cross_indicators
from app.strategies import EmaCrossStrategy

MIN_USABLE_BARS = 250
MIN_PROFIT_FACTOR = 1.25
MAX_DRAWDOWN_PCT = 15.0
MIN_TRADES = 5
SINCE = "2021-01-01T00:00:00Z"

CANDIDATES = [
    "BTC", "ETH", "BNB", "XRP", "SOL", "TRX", "DOGE", "ZEC", "LINK", "XMR",
    "ADA", "XLM", "BCH", "LTC", "HBAR", "AVAX", "SHIB", "SUI", "UNI", "NEAR",
    "TAO", "AAVE", "ONDO", "THETA", "PEPE", "DOT", "ENA", "WLD", "ICP", "ETC",
    "POL", "QNT", "ALGO", "ATOM", "RENDER", "EOS", "JUP", "ARB", "FIL", "VET",
    "CAKE", "TON", "MKR", "LDO", "CRV", "INJ", "OP", "APT", "IMX", "STX",
]


def _fetch_one(base: str) -> pd.DataFrame | None:
    try:
        frame = fetch_ohlcv(f"{base}/USDT", "1d", SINCE, None)
    except Exception as exc:  # noqa: BLE001
        print(f"  {base}: 수집 실패 ({exc})")
        return None
    print(f"  {base}: {len(frame)}봉")
    return frame


def _process_one(base: str, frame: pd.DataFrame) -> dict | None:
    if frame.empty or len(frame) < MIN_USABLE_BARS:
        return None
    enriched = add_ema_cross_indicators(frame).dropna()
    if len(enriched) < MIN_USABLE_BARS:
        return None
    try:
        stats = Backtest(enriched, EmaCrossStrategy, cash=10_000.0, commission=0.001, exclusive_orders=True).run()
    except Exception as exc:  # noqa: BLE001
        print(f"  [오류] {base}: {exc}")
        return None
    pf = stats.get("Profit Factor", float("nan"))
    mdd = abs(stats.get("Max. Drawdown [%]", float("inf")))
    trades = stats.get("# Trades", 0)
    buy_hold = stats.get("Buy & Hold Return [%]", float("nan"))
    hard_pass = pf == pf and pf >= MIN_PROFIT_FACTOR and mdd <= MAX_DRAWDOWN_PCT and trades >= MIN_TRADES
    return {
        "base": base, "return_pct": stats.get("Return [%]", float("nan")),
        "buy_hold_pct": buy_hold, "profit_factor": pf, "max_drawdown_pct": mdd,
        "trades": trades, "gate_pass": hard_pass,
    }


def run() -> None:
    print(f"[1/2] {len(CANDIDATES)}개 후보 일봉 수집(바이낸스 스팟, 공개API)...")
    frames: dict[str, pd.DataFrame] = {}
    for base in CANDIDATES:
        frame = _fetch_one(base)
        if frame is not None:
            frames[base] = frame

    available = [b for b in CANDIDATES if b in frames]
    print(f"[2/2] ema_cross(default) 백테스트 x 종목 {len(available)}개...")
    started = time.monotonic()
    rows: list[dict] = []
    max_workers = min(len(available) or 1, os.cpu_count() or 4, 8)
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_process_one, b, frames[b]): b for b in available}
        for future in as_completed(futures):
            base = futures[future]
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001
                print(f"[오류] {base}: {exc}")
                continue
            if result:
                rows.append(result)
    print(f"총 소요 {time.monotonic()-started:.0f}초")

    passed = [r for r in rows if r["gate_pass"]]
    passed.sort(key=lambda r: r["profit_factor"], reverse=True)
    print(f"\n게이트 통과(PF>={MIN_PROFIT_FACTOR}, MDD<={MAX_DRAWDOWN_PCT}%, 거래>={MIN_TRADES}건): {len(passed)}/{len(rows)}건\n")
    for r in passed:
        flag = "" if r["buy_hold_pct"] > 0 else "  [주의: 매수&보유 자체가 하락]"
        print(f"  {r['base']}: 수익률 {r['return_pct']:.1f}% PF {r['profit_factor']:.2f} "
              f"MDD {r['max_drawdown_pct']:.1f}% 거래 {r['trades']}건 B&H {r['buy_hold_pct']:.1f}%{flag}")


if __name__ == "__main__":
    run()
