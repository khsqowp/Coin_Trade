"""마하세븐 '이평선 눌림목' 전략 실험실 — 파라미터가 아니라 *전략 구조*를 바꿔가며 테스트한다.

바꾸는 축:
  1. stop_mode  : 손절가 산정 방식
       swing  = 최근 pullback_window 봉 스윙 저점
       atr    = 진입가 - 2.5 * ATR14
       pct    = 진입가 * (1 - 0.07)   (고정 -7%)
  2. exit_mode  : 익절/청산 방식
       rr15     = 익절 1.5R + 하드손절 + EMA_exit 이탈
       rr25     = 익절 2.5R + 하드손절 + EMA_exit 이탈
       trail_atr= 고정익절 없음, 트레일링 스탑(고점 - 3*ATR)
       trail_ema= 종가 < EMA_fast 일 때만 청산(추세 끝까지), 하드손절은 유지
  3. regime     : 진입 허용 레짐 필터
       none        = 항상
       self_sma200 = 해당 종목 종가 > 자체 SMA200 일 때만
       btc_sma200  = BTC 종가 > BTC SMA200 일 때만 (시장 전체 게이트)
  4. rs_filter  : 상대강도 필터
       off    = 전종목
       rs_top = 그날 90일 수익률이 유니버스 상위 50% 인 종목만

3*4*3*2 = 72 조합. 데이터는 심볼당 한 번만 받아 캐시.

실행: docker run --rm --entrypoint python -v .../trading/app:/app/app \
        ochestration-trading-momentum-rotation -m app.mach7_ma_pullback_lab
"""
from __future__ import annotations

import itertools
import os
import statistics

import pandas as pd
import pandas_ta as ta

from app.data import fetch_ohlcv
from app.mach7_indicators import add_mach7_ma_pullback
from app.momentum_rotation_loop import UNIVERSE

# 구간은 환경변수로 조절: 강세장 슬라이스(LAB_SINCE=2020-01-01 LAB_UNTIL=2021-11-30) 등.
SINCE = os.environ.get("LAB_SINCE", "2020-01-01")
UNTIL = os.environ.get("LAB_UNTIL") or None
LABEL = os.environ.get("LAB_LABEL", f"{SINCE}~{UNTIL or 'now'}")
INITIAL_CAPITAL = 10_000.0
FEE_PCT = 0.1
MIN_BARS = int(os.environ.get("LAB_MIN_BARS", "260"))

# 고정 신호 파라미터(스윕에서 그럭저럭 나온 값)
EMA_FAST, EMA_MID, EMA_SLOW = 10, 50, 200
PULLBACK_WINDOW = 10
EXIT_EMA = 50

STOP_MODES = ["swing", "atr", "pct"]
EXIT_MODES = ["rr15", "rr25", "trail_atr", "trail_ema"]
REGIMES = ["none", "self_sma200", "btc_sma200"]
RS_FILTERS = ["off", "rs_top"]

ATR_STOP_MULT = 2.5
ATR_TRAIL_MULT = 3.0
PCT_STOP = 0.07
RS_LOOKBACK = 90


def _prep(frame: pd.DataFrame) -> pd.DataFrame:
    out = add_mach7_ma_pullback(
        frame, ema_fast=EMA_FAST, ema_mid=EMA_MID, ema_slow=EMA_SLOW,
        pullback_window=PULLBACK_WINDOW, exit_ema=EXIT_EMA,
    )
    out["ATR14"] = ta.atr(out["High"], out["Low"], out["Close"], length=14)
    out["SMA200"] = ta.sma(out["Close"], length=200)
    out["RET90"] = out["Close"].pct_change(RS_LOOKBACK)
    return out


def _simulate(df: pd.DataFrame, allow_entry: pd.Series, stop_mode: str, exit_mode: str) -> dict | None:
    df = df.dropna(subset=["ENTRY_SIGNAL", "EXIT_SIGNAL", "STOP_PRICE", "ATR14"])
    if len(df) < MIN_BARS:
        return None
    allow = allow_entry.reindex(df.index).fillna(False).astype(bool)

    cash, qty = INITIAL_CAPITAL, 0.0
    entry_price = stop_price = tp_price = trail_high = None
    trades = wins = 0
    cooldown = 0
    eq_idx, eq_val = [], []

    closes = df["Close"].to_numpy(dtype=float)
    lows = df["Low"].to_numpy(dtype=float)
    highs = df["High"].to_numpy(dtype=float)
    atrs = df["ATR14"].to_numpy(dtype=float)
    ent = df["ENTRY_SIGNAL"].to_numpy(dtype=bool)
    ext = df["EXIT_SIGNAL"].to_numpy(dtype=bool)
    swing = df["STOP_PRICE"].to_numpy(dtype=float)
    allow_np = allow.to_numpy(dtype=bool)

    for i in range(len(df)):
        price, low, high, atr = closes[i], lows[i], highs[i], atrs[i]

        if qty > 0:
            if exit_mode == "trail_atr":
                trail_high = max(trail_high, high)
                dyn_stop = max(stop_price, trail_high - ATR_TRAIL_MULT * atr)
            else:
                dyn_stop = stop_price

            stop_hit = low <= dyn_stop
            tp_hit = tp_price is not None and high >= tp_price
            sig_exit = (exit_mode in ("rr15", "rr25") and ext[i]) or \
                       (exit_mode == "trail_ema" and price < df["EMA_FAST"].iat[i])

            if stop_hit or tp_hit or sig_exit:
                exit_p = min(dyn_stop, price) if stop_hit else (tp_price if tp_hit else price)
                cash += qty * exit_p * (1 - FEE_PCT / 100)
                wins += 1 if exit_p > entry_price else 0
                trades += 1
                qty = 0.0
                entry_price = stop_price = tp_price = trail_high = None
                cooldown = 3
        else:
            if cooldown > 0:
                cooldown -= 1
            elif ent[i] and allow_np[i]:
                if stop_mode == "swing":
                    cand = swing[i]
                elif stop_mode == "atr":
                    cand = price - ATR_STOP_MULT * atr
                else:  # pct
                    cand = price * (1 - PCT_STOP)
                if cand < price:
                    entry_price, stop_price = price, cand
                    trail_high = high
                    if exit_mode == "rr15":
                        tp_price = price + (price - cand) * 1.5
                    elif exit_mode == "rr25":
                        tp_price = price + (price - cand) * 2.5
                    else:
                        tp_price = None
                    qty = cash * (1 - FEE_PCT / 100) / price
                    cash = 0.0

        eq_idx.append(df.index[i])
        eq_val.append(cash + qty * price)

    equity = pd.Series(eq_val, index=eq_idx)
    final = float(equity.iloc[-1])
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1e-6)
    ann = ((final / INITIAL_CAPITAL) ** (1 / years) - 1) * 100 if final > 0 else -100.0
    peak = equity.cummax()
    mdd = float(((peak - equity) / peak).max() * 100)

    f0, f1 = float(df["Close"].iloc[0]), float(df["Close"].iloc[-1])
    bh_ann = ((f1 / f0) ** (1 / years) - 1) * 100 if f1 > 0 else -100.0

    return {
        "ann": ann, "alpha": ann - bh_ann, "mdd": mdd, "trades": trades,
        "win_rate": (wins / trades * 100) if trades else float("nan"),
    }


def run() -> None:
    print(f"[{LABEL}] 코인 {len(UNIVERSE)}종목 데이터 로드...")
    raw: dict[str, pd.DataFrame] = {}
    for base in UNIVERSE:
        try:
            fr = fetch_ohlcv(f"{base}/USDT", "1d", SINCE, UNTIL)
        except Exception as exc:  # noqa: BLE001
            print(f"  {base}: 실패 {exc}")
            continue
        if len(fr) >= MIN_BARS:
            raw[base] = fr
    print(f"유효 {len(raw)}종목. 지표 계산...")

    prepped = {b: _prep(fr) for b, fr in raw.items()}
    btc = prepped.get("BTC")
    btc_ok = (btc["Close"] > btc["SMA200"]) if btc is not None else None

    # 상대강도: 날짜별 90일 수익률 중앙값
    ret90 = pd.DataFrame({b: d["RET90"] for b, d in prepped.items()})
    rs_median = ret90.median(axis=1)

    combos = list(itertools.product(STOP_MODES, EXIT_MODES, REGIMES, RS_FILTERS))
    print(f"조합 {len(combos)}개 실행...\n")

    rows = []
    for stop_mode, exit_mode, regime, rs_filter in combos:
        anns, alphas, mdds, trs = [], [], [], []
        for b, d in prepped.items():
            allow = pd.Series(True, index=d.index)
            if regime == "self_sma200":
                allow &= d["Close"] > d["SMA200"]
            elif regime == "btc_sma200" and btc_ok is not None:
                allow &= btc_ok.reindex(d.index).fillna(False)
            if rs_filter == "rs_top":
                allow &= d["RET90"] > rs_median.reindex(d.index)
            res = _simulate(d, allow, stop_mode, exit_mode)
            if res is None:
                continue
            anns.append(res["ann"]); alphas.append(res["alpha"])
            mdds.append(res["mdd"]); trs.append(res["trades"])
        if len(anns) < 10:
            continue
        rows.append({
            "key": f"{stop_mode:<6} {exit_mode:<9} {regime:<12} {rs_filter:<6}",
            "n": len(anns),
            "med_ann": statistics.median(anns), "mean_ann": statistics.mean(anns),
            "med_alpha": statistics.median(alphas), "mean_alpha": statistics.mean(alphas),
            "med_mdd": statistics.median(mdds),
            "pos_pct": sum(1 for a in anns if a > 0) / len(anns) * 100,
            "beat_pct": sum(1 for a in alphas if a > 0) / len(alphas) * 100,
            "avg_tr": statistics.mean(trs),
        })

    rows.sort(key=lambda r: r["med_ann"], reverse=True)
    print("=" * 118)
    print("랭킹 (median 연환산 절대수익 기준)")
    print("=" * 118)
    print(f"{'stop':<6} {'exit':<9} {'regime':<12} {'rs':<6} | {'유효':>4} {'med연환산':>9} {'avg연환산':>9} "
          f"{'med알파':>8} {'medMDD':>7} {'수익%':>6} {'B&H초과%':>8} {'avg매매':>7}")
    for r in rows:
        print(f"{r['key']} | {r['n']:>4} {r['med_ann']:>+8.2f}% {r['mean_ann']:>+8.2f}% "
              f"{r['med_alpha']:>+7.2f}% {r['med_mdd']:>6.1f}% {r['pos_pct']:>5.0f}% "
              f"{r['beat_pct']:>7.0f}% {r['avg_tr']:>7.1f}")

    if rows:
        b = rows[0]
        print(f"\n최고(절대수익): {b['key'].strip()}")
        print(f"  median 연환산 {b['med_ann']:+.2f}%, 수익종목 {b['pos_pct']:.0f}%, medMDD {b['med_mdd']:.1f}%")


if __name__ == "__main__":
    run()
