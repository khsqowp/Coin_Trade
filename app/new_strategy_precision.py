"""Phase-3 portfolio precision validation for the new strategy catalog.

This runner is intentionally narrow:
- top-15 candidates from docs/신규전략100-1차스크리닝.md only
- original + two indicator-combination variants per candidate
- no capital_fraction, leverage, or cash-ratio fitting
- futures fee fixed at 0.05% one-way
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from app.new_strategy_screening import (
    CACHE_DIR,
    SINCE,
    TIMEFRAME,
    UNIVERSE,
    adx,
    anchored_vwap_rejection,
    ar_residual,
    atr,
    bollinger_trend,
    clv_classifier,
    dual_thrust,
    dynamic_breakout,
    fourier_energy,
    ichimoku,
    keltner_trend,
    larry_vol_breakout,
    load_frames,
    low_frequency_momentum,
    ma_band_breakout,
    ma200_trend,
    rolling_vwap,
    squeeze_momentum,
    zscore,
)

FUTURES_FEE_ONE_WAY_PCT = 0.05
REPORT_PATH = Path("docs/신규전략100-정밀검증.md")
TRAIN_END = pd.Timestamp("2023-12-31 23:59:59", tz="UTC")
TEST_START = pd.Timestamp("2024-01-01 00:00:00", tz="UTC")
BENCHMARK_CAGR = 28.9
BENCHMARK_MDD = 18.6
BENCHMARK_SHARPE = 1.20
BENCHMARK_CALMAR = 1.56


SignalFunc = Callable[[pd.DataFrame], pd.Series]
ScoreFunc = Callable[[pd.DataFrame, pd.Series], pd.Series]


@dataclass(frozen=True)
class Candidate:
    rank: int
    no: int
    name: str
    event_10_edge: float
    event_20_edge: float
    event_10_n: int
    base_signal: SignalFunc
    base_top_k: int = 8
    hold_days: int = 20


@dataclass(frozen=True)
class Variant:
    code: str
    label: str
    hypothesis: str
    signal: SignalFunc
    score: ScoreFunc
    top_k: int
    hold_days: int


def _dir(long: pd.Series, short: pd.Series | None = None) -> pd.Series:
    out = pd.Series(0, index=long.index, dtype=int)
    out[long.fillna(False)] = 1
    if short is not None:
        out[short.fillna(False)] = -1
    return out


def _default_score(frame: pd.DataFrame, direction: pd.Series) -> pd.Series:
    return direction.abs() * frame["Close"].pct_change(20).abs().fillna(0)


def _adx_score(frame: pd.DataFrame, direction: pd.Series) -> pd.Series:
    return direction.abs() * adx(frame, 14).fillna(0)


def _breakout_score(frame: pd.DataFrame, direction: pd.Series) -> pd.Series:
    don_hi = frame["High"].shift(1).rolling(20).max()
    don_lo = frame["Low"].shift(1).rolling(20).min()
    long_dist = (frame["Close"] / don_hi.replace(0, np.nan) - 1).clip(lower=0)
    short_dist = (don_lo.replace(0, np.nan) / frame["Close"] - 1).clip(lower=0)
    return np.where(direction > 0, long_dist, np.where(direction < 0, short_dist, 0.0))


def _vol_score(frame: pd.DataFrame, direction: pd.Series) -> pd.Series:
    vol = frame["Close"].pct_change().rolling(20).std()
    return direction.abs() * vol.rank(pct=True).fillna(0)


def _z_score_abs(frame: pd.DataFrame, direction: pd.Series) -> pd.Series:
    return direction.abs() * zscore(frame["Close"], 60).abs().fillna(0)


def _with_adx(signal_func: SignalFunc, threshold: float) -> SignalFunc:
    def inner(frame: pd.DataFrame) -> pd.Series:
        sig = signal_func(frame)
        return sig.where(adx(frame, 14) >= threshold, 0).astype(int)

    return inner


def _with_donchian_confirm(signal_func: SignalFunc, lookback: int = 20) -> SignalFunc:
    def inner(frame: pd.DataFrame) -> pd.Series:
        sig = signal_func(frame)
        high = frame["High"].shift(1).rolling(lookback).max()
        low = frame["Low"].shift(1).rolling(lookback).min()
        ok_long = frame["Close"] > high
        ok_short = frame["Close"] < low
        return sig.where(((sig > 0) & ok_long) | ((sig < 0) & ok_short), 0).astype(int)

    return inner


def _with_btc_regime(signal_func: SignalFunc, btc_close: pd.Series | None) -> SignalFunc:
    if btc_close is None:
        return signal_func
    btc_ma = btc_close.rolling(200).mean()

    def inner(frame: pd.DataFrame) -> pd.Series:
        sig = signal_func(frame)
        regime = (btc_close > btc_ma).reindex(frame.index).ffill().fillna(False)
        out = sig.copy()
        out[(out > 0) & (~regime)] = 0
        out[(out < 0) & (regime)] = 0
        return out.astype(int)

    return inner


def _keltner_tight(frame: pd.DataFrame) -> pd.Series:
    ema = frame["Close"].ewm(span=20, adjust=False).mean()
    width = 1.5 * atr(frame, 20)
    return _dir(frame["Close"] > ema + width, frame["Close"] < ema - width)


def _bollinger_trend_wide(frame: pd.DataFrame) -> pd.Series:
    ma = frame["Close"].rolling(20).mean()
    sd = frame["Close"].rolling(20).std()
    trend = adx(frame, 14)
    return _dir((frame["Close"] > ma + 2.5 * sd) & (trend > 25), (frame["Close"] < ma - 2.5 * sd) & (trend > 25))


def _dynamic_breakout_fast(frame: pd.DataFrame) -> pd.Series:
    high = frame["High"].shift(1).rolling(20).max()
    low = frame["Low"].shift(1).rolling(20).min()
    return _dir(frame["Close"] > high, frame["Close"] < low)


def _ma_band_adx(frame: pd.DataFrame) -> pd.Series:
    sig = ma_band_breakout(frame)
    return sig.where(adx(frame, 14) >= 25, 0).astype(int)


def _ichimoku_strict(frame: pd.DataFrame) -> pd.Series:
    sig = ichimoku(frame)
    return sig.where((adx(frame, 14) >= 20) & (frame["Close"].pct_change(20).abs() > atr(frame, 20) / frame["Close"]), 0).astype(int)


def _dual_thrust_k07(frame: pd.DataFrame) -> pd.Series:
    hh = frame["High"].shift(1).rolling(4).max()
    hc = frame["Close"].shift(1).rolling(4).max()
    lc = frame["Close"].shift(1).rolling(4).min()
    ll = frame["Low"].shift(1).rolling(4).min()
    rng = pd.concat([hh - lc, hc - ll], axis=1).max(axis=1)
    return _dir(frame["Close"] > frame["Open"] + 0.7 * rng, frame["Close"] < frame["Open"] - 0.7 * rng)


def _squeeze_adx(frame: pd.DataFrame) -> pd.Series:
    sig = squeeze_momentum(frame)
    return sig.where(adx(frame, 14) >= 20, 0).astype(int)


def _lfm_adx(frame: pd.DataFrame) -> pd.Series:
    sig = low_frequency_momentum(frame)
    return sig.where(adx(frame, 14) >= 18, 0).astype(int)


def _fourier_adx(frame: pd.DataFrame) -> pd.Series:
    sig = fourier_energy(frame)
    return sig.where(adx(frame, 14) >= 18, 0).astype(int)


def _avwap_trend(frame: pd.DataFrame) -> pd.Series:
    sig = anchored_vwap_rejection(frame)
    ma = frame["Close"].rolling(100).mean()
    return sig.where(((sig > 0) & (frame["Close"] > ma)) | ((sig < 0) & (frame["Close"] < ma)), 0).astype(int)


def _larry_adx(frame: pd.DataFrame) -> pd.Series:
    sig = larry_vol_breakout(frame)
    return sig.where(adx(frame, 14) >= 20, 0).astype(int)


def _ma200_slope(frame: pd.DataFrame) -> pd.Series:
    ma = frame["Close"].rolling(200).mean()
    slope = ma.pct_change(20)
    return _dir((frame["Close"] > ma) & (slope > 0), (frame["Close"] < ma) & (slope < 0))


def _ar_resid_strong(frame: pd.DataFrame) -> pd.Series:
    sig = ar_residual(frame)
    return sig.where(_z_score_abs(frame, sig) >= 1.5, 0).astype(int)


def _clv_adx(frame: pd.DataFrame) -> pd.Series:
    sig = clv_classifier(frame)
    return sig.where(adx(frame, 14) >= 18, 0).astype(int)


CANDIDATES = [
    Candidate(1, 94, "Keltner Channel Trend Following", 3.35, 5.85, 9508, keltner_trend),
    Candidate(2, 100, "Bollinger Band Riding Trend", 3.07, 5.47, 4918, bollinger_trend),
    Candidate(3, 1, "Dynamic Breakout II", 3.13, 4.93, 4256, dynamic_breakout),
    Candidate(4, 43, "MA Band + N-Day High/Low Breakout", 2.65, 4.14, 6660, ma_band_breakout),
    Candidate(5, 19, "Ichimoku Cloud Crossover", 1.48, 2.21, 55356, ichimoku),
    Candidate(6, 2, "Dual Thrust Intraday", 1.09, 2.17, 15723, dual_thrust),
    Candidate(7, 95, "TTM/LazyBear Squeeze Momentum", 1.35, 1.26, 2923, squeeze_momentum, 6, 10),
    Candidate(8, 96, "Crypto Squeeze Strategy Pine", 1.35, 1.26, 2923, squeeze_momentum, 6, 10),
    Candidate(9, 6, "Low-Frequency Component Momentum", 1.00, 1.38, 60912, low_frequency_momentum),
    Candidate(10, 49, "Fourier Seasonality/Energy Strategy", 0.83, 1.52, 70018, fourier_energy),
    Candidate(11, 105, "Anchored VWAP Touch/Rejection", 0.85, 1.44, 24585, anchored_vwap_rejection, 8, 10),
    Candidate(12, 103, "Larry Williams Volatility Breakout", 0.49, 1.23, 33381, larry_vol_breakout, 8, 10),
    Candidate(13, 8, "10-Month Moving Average Trend Following", 0.51, 0.68, 75676, ma200_trend),
    Candidate(14, 47, "AR Residual Sign Strategy", 0.27, 0.89, 19912, ar_residual, 8, 10),
    Candidate(15, 46, "Close Location Value Classifier", 0.23, 0.93, 12861, clv_classifier, 8, 10),
]


def variants_for(candidate: Candidate, btc_close: pd.Series | None) -> list[Variant]:
    base = candidate.base_signal
    choices: dict[int, list[tuple[str, str, str, SignalFunc, ScoreFunc]]] = {
        94: [
            ("base", "원형", "Keltner 상·하단 이탈이 추세 지속을 선별하는지 본다.", base, _breakout_score),
            ("adx25", "ADX>=25", "채널 돌파 중 추세강도가 확인된 이벤트만 남겨 노이즈를 줄인다.", _with_adx(base, 25), _adx_score),
            ("tight_btc", "1.5ATR+BTC레짐", "더 빠른 채널 진입에 BTC 장기레짐을 결합해 방향 신호 품질을 바꾼다.", _with_btc_regime(_keltner_tight, btc_close), _breakout_score),
        ],
        100: [
            ("base", "원형", "볼린저 밴드 바깥에서 ADX 추세가 붙는 구간의 band-riding을 본다.", base, _adx_score),
            ("wide", "2.5σ", "밴드 폭을 넓혀 더 강한 추세 추종 이벤트만 남긴다.", _bollinger_trend_wide, _adx_score),
            ("donchian", "돈치안확인", "밴드 돌파가 직전 20일 고저 돌파와 겹칠 때만 추세로 인정한다.", _with_donchian_confirm(base), _breakout_score),
        ],
        1: [
            ("base", "원형", "변동성에 따라 breakout lookback을 바꾸는 원형을 검증한다.", base, _breakout_score),
            ("adx25", "ADX>=25", "동적 돌파 신호에 추세강도 필터를 붙여 whipsaw를 줄인다.", _with_adx(base, 25), _adx_score),
            ("fast20", "20일돈치안", "적응형 lookback 대신 20일 돌파로 더 빠른 확장 구간을 잡는다.", _dynamic_breakout_fast, _breakout_score),
        ],
        43: [
            ("base", "원형", "MA band와 N-day high/low 동시 돌파가 단순 추세보다 강한지 본다.", base, _breakout_score),
            ("adx25", "ADX>=25", "MA band 돌파에 추세강도 조건을 추가한다.", _ma_band_adx, _adx_score),
            ("btc_regime", "BTC레짐", "롱은 BTC 장기상승, 숏은 BTC 장기하락에서만 허용해 시장방향 불일치를 줄인다.", _with_btc_regime(base, btc_close), _breakout_score),
        ],
        19: [
            ("base", "원형", "전환선·기준선·구름 위치 조합이 포트폴리오에서도 유효한지 본다.", base, _adx_score),
            ("strict", "ADX+ATR강도", "구름 신호에 추세강도와 20일 가격 이동폭 조건을 추가한다.", _ichimoku_strict, _adx_score),
            ("btc_regime", "BTC레짐", "구름 방향과 BTC 장기레짐이 맞는 이벤트만 남긴다.", _with_btc_regime(base, btc_close), _adx_score),
        ],
        2: [
            ("base", "원형", "Dual Thrust 일봉 변형의 range breakout을 검증한다.", base, _breakout_score),
            ("k07", "K=0.7", "돌파 임계폭을 넓혀 강한 range expansion만 남긴다.", _dual_thrust_k07, _breakout_score),
            ("adx20", "ADX>=20", "range breakout 뒤 추세강도가 있는 이벤트만 거래한다.", _with_adx(base, 20), _adx_score),
        ],
        95: [
            ("base", "원형", "squeeze-off와 모멘텀 방향이 동시에 발생한 압축 해제 이벤트를 본다.", base, _vol_score),
            ("adx20", "ADX>=20", "압축 해제 후 추세강도가 확인된 이벤트만 남긴다.", _squeeze_adx, _adx_score),
            ("donchian", "돈치안확인", "squeeze 해제가 직전 20일 고저 돌파와 겹칠 때만 진입한다.", _with_donchian_confirm(base), _breakout_score),
        ],
        96: [
            ("base", "원형", "95번과 같은 TTM squeeze 계열 신호를 중복 후보로 별도 확인한다.", base, _vol_score),
            ("adx20", "ADX>=20", "중복 후보라도 추세강도 결합이 성과를 바꾸는지 본다.", _squeeze_adx, _adx_score),
            ("donchian", "돈치안확인", "압축 해제 신호에 가격 돌파 확인을 추가한다.", _with_donchian_confirm(base), _breakout_score),
        ],
        6: [
            ("base", "원형", "저주파 이동평균 방향성이 포트폴리오 롱숏에서도 작동하는지 본다.", base, _default_score),
            ("adx18", "ADX>=18", "완만한 저주파 신호 중 추세강도가 있는 구간만 남긴다.", _lfm_adx, _adx_score),
            ("btc_regime", "BTC레짐", "저주파 방향과 BTC 장기레짐을 결합한다.", _with_btc_regime(base, btc_close), _default_score),
        ],
        49: [
            ("base", "원형", "저주파 Fourier energy와 단기 slope가 방향성을 제공하는지 본다.", base, _default_score),
            ("adx18", "ADX>=18", "주파수 신호 중 추세강도가 붙은 이벤트만 남긴다.", _fourier_adx, _adx_score),
            ("btc_regime", "BTC레짐", "Fourier 방향과 BTC 장기레짐을 결합한다.", _with_btc_regime(base, btc_close), _default_score),
        ],
        105: [
            ("base", "원형", "swing anchor VWAP 터치 후 거부가 단기 방향성을 주는지 본다.", base, _z_score_abs),
            ("trend", "100MA방향", "AVWAP 거부 방향이 100일 추세와 같을 때만 거래한다.", _avwap_trend, _z_score_abs),
            ("adx18", "ADX>=18", "AVWAP 반응 중 추세강도 조건을 통과한 이벤트만 남긴다.", _with_adx(base, 18), _adx_score),
        ],
        103: [
            ("base", "원형", "전일 range 기반 Larry Williams breakout을 일봉 포트폴리오로 검증한다.", base, _breakout_score),
            ("adx20", "ADX>=20", "range breakout 뒤 추세강도 조건을 추가한다.", _larry_adx, _adx_score),
            ("donchian", "돈치안확인", "전일 range 돌파가 20일 고저 돌파와 겹치는 경우만 남긴다.", _with_donchian_confirm(base), _breakout_score),
        ],
        8: [
            ("base", "원형", "10개월 이동평균 상하 방향 신호를 롱숏으로 검증한다.", base, _default_score),
            ("slope", "MA기울기", "200일선 위/아래 조건에 장기선 기울기를 추가한다.", _ma200_slope, _default_score),
            ("adx18", "ADX>=18", "장기 추세 신호 중 추세강도가 붙은 구간만 거래한다.", _with_adx(base, 18), _adx_score),
        ],
        47: [
            ("base", "원형", "AR(1) 잔차 z-score 방향 신호를 검증한다.", base, _z_score_abs),
            ("strong", "|z|>=1.5", "잔차 방향 중 강한 이탈만 남긴다.", _ar_resid_strong, _z_score_abs),
            ("adx18", "ADX>=18", "잔차 신호가 추세강도와 결합될 때 성과가 바뀌는지 본다.", _with_adx(base, 18), _adx_score),
        ],
        46: [
            ("base", "원형", "종가 위치가 일중 range의 극단에 닫힌 날의 방향성을 검증한다.", base, _vol_score),
            ("adx18", "ADX>=18", "CLV 극단 신호 중 추세강도가 있는 이벤트만 남긴다.", _clv_adx, _adx_score),
            ("donchian", "돈치안확인", "CLV 극단이 20일 고저 돌파와 겹치는 경우만 거래한다.", _with_donchian_confirm(base), _breakout_score),
        ],
    }
    return [
        Variant(code, label, hypothesis, signal, score, candidate.base_top_k, candidate.hold_days)
        for code, label, hypothesis, signal, score in choices[candidate.no]
    ]


def _prepare(frames: dict[str, pd.DataFrame], variant: Variant) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for sym, frame in frames.items():
        df = frame.copy()
        direction = variant.signal(df).reindex(df.index).fillna(0).astype(int).clip(-1, 1)
        score = pd.Series(variant.score(df, direction), index=df.index).replace([np.inf, -np.inf], np.nan).fillna(0)
        df["DIRECTION"] = direction
        df["SCORE"] = score
        out[sym] = df
    return out


def simulate_market_neutral(prepped: dict[str, pd.DataFrame], top_k: int, hold_days: int, start: pd.Timestamp | None = None, end: pd.Timestamp | None = None) -> dict:
    dates = sorted(set().union(*(df.index for df in prepped.values())))
    if start is not None:
        dates = [d for d in dates if d >= start]
    if end is not None:
        dates = [d for d in dates if d <= end]
    fee = FUTURES_FEE_ONE_WAY_PCT / 100
    cash = 1.0
    positions: dict[str, dict] = {}
    eq_curve: list[tuple[pd.Timestamp, float]] = []
    n_trades = 0
    exposure_days = 0
    per_side = max(1, top_k // 2)

    for idx, d in enumerate(dates):
        for sym in list(positions):
            pos = positions[sym]
            df = prepped[sym]
            if d not in df.index:
                continue
            row = df.loc[d]
            if d >= pos["exit_date"]:
                exit_price = float(row["Close"])
                if exit_price > 0:
                    pnl = pos["notional"] * pos["direction"] * (exit_price / pos["entry_price"] - 1)
                    cash += pos["notional"] + pnl - pos["notional"] * fee
                    n_trades += 1
                del positions[sym]

        if idx > 0:
            prev_d = dates[idx - 1]
            long_free = per_side - sum(1 for p in positions.values() if p["direction"] > 0)
            short_free = per_side - sum(1 for p in positions.values() if p["direction"] < 0)
            cands_long: list[tuple[str, float]] = []
            cands_short: list[tuple[str, float]] = []
            for sym, df in prepped.items():
                if sym in positions or prev_d not in df.index or d not in df.index:
                    continue
                direction = int(df.loc[prev_d, "DIRECTION"])
                score = float(df.loc[prev_d, "SCORE"])
                if direction > 0:
                    cands_long.append((sym, score))
                elif direction < 0:
                    cands_short.append((sym, score))
            cands_long.sort(key=lambda x: x[1], reverse=True)
            cands_short.sort(key=lambda x: x[1], reverse=True)
            selected = [(sym, 1) for sym, _ in cands_long[:max(0, long_free)]]
            selected += [(sym, -1) for sym, _ in cands_short[:max(0, short_free)]]
            if selected:
                gross_slots = per_side * 2
                mtm = mark_to_market(prepped, positions, d, cash)
                notional = mtm / gross_slots
                exit_date = dates[min(idx + hold_days, len(dates) - 1)]
                for sym, direction in selected:
                    price = float(prepped[sym].loc[d, "Open"])
                    if price <= 0 or cash <= 0:
                        continue
                    required_margin = min(notional, cash)
                    cash -= required_margin
                    cash -= required_margin * fee
                    positions[sym] = {
                        "direction": direction,
                        "entry_price": price,
                        "notional": required_margin,
                        "exit_date": exit_date,
                    }

        mtm = mark_to_market(prepped, positions, d, cash)
        if mtm <= 0:
            eq_curve.append((d, 0.0))
            break
        eq_curve.append((d, mtm))
        if positions:
            exposure_days += 1

    equity = pd.Series([v for _, v in eq_curve], index=[t for t, _ in eq_curve])
    return summarize_equity(equity, n_trades, exposure_days)


def mark_to_market(prepped: dict[str, pd.DataFrame], positions: dict[str, dict], d: pd.Timestamp, cash: float) -> float:
    mtm = cash
    for sym, pos in positions.items():
        if d not in prepped[sym].index:
            mtm += pos["notional"]
            continue
        close = float(prepped[sym].loc[d, "Close"])
        pnl = pos["notional"] * pos["direction"] * (close / pos["entry_price"] - 1)
        mtm += pos["notional"] + pnl
    return float(mtm)


def summarize_equity(equity: pd.Series, trades: int, exposure_days: int) -> dict:
    if equity.empty:
        return empty_result()
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1e-6)
    final = float(equity.iloc[-1])
    cagr = (final ** (1 / years) - 1) * 100 if final > 0 else -100.0
    peak = equity.cummax()
    mdd = float(((peak - equity) / peak).max() * 100)
    daily = equity.pct_change().dropna()
    sharpe = float(daily.mean() / daily.std() * np.sqrt(365)) if daily.std() > 0 else 0.0
    yearly_returns: dict[int, float] = {}
    yearly_mdds: dict[int, float] = {}
    for year, chunk in equity.groupby(equity.index.year):
        if len(chunk) < 2:
            continue
        yearly_returns[int(year)] = (float(chunk.iloc[-1] / chunk.iloc[0]) - 1) * 100
        y_peak = chunk.cummax()
        yearly_mdds[int(year)] = float(((y_peak - chunk) / y_peak).max() * 100)
    return {
        "start": equity.index[0],
        "end": equity.index[-1],
        "cagr": cagr,
        "mdd": mdd,
        "sharpe": sharpe,
        "calmar": cagr / mdd if mdd > 0 else 0.0,
        "final": final,
        "trades": trades,
        "exposure_pct": exposure_days / len(equity) * 100,
        "yearly_returns": yearly_returns,
        "yearly_mdds": yearly_mdds,
    }


def empty_result() -> dict:
    return {
        "start": None,
        "end": None,
        "cagr": float("nan"),
        "mdd": float("nan"),
        "sharpe": float("nan"),
        "calmar": float("nan"),
        "final": float("nan"),
        "trades": 0,
        "exposure_pct": 0.0,
        "yearly_returns": {},
        "yearly_mdds": {},
    }


def fmt_pct(v: float, signed: bool = True) -> str:
    if not np.isfinite(v):
        return "-"
    return f"{v:+.2f}%" if signed else f"{v:.1f}%"


def fmt_num(v: float) -> str:
    if not np.isfinite(v):
        return "-"
    return f"{v:.2f}"


def year_line(values: dict[int, float], signed: bool) -> str:
    parts = []
    for year in range(2019, 2027):
        if year in values:
            parts.append(f"{year} {fmt_pct(values[year], signed=signed)}")
        else:
            parts.append(f"{year} -")
    return ", ".join(parts)


def verdict(full: dict, wf: dict, candidate: Candidate, variant: Variant) -> tuple[str, str]:
    if not np.isfinite(full["cagr"]) or full["trades"] < 20:
        return "효과없음", "거래 수가 너무 적거나 유효 결과가 없다."
    yr = full["yearly_returns"]
    weak_2022 = 2022 in yr and yr[2022] < -10
    concentrated = False
    positive_sum = sum(max(v, 0) for v in yr.values())
    if positive_sum > 0:
        concentrated = max(max(v, 0) for v in yr.values()) / positive_sum >= 0.80
    beats_full = full["cagr"] > BENCHMARK_CAGR and full["mdd"] < BENCHMARK_MDD and full["sharpe"] > BENCHMARK_SHARPE
    beats_wf = wf["cagr"] > BENCHMARK_CAGR and wf["mdd"] < BENCHMARK_MDD and wf["sharpe"] > BENCHMARK_SHARPE
    if beats_full and beats_wf and not weak_2022 and not concentrated:
        return "승자", "풀기간과 2024~2026 블라인드 모두 시장중립 1배 벤치마크를 CAGR/MDD/Sharpe 기준으로 상회했고 연도 집중도 조건도 통과했다."
    if full["calmar"] > 0.8 or wf["calmar"] > 0.8 or full["cagr"] > 10 or wf["cagr"] > 10:
        reasons = []
        if not beats_wf:
            reasons.append("워크포워드가 벤치마크를 넘지 못함")
        if not beats_full:
            reasons.append("풀기간 집계가 벤치마크를 넘지 못함")
        if weak_2022:
            reasons.append("2022년 약세장 방어 실패")
        if concentrated:
            reasons.append("수익이 특정 연도에 과도하게 집중")
        return "참고용 후보", ", ".join(reasons) if reasons else "일부 지표는 양호하나 승자 기준에는 부족하다."
    return "효과없음", "수익·낙폭·워크포워드 기준에서 채택 근거가 약하다."


def write_header() -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        "작성 중 — 정밀검증\n\n"
        "# 신규전략100 정밀검증\n\n"
        "## 검증 기준\n\n"
        f"- 실행 데이터: Binance USDT-M 선물 일봉, since=`{SINCE}`, timeframe=`{TIMEFRAME}`. 로컬 캐시: `{CACHE_DIR}`.\n"
        "- 유니버스: `app/momentum_rotation_loop.py`의 45종목과 동일.\n"
        f"- 수수료: `FUTURES_FEE_ONE_WAY_PCT = {FUTURES_FEE_ONE_WAY_PCT}`. 진입과 청산 각각 차감.\n"
        "- 포트폴리오: TOP_K 동시보유, 동일비중, 단일계좌. 롱숏 후보는 롱 슬롯과 숏 슬롯을 같은 수로 둔 달러중립 구조로 실행.\n"
        "- 워크포워드: 2019~2023 구간에서 설정을 확정했다는 가정으로 같은 파라미터를 2024~2026에 재튜닝 없이 적용.\n"
        f"- 비교 벤치마크: 롱숏/시장중립 후보는 모멘텀 로테이션 1배 CAGR {BENCHMARK_CAGR:.1f}% / MDD {BENCHMARK_MDD:.1f}% / Sharpe {BENCHMARK_SHARPE:.2f} / Calmar {BENCHMARK_CALMAR:.2f}. 2배 delever 실거래 결정값은 참고치(CAGR +33%, MDD 29%, Calmar 1.11)로만 본다.\n"
        "- 가드레일: capital_fraction·현금비중·레버리지 미세조정 없음. 후보당 원형+2개 지표결합 변형만 실행.\n\n",
        encoding="utf-8",
    )


def append_candidate(candidate: Candidate, rows: list[tuple[Variant, dict, dict, dict, str, str]]) -> None:
    with REPORT_PATH.open("a", encoding="utf-8") as f:
        f.write(f"## [{candidate.rank}/15] {candidate.no}. {candidate.name}\n\n")
        f.write(f"- 이벤트스터디 재인용: 10일 엣지 {candidate.event_10_edge:+.2f}%p, 20일 엣지 {candidate.event_20_edge:+.2f}%p, 10일 신호수 {candidate.event_10_n}.\n")
        for variant, full, train, wf, label, reason in rows:
            f.write(f"\n### {candidate.no}-{variant.code} {variant.label}\n\n")
            f.write(f"- 가설: {variant.hypothesis}\n")
            f.write(f"- 구현: TOP_K={variant.top_k}, hold_days={variant.hold_days}, 수수료 편도 {FUTURES_FEE_ONE_WAY_PCT:.2f}%, 달러중립 롱/숏 슬롯 각각 {max(1, variant.top_k // 2)}개, score=`{variant.score.__name__}`.\n")
            f.write(f"- 이벤트스터디 결과: 1차 스크리닝 값 재인용. 10일 엣지 {candidate.event_10_edge:+.2f}%p, 20일 엣지 {candidate.event_20_edge:+.2f}%p.\n")
            f.write(
                f"- 포트폴리오: CAGR {fmt_pct(full['cagr'])}, MDD {fmt_pct(full['mdd'], signed=False)}, "
                f"Sharpe {fmt_num(full['sharpe'])}, Calmar {fmt_num(full['calmar'])}, 최종 {fmt_num(full['final'])}x, "
                f"매매 {full['trades']}건, 노출 {fmt_pct(full['exposure_pct'], signed=False)}.\n"
            )
            f.write(f"- 연도별 수익률: {year_line(full['yearly_returns'], signed=True)}.\n")
            f.write(f"- 연도별 최악 MDD: {year_line(full['yearly_mdds'], signed=False)}.\n")
            f.write(
                f"- 워크포워드: 2019~2023 확정 파라미터 동일 적용. "
                f"train CAGR {fmt_pct(train['cagr'])}/MDD {fmt_pct(train['mdd'], signed=False)}/Sharpe {fmt_num(train['sharpe'])}; "
                f"2024~2026 blind CAGR {fmt_pct(wf['cagr'])}/MDD {fmt_pct(wf['mdd'], signed=False)}/Sharpe {fmt_num(wf['sharpe'])}.\n"
            )
            f.write(f"- 판정: {label}. 근거: {reason}\n")
        f.write("\n")


def finalize(all_rows: list[tuple[Candidate, Variant, dict, dict, str, str]]) -> None:
    winners = [(c, v, full, wf, reason) for c, v, full, wf, label, reason in all_rows if label == "승자"]
    refs = [(c, v, full, wf, reason) for c, v, full, wf, label, reason in all_rows if label == "참고용 후보"]
    refs.sort(key=lambda x: (x[3]["calmar"], x[2]["calmar"], x[3]["cagr"]), reverse=True)
    with REPORT_PATH.open("a", encoding="utf-8") as f:
        f.write("## 종합 결론\n\n")
        if winners:
            f.write("워크포워드까지 통과한 승자 있음.\n\n")
            for c, v, full, wf, reason in winners:
                f.write(f"- {c.no}-{v.code} {c.name} / {v.label}: full CAGR {fmt_pct(full['cagr'])}, MDD {fmt_pct(full['mdd'], signed=False)}, WF CAGR {fmt_pct(wf['cagr'])}, WF MDD {fmt_pct(wf['mdd'], signed=False)}. {reason}\n")
            f.write("\n과거 R14와 다른 점: 자본투입률이나 현금비중으로 MDD 숫자를 맞추지 않았고, 롱숏 후보를 실제 달러중립 구조로 구현했으며, 2024~2026 블라인드와 2022년 연도별 방어력을 판정 조건에 넣었다.\n")
        else:
            f.write("워크포워드까지 통과한 승자 없음.\n\n")
            if refs:
                f.write("상위 참고용 후보:\n")
                for c, v, full, wf, reason in refs[:5]:
                    f.write(f"- {c.no}-{v.code} {c.name} / {v.label}: full CAGR {fmt_pct(full['cagr'])}, MDD {fmt_pct(full['mdd'], signed=False)}, Calmar {fmt_num(full['calmar'])}; WF CAGR {fmt_pct(wf['cagr'])}, MDD {fmt_pct(wf['mdd'], signed=False)}, Calmar {fmt_num(wf['calmar'])}. 참고용 사유: {reason}\n")
            f.write("\n이번 검증은 과거 R14의 오류를 반복하지 않았다. capital_fraction·현금비중·레버리지를 스윕하지 않았고, 후보별 변형 수를 3개로 제한했으며, 모든 후보를 동일 수수료 0.05%와 달러중립 포트폴리오 구조로 평가했다. 집계 성과가 좋아 보여도 2024~2026 워크포워드 또는 2022년 방어력이 약하면 승자로 인정하지 않았다.\n")

    text = REPORT_PATH.read_text(encoding="utf-8")
    REPORT_PATH.write_text(text.replace("작성 중 — 정밀검증", "완료 — 정밀검증", 1), encoding="utf-8")


def run() -> None:
    write_header()
    frames = load_frames()
    btc_close = frames.get("BTC", pd.DataFrame()).get("Close") if "BTC" in frames else None
    all_rows: list[tuple[Candidate, Variant, dict, dict, str, str]] = []
    for candidate in CANDIDATES:
        print(f"[candidate {candidate.rank}/15] {candidate.no} {candidate.name}", flush=True)
        candidate_rows = []
        for variant in variants_for(candidate, btc_close):
            prepped = _prepare(frames, variant)
            full = simulate_market_neutral(prepped, variant.top_k, variant.hold_days)
            train = simulate_market_neutral(prepped, variant.top_k, variant.hold_days, end=TRAIN_END)
            wf = simulate_market_neutral(prepped, variant.top_k, variant.hold_days, start=TEST_START)
            label, reason = verdict(full, wf, candidate, variant)
            candidate_rows.append((variant, full, train, wf, label, reason))
            all_rows.append((candidate, variant, full, wf, label, reason))
            print(
                f"  - {variant.code}: full CAGR={full['cagr']:.2f}% MDD={full['mdd']:.1f}% "
                f"WF CAGR={wf['cagr']:.2f}% MDD={wf['mdd']:.1f}% {label}",
                flush=True,
            )
        append_candidate(candidate, candidate_rows)
    finalize(all_rows)
    print(f"[done] wrote {REPORT_PATH}", flush=True)


if __name__ == "__main__":
    run()
