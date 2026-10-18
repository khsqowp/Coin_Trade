"""마켓 뉴트럴 펀딩비 차익거래(cash-and-carry) 백테스트 — 방향을 전혀 예측하지 않고 현물 롱 +
선물 숏을 동시에 잡아 델타 뉴트럴 포지션을 유지하면서, 8시간마다 정산되는 펀딩비를 계속
받아가는 구조를 검증한다. Ethena(USDE)가 실제로 하는 것과 같은 메커니즘.

단순화(정직하게 명시): 스팟-선물 가격 차이(베이시스)는 무시하고 펀딩비 수취만 계산한다.
실제로는 진입/청산 시점의 베이시스, 주기적 재조정 비용, 레버리지 사용 시 청산 리스크가
추가로 있다 — 여기 수치는 "펀딩비만 놓고 봤을 때"의 근사치다.
"""
from __future__ import annotations

import argparse

import ccxt
import pandas as pd


def fetch_funding_history(symbol: str, since_iso: str, until_iso: str | None = None) -> pd.DataFrame:
    exchange = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "future"}})
    since = exchange.parse8601(since_iso)
    until = exchange.parse8601(until_iso) if until_iso else exchange.milliseconds()
    rows: list[dict] = []
    for _ in range(2000):
        batch = exchange.fetch_funding_rate_history(symbol, since=since, limit=200)
        if not batch:
            break
        rows.extend(batch)
        last_ts = batch[-1]["timestamp"]
        if last_ts >= until or len(batch) < 2:
            break
        since = last_ts + 1

    if not rows:
        return pd.DataFrame(columns=["fundingRate"])
    frame = pd.DataFrame(rows)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
    frame = frame.drop_duplicates(subset="timestamp").sort_values("timestamp").set_index("timestamp")
    return frame[frame.index <= pd.Timestamp(until, unit="ms", tz="UTC")][["fundingRate"]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="펀딩비 차익거래(델타 뉴트럴 cash-and-carry) 백테스트")
    parser.add_argument("--symbols", default="BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT,XRP/USDT:USDT,DOGE/USDT:USDT")
    parser.add_argument("--since", default="2022-01-01T00:00:00Z")
    parser.add_argument("--until", default=None)
    parser.add_argument("--spot-fee-pct", type=float, default=0.1, help="스팟 거래 수수료 (%, 편도)")
    parser.add_argument("--perp-fee-pct", type=float, default=0.05, help="선물 거래 수수료 (%, 편도)")
    return parser.parse_args()


def run(args: argparse.Namespace) -> None:
    print("*** 단순화: 스팟-선물 베이시스 미반영, 펀딩비 수취만 계산. 재조정 비용도 미반영 ***\n")
    round_trip_cost_pct = (args.spot_fee_pct + args.perp_fee_pct) * 2  # 진입 + 청산

    for symbol in [s.strip() for s in args.symbols.split(",")]:
        print(f"[데이터] {symbol} 펀딩비 이력 수집 중...")
        funding = fetch_funding_history(symbol, args.since, args.until)
        if funding.empty:
            print(f"  {symbol}: 데이터 없음, 건너뜀")
            continue

        total_funding_pct = funding["fundingRate"].sum() * 100
        avg_funding_pct = funding["fundingRate"].mean() * 100
        n_periods = len(funding)
        positive_periods = int((funding["fundingRate"] > 0).sum())
        net_pct = total_funding_pct - round_trip_cost_pct
        years = (funding.index[-1] - funding.index[0]).days / 365.25 or float("nan")
        annualized_pct = net_pct / years if years and years == years else float("nan")

        print(f"  [{symbol}] 총 펀딩 수취 {total_funding_pct:.2f}% (평균 {avg_funding_pct:.4f}%/회, "
              f"{n_periods}회 중 {positive_periods}회 양수 = {positive_periods/n_periods*100:.0f}%) "
              f"- 진입/청산 비용 {round_trip_cost_pct:.2f}% = 순수익 {net_pct:.2f}% "
              f"(연환산 약 {annualized_pct:.2f}%/년, 기간 {years:.1f}년)")


if __name__ == "__main__":
    run(parse_args())
