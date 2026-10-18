"""도치안 채널 브레이크아웃 롱숏(선물) — 터틀트레이딩 계열, EMA-cross/MACD와는 진입 로직이
다른 추세추종(상단 돌파=롱, 하단 돌파=숏, ATR 트레일링 스탑). 50종목 유니버스 전체 테스트.
"""
from __future__ import annotations

import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import pandas as pd
import pandas_ta as ta
from backtesting import Strategy

from app.futures_data import fetch_perp_ohlcv
from app.futures_long_short_probe import MIN_USABLE_BARS, SINCE, run_backtest_one

UNIVERSE = [
    "BTC", "ETH", "BNB", "XRP", "SOL", "TRX", "DOGE", "ZEC", "LINK", "XMR",
    "ADA", "XLM", "BCH", "LTC", "HBAR", "AVAX", "SUI", "UNI", "NEAR",
    "TAO", "AAVE", "ONDO", "THETA", "DOT", "ENA", "WLD", "ICP", "ETC",
    "POL", "QNT", "ALGO", "ATOM", "RENDER", "JUP", "ARB", "FIL", "VET",
    "CAKE", "TON", "MKR", "LDO", "CRV", "INJ", "OP", "APT", "IMX", "STX",
]


def add_donchian_indicators(frame: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    out = frame.copy()
    out["DC_UPPER"] = out["High"].rolling(period).max()
    out["DC_LOWER"] = out["Low"].rolling(period).min()
    out["ATR"] = ta.atr(out["High"], out["Low"], out["Close"], length=14)
    return out


class DonchianLongShortStrategy(Strategy):
    PERIOD = 20
    STOP_ATR_MULT = 3.0
    RISK_PER_TRADE = 0.02
    MAX_POSITION = 0.95
    WARMUP_BARS = 25

    def init(self):
        pass

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return
        close = self.data.Close[-1]
        upper_prev = self.data.DC_UPPER[-2]
        lower_prev = self.data.DC_LOWER[-2]
        atr = self.data.ATR[-1]
        if pd.isna(atr) or pd.isna(upper_prev) or pd.isna(lower_prev):
            return

        if self.position:
            if self.position.is_long:
                stop = close - self.STOP_ATR_MULT * atr
                for trade in self.trades:
                    if trade.sl is None or stop > trade.sl:
                        trade.sl = stop
            elif self.position.is_short:
                stop = close + self.STOP_ATR_MULT * atr
                for trade in self.trades:
                    if trade.sl is None or stop < trade.sl:
                        trade.sl = stop
            return

        if close > upper_prev:
            stop = close - self.STOP_ATR_MULT * atr
            size = self.RISK_PER_TRADE / (abs(close - stop) / close + 1e-6)
            size = min(size, self.MAX_POSITION)
            if size > 0:
                self.buy(size=size, sl=stop)
        elif close < lower_prev:
            stop = close + self.STOP_ATR_MULT * atr
            size = self.RISK_PER_TRADE / (abs(close - stop) / close + 1e-6)
            size = min(size, self.MAX_POSITION)
            if size > 0:
                self.sell(size=size, sl=stop)


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
    print(f"[1/2] {len(UNIVERSE)}개 종목 수집...")
    frames = {}
    for base in UNIVERSE:
        frame = _fetch_one(base)
        if frame is not None and not frame.empty:
            frames[base] = frame

    available = [b for b in UNIVERSE if b in frames]
    print(f"[2/2] Donchian 롱숏 백테스트 x 종목 {len(available)}개...")
    started = time.monotonic()
    results = []
    max_workers = min(len(available) or 1, os.cpu_count() or 4, 8)
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(run_backtest_one, b, frames[b], DonchianLongShortStrategy, add_donchian_indicators, "Donchian"): b
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
    real_edge = [r for r in passed if r.return_pct >= r.buy_hold_pct * 0.5 or (r.buy_hold_pct < 0 and r.return_pct > 0)]
    print(f"\n게이트 통과: {len(passed)}/{len(results)}건, 실질엣지: {len(real_edge)}건")
    if real_edge:
        print(f"동일비중 포트폴리오 평균 연환산(실질엣지, {len(real_edge)}개): "
              f"{sum(r.annualized_return_pct for r in real_edge)/len(real_edge):.2f}%")


if __name__ == "__main__":
    run()
