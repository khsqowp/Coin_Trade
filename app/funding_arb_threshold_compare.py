"""펀딩비 차익거래의 진입기준(MIN_ANNUALIZED_FUNDING_PCT_TO_ENTER)을 5.0%(현재 운영값)와
3.0%(제안값)로 각각 시뮬레이션해서 비교한다 — 실계좌 코드(app/paper_funding_arb.py)를
건드리지 않는 별도 백테스트다. 실제 8시간 정산 내역(공개 API)을 그대로 재생하며, 진입/청산
로직은 run_cycle()의 판단 규칙(진입기준 이상이면 진입, EXIT_IF_ANNUALIZED_FUNDING_PCT_BELOW
미만이면 청산)을 그대로 흉내낸다.
"""
from __future__ import annotations

import ccxt
import pandas as pd

SYMBOLS = ["ETH", "XRP", "DOGE"]
LOOKBACK_DAYS = 180
NOTIONAL_PER_SYMBOL_USDT = 30.0
ROUND_TRIP_FEE_PCT = (0.1 + 0.05) * 2 / 100  # 스팟 0.1% + 선물 0.05%, 진입+청산 왕복
EXIT_IF_BELOW_PCT = 0.0
FUNDING_SETTLEMENTS_PER_YEAR = 3 * 365


def _fetch_history(exchange: ccxt.binance, base: str) -> pd.DataFrame:
    symbol = f"{base}/USDT:USDT"
    since = exchange.milliseconds() - LOOKBACK_DAYS * 24 * 3600 * 1000
    rows: list[dict] = []
    while True:
        batch = exchange.fetch_funding_rate_history(symbol, since=since, limit=1000)
        if not batch:
            break
        rows.extend(batch)
        last_ts = batch[-1]["timestamp"]
        if last_ts <= since or len(batch) < 1000:
            break
        since = last_ts + 1
    frame = pd.DataFrame(rows)
    frame["fundingRate"] = frame["fundingRate"].astype(float)
    frame["annualized_pct"] = frame["fundingRate"] * 100 * FUNDING_SETTLEMENTS_PER_YEAR
    return frame.sort_values("timestamp").reset_index(drop=True)


def _simulate(frame: pd.DataFrame, entry_threshold_pct: float) -> dict:
    """정산 시점을 순서대로 재생하며 진입/보유/청산을 흉내낸다."""
    holding = False
    n_entries = 0
    n_exits = 0
    funding_collected = 0.0
    fee_paid = 0.0
    period_pnls = []  # 진입~청산 한 사이클(포지션 하나) 단위 순손익
    current_cycle_funding = 0.0

    for _, row in frame.iterrows():
        annualized = row["annualized_pct"]
        if not holding:
            if annualized >= entry_threshold_pct:
                holding = True
                n_entries += 1
                fee_paid += NOTIONAL_PER_SYMBOL_USDT * ROUND_TRIP_FEE_PCT / 2  # 진입 절반(스팟+선물 진입)
                current_cycle_funding = 0.0
        else:
            settled = row["fundingRate"] * NOTIONAL_PER_SYMBOL_USDT
            funding_collected += settled
            current_cycle_funding += settled
            if annualized < EXIT_IF_BELOW_PCT:
                holding = False
                n_exits += 1
                fee_paid += NOTIONAL_PER_SYMBOL_USDT * ROUND_TRIP_FEE_PCT / 2  # 청산 절반
                period_pnls.append(current_cycle_funding - NOTIONAL_PER_SYMBOL_USDT * ROUND_TRIP_FEE_PCT)

    net_pnl = funding_collected - fee_paid
    days_covered = (frame["timestamp"].iloc[-1] - frame["timestamp"].iloc[0]) / (1000 * 3600 * 24)
    annualized_yield_pct = net_pnl / NOTIONAL_PER_SYMBOL_USDT / days_covered * 365 * 100 if days_covered > 0 else float("nan")

    return {
        "n_entries": n_entries,
        "n_exits": n_exits,
        "funding_collected": funding_collected,
        "fee_paid": fee_paid,
        "net_pnl": net_pnl,
        "period_pnls": period_pnls,
        "annualized_yield_pct": annualized_yield_pct,
        "days_covered": days_covered,
    }


def run() -> None:
    exchange = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "future"}})
    print(f"[1/1] 최근 {LOOKBACK_DAYS}일 실제 펀딩 정산 내역 수집 (바이낸스 공개 API)...")

    frames = {}
    for base in SYMBOLS:
        frame = _fetch_history(exchange, base)
        frames[base] = frame
        print(f"  {base}: {len(frame)}건")

    for label, threshold in [("현재 운영값 (5.0%)", 5.0), ("제안값 (3.0%)", 3.0)]:
        print(f"\n{'='*60}\n[진입기준 {label}]\n{'='*60}")
        total_net = 0.0
        total_notional = NOTIONAL_PER_SYMBOL_USDT * len(SYMBOLS)
        all_period_pnls = []
        for base, frame in frames.items():
            result = _simulate(frame, threshold)
            total_net += result["net_pnl"]
            all_period_pnls.extend(result["period_pnls"])
            print(f"  {base}: 진입 {result['n_entries']}회, 청산 {result['n_exits']}회, "
                  f"펀딩수취 {result['funding_collected']:+.2f} USDT, 수수료 -{result['fee_paid']:.2f} USDT, "
                  f"순손익 {result['net_pnl']:+.2f} USDT (연환산 {result['annualized_yield_pct']:.2f}%)")

        pnls = pd.Series(all_period_pnls)
        wins = pnls[pnls > 0]
        losses = pnls[pnls < 0]
        days = next(iter(frames.values()))["timestamp"]
        days_covered = (days.iloc[-1] - days.iloc[0]) / (1000 * 3600 * 24)
        overall_annualized = total_net / total_notional / days_covered * 365 * 100 if days_covered > 0 else float("nan")

        print(f"\n  [3종목 합산] {LOOKBACK_DAYS}일 순손익 {total_net:+.2f} USDT "
              f"(배분자본 ${total_notional:.0f} 기준 연환산 {overall_annualized:.2f}%)")
        if len(pnls):
            win_rate = len(wins) / len(pnls) * 100
            print(f"  포지션 사이클(진입~청산) 단위 승률 {win_rate:.1f}% ({len(wins)}/{len(pnls)}건), "
                  f"평균 수익 사이클 ${wins.mean():+.2f}" if len(wins) else "  수익 사이클 없음", end="")
            if len(losses):
                print(f", 평균 손실 사이클 ${losses.mean():+.2f}")
            else:
                print()
            print(f"  사이클 손익 표준편차(금액 편차): ${pnls.std():.2f}")
        else:
            print("  포지션 사이클 완결 건 없음(계속 보유중이거나 진입 자체가 없었음)")


if __name__ == "__main__":
    run()
