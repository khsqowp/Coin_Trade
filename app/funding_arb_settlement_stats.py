"""펀딩비 차익거래(paper_funding_arb.py)의 '스타일'을 정량적으로 보여주기 위한 통계 스크립트.

모멘텀 로테이션과 비교 가능한 형태로 승률/손실률/금액 편차를 계산한다 — 다만 두 전략은
근본적으로 다른 방식으로 돈을 번다:
  - 모멘텀 로테이션: 가격 방향성 베팅(롱/숏), 리밸런스 구간마다 수익/손실이 갈린다.
  - 펀딩비 차익거래: 델타중립(가격 방향성 없음), 8시간마다 실제 정산되는 펀딩비 자체가
    수익의 원천이고, 그 펀딩요율의 부호(+/-)가 이 전략의 '승/패'에 해당한다.

바이낸스 공개 API(fetch_funding_rate_history)로 최근 정산 내역을 가져와 실측 기반으로 계산한다.
"""
from __future__ import annotations

import ccxt
import pandas as pd

SYMBOLS = ["ETH", "XRP", "DOGE"]  # app/paper_funding_arb.py의 SYMBOLS와 동일
LOOKBACK_DAYS = 180
NOTIONAL_PER_SYMBOL_USDT = 30.0  # 현재 실계좌 배분 규모(코드 로그 실측값)와 동일하게 맞춤


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
    return frame


def run() -> None:
    exchange = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "future"}})

    print(f"[1/1] 최근 {LOOKBACK_DAYS}일 실제 펀딩 정산 내역 수집 (바이낸스 공개 API)...")
    all_rates: dict[str, pd.DataFrame] = {}
    for base in SYMBOLS:
        frame = _fetch_history(exchange, base)
        all_rates[base] = frame
        print(f"  {base}: {len(frame)}건 정산 내역")

    print(f"\n[펀딩비 차익거래 — 정산({8}시간) 단위 승/패 통계, 종목당 노셔널 ${NOTIONAL_PER_SYMBOL_USDT:.0f} 기준]")
    combined_amounts = []
    for base, frame in all_rates.items():
        if frame.empty:
            continue
        amounts_usdt = frame["fundingRate"] * NOTIONAL_PER_SYMBOL_USDT  # 롱 포지션 기준: rate>0이면 숏이 롱에게 지급받음(수익)
        wins = amounts_usdt[amounts_usdt > 0]
        losses = amounts_usdt[amounts_usdt < 0]
        win_rate = len(wins) / len(amounts_usdt) * 100
        loss_rate = len(losses) / len(amounts_usdt) * 100
        print(f"\n  {base} ({len(amounts_usdt)}건 정산):")
        print(f"    승률 {win_rate:.1f}% ({len(wins)}건) / 손실률 {loss_rate:.1f}% ({len(losses)}건)")
        print(f"    평균 수취 {amounts_usdt.mean():+.4f} USDT/건, 표준편차(금액 편차) {amounts_usdt.std():.4f} USDT")
        print(f"    최대 수취 {amounts_usdt.max():+.4f} USDT, 최대 지급 {amounts_usdt.min():+.4f} USDT")
        print(f"    {LOOKBACK_DAYS}일 누적(연환산 아님, 실측 그대로): {amounts_usdt.sum():+.2f} USDT")
        combined_amounts.append(amounts_usdt)

    if combined_amounts:
        all_amounts = pd.concat(combined_amounts)
        total_notional = NOTIONAL_PER_SYMBOL_USDT * len(SYMBOLS)
        annualized_yield_pct = all_amounts.sum() / total_notional / LOOKBACK_DAYS * 365 * 100
        print(f"\n  [3종목 합산] 총 {len(all_amounts)}건 정산, 승률 {(all_amounts > 0).mean()*100:.1f}%, "
              f"정산 1건당 표준편차 {all_amounts.std():.4f} USDT")
        print(f"  {LOOKBACK_DAYS}일 누적 {all_amounts.sum():+.2f} USDT → 연환산 수익률(현재 배분 ${total_notional:.0f} 기준) {annualized_yield_pct:.2f}%")
        print(f"  (수수료·베이시스 손익 미포함 — 순수 펀딩비만의 이론적 수익률)")


if __name__ == "__main__":
    run()
