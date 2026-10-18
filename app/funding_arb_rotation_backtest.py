"""펀딩비 차익거래 — 고정종목 방식 vs 동적 로테이션(매일 상위 N개 교체) 비교 백테스트.

잡코인(유동성 얕은 소형 알트) 급락/베이시스 급변 리스크를 피하려고 후보군을 시총 크고
유동성 좋은 대형 코인으로만 제한한다. 델타중립이라 방향 리스크는 헤지되지만, 유동성이
얕으면 스팟-선물 베이시스가 크게 벌어지거나 청산 슬리피지가 커져 헤지가 사실상 깨질 수
있어서다.

방식: 8시간 정산주기 3번(하루)마다 리밸런스 시점을 두고, 그 시점의 최근 펀딩비 기준
연환산 수익률이 진입기준(5%) 이상인 종목 중 상위 N개를 보유한다. 이미 보유중인 종목은
그대로 두고(재조정 없음, paper_funding_arb.py와 동일 원칙), 슬롯이 남으면 새 종목으로
채운다. 종목이 바뀔 때만 왕복수수료를 반영한다.
"""
from __future__ import annotations

import argparse

import pandas as pd

from app.funding_arb_backtest import fetch_funding_history

# 잡코인 배제 — 시총 상위/유동성 좋은 대형 코인만 후보로 둔다.
CANDIDATE_UNIVERSE = [
    "BTC", "ETH", "BNB", "SOL", "XRP", "DOGE", "ADA", "TRX",
    "LINK", "AVAX", "DOT", "LTC", "ATOM", "UNI", "NEAR",
]
BASELINE_SYMBOLS = ["ETH", "XRP", "DOGE"]  # 현재 실거래 중인 고정 3종목

N_SLOTS = 3
MIN_ANNUALIZED_FUNDING_PCT_TO_ENTER = 5.0
ROUND_TRIP_FEE_PCT = (0.1 + 0.05) * 2  # 스팟+선물 편도수수료 합 * 진입/청산
REBALANCE_EVERY_N_PERIODS = 90  # 8시간 정산 90번 = 1달 (교체수수료가 커서 일/주단위는 과도한 회전 유발)


def _perp_symbol(base: str) -> str:
    return f"{base}/USDT:USDT"


def run(args: argparse.Namespace) -> None:
    print(f"[1/2] {len(CANDIDATE_UNIVERSE)}개 후보 펀딩비 이력 수집 중 ({args.since} ~ {args.until or '현재'})...")
    frames: dict[str, pd.DataFrame] = {}
    for base in CANDIDATE_UNIVERSE:
        hist = fetch_funding_history(_perp_symbol(base), args.since, args.until)
        if hist.empty:
            print(f"  {base}: 데이터 없음, 건너뜀")
            continue
        frames[base] = hist
        print(f"  {base}: {len(hist)}건")

    # 모든 종목의 정산 타임스탬프를 하나의 축으로 정렬(바이낸스 USDT-M 무기한은 전부 동일 정산시각)
    all_index = sorted(set().union(*[set(f.index) for f in frames.values()]))
    rate_table = pd.DataFrame(index=all_index)
    for base, f in frames.items():
        rate_table[base] = f["fundingRate"].reindex(all_index)

    print(f"[2/2] 시뮬레이션 ({len(all_index)}개 정산시점)...")

    # --- 방식 A: 고정 3종목(현재 실거래 방식) ---
    baseline_net_pct = 0.0
    for base in BASELINE_SYMBOLS:
        if base not in rate_table.columns:
            continue
        col = rate_table[base].dropna()
        baseline_net_pct += col.sum() * 100 - ROUND_TRIP_FEE_PCT
    baseline_net_pct /= len(BASELINE_SYMBOLS)

    # --- 방식 B: 동적 로테이션(하루 1회 리밸런스, 상위 N개, 문턱 미만이면 관망) ---
    held: dict[str, int] = {}  # base -> 진입한 시점 인덱스(entry_idx), 수수료 계산용
    total_funding_pct = 0.0
    total_fee_pct = 0.0
    n_swaps = 0
    settlements_per_year = 3 * 365

    for i, ts in enumerate(all_index):
        row = rate_table.loc[ts]
        # 보유중인 종목은 이번 정산분 펀딩비를 슬롯 지분(1/N_SLOTS)만큼 수취
        for base in list(held.keys()):
            rate = row.get(base)
            if pd.notna(rate):
                total_funding_pct += float(rate) * 100 / N_SLOTS

        if i % REBALANCE_EVERY_N_PERIODS != 0:
            continue

        # 리밸런스 시점 — 최근값 기준 연환산 펀딩비로 후보 순위
        annualized = (row * 100 * settlements_per_year).dropna().sort_values(ascending=False)
        ranked = [b for b in annualized.index if annualized[b] >= MIN_ANNUALIZED_FUNDING_PCT_TO_ENTER]

        # 보유중인데 더 이상 문턱을 못 넘는 종목은 청산
        for base in list(held.keys()):
            if base not in ranked[:N_SLOTS] and (base not in annualized.index or annualized[base] < 0):
                del held[base]
                total_fee_pct += ROUND_TRIP_FEE_PCT / N_SLOTS
                n_swaps += 1

        # 빈 슬롯을 상위 후보로 채움
        for base in ranked:
            if len(held) >= N_SLOTS:
                break
            if base in held:
                continue
            held[base] = i
            total_fee_pct += ROUND_TRIP_FEE_PCT / N_SLOTS
            n_swaps += 1

    rotation_net_pct = total_funding_pct - total_fee_pct
    years = (all_index[-1] - all_index[0]).days / 365.25

    print("\n" + "=" * 70)
    print(f"기간: {all_index[0].date()} ~ {all_index[-1].date()} ({years:.1f}년)")
    print(f"[방식A: 고정 {'/'.join(BASELINE_SYMBOLS)}] 순수익 {baseline_net_pct:.2f}% "
          f"(연환산 약 {baseline_net_pct/years:.2f}%/년)")
    days_per_rebalance = REBALANCE_EVERY_N_PERIODS / 3
    print(f"[방식B: 동적 로테이션(상위{N_SLOTS}, {days_per_rebalance:.0f}일마다 리밸런스)] 순수익 {rotation_net_pct:.2f}% "
          f"(연환산 약 {rotation_net_pct/years:.2f}%/년, 종목교체 {n_swaps}회, 수수료 총 {total_fee_pct:.2f}%p)")
    print(f"차이: {rotation_net_pct - baseline_net_pct:+.2f}%p")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="펀딩비 차익거래 고정종목 vs 동적로테이션 비교 백테스트")
    parser.add_argument("--since", default="2023-01-01T00:00:00Z")
    parser.add_argument("--until", default=None)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
