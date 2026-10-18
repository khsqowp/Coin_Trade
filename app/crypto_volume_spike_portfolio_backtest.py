"""거래량 3배↑ + 당일등락 3%미만 시그널(app/volume_spike_signal_core.py)을 하나의 계좌로
포트폴리오 레벨 백테스트한다 — 시뮬레이션 엔진 자체는 volume_spike_signal_core.simulate_portfolio()
(app/crypto_volume_spike_sweep.py와 공유).

목적: 이벤트 스터디(crypto_volume_spike_backtest.py, 심볼별 평균 수익률)만으로는 "지금 라이브
로 돌리는 모멘텀 로테이션(연환산 29.16%, MDD 18.6%, README 기준)"과 비교할 CAGR/MDD가 없다.
같은 TOP_K(8)·같은 유니버스(momentum_rotation_loop.UNIVERSE)로 단일 자산곡선을 뽑아 공정 비교.

전략: 매일 신호 발생 종목 중 VOL_RATIO(거래량/20일평균) 큰 순으로 빈 슬롯(최대 TOP_K)을
채우고, 다음날 시가 진입 → 정확히 HOLD_DAYS 거래일 보유 후 종가 청산(또는 STOP_PCT 손절). 롱 온리.

주의(README futures_data.py와 동일): 펀딩비(8시간마다 정산)를 반영하지 않은 순수 가격백테스트다
— 롱 온리로 HOLD_DAYS일씩 걸쳐 들고 있으므로 펀딩비가 수익을 갉아먹을 수 있다. 여기 나온
CAGR은 상한선으로만 참고.
"""
from __future__ import annotations

import os

import ccxt
import pandas as pd
import pandas_ta as ta

from app.futures_data import fetch_perp_ohlcv
from app.momentum_rotation_loop import UNIVERSE
from app.volume_spike_signal_core import (
    LOOKBACK_DAYS_DEFAULT,
    MAX_PRICE_CHANGE_PCT_DEFAULT,
    VOLUME_MULTIPLE_DEFAULT,
    find_signals,
    simulate_portfolio,
)

SINCE = os.environ.get("LAB_SINCE", "2019-01-01")
TOP_K = int(os.environ.get("LAB_TOP_K", "8"))       # momentum_rotation_loop.TOP_K와 동일 — 공정 비교용
HOLD_DAYS = int(os.environ.get("LAB_HOLD_DAYS", "10"))  # 이벤트 스터디상 엣지/매매빈도 균형점
STOP_PCT = float(os.environ.get("LAB_STOP_PCT", "0"))  # 0이면 손절 없음(기존 동작). 0.10 = -10% 손절
REGIME = os.environ.get("LAB_REGIME", "none")  # "none" | "btc_sma200" — BTC 200일선 위에서만 신규진입
_month_cap_env = os.environ.get("LAB_MONTH_RETURN_CAP_PCT", "")
MONTH_RETURN_CAP_PCT = float(_month_cap_env) if _month_cap_env else None  # 예: 3 → 20일 누적수익률 ±3% 이내만 신호
FEE_PCT_ONE_WAY = 0.04  # momentum_rotation_loop.COMMISSION_PCT와 동일(편도)


def run() -> None:
    exchange = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "future"}})
    prepped: dict[str, pd.DataFrame] = {}
    print(f"코인 {len(UNIVERSE)}종목 로드 중...")
    for base in UNIVERSE:
        try:
            frame = fetch_perp_ohlcv(f"{base}/USDT:USDT", "1d", SINCE, exchange=exchange)
        except Exception as exc:  # noqa: BLE001
            print(f"  {base}: 실패 {exc}")
            continue
        if len(frame) < LOOKBACK_DAYS_DEFAULT + HOLD_DAYS + 2:
            continue
        enriched = find_signals(
            frame, LOOKBACK_DAYS_DEFAULT, VOLUME_MULTIPLE_DEFAULT, MAX_PRICE_CHANGE_PCT_DEFAULT,
            month_return_cap_pct=MONTH_RETURN_CAP_PCT,
        )
        prepped[base] = enriched
    print(f"유효 {len(prepped)}종목, TOP_K={TOP_K}, HOLD_DAYS={HOLD_DAYS}, REGIME={REGIME}")

    btc_ok: pd.Series | None = None
    if REGIME == "btc_sma200":
        btc = prepped.get("BTC")
        if btc is None:
            btc = fetch_perp_ohlcv("BTC/USDT:USDT", "1d", SINCE, exchange=exchange)
        sma200 = ta.sma(btc["Close"], length=200)
        btc_ok = (btc["Close"] > sma200).reindex(btc.index).fillna(False)

    m = simulate_portfolio(prepped, TOP_K, HOLD_DAYS, STOP_PCT, FEE_PCT_ONE_WAY, btc_ok)

    stop_label = f"-{STOP_PCT * 100:.0f}% 손절" if STOP_PCT > 0 else "손절 없음"
    regime_label = "BTC 200일선 위에서만 진입" if REGIME == "btc_sma200" else "레짐필터 없음"
    month_label = f"±{MONTH_RETURN_CAP_PCT:.0f}%/20일 이내만" if MONTH_RETURN_CAP_PCT is not None else "월누적 필터 없음"
    print(f"\n[코인 거래량 3배↑ + 당일등락<3% 포트폴리오, TOP_K={TOP_K}, HOLD_DAYS={HOLD_DAYS}거래일, {stop_label}, {regime_label}, {month_label}]")
    print(f"  기간 {m['start'].date()} ~ {m['end'].date()} ({m['years']:.1f}년)")
    print(f"  CAGR {m['cagr']:+.2f}%  MDD {m['mdd']:.1f}%  Sharpe {m['sharpe']:.2f}")
    print(f"  매매 {m['trades']}건(손절 {m['stopped']}건), 노출 {m['exposure_pct']:.1f}%")
    print(f"  최종 자산 {m['final']:.2f}x (시작 1.0x 기준)")
    print(f"\n[비교] momentum_rotation_loop(README 기준, 라이브 페이퍼) 연환산 +29.16%, MDD 18.6%")


if __name__ == "__main__":
    run()
