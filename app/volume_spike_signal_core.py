"""거래량 폭증 + 가격 비반응 시그널 백테스트(이벤트 스터디) 공통 엔진.

사용자 가설: "최근 1개월(거래일 20일) 평균 대비 거래량이 3배 이상 터졌는데, 당일 종가 기준
등락률은 3% 미만인 종목"을 신호로 보고 그 이후 수익률을 추적한다 — 거래량은 급증했지만
가격이 따라 오르지 않은("조용한 수급") 지점을 조기 매집/눌림목 신호로 볼 수 있는지 검증.

국장/미장/코인 세 러너(kr_volume_spike_backtest.py / us_volume_spike_backtest.py /
crypto_volume_spike_backtest.py)가 이 모듈 하나를 공유한다 — squeeze_backtest_core.py와
동일한 "코어 분리 + 시장별 러너" 패턴.

주의: 신호 자체가 당일 거래량/종가로 확정되므로(장중 실시간으로는 당일 거래량을 끝까지
알 수 없음) 여기서는 "당일 종가 확정 후 신호 판정 → 다음날 시가 매수"를 체결 가정으로 쓴다.
"""
from __future__ import annotations

import pandas as pd

LOOKBACK_DAYS_DEFAULT = 20          # "한 달" ≈ 거래일 20일
VOLUME_MULTIPLE_DEFAULT = 3.0       # 거래량 3배 이상
MAX_PRICE_CHANGE_PCT_DEFAULT = 3.0  # 당일 등락률 3% 미만(음수 포함, 상한만 건다)
HORIZONS_DEFAULT = (5, 10, 20, 60)  # 신호 다음날 시가 매수 후 n거래일 보유


def find_signals(
    frame: pd.DataFrame,
    lookback: int = LOOKBACK_DAYS_DEFAULT,
    volume_multiple: float = VOLUME_MULTIPLE_DEFAULT,
    max_price_change_pct: float = MAX_PRICE_CHANGE_PCT_DEFAULT,
) -> pd.DataFrame:
    """frame에 SIGNAL(bool) 컬럼을 더해 반환한다.

    baseline 거래량은 당일을 뺀 과거 lookback일 평균(shift(1).rolling) — 당일 거래량을
    스스로의 기준에 포함시키는 미래참조를 막는다.
    """
    df = frame.copy()
    df["PCT_CHANGE"] = df["Close"].pct_change() * 100
    df["VOL_BASELINE"] = df["Volume"].shift(1).rolling(lookback).mean()
    df["VOL_RATIO"] = df["Volume"] / df["VOL_BASELINE"]
    df["SIGNAL"] = (df["VOL_RATIO"] >= volume_multiple) & (df["PCT_CHANGE"] < max_price_change_pct)
    df.loc[df["VOL_BASELINE"].isna() | df["PCT_CHANGE"].isna(), "SIGNAL"] = False
    return df


def evaluate(
    frame: pd.DataFrame,
    lookback: int = LOOKBACK_DAYS_DEFAULT,
    volume_multiple: float = VOLUME_MULTIPLE_DEFAULT,
    max_price_change_pct: float = MAX_PRICE_CHANGE_PCT_DEFAULT,
    horizons: tuple[int, ...] = HORIZONS_DEFAULT,
) -> dict | None:
    """신호 발생 후 n거래일 보유 수익률과, 같은 종목의 "아무 날에나 샀을 때" 베이스라인을
    같은 horizon으로 계산해 비교한다. 데이터가 부족하면(최소 길이 미달) None."""
    max_h = max(horizons)
    min_len = lookback + max_h + 2
    if len(frame) < min_len:
        return None

    df = find_signals(frame, lookback, volume_multiple, max_price_change_pct)
    opens = df["Open"].to_numpy()
    closes = df["Close"].to_numpy()
    n = len(df)

    signal_idx = [i for i in range(n - 1 - max_h) if bool(df["SIGNAL"].iloc[i])]

    per_horizon: dict[int, dict] = {}
    for h in horizons:
        signal_rets: list[float] = []
        for i in signal_idx:
            entry_i = i + 1          # 신호 확정 다음날 시가 매수
            exit_i = entry_i + h
            if exit_i >= n:
                continue
            entry_price = opens[entry_i]
            exit_price = closes[exit_i]
            if entry_price > 0:
                signal_rets.append((exit_price / entry_price - 1) * 100)

        baseline_rets: list[float] = []
        for i in range(n - 1 - h):
            entry_i = i + 1
            exit_i = entry_i + h
            if exit_i >= n:
                continue
            entry_price = opens[entry_i]
            exit_price = closes[exit_i]
            if entry_price > 0:
                baseline_rets.append((exit_price / entry_price - 1) * 100)

        per_horizon[h] = {
            "signal_n": len(signal_rets),
            "signal_avg_pct": (sum(signal_rets) / len(signal_rets)) if signal_rets else float("nan"),
            "signal_win_rate_pct": (sum(1 for r in signal_rets if r > 0) / len(signal_rets) * 100) if signal_rets else float("nan"),
            "baseline_avg_pct": (sum(baseline_rets) / len(baseline_rets)) if baseline_rets else float("nan"),
            "baseline_win_rate_pct": (sum(1 for r in baseline_rets if r > 0) / len(baseline_rets) * 100) if baseline_rets else float("nan"),
        }

    return {
        "bars": n,
        "start": df.index[0],
        "end": df.index[-1],
        "signal_count": len(signal_idx),
        "signal_dates": [df.index[i] for i in signal_idx],
        "per_horizon": per_horizon,
    }


def print_report(label: str, results: list[dict], horizons: tuple[int, ...] = HORIZONS_DEFAULT) -> None:
    if not results:
        print(f"[{label}] 유효 결과 없음(전종목 데이터 부족 또는 조회 실패)")
        return

    total_signals = sum(r["stats"]["signal_count"] for r in results)
    print(f"\n[{label} — 거래량 3배↑ + 당일등락 3%미만 시그널, {len(results)}종목, 신호 총 {total_signals}건]")

    with_signal = [r for r in results if r["stats"]["signal_count"] > 0]
    print(f"{'종목':<22} {'기간':>6} {'신호수':>5} | " + " | ".join(f"{h:>3}일수익(신호/기준)" for h in horizons))
    for r in sorted(with_signal, key=lambda r: r["stats"]["signal_count"], reverse=True):
        s = r["stats"]
        row = f"{r['display']:<22} {s['bars']:>5}일 {s['signal_count']:>5} | "
        cells = []
        for h in horizons:
            ph = s["per_horizon"][h]
            if ph["signal_n"] == 0:
                cells.append(f"{'-':>14}")
            else:
                cells.append(f"{ph['signal_avg_pct']:>+5.1f}%/{ph['baseline_avg_pct']:>+5.1f}%")
        print(row + " | ".join(cells))

    print(f"\n[{label} 전체 집계] 데이터 확보 {len(results)}종목 중 신호 발생 {len(with_signal)}종목")
    for h in horizons:
        all_signal_n = sum(r["stats"]["per_horizon"][h]["signal_n"] for r in results)
        if all_signal_n == 0:
            print(f"  {h:>3}거래일 보유: 신호 0건(비교 불가)")
            continue
        weighted_signal_avg = sum(
            r["stats"]["per_horizon"][h]["signal_avg_pct"] * r["stats"]["per_horizon"][h]["signal_n"]
            for r in results if r["stats"]["per_horizon"][h]["signal_n"] > 0
        ) / all_signal_n
        signal_wins = sum(
            round(r["stats"]["per_horizon"][h]["signal_win_rate_pct"] / 100 * r["stats"]["per_horizon"][h]["signal_n"])
            for r in results if r["stats"]["per_horizon"][h]["signal_n"] > 0
        )
        baseline_candidates = [r["stats"]["per_horizon"][h]["baseline_avg_pct"] for r in results if r["stats"]["per_horizon"][h]["signal_n"] > 0]
        baseline_avg_simple = sum(baseline_candidates) / len(baseline_candidates) if baseline_candidates else float("nan")
        edge = weighted_signal_avg - baseline_avg_simple
        print(
            f"  {h:>3}거래일 보유: 신호 {all_signal_n}건 평균수익 {weighted_signal_avg:+.2f}% "
            f"(승률 {signal_wins / all_signal_n * 100:.1f}%) vs 같은종목 무작위진입 평균 {baseline_avg_simple:+.2f}% "
            f"→ 엣지 {edge:+.2f}%p"
        )
