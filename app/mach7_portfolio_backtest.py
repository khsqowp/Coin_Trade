"""마하세븐 이평선 눌림목 — 포트폴리오 레벨 백테스트.

종목별 독립 백테스트의 산술평균이 아니라, 하나의 계좌로 매일:
  - 보유 포지션의 청산(손절/익절/추세이탈)을 먼저 처리
  - 빈 슬롯이 있으면 그날 진입신호 + 필터 통과 종목을 상대강도 순으로 채움
  - 최대 top_n 종목 균등배분, 나머지는 현금

단일 자산곡선으로 CAGR / MDD / 노출도 / 매매수를 계산하고,
BTC 매수보유 및 유니버스 균등매수보유와 비교한다.

스윕 축(3*3*2*2*2 = 72):
  top_n     : 3 / 5 / 8
  regime    : none / self_sma200 / btc_sma200
  rs_rank   : off / on  (진입 후보를 90일 수익률 상위 절반으로 제한)
  exit_mode : trail_ema / rr2
  stop_mode : swing / pct(-8%)

실행: docker run --rm --entrypoint python -v .../trading/app:/app/app \
        ochestration-trading-momentum-rotation -m app.mach7_portfolio_backtest
구간: 환경변수 LAB_SINCE / LAB_UNTIL / LAB_LABEL 로 조절.
"""
from __future__ import annotations

import itertools
import os
import statistics

import numpy as np
import pandas as pd
import pandas_ta as ta

from app.data import fetch_ohlcv
from app.mach7_indicators import add_mach7_ma_pullback
from app.momentum_rotation_loop import UNIVERSE

SINCE = os.environ.get("LAB_SINCE", "2020-01-01")
UNTIL = os.environ.get("LAB_UNTIL") or None
LABEL = os.environ.get("LAB_LABEL", f"{SINCE}~{UNTIL or 'now'}")
MIN_BARS = int(os.environ.get("LAB_MIN_BARS", "260"))

FEE_PCT = 0.1
EMA_FAST, EMA_MID, EMA_SLOW, EXIT_EMA, PULLBACK_WINDOW = 10, 50, 200, 50, 10
ATR_STOP_MULT = 2.5
PCT_STOP = 0.08
RS_LOOKBACK = 90

TOP_NS = [3, 5, 8]
REGIMES = ["none", "self_sma200", "btc_sma200"]
RS_RANKS = ["off", "on"]
EXIT_MODES = ["trail_ema", "rr2"]
STOP_MODES = ["swing", "pct"]


def _prep(frame: pd.DataFrame) -> pd.DataFrame:
    out = add_mach7_ma_pullback(
        frame, ema_fast=EMA_FAST, ema_mid=EMA_MID, ema_slow=EMA_SLOW,
        pullback_window=PULLBACK_WINDOW, exit_ema=EXIT_EMA,
    )
    out["ATR14"] = ta.atr(out["High"], out["Low"], out["Close"], length=14)
    out["SMA200f"] = ta.sma(out["Close"], length=200)
    out["RET90"] = out["Close"].pct_change(RS_LOOKBACK)
    return out


def _metrics(equity: pd.Series) -> dict:
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1e-6)
    final = float(equity.iloc[-1])
    cagr = (final ** (1 / years) - 1) * 100 if final > 0 else -100.0
    peak = equity.cummax()
    mdd = float(((peak - equity) / peak).max() * 100)
    daily = equity.pct_change().dropna()
    sharpe = float(daily.mean() / daily.std() * np.sqrt(365)) if daily.std() > 0 else 0.0
    return {"cagr": cagr, "mdd": mdd, "sharpe": sharpe, "final": final}


def _run_portfolio(prepped: dict, dates: pd.DatetimeIndex, btc_ok: pd.Series | None,
                   rs_median: pd.Series, top_n: int, regime: str, rs_rank: str,
                   exit_mode: str, stop_mode: str) -> dict:
    cash = 1.0
    positions: dict[str, dict] = {}
    fee = FEE_PCT / 100
    eq_curve = []
    n_trades = 0
    exposure_days = 0

    for d in dates:
        # 1) 청산
        for sym in list(positions):
            df = prepped[sym]
            if d not in df.index:
                continue
            row = df.loc[d]
            pos = positions[sym]
            price, low, high = float(row["Close"]), float(row["Low"]), float(row["High"])
            pos["trail_high"] = max(pos["trail_high"], high)
            stop = pos["stop"]
            exit_p = None
            if low <= stop:
                exit_p = min(stop, price)
            elif exit_mode == "rr2" and pos["tp"] is not None and high >= pos["tp"]:
                exit_p = pos["tp"]
            elif exit_mode == "trail_ema" and price < float(row["EMA_FAST"]):
                exit_p = price
            elif exit_mode == "rr2" and price < float(row["EMA_EXIT"]):
                exit_p = price
            if exit_p is not None:
                cash += pos["qty"] * exit_p * (1 - fee)
                del positions[sym]
                n_trades += 1

        # 2) 진입
        free = top_n - len(positions)
        if free > 0:
            cands = []
            for sym, df in prepped.items():
                if sym in positions or d not in df.index:
                    continue
                row = df.loc[d]
                if not bool(row["ENTRY_SIGNAL"]):
                    continue
                if regime == "self_sma200" and not (row["Close"] > row["SMA200f"]):
                    continue
                if regime == "btc_sma200" and btc_ok is not None and not bool(btc_ok.get(d, False)):
                    continue
                rs = row["RET90"]
                if rs_rank == "on" and not (pd.notna(rs) and rs > rs_median.get(d, np.inf)):
                    continue
                cands.append((sym, rs if pd.notna(rs) else -np.inf, row))
            cands.sort(key=lambda x: x[1], reverse=True)

            # 현재 총자산 기준 균등 목표배분
            mtm = cash + sum(
                positions[s]["qty"] * float(prepped[s].loc[d, "Close"])
                for s in positions if d in prepped[s].index
            )
            for sym, _, row in cands[:free]:
                price = float(row["Close"])
                if stop_mode == "swing":
                    stop = float(row["STOP_PRICE"])
                else:
                    stop = price * (1 - PCT_STOP)
                if stop >= price:
                    continue
                alloc = min(mtm / top_n, cash)
                if alloc <= 0:
                    break
                qty = alloc * (1 - fee) / price
                cash -= alloc
                tp = price + (price - stop) * 2.0 if exit_mode == "rr2" else None
                positions[sym] = {"qty": qty, "entry": price, "stop": stop, "tp": tp, "trail_high": price}

        # 3) 자산곡선
        mtm = cash + sum(
            positions[s]["qty"] * float(prepped[s].loc[d, "Close"])
            for s in positions if d in prepped[s].index
        )
        eq_curve.append((d, mtm))
        if positions:
            exposure_days += 1

    equity = pd.Series([v for _, v in eq_curve], index=[t for t, _ in eq_curve])
    m = _metrics(equity)
    m["trades"] = n_trades
    m["exposure_pct"] = exposure_days / len(dates) * 100
    return m


def run() -> None:
    print(f"[{LABEL}] 코인 {len(UNIVERSE)}종목 로드...")
    prepped: dict[str, pd.DataFrame] = {}
    for base in UNIVERSE:
        try:
            fr = fetch_ohlcv(f"{base}/USDT", "1d", SINCE, UNTIL)
        except Exception as exc:  # noqa: BLE001
            print(f"  {base}: 실패 {exc}")
            continue
        if len(fr) >= MIN_BARS:
            prepped[base] = _prep(fr)
    print(f"유효 {len(prepped)}종목.")

    all_dates = sorted(set().union(*[set(df.index) for df in prepped.values()]))
    dates = pd.DatetimeIndex([d for d in all_dates])
    # SMA200/RET90 워밍업 이후만
    warm = dates[max(210, RS_LOOKBACK + 10):]
    print(f"거래일 {len(warm)}일 ({warm[0].date()} ~ {warm[-1].date()})")

    ret90 = pd.DataFrame({b: d["RET90"] for b, d in prepped.items()})
    rs_median = ret90.median(axis=1)
    btc = prepped.get("BTC")
    btc_ok = (btc["Close"] > btc["SMA200f"]) if btc is not None else None

    # 벤치마크
    btc_bh = _metrics((btc["Close"] / btc["Close"].iloc[0]).reindex(warm).dropna()) if btc is not None else None
    ew = pd.DataFrame({b: d["Close"] / d["Close"].reindex(warm).dropna().iloc[0]
                       for b, d in prepped.items()}).reindex(warm)
    ew_bh = _metrics(ew.mean(axis=1).dropna())

    combos = list(itertools.product(TOP_NS, REGIMES, RS_RANKS, EXIT_MODES, STOP_MODES))
    print(f"조합 {len(combos)}개 실행...\n")
    rows = []
    for i, (top_n, regime, rs_rank, exit_mode, stop_mode) in enumerate(combos, 1):
        m = _run_portfolio(prepped, warm, btc_ok, rs_median, top_n, regime, rs_rank, exit_mode, stop_mode)
        m["key"] = f"n{top_n:<2} {regime:<12} rs:{rs_rank:<3} {exit_mode:<9} {stop_mode:<6}"
        rows.append(m)
        print(f"  [{i}/{len(combos)}] {m['key']} -> CAGR {m['cagr']:+.1f}% MDD {m['mdd']:.0f}% Sharpe {m['sharpe']:.2f}")

    rows.sort(key=lambda r: r["cagr"], reverse=True)
    print("\n" + "=" * 100)
    print(f"[{LABEL}] 포트폴리오 랭킹 (CAGR)")
    if btc_bh:
        print(f"  벤치마크  BTC 매수보유: CAGR {btc_bh['cagr']:+.1f}%  MDD {btc_bh['mdd']:.0f}%  Sharpe {btc_bh['sharpe']:.2f}")
    print(f"  벤치마크  유니버스 균등매수보유: CAGR {ew_bh['cagr']:+.1f}%  MDD {ew_bh['mdd']:.0f}%  Sharpe {ew_bh['sharpe']:.2f}")
    print("=" * 100)
    print(f"{'설정':<44} {'CAGR':>8} {'MDD':>6} {'Sharpe':>7} {'노출%':>6} {'매매':>5}")
    for r in rows:
        print(f"{r['key']:<44} {r['cagr']:>+7.1f}% {r['mdd']:>5.0f}% {r['sharpe']:>7.2f} {r['exposure_pct']:>5.0f}% {r['trades']:>5}")

    b = rows[0]
    print(f"\n최고: {b['key'].strip()}")
    print(f"  CAGR {b['cagr']:+.1f}%, MDD {b['mdd']:.0f}%, Sharpe {b['sharpe']:.2f}, 노출 {b['exposure_pct']:.0f}%, {b['trades']}매매")


if __name__ == "__main__":
    run()
