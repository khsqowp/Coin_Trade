"""국내주식 워치리스트 전체(kr_watchlist.STOCK_UNIVERSE)에 "거래량 20일평균 3배↑ + 당일
등락률 3%미만" 시그널을 과거 일봉으로 이벤트 스터디한다. app/volume_spike_signal_core.py 사용.
"""
from __future__ import annotations

from app.kis_auth import issue_token
from app.kis_data import fetch_ohlcv_kis
from app.kr_watchlist import STOCK_UNIVERSE
from app.volume_spike_signal_core import HORIZONS_DEFAULT, evaluate, print_report

SINCE = "2015-01-01"


def run() -> None:
    token = issue_token()
    results = []
    for symbol, name in STOCK_UNIVERSE:
        try:
            frame = fetch_ohlcv_kis(symbol, token, SINCE)
        except Exception as exc:  # noqa: BLE001
            print(f"  {name}({symbol}): 시세조회 실패 — {exc}")
            continue
        stats = evaluate(frame)
        if stats is None:
            print(f"  {name}({symbol}): 데이터 부족 — 건너뜀")
            continue
        results.append({"symbol": symbol, "display": f"{name}({symbol})", "stats": stats})

    print_report("국장", results, HORIZONS_DEFAULT)


if __name__ == "__main__":
    run()
