"""바이낸스 USDⓈ-M 선물 UNIVERSE(momentum_rotation_loop.UNIVERSE, 47종목)에 "거래량 20일평균
3배↑ + 당일 등락률 3%미만" 시그널을 과거 일봉으로 이벤트 스터디한다.

코인은 24시간 연속 거래라 "거래일" 개념이 없다 — lookback/horizon 단위는 그대로 "일(day)"
캔들 개수로 쓴다(20일 ≈ 한 달, 국장/미장과 동일 해석).
"""
from __future__ import annotations

import ccxt

from app.futures_data import fetch_perp_ohlcv
from app.momentum_rotation_loop import UNIVERSE
from app.volume_spike_signal_core import HORIZONS_DEFAULT, evaluate, print_report

SINCE = "2019-01-01"


def run() -> None:
    exchange = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "future"}})
    results = []
    for base in UNIVERSE:
        symbol = f"{base}/USDT:USDT"
        try:
            frame = fetch_perp_ohlcv(symbol, "1d", SINCE, exchange=exchange)
        except Exception as exc:  # noqa: BLE001
            print(f"  {base}: 시세조회 실패 — {exc}")
            continue
        stats = evaluate(frame)
        if stats is None:
            print(f"  {base}: 데이터 부족 — 건너뜀")
            continue
        results.append({"symbol": base, "display": base, "stats": stats})

    print_report("코인", results, HORIZONS_DEFAULT)


if __name__ == "__main__":
    run()
