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

import numpy as np
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
    month_return_cap_pct: float | None = None,
) -> pd.DataFrame:
    """frame에 SIGNAL(bool) 컬럼을 더해 반환한다.

    baseline 거래량은 당일을 뺀 과거 lookback일 평균(shift(1).rolling) — 당일 거래량을
    스스로의 기준에 포함시키는 미래참조를 막는다.

    month_return_cap_pct를 주면 추가조건: 과거 lookback일 누적수익률(오늘종가 vs
    lookback일 전 종가)의 절댓값이 이 값 이내여야 신호로 친다 — "당일 하루만 안 움직였나"가
    아니라 "한 달 내내 옆으로 기었나"까지 요구하는 더 엄격한 버전.
    """
    df = frame.copy()
    df["PCT_CHANGE"] = df["Close"].pct_change() * 100
    df["VOL_BASELINE"] = df["Volume"].shift(1).rolling(lookback).mean()
    df["VOL_RATIO"] = df["Volume"] / df["VOL_BASELINE"]
    df["MONTH_RETURN_PCT"] = df["Close"].pct_change(lookback) * 100
    signal = (df["VOL_RATIO"] >= volume_multiple) & (df["PCT_CHANGE"] < max_price_change_pct)
    invalid = df["VOL_BASELINE"].isna() | df["PCT_CHANGE"].isna()
    if month_return_cap_pct is not None:
        signal = signal & (df["MONTH_RETURN_PCT"].abs() <= month_return_cap_pct)
        invalid = invalid | df["MONTH_RETURN_PCT"].isna()
    df["SIGNAL"] = signal
    df.loc[invalid, "SIGNAL"] = False
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


def simulate_portfolio(
    prepped: dict[str, pd.DataFrame],
    top_k: int,
    hold_days: int,
    stop_pct: float = 0.0,
    fee_pct_one_way: float = 0.04,
    btc_ok: pd.Series | None = None,
    tp_pct: float = 0.0,
) -> dict:
    """SIGNAL/VOL_RATIO 컬럼이 이미 있는(find_signals() 처리된) 심볼별 frame들을 하나의
    계좌로 포트폴리오 백테스트한다. app/crypto_volume_spike_portfolio_backtest.py와
    app/crypto_volume_spike_sweep.py가 이 함수 하나를 공유한다.

    매일: 1) 손절(저가 기준, stop_pct>0일 때만) → 2) 익절(고가 기준, tp_pct>0일 때만) →
          3) 보유기간 만료(종가) 순으로 청산
          4) 빈 슬롯을 전날 신호 확정분 중 VOL_RATIO 큰 순으로, 오늘 시가에 균등배분 진입
    롱 온리, btc_ok를 주면(날짜→bool) 그 날 True일 때만 신규진입 허용(BTC 200일선 레짐필터 등).
    tp_pct>0이면 진입가 대비 그 비율만큼 오르면(고가 기준) hold_days를 기다리지 않고 즉시
    목표가에 청산한다 — "가격 팍 오르면 판다" 익절 룰. hold_days는 이때도 상한선으로 남는다
    (익절이 안 터지면 결국 hold_days째에 종가 청산).
    """
    dates = sorted(set().union(*(df.index for df in prepped.values())))
    fee = fee_pct_one_way / 100

    cash = 1.0
    positions: dict[str, dict] = {}
    eq_curve: list[tuple[pd.Timestamp, float]] = []
    n_trades = 0
    n_stopped = 0
    n_tp = 0
    exposure_days = 0

    for idx, d in enumerate(dates):
        for sym in list(positions):
            pos = positions[sym]
            df = prepped[sym]
            if d not in df.index:
                continue
            row = df.loc[d]
            close = float(row["Close"])
            exit_price = None
            stopped = False
            took_profit = False
            if pos["stop_price"] is not None and float(row["Low"]) <= pos["stop_price"]:
                exit_price = min(pos["stop_price"], close)
                stopped = True
            elif pos["tp_price"] is not None and float(row["High"]) >= pos["tp_price"]:
                exit_price = pos["tp_price"]
                took_profit = True
            elif d >= pos["exit_date"]:
                exit_price = close
            if exit_price is not None:
                cash += pos["qty"] * exit_price * (1 - fee)
                del positions[sym]
                n_trades += 1
                if stopped:
                    n_stopped += 1
                if took_profit:
                    n_tp += 1

        free = top_k - len(positions)
        if free > 0 and idx > 0:
            prev_d = dates[idx - 1]
            regime_ok = btc_ok is None or bool(btc_ok.get(prev_d, False))
            cands = []
            if regime_ok:
                for sym, df in prepped.items():
                    if sym in positions or prev_d not in df.index or d not in df.index:
                        continue
                    prow = df.loc[prev_d]
                    if not bool(prow["SIGNAL"]):
                        continue
                    cands.append((sym, float(prow["VOL_RATIO"])))
            cands.sort(key=lambda x: x[1], reverse=True)

            mtm = cash + sum(
                positions[s]["qty"] * float(prepped[s].loc[d, "Close"])
                for s in positions if d in prepped[s].index
            )
            exit_date = dates[min(idx + hold_days, len(dates) - 1)]
            for sym, _ in cands[:free]:
                price = float(prepped[sym].loc[d, "Open"])
                if price <= 0:
                    continue
                alloc = min(mtm / top_k, cash)
                if alloc <= 0:
                    break
                qty = alloc * (1 - fee) / price
                cash -= alloc
                stop_price = price * (1 - stop_pct) if stop_pct > 0 else None
                tp_price = price * (1 + tp_pct) if tp_pct > 0 else None
                positions[sym] = {
                    "qty": qty, "entry_price": price, "exit_date": exit_date,
                    "stop_price": stop_price, "tp_price": tp_price,
                }

        mtm = cash + sum(
            positions[s]["qty"] * float(prepped[s].loc[d, "Close"])
            for s in positions if d in prepped[s].index
        )
        eq_curve.append((d, mtm))
        if positions:
            exposure_days += 1

    equity = pd.Series([v for _, v in eq_curve], index=[t for t, _ in eq_curve])
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1e-6)
    final = float(equity.iloc[-1])
    cagr = (final ** (1 / years) - 1) * 100 if final > 0 else -100.0
    peak = equity.cummax()
    mdd = float(((peak - equity) / peak).max() * 100)
    daily = equity.pct_change().dropna()
    sharpe = float(daily.mean() / daily.std() * np.sqrt(365)) if daily.std() > 0 else 0.0

    return {
        "cagr": cagr, "mdd": mdd, "sharpe": sharpe, "final": final, "years": years,
        "trades": n_trades, "stopped": n_stopped, "tp_hit": n_tp,
        "exposure_pct": exposure_days / len(dates) * 100 if dates else 0.0,
        "start": equity.index[0], "end": equity.index[-1],
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
