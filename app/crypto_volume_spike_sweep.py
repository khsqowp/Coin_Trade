"""거래량 폭증 시그널(app/volume_spike_signal_core.py)의 핵심 파라미터 조합 50종 스윕.

mach7_portfolio_backtest.py의 스윕 패턴과 동일하게, 가격데이터는 한 번만 받고(네트워크 I/O가
가장 비싼 부분) 조합마다 신호 재계산 + 포트폴리오 시뮬레이션만 반복한다.

축 3개 x 조합 48 + 추가 2 = 50:
  VOLUME_MULTIPLES   : 2 / 3 / 4 / 5 배
  PRICE_CAPS         : 당일등락 1 / 2 / 3 / 5% 미만
  HOLD_DAYS_GRID     : 5 / 10 / 20 거래일 보유
  (TOP_K=8, STOP_PCT=0, REGIME 없음 고정 — 이 세 값은 이미 개별 테스트로 효과 없음/역효과 확인됨)
+ 보너스 2종: baseline(3배/3%/10일) 기준에서 LOOKBACK만 10일/30일로 바꿔본 것 — "한 달" 정의 자체를
  흔들어보는 축.

실행: docker run --rm --entrypoint python coin-trade -u -m app.crypto_volume_spike_sweep
"""
from __future__ import annotations

import itertools
import os

import ccxt
import pandas as pd

from app.futures_data import fetch_perp_ohlcv
from app.momentum_rotation_loop import UNIVERSE
from app.volume_spike_signal_core import find_signals, simulate_portfolio

SINCE = os.environ.get("LAB_SINCE", "2019-01-01")
TOP_K = 8
STOP_PCT = 0.0
FEE_PCT_ONE_WAY = 0.04
MIN_BARS = 30 + 20 + 2  # 가장 긴 lookback(30)/hold(20) 기준 최소 바 수에 여유

VOLUME_MULTIPLES = [2.0, 3.0, 4.0, 5.0]
PRICE_CAPS = [1.0, 2.0, 3.0, 5.0]
HOLD_DAYS_GRID = [5, 10, 20]

BONUS_LOOKBACKS = [10, 30]  # baseline(volmult=3, cap=3, hold=10)에서 lookback만 교체


def _load_raw() -> dict[str, pd.DataFrame]:
    exchange = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "future"}})
    raw: dict[str, pd.DataFrame] = {}
    print(f"코인 {len(UNIVERSE)}종목 원본 가격데이터 로드 중 (조합당 재사용)...")
    for base in UNIVERSE:
        try:
            frame = fetch_perp_ohlcv(f"{base}/USDT:USDT", "1d", SINCE, exchange=exchange)
        except Exception as exc:  # noqa: BLE001
            print(f"  {base}: 실패 {exc}")
            continue
        if len(frame) >= MIN_BARS:
            raw[base] = frame
    print(f"유효 {len(raw)}종목.\n")
    return raw


def _run_one(raw: dict[str, pd.DataFrame], lookback: int, vol_mult: float, price_cap: float, hold_days: int) -> dict:
    prepped = {
        sym: find_signals(frame, lookback, vol_mult, price_cap)
        for sym, frame in raw.items()
        if len(frame) >= lookback + hold_days + 2
    }
    m = simulate_portfolio(prepped, TOP_K, hold_days, STOP_PCT, FEE_PCT_ONE_WAY)
    signal_count = sum(int(df["SIGNAL"].sum()) for df in prepped.values())
    m["signal_count"] = signal_count
    return m


def run() -> None:
    raw = _load_raw()

    combos: list[tuple[str, int, float, float, int]] = []
    for vol_mult, price_cap, hold_days in itertools.product(VOLUME_MULTIPLES, PRICE_CAPS, HOLD_DAYS_GRID):
        combos.append((f"vol{vol_mult:g}x_cap{price_cap:g}%_hold{hold_days}d", 20, vol_mult, price_cap, hold_days))
    for lb in BONUS_LOOKBACKS:
        combos.append((f"BONUS_lookback{lb}d_vol3x_cap3%_hold10d", lb, 3.0, 3.0, 10))

    print(f"총 {len(combos)}개 조합 실행 (TOP_K={TOP_K}, 손절 없음, 레짐필터 없음 고정)\n")

    results = []
    for i, (label, lookback, vol_mult, price_cap, hold_days) in enumerate(combos, 1):
        m = _run_one(raw, lookback, vol_mult, price_cap, hold_days)
        m["label"] = label
        results.append(m)
        print(f"  [{i:>2}/{len(combos)}] {label:<32} 신호{m['signal_count']:>4}건 CAGR {m['cagr']:>+7.2f}% MDD {m['mdd']:>5.1f}% Sharpe {m['sharpe']:>5.2f}")

    print(f"\n[CAGR 상위 10개]")
    for r in sorted(results, key=lambda r: r["cagr"], reverse=True)[:10]:
        print(f"  {r['label']:<32} CAGR {r['cagr']:>+7.2f}% MDD {r['mdd']:>5.1f}% Sharpe {r['sharpe']:>5.2f} 신호{r['signal_count']:>4}건 매매{r['trades']:>4}건")

    print(f"\n[CAGR/MDD 비율(위험조정 수익) 상위 10개]")
    for r in sorted(results, key=lambda r: r["cagr"] / max(r["mdd"], 1e-6), reverse=True)[:10]:
        ratio = r["cagr"] / max(r["mdd"], 1e-6)
        print(f"  {r['label']:<32} CAGR/MDD {ratio:>5.2f} (CAGR {r['cagr']:>+7.2f}% MDD {r['mdd']:>5.1f}%) Sharpe {r['sharpe']:>5.2f}")

    print(f"\n[Sharpe 상위 10개]")
    for r in sorted(results, key=lambda r: r["sharpe"], reverse=True)[:10]:
        print(f"  {r['label']:<32} Sharpe {r['sharpe']:>5.2f} CAGR {r['cagr']:>+7.2f}% MDD {r['mdd']:>5.1f}%")

    print(f"\n[비교] 기존 baseline(3배/3%/10일) CAGR +40.55% MDD 44.6% Sharpe 1.02")
    print(f"[비교] momentum_rotation_loop(README 기준, 라이브 페이퍼) CAGR +29.16%, MDD 18.6%")


if __name__ == "__main__":
    run()
