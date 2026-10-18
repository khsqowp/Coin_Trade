"""MACD long/short(선물) 50종목 전체 유니버스 테스트 — Round 1에서 통과율(5/10) 가장 좋았던
전략만 골라 유니버스를 넓혀본다. 개별 종목이 아니라 포트폴리오(동일비중) 관점 연환산도 같이 본다.
"""
from __future__ import annotations

import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import pandas as pd

from app.futures_data import fetch_perp_ohlcv
from app.futures_long_short_probe import (
    MIN_USABLE_BARS, MIN_PROFIT_FACTOR, MAX_DRAWDOWN_PCT, MIN_TRADES, SINCE,
    MacdLongShortStrategy, add_macd_indicators, run_backtest_one,
)

UNIVERSE = [
    "BTC", "ETH", "BNB", "XRP", "SOL", "TRX", "DOGE", "ZEC", "LINK", "XMR",
    "ADA", "XLM", "BCH", "LTC", "HBAR", "AVAX", "SHIB", "SUI", "UNI", "NEAR",
    "TAO", "AAVE", "ONDO", "THETA", "PEPE", "DOT", "ENA", "WLD", "ICP", "ETC",
    "POL", "QNT", "ALGO", "ATOM", "RENDER", "EOS", "JUP", "ARB", "FIL", "VET",
    "CAKE", "TON", "MKR", "LDO", "CRV", "INJ", "OP", "APT", "IMX", "STX",
]


def _fetch_one(base: str) -> pd.DataFrame | None:
    try:
        frame = fetch_perp_ohlcv(f"{base}/USDT:USDT", "1d", SINCE, None)
        if not frame.empty:
            print(f"  {base:6}: {len(frame):5d}봉")
        return frame
    except Exception as exc:  # noqa: BLE001
        print(f"  {base:6}: 수집실패 ({exc})")
        return None


def run() -> None:
    print(f"[1/2] {len(UNIVERSE)}개 종목 수집(바이낸스 무기한선물, 공개API)...")
    frames = {}
    for base in UNIVERSE:
        frame = _fetch_one(base)
        if frame is not None and not frame.empty:
            frames[base] = frame

    available = [b for b in UNIVERSE if b in frames]
    print(f"[2/2] MACD 롱숏 백테스트 x 종목 {len(available)}개...")
    started = time.monotonic()
    results = []
    max_workers = min(len(available) or 1, os.cpu_count() or 4, 8)
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(run_backtest_one, b, frames[b], MacdLongShortStrategy, add_macd_indicators, "MACD"): b
            for b in available
        }
        for future in as_completed(futures):
            b = futures[future]
            try:
                r = future.result()
            except Exception as exc:  # noqa: BLE001
                print(f"[오류] {b}: {exc}")
                continue
            if r:
                results.append(r)
    print(f"총 소요 {time.monotonic()-started:.0f}초\n")

    results.sort(key=lambda r: r.annualized_return_pct, reverse=True)
    print(f"{'종목':<8}{'수익률':>9}{'연환산':>9}{'PF':>7}{'MDD':>7}{'거래':>6}{'B&H':>9}{'게이트':>6}")
    for r in results:
        print(f"{r.symbol:<8}{r.return_pct:>8.1f}%{r.annualized_return_pct:>8.1f}%{r.profit_factor:>7.2f}"
              f"{r.max_drawdown_pct:>6.1f}%{r.trades:>6}{r.buy_hold_pct:>8.1f}%{'  P' if r.passes_gate else '  F':>6}")

    passed = [r for r in results if r.passes_gate]
    # buy&hold 대비 실제 엣지 있는 것만(전략이 자산 자체 하락보다 못한 경우 제외)
    real_edge = [r for r in passed if r.return_pct >= r.buy_hold_pct * 0.5 or r.buy_hold_pct < 0 and r.return_pct > 0]

    print(f"\n게이트 통과: {len(passed)}/{len(results)}건, 그중 B&H 대비 실질엣지 있는 것: {len(real_edge)}건")
    if real_edge:
        port_ann = sum(r.annualized_return_pct for r in real_edge) / len(real_edge)
        print(f"동일비중 포트폴리오 평균 연환산(실질엣지 종목만, {len(real_edge)}개): {port_ann:.2f}%")
    if passed:
        port_ann_all = sum(r.annualized_return_pct for r in passed) / len(passed)
        print(f"동일비중 포트폴리오 평균 연환산(게이트 통과 전체, {len(passed)}개): {port_ann_all:.2f}%")


if __name__ == "__main__":
    run()
