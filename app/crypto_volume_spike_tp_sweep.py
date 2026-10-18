"""거래량 3배↑ + 당일등락 3%미만 시그널에 "익절(가격 팍 오르면 판다)" 룰을 추가했을 때
효과를 본다 — app/volume_spike_signal_core.simulate_portfolio()의 신규 tp_pct 파라미터 검증.

사용자 가설 재확인 축 2개:
  LOOKBACK : 20거래일("한달") vs 60거래일("세달") — 사용자가 "1달이었나 3달이었나" 불확실해함
  TP_PCT   : 0(익절 없음, 기존 baseline) / 10% / 15% / 20% / 30% 오르면 즉시 청산

VOLUME_MULTIPLE=3배, PRICE_CAP=3%(사용자 원 가설 그대로), HOLD_DAYS=20(§12-3에서 가장 좋았던
보유기간 — 익절이 안 터지면 이 날짜에 종가로 청산하는 상한선 역할), TOP_K=8·손절없음·레짐없음
고정(이미 개별 테스트로 손절/레짐 역효과 확인됨, §12-2).

실행: docker run --rm --entrypoint python coin-trade -u -m app.crypto_volume_spike_tp_sweep
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
HOLD_DAYS = 20
VOL_MULT = 3.0
PRICE_CAP = 3.0
STOP_PCT = 0.0
FEE_PCT_ONE_WAY = 0.04  # momentum_rotation_loop / 기존 §12 표와 동일 조건(공정 비교)

LOOKBACKS = [20, 60]          # "한달" vs "세달"
TP_PCTS = [0.0, 0.10, 0.15, 0.20, 0.30]

MIN_BARS = max(LOOKBACKS) + HOLD_DAYS + 2


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


def _run_one(raw: dict[str, pd.DataFrame], lookback: int, tp_pct: float) -> dict:
    prepped = {
        sym: find_signals(frame, lookback, VOL_MULT, PRICE_CAP)
        for sym, frame in raw.items()
        if len(frame) >= lookback + HOLD_DAYS + 2
    }
    m = simulate_portfolio(prepped, TOP_K, HOLD_DAYS, STOP_PCT, FEE_PCT_ONE_WAY, tp_pct=tp_pct)
    m["signal_count"] = sum(int(df["SIGNAL"].sum()) for df in prepped.values())
    return m


def run() -> None:
    raw = _load_raw()

    combos = [
        (f"lookback{lb}d_tp{tp * 100:g}%", lb, tp)
        for lb, tp in itertools.product(LOOKBACKS, TP_PCTS)
    ]

    print(f"총 {len(combos)}개 조합 (vol{VOL_MULT:g}x/cap{PRICE_CAP:g}%/hold상한{HOLD_DAYS}일, TOP_K={TOP_K}, 손절 없음)\n")

    results = []
    for i, (label, lookback, tp_pct) in enumerate(combos, 1):
        m = _run_one(raw, lookback, tp_pct)
        m["label"] = label
        results.append(m)
        tp_label = "없음" if tp_pct == 0 else f"{tp_pct * 100:.0f}%"
        print(
            f"  [{i:>2}/{len(combos)}] {label:<22} 신호{m['signal_count']:>4}건 매매{m['trades']:>4}건"
            f"(익절{m['tp_hit']:>4}건) CAGR {m['cagr']:>+7.2f}% MDD {m['mdd']:>5.1f}% Sharpe {m['sharpe']:>5.2f}"
        )

    print(f"\n[lookback별 비교, 익절 유무]")
    for lb in LOOKBACKS:
        rows = [r for r in results if r["label"].startswith(f"lookback{lb}d_")]
        for r in sorted(rows, key=lambda r: r["label"]):
            print(f"  {r['label']:<22} CAGR {r['cagr']:>+7.2f}% MDD {r['mdd']:>5.1f}% Sharpe {r['sharpe']:>5.2f} 익절비중 {r['tp_hit'] / max(r['trades'],1) * 100:>5.1f}%")

    print(f"\n[Sharpe 상위 5개]")
    for r in sorted(results, key=lambda r: r["sharpe"], reverse=True)[:5]:
        print(f"  {r['label']:<22} Sharpe {r['sharpe']:>5.2f} CAGR {r['cagr']:>+7.2f}% MDD {r['mdd']:>5.1f}%")

    print(f"\n[비교] 기존 §12-3 baseline(lookback20일/vol3x/cap3%/hold20일, 익절 없음) CAGR +54.2% MDD 56.2% Sharpe 1.09")
    print(f"[비교] momentum_rotation_loop(README 기준, 라이브 페이퍼) CAGR +29.16%, MDD 18.6%")


if __name__ == "__main__":
    run()
