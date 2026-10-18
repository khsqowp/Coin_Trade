"""Run the phase-2 first-pass screening for the new strategy catalog.

This module intentionally writes the markdown report incrementally. If a run is
interrupted, completed rows remain in docs/신규전략100-1차스크리닝.md.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import ccxt
import numpy as np
import pandas as pd

from app.futures_data import fetch_perp_ohlcv
from app.strategy_screen_core import (
    HORIZONS_DEFAULT,
    StrategyStats,
    adx,
    aggregate_symbol_stats,
    atr,
    clean_direction,
    connors_rsi,
    evaluate_direction_series,
    rsi,
    rolling_vwap,
    zscore,
)

SINCE = "2019-01-01T00:00:00Z"
TIMEFRAME = "1d"
REPORT_PATH = Path("docs/신규전략100-1차스크리닝.md")
CACHE_DIR = Path(".screen_cache/binance_usdtm_1d")
MIN_BARS = 260
PAIR_BASES = ("BTC", "ETH", "SOL", "BNB")

UNIVERSE = [
    "BTC", "ETH", "BNB", "XRP", "SOL", "TRX", "DOGE", "ZEC", "LINK", "XMR",
    "ADA", "XLM", "BCH", "LTC", "HBAR", "AVAX", "SUI", "UNI", "NEAR",
    "TAO", "AAVE", "ONDO", "THETA", "DOT", "ENA", "WLD", "ICP", "ETC",
    "POL", "QNT", "ALGO", "ATOM", "RENDER", "JUP", "ARB", "FIL", "VET",
    "CAKE", "LDO", "CRV", "INJ", "OP", "APT", "IMX", "STX",
]


@dataclass(frozen=True)
class CatalogStrategy:
    no: int
    name: str
    direction: str
    impl: str
    kind: str = "single"
    reason: str = ""


def _bool_dir(long: pd.Series, short: pd.Series | None = None) -> pd.Series:
    out = pd.Series(0, index=long.index, dtype=int)
    out[long.fillna(False)] = 1
    if short is not None:
        out[short.fillna(False)] = -1
    return out


def dynamic_breakout(frame: pd.DataFrame) -> pd.Series:
    vol_fast = frame["Close"].pct_change().rolling(20).std()
    vol_slow = frame["Close"].pct_change().rolling(100).std()
    ratio = (vol_fast / vol_slow.replace(0, np.nan)).clip(0.5, 2.0).fillna(1.0)
    lookback = (40 / ratio).round().clip(20, 60).astype(int)
    highs = frame["High"].shift(1)
    lows = frame["Low"].shift(1)
    long = pd.Series(False, index=frame.index)
    short = pd.Series(False, index=frame.index)
    for i in range(60, len(frame)):
        lb = int(lookback.iloc[i])
        long.iloc[i] = frame["Close"].iloc[i] > highs.iloc[i - lb + 1:i + 1].max()
        short.iloc[i] = frame["Close"].iloc[i] < lows.iloc[i - lb + 1:i + 1].min()
    return _bool_dir(long, short)


def dual_thrust(frame: pd.DataFrame) -> pd.Series:
    hh = frame["High"].shift(1).rolling(4).max()
    hc = frame["Close"].shift(1).rolling(4).max()
    lc = frame["Close"].shift(1).rolling(4).min()
    ll = frame["Low"].shift(1).rolling(4).min()
    rng = pd.concat([hh - lc, hc - ll], axis=1).max(axis=1)
    upper = frame["Open"] + 0.5 * rng
    lower = frame["Open"] - 0.5 * rng
    return _bool_dir(frame["Close"] > upper, frame["Close"] < lower)


def low_frequency_momentum(frame: pd.DataFrame) -> pd.Series:
    slow = frame["Close"].rolling(100).mean()
    slope = slow.pct_change(20)
    return _bool_dir((frame["Close"] > slow) & (slope > 0), (frame["Close"] < slow) & (slope < 0))


def ma200_trend(frame: pd.DataFrame) -> pd.Series:
    ma = frame["Close"].rolling(200).mean()
    return _bool_dir(frame["Close"] > ma, frame["Close"] < ma)


def cta_trend(frame: pd.DataFrame) -> pd.Series:
    fast = frame["Close"].rolling(50).mean()
    slow = frame["Close"].rolling(200).mean()
    return _bool_dir(fast > slow, fast < slow)


def low_volatility(frame: pd.DataFrame) -> pd.Series:
    vol = frame["Close"].pct_change().rolling(30).std()
    return _bool_dir(vol < vol.rolling(252).quantile(0.25))


def ichimoku(frame: pd.DataFrame) -> pd.Series:
    high = frame["High"]
    low = frame["Low"]
    close = frame["Close"]
    tenkan = (high.rolling(9).max() + low.rolling(9).min()) / 2
    kijun = (high.rolling(26).max() + low.rolling(26).min()) / 2
    span_a = ((tenkan + kijun) / 2).shift(26)
    span_b = ((high.rolling(52).max() + low.rolling(52).min()) / 2).shift(26)
    cloud_top = pd.concat([span_a, span_b], axis=1).max(axis=1)
    cloud_bot = pd.concat([span_a, span_b], axis=1).min(axis=1)
    return _bool_dir((tenkan > kijun) & (close > cloud_top), (tenkan < kijun) & (close < cloud_bot))


def seasonality_month(frame: pd.DataFrame) -> pd.Series:
    ret = frame["Close"].pct_change()
    hist = ret.groupby(frame.index.month).transform(lambda s: s.shift(1).rolling(4).mean())
    return _bool_dir(hist > 0, hist < 0)


def vwap_band_reversion(frame: pd.DataFrame) -> pd.Series:
    vw = rolling_vwap(frame, 20)
    dev = frame["Close"] - vw
    band = 2 * dev.rolling(20).std()
    return _bool_dir(frame["Close"] < vw - band, frame["Close"] > vw + band)


def vwap_midline_reversion(frame: pd.DataFrame) -> pd.Series:
    vw = rolling_vwap(frame, 20)
    dev_z = zscore(frame["Close"] - vw, 20)
    return _bool_dir(dev_z < -1.5, dev_z > 1.5)


def stochastic_reversion(frame: pd.DataFrame) -> pd.Series:
    low = frame["Low"].rolling(14).min()
    high = frame["High"].rolling(14).max()
    k = (frame["Close"] - low) / (high - low).replace(0, np.nan) * 100
    trend = adx(frame, 14)
    return _bool_dir((k < 20) & (trend < 25), (k > 80) & (trend < 25))


def sma_z_reversion(frame: pd.DataFrame) -> pd.Series:
    zs = zscore(frame["Close"], 20)
    return _bool_dir(zs < -1.5, zs > 1.5)


def adx_gated_range_fade(frame: pd.DataFrame) -> pd.Series:
    rr = rsi(frame["Close"], 14)
    trend = adx(frame, 14)
    return _bool_dir((rr < 30) & (trend < 25), (rr > 70) & (trend < 25))


def keltner_trend(frame: pd.DataFrame) -> pd.Series:
    ema = frame["Close"].ewm(span=20, adjust=False).mean()
    width = 2 * atr(frame, 20)
    return _bool_dir(frame["Close"] > ema + width, frame["Close"] < ema - width)


def squeeze_momentum(frame: pd.DataFrame) -> pd.Series:
    close = frame["Close"]
    ma = close.rolling(20).mean()
    sd = close.rolling(20).std()
    bb_width = 4 * sd
    kc_width = 3 * atr(frame, 20)
    squeeze_off = (bb_width.shift(1) < kc_width.shift(1)) & (bb_width > kc_width)
    mom = close - ((frame["High"].rolling(20).max() + frame["Low"].rolling(20).min()) / 2)
    return _bool_dir(squeeze_off & (mom > 0), squeeze_off & (mom < 0))


def nr7_breakout(frame: pd.DataFrame) -> pd.Series:
    rng = frame["High"] - frame["Low"]
    nr7_prev = rng.shift(1) == rng.shift(1).rolling(7).min()
    return _bool_dir(nr7_prev & (frame["Close"] > frame["High"].shift(1)), nr7_prev & (frame["Close"] < frame["Low"].shift(1)))


def bollinger_reversion(frame: pd.DataFrame) -> pd.Series:
    ma = frame["Close"].rolling(20).mean()
    sd = frame["Close"].rolling(20).std()
    return _bool_dir(frame["Close"] < ma - 2 * sd, frame["Close"] > ma + 2 * sd)


def bollinger_trend(frame: pd.DataFrame) -> pd.Series:
    ma = frame["Close"].rolling(20).mean()
    sd = frame["Close"].rolling(20).std()
    upper = ma + 2 * sd
    lower = ma - 2 * sd
    trend = adx(frame, 14)
    return _bool_dir((frame["Close"] > upper) & (trend > 25), (frame["Close"] < lower) & (trend > 25))


def connors_pullback(frame: pd.DataFrame) -> pd.Series:
    crsi = connors_rsi(frame["Close"])
    ma = frame["Close"].rolling(200).mean()
    return _bool_dir((frame["Close"] > ma) & (crsi < 20), (frame["Close"] < ma) & (crsi > 80))


def rsi2_pullback(frame: pd.DataFrame) -> pd.Series:
    rr = rsi(frame["Close"], 2)
    ma = frame["Close"].rolling(200).mean()
    return _bool_dir((frame["Close"] > ma) & (rr < 10), (frame["Close"] < ma) & (rr > 90))


def larry_vol_breakout(frame: pd.DataFrame) -> pd.Series:
    prev_range = (frame["High"].shift(1) - frame["Low"].shift(1))
    upper = frame["Open"] + 0.5 * prev_range
    lower = frame["Open"] - 0.5 * prev_range
    return _bool_dir(frame["Close"] > upper, frame["Close"] < lower)


def williams_reversal(frame: pd.DataFrame) -> pd.Series:
    hh = frame["High"].rolling(14).max()
    ll = frame["Low"].rolling(14).min()
    wr = -100 * (hh - frame["Close"]) / (hh - ll).replace(0, np.nan)
    return _bool_dir((wr.shift(1) < -80) & (wr > -80), (wr.shift(1) > -20) & (wr < -20))


def volatility_breakout(frame: pd.DataFrame) -> pd.Series:
    vol = atr(frame, 20) / frame["Close"]
    burst = vol > vol.shift(1).rolling(100).quantile(0.8)
    mom = frame["Close"].pct_change(5)
    return _bool_dir(burst & (mom > 0), burst & (mom < 0))


def rolling_z_reversion(frame: pd.DataFrame) -> pd.Series:
    zs = zscore(frame["Close"], 60)
    return _bool_dir(zs < -2.0, zs > 2.0)


def ma_band_breakout(frame: pd.DataFrame) -> pd.Series:
    ma = frame["Close"].rolling(50).mean()
    band = atr(frame, 20)
    high = frame["High"].shift(1).rolling(20).max()
    low = frame["Low"].shift(1).rolling(20).min()
    return _bool_dir((frame["Close"] > ma + band) & (frame["Close"] > high), (frame["Close"] < ma - band) & (frame["Close"] < low))


def clv_classifier(frame: pd.DataFrame) -> pd.Series:
    clv = ((frame["Close"] - frame["Low"]) - (frame["High"] - frame["Close"])) / (frame["High"] - frame["Low"]).replace(0, np.nan)
    return _bool_dir(clv > 0.8, clv < -0.8)


def ar_residual(frame: pd.DataFrame) -> pd.Series:
    ret = frame["Close"].pct_change()
    lag = ret.shift(1)
    beta = ret.rolling(60).cov(lag) / lag.rolling(60).var()
    pred = beta * lag
    resid = ret - pred
    rz = zscore(resid, 60)
    return _bool_dir(rz > 1.0, rz < -1.0)


def fourier_energy(frame: pd.DataFrame) -> pd.Series:
    close = np.log(frame["Close"])
    out = pd.Series(0, index=frame.index, dtype=int)
    for i in range(128, len(frame)):
        window = close.iloc[i - 127:i + 1].to_numpy()
        coeff = np.fft.rfft(window - window.mean())
        low_energy = float(np.abs(coeff[1:4]).sum())
        high_energy = float(np.abs(coeff[10:30]).sum())
        slope = pd.Series(window).rolling(20).mean().diff().iloc[-1]
        if low_energy > high_energy and slope > 0:
            out.iloc[i] = 1
        elif low_energy > high_energy and slope < 0:
            out.iloc[i] = -1
    return out


def anchored_vwap_rejection(frame: pd.DataFrame) -> pd.Series:
    typical = (frame["High"] + frame["Low"] + frame["Close"]) / 3
    pv = typical * frame["Volume"]
    anchor_low = frame["Low"] == frame["Low"].rolling(60).min()
    anchor_high = frame["High"] == frame["High"].rolling(60).max()
    avwap = pd.Series(np.nan, index=frame.index)
    current_pv = 0.0
    current_vol = 0.0
    for i in range(len(frame)):
        if bool(anchor_low.iloc[i]) or bool(anchor_high.iloc[i]) or current_vol == 0:
            current_pv = 0.0
            current_vol = 0.0
        current_pv += float(pv.iloc[i])
        current_vol += float(frame["Volume"].iloc[i])
        avwap.iloc[i] = current_pv / current_vol if current_vol else np.nan
    touched = (frame["Low"] <= avwap) & (frame["High"] >= avwap)
    return _bool_dir(touched & (frame["Close"] > avwap) & (frame["Close"].pct_change(3) > 0), touched & (frame["Close"] < avwap) & (frame["Close"].pct_change(3) < 0))


def session_avwap_band(frame: pd.DataFrame) -> pd.Series:
    typical = (frame["High"] + frame["Low"] + frame["Close"]) / 3
    key = pd.Series(frame.index.to_period("M"), index=frame.index)
    pv_cum = (typical * frame["Volume"]).groupby(key).cumsum()
    vol_cum = frame["Volume"].groupby(key).cumsum()
    vw = pv_cum / vol_cum
    dev = typical - vw
    sd = dev.groupby(key).expanding().std().reset_index(level=0, drop=True)
    return _bool_dir(frame["Close"] < vw - 2 * sd, frame["Close"] > vw + 2 * sd)


SINGLE_SIGNALS = {
    "dynamic_breakout": dynamic_breakout,
    "dual_thrust": dual_thrust,
    "low_frequency_momentum": low_frequency_momentum,
    "ma200_trend": ma200_trend,
    "cta_trend": cta_trend,
    "low_volatility": low_volatility,
    "ichimoku": ichimoku,
    "seasonality_month": seasonality_month,
    "vwap_band_reversion": vwap_band_reversion,
    "vwap_midline_reversion": vwap_midline_reversion,
    "stochastic_reversion": stochastic_reversion,
    "sma_z_reversion": sma_z_reversion,
    "adx_gated_range_fade": adx_gated_range_fade,
    "keltner_trend": keltner_trend,
    "squeeze_momentum": squeeze_momentum,
    "nr7_breakout": nr7_breakout,
    "bollinger_reversion": bollinger_reversion,
    "bollinger_trend": bollinger_trend,
    "connors_pullback": connors_pullback,
    "rsi2_pullback": rsi2_pullback,
    "larry_vol_breakout": larry_vol_breakout,
    "williams_reversal": williams_reversal,
    "volatility_breakout": volatility_breakout,
    "rolling_z_reversion": rolling_z_reversion,
    "ma_band_breakout": ma_band_breakout,
    "clv_classifier": clv_classifier,
    "ar_residual": ar_residual,
    "fourier_energy": fourier_energy,
    "anchored_vwap_rejection": anchored_vwap_rejection,
    "session_avwap_band": session_avwap_band,
}


def _rank_panel(frames: dict[str, pd.DataFrame], score_by_symbol: dict[str, pd.Series], top_q: float = 0.2, bottom_q: float = 0.2) -> dict[str, pd.Series]:
    dates = sorted(set().union(*(s.index for s in score_by_symbol.values())))
    out = {sym: pd.Series(0, index=df.index, dtype=int) for sym, df in frames.items()}
    for d in dates:
        vals = {sym: float(score.get(d, np.nan)) for sym, score in score_by_symbol.items()}
        vals = {sym: v for sym, v in vals.items() if np.isfinite(v)}
        if len(vals) < 10:
            continue
        ranked = sorted(vals.items(), key=lambda x: x[1])
        n_top = max(1, int(len(ranked) * top_q))
        n_bot = max(1, int(len(ranked) * bottom_q))
        for sym, _ in ranked[-n_top:]:
            if d in out[sym].index:
                out[sym].loc[d] = 1
        for sym, _ in ranked[:n_bot]:
            if d in out[sym].index:
                out[sym].loc[d] = -1
    return out


def cs_momentum(frames: dict[str, pd.DataFrame], lookback: int = 126) -> dict[str, pd.Series]:
    scores = {sym: df["Close"].pct_change(lookback) for sym, df in frames.items()}
    return _rank_panel(frames, scores)


def cs_reversal(frames: dict[str, pd.DataFrame]) -> dict[str, pd.Series]:
    scores = {sym: -df["Close"].pct_change(5) for sym, df in frames.items()}
    return _rank_panel(frames, scores)


def residual_momentum(frames: dict[str, pd.DataFrame]) -> dict[str, pd.Series]:
    btc = frames["BTC"]["Close"].pct_change()
    scores: dict[str, pd.Series] = {}
    for sym, df in frames.items():
        ret = df["Close"].pct_change()
        aligned = pd.concat([ret, btc], axis=1).dropna()
        cov = aligned.iloc[:, 0].rolling(90).cov(aligned.iloc[:, 1])
        var = aligned.iloc[:, 1].rolling(90).var()
        beta = cov / var.replace(0, np.nan)
        resid = aligned.iloc[:, 0] - beta * aligned.iloc[:, 1]
        scores[sym] = resid.rolling(60).sum().reindex(df.index)
    return _rank_panel(frames, scores)


def improved_momentum(frames: dict[str, pd.DataFrame]) -> dict[str, pd.Series]:
    scores = {}
    for sym, df in frames.items():
        ret = df["Close"].pct_change(126)
        vol = df["Close"].pct_change().rolling(60).std()
        scores[sym] = ret / vol.replace(0, np.nan)
    return _rank_panel(frames, scores)


def basket_allocation(frames: dict[str, pd.DataFrame]) -> dict[str, pd.Series]:
    scores = {}
    for sym, df in frames.items():
        mom = df["Close"].pct_change(90)
        vol = df["Close"].pct_change().rolling(60).std()
        scores[sym] = mom - vol
    ranked = _rank_panel(frames, scores, top_q=0.25, bottom_q=0.0)
    return {sym: s.clip(lower=0) for sym, s in ranked.items()}


def beta_relative_value(frames: dict[str, pd.DataFrame]) -> dict[str, pd.Series]:
    btc = frames["BTC"]["Close"].pct_change()
    scores = {}
    for sym, df in frames.items():
        ret = df["Close"].pct_change()
        aligned = pd.concat([ret, btc], axis=1).dropna()
        beta = aligned.iloc[:, 0].rolling(60).cov(aligned.iloc[:, 1]) / aligned.iloc[:, 1].rolling(60).var().replace(0, np.nan)
        fitted = beta * aligned.iloc[:, 1]
        spread = (aligned.iloc[:, 0] - fitted).rolling(20).sum()
        scores[sym] = -zscore(spread, 120).reindex(df.index)
    return _rank_panel(frames, scores)


def pair_zscore(frames: dict[str, pd.DataFrame]) -> dict[str, pd.Series]:
    out = {sym: pd.Series(0, index=df.index, dtype=int) for sym, df in frames.items()}
    for sym, df in frames.items():
        if sym in PAIR_BASES:
            continue
        best_base = None
        best_corr = -2.0
        ret = df["Close"].pct_change()
        for base in PAIR_BASES:
            corr = ret.rolling(180).corr(frames[base]["Close"].pct_change()).mean()
            if np.isfinite(corr) and corr > best_corr:
                best_base = base
                best_corr = float(corr)
        if best_base is None:
            continue
        base_close = frames[best_base]["Close"].reindex(df.index).ffill()
        ratio = np.log(df["Close"]) - np.log(base_close)
        zs = zscore(ratio, 60)
        out[sym] = _bool_dir(zs < -2, zs > 2)
    return out


PANEL_SIGNALS = {
    "cs_momentum": cs_momentum,
    "cs_reversal": cs_reversal,
    "residual_momentum": residual_momentum,
    "improved_momentum": improved_momentum,
    "basket_allocation": basket_allocation,
    "beta_relative_value": beta_relative_value,
    "pair_zscore": pair_zscore,
}


STRATEGIES = [
    CatalogStrategy(1, "Dynamic Breakout II", "롱숏", "dynamic_breakout"),
    CatalogStrategy(2, "Dual Thrust Intraday", "롱숏", "dual_thrust"),
    CatalogStrategy(3, "Copula Pairs Trading", "시장중립", "pair_zscore", "panel", "Copula 자체가 아니라 일봉 가격비율 z-score 페어 스크리닝으로 1차 대체. Copula 모형은 3단계 별도."),
    CatalogStrategy(4, "Cointegration Pairs Trading", "시장중립", "pair_zscore", "panel", "정식 공적분 검정 라이브러리 없이 가격비율 z-score 페어 이벤트만 1차 확인."),
    CatalogStrategy(5, "Intraday Dynamic Pairs Trading", "시장중립", "skip", reason="구현 불가(분봉·장중 동적 페어 재추정 필요) — 스킵"),
    CatalogStrategy(6, "Low-Frequency Component Momentum", "롱숏", "low_frequency_momentum"),
    CatalogStrategy(7, "Short-Term Reversal", "롱숏", "cs_reversal", "panel"),
    CatalogStrategy(8, "10-Month Moving Average Trend Following", "롱숏", "ma200_trend"),
    CatalogStrategy(9, "Asset Class Momentum", "롱온리", "skip", reason="구현 불가(자산군·섹터 버킷 데이터 없음) — 스킵"),
    CatalogStrategy(10, "Residual Momentum", "롱숏", "residual_momentum", "panel"),
    CatalogStrategy(11, "Sector Momentum", "롱숏", "skip", reason="구현 불가(코인 섹터 태깅 없음) — 스킵"),
    CatalogStrategy(14, "Low Volatility Effect", "롱온리", "low_volatility"),
    CatalogStrategy(15, "12-Month Relative Momentum", "롱숏", "cs_momentum", "panel"),
    CatalogStrategy(16, "Country Mean Reversion의 코인 섹터 변형", "롱숏", "skip", reason="구현 불가(섹터 지수 생성 데이터 없음) — 스킵"),
    CatalogStrategy(17, "Improved Momentum with Baltas-Kosowski Weights", "롱숏", "improved_momentum", "panel"),
    CatalogStrategy(18, "Commodities Futures Trend Following", "롱숏", "cta_trend"),
    CatalogStrategy(19, "Ichimoku Cloud Crossover", "롱숏", "ichimoku"),
    CatalogStrategy(20, "Intraday ETF Momentum의 코인 세션 변형", "롱숏", "skip", reason="구현 불가(세션 내부 수익률을 볼 분봉 데이터 없음) — 스킵"),
    CatalogStrategy(21, "Price and Earnings Momentum의 가격·온체인 성장 변형", "롱온리", "skip", reason="구현 불가(온체인·TVL·수수료 매출 데이터 없음) — 스킵"),
    CatalogStrategy(22, "Standardized Unexpected Earnings의 온체인 서프라이즈 변형", "롱숏", "skip", reason="구현 불가(온체인 서프라이즈 예측 데이터 없음) — 스킵"),
    CatalogStrategy(23, "Seasonality Same-Calendar Month", "롱숏", "seasonality_month"),
    CatalogStrategy(24, "Mean-Reversion Statistical Arbitrage Basket", "시장중립", "beta_relative_value", "panel"),
    CatalogStrategy(26, "Funding Rate Z-Score Contrarian", "롱숏", "skip", reason="구현 불가(funding history 미수집) — 스킵"),
    CatalogStrategy(27, "RSI + Funding Confluence", "롱숏", "skip", reason="구현 불가(funding history 미수집) — 스킵"),
    CatalogStrategy(28, "VWAP ±2σ Mean Reversion", "롱숏", "vwap_band_reversion"),
    CatalogStrategy(29, "RSI-2 Reversion", "롱숏", "rsi2_pullback", reason="스킵에 가까운 중복 후보. 숫자는 참고용."),
    CatalogStrategy(30, "VWAP Reversion to Midline", "롱숏", "vwap_midline_reversion"),
    CatalogStrategy(31, "Stochastic Range Reversion", "롱숏", "stochastic_reversion"),
    CatalogStrategy(32, "SMA Z-Score Reversion", "롱숏", "sma_z_reversion"),
    CatalogStrategy(33, "ADX-Gated Range Fade", "롱숏", "adx_gated_range_fade"),
    CatalogStrategy(34, "Dynamic Grid Trading", "중립형", "skip", reason="구현 불가(grid 호가·inventory 실행 알고리즘이라 이벤트스터디와 불일치) — 스킵"),
    CatalogStrategy(36, "Score-Driven Multi-Scenario Engine", "롱숏", "skip", reason="구현 불가(원 전략의 점수 구성·시나리오 정의 불명확) — 스킵"),
    CatalogStrategy(37, "Bollinger Grid", "중립형", "skip", reason="구현 불가(grid 호가·inventory 실행 알고리즘이라 이벤트스터디와 불일치) — 스킵"),
    CatalogStrategy(38, "Crypto Basket Allocation", "롱온리", "basket_allocation", "panel"),
    CatalogStrategy(40, "Cross-Sectional Momentum Panel", "롱온리", "cs_momentum", "panel"),
    CatalogStrategy(41, "Rolling Z-Score Mean Reversion", "롱숏", "rolling_z_reversion"),
    CatalogStrategy(43, "MA Band + N-Day High/Low Breakout", "롱숏", "ma_band_breakout"),
    CatalogStrategy(44, "Beta Regression Relative-Value", "시장중립", "beta_relative_value", "panel"),
    CatalogStrategy(45, "VWAP/Volume-Weighted Deviation Strategy", "롱숏", "vwap_midline_reversion"),
    CatalogStrategy(46, "Close Location Value Classifier", "롱숏", "clv_classifier"),
    CatalogStrategy(47, "AR Residual Sign Strategy", "롱숏", "ar_residual"),
    CatalogStrategy(48, "ARMA Residual Sign Strategy", "롱숏", "skip", reason="구현 불가(ARMA 추정 라이브러리·walk-forward 모형 없음) — 스킵"),
    CatalogStrategy(49, "Fourier Seasonality/Energy Strategy", "롱숏", "fourier_energy"),
    CatalogStrategy(52, "Walk-Forward Funding Carry", "시장중립", "skip", reason="구현 불가(funding·basis 데이터 및 spot leg 없음) — 스킵"),
    CatalogStrategy(53, "Funding Rate + Basis Filtered Arbitrage", "시장중립", "skip", reason="구현 불가(spot basis·funding 데이터 없음) — 스킵"),
    CatalogStrategy(54, "Cross-Exchange Funding Rate Arbitrage", "시장중립", "skip", reason="구현 불가(다거래소 funding 데이터 없음) — 스킵"),
    CatalogStrategy(55, "Pure Futures Perp-Perp Spread", "시장중립", "skip", reason="구현 불가(다거래소 perp spread 데이터 없음) — 스킵"),
    CatalogStrategy(56, "Calendar/Basis Trade", "시장중립", "skip", reason="구현 불가(delivery futures·spot basis 데이터 없음) — 스킵"),
    CatalogStrategy(57, "Avellaneda-Stoikov Market Making", "시장중립", "skip", reason="구현 불가(실시간 호가·재고·체결 큐 시뮬레이터 없음) — 스킵"),
    CatalogStrategy(58, "Execution-Aware Inventory Market Making", "시장중립", "skip", reason="구현 불가(L2/L3·latency·queue 데이터 없음) — 스킵"),
    CatalogStrategy(59, "Cross-Exchange Market Making", "시장중립", "skip", reason="구현 불가(다거래소 호가·헤지 인프라 없음) — 스킵"),
    CatalogStrategy(60, "Pure Market Making Multi-Level Spread", "시장중립", "skip", reason="구현 불가(실시간 다중호가·inventory 실행 필요) — 스킵"),
    CatalogStrategy(61, "AMM/CEX Arbitrage", "시장중립", "skip", reason="구현 불가(DEX AMM·가스·CEX hedge 데이터 없음) — 스킵"),
    CatalogStrategy(62, "Triangular Arbitrage", "시장중립", "skip", reason="구현 불가(spot multi-pair 실시간 호가 필요) — 스킵"),
    CatalogStrategy(63, "Binance Triangle Arbitrage Bot", "시장중립", "skip", reason="구현 불가(spot 삼각호가 실시간 데이터 필요) — 스킵"),
    CatalogStrategy(65, "BTC Covered Call Overlay", "옵션", "skip", reason="구현 불가(옵션 체인·프리미엄 데이터 없음) — 스킵"),
    CatalogStrategy(66, "Protective Collar", "옵션", "skip", reason="구현 불가(옵션 체인·프리미엄 데이터 없음) — 스킵"),
    CatalogStrategy(67, "Order Book Imbalance Scalping", "롱숏", "skip", reason="구현 불가(L2 order book 데이터 없음) — 스킵"),
    CatalogStrategy(68, "OBI + Bid-Ask Spread Microstructure", "롱숏", "skip", reason="구현 불가(L2 order book·spread 데이터 없음) — 스킵"),
    CatalogStrategy(69, "Liquidity Sweep / Stop Cluster Strategy", "롱숏", "skip", reason="구현 불가(liquidation·stop cluster·L2 데이터 없음) — 스킵"),
    CatalogStrategy(70, "Binance Volatility Breakout Bot", "롱숏", "volatility_breakout"),
    CatalogStrategy(71, "Reddit Positive Sentiment Long", "롱온리", "skip", reason="구현 불가(Reddit 수집·NLP 데이터 없음) — 스킵"),
    CatalogStrategy(72, "News Sentiment Spike Strategy", "롱온리", "skip", reason="구현 불가(뉴스 API·NLP 데이터 없음) — 스킵"),
    CatalogStrategy(73, "Inverse Reddit Sentiment", "롱숏", "skip", reason="구현 불가(Reddit 수집·NLP 데이터 없음) — 스킵"),
    CatalogStrategy(74, "Google Trends Attention Signal", "롱숏", "skip", reason="구현 불가(Google Trends 데이터 없음) — 스킵"),
    CatalogStrategy(75, "X/Twitter Sentiment Signal", "롱숏", "skip", reason="구현 불가(X API·NLP 데이터 없음) — 스킵"),
    CatalogStrategy(76, "Random Forest/XGBoost Crypto Classifier", "롱숏", "skip", reason="구현 불가(대규모 ML 학습·walk-forward 검증은 1차 이벤트스터디 범위 밖) — 스킵"),
    CatalogStrategy(77, "Walk-Forward XGBoost Bitcoin Strategy", "롱온리", "skip", reason="구현 불가(ML walk-forward 학습 범위 밖) — 스킵"),
    CatalogStrategy(78, "PPO Reinforcement Learning Agent", "롱숏", "skip", reason="구현 불가(RL 학습 인프라·환경 없음) — 스킵"),
    CatalogStrategy(79, "Deep Reinforcement Learning Bitcoin Bot", "롱숏", "skip", reason="구현 불가(RL 학습 인프라·환경 없음) — 스킵"),
    CatalogStrategy(80, "Recurrent Reinforcement Learning Perp Agent", "롱숏", "skip", reason="구현 불가(RL 학습 인프라·분봉 환경 없음) — 스킵"),
    CatalogStrategy(81, "Temporal CNN Forecasting Strategy", "롱숏", "skip", reason="구현 불가(딥러닝 학습·walk-forward 검증 범위 밖) — 스킵"),
    CatalogStrategy(82, "Deep Momentum Networks", "롱숏", "skip", reason="구현 불가(딥러닝 학습 인프라 없음) — 스킵"),
    CatalogStrategy(83, "Momentum Transformer", "롱숏", "skip", reason="구현 불가(transformer 학습 인프라 없음) — 스킵"),
    CatalogStrategy(84, "Spatio-Temporal Momentum", "롱숏", "skip", reason="구현 불가(딥러닝 panel 학습 인프라 없음) — 스킵"),
    CatalogStrategy(85, "MVRV Z-Score Cycle Strategy", "롱온리", "skip", reason="구현 불가(MVRV 온체인 데이터 없음) — 스킵"),
    CatalogStrategy(86, "MVRV Percentile Regime Filter", "롱숏", "skip", reason="구현 불가(MVRV 온체인 데이터 없음) — 스킵"),
    CatalogStrategy(87, "NVT Valuation Signal", "롱숏", "skip", reason="구현 불가(NVT 온체인 데이터 없음) — 스킵"),
    CatalogStrategy(88, "NUPL Cycle Extremes", "롱온리", "skip", reason="구현 불가(NUPL 온체인 데이터 없음) — 스킵"),
    CatalogStrategy(89, "Percent Supply in Profit Extremes", "롱온리", "skip", reason="구현 불가(supply in profit 온체인 데이터 없음) — 스킵"),
    CatalogStrategy(90, "SOPR Profit-Taking Signal", "롱온리", "skip", reason="구현 불가(SOPR 온체인 데이터 없음) — 스킵"),
    CatalogStrategy(91, "Opening Range Breakout", "롱숏", "skip", reason="구현 불가(opening range 산출용 분봉 데이터 없음) — 스킵"),
    CatalogStrategy(92, "Stocks-in-Play ORB with Volume/ATR Filter", "롱숏", "skip", reason="구현 불가(opening range 산출용 분봉 데이터 없음) — 스킵"),
    CatalogStrategy(94, "Keltner Channel Trend Following", "롱숏", "keltner_trend"),
    CatalogStrategy(95, "TTM/LazyBear Squeeze Momentum", "롱숏", "squeeze_momentum"),
    CatalogStrategy(96, "Crypto Squeeze Strategy Pine", "롱숏", "squeeze_momentum", reason="95번과 같은 TTM squeeze 계열로 동일 신호 사용."),
    CatalogStrategy(97, "NR7 Narrow Range Breakout", "롱숏", "nr7_breakout"),
    CatalogStrategy(98, "NR7 + Opening Range Breakout", "롱숏", "skip", reason="구현 불가(NR7 이후 opening range 분봉 데이터 없음) — 스킵"),
    CatalogStrategy(99, "Bollinger Band Mean Reversion", "롱숏", "bollinger_reversion"),
    CatalogStrategy(100, "Bollinger Band Riding Trend", "롱숏", "bollinger_trend"),
    CatalogStrategy(101, "ConnorsRSI Pullback", "롱숏", "connors_pullback"),
    CatalogStrategy(102, "Larry Connors RSI(2) Pullback", "롱숏", "rsi2_pullback", reason="스킵에 가까운 중복 후보. 숫자는 참고용."),
    CatalogStrategy(103, "Larry Williams Volatility Breakout", "롱숏", "larry_vol_breakout"),
    CatalogStrategy(104, "Williams %R Reversal", "롱숏", "williams_reversal"),
    CatalogStrategy(105, "Anchored VWAP Touch/Rejection", "롱숏", "anchored_vwap_rejection"),
    CatalogStrategy(106, "Session Anchored VWAP with SD Bands", "롱숏", "session_avwap_band"),
    CatalogStrategy(108, "Optimal Market-Neutral Crypto Currency Trading", "시장중립", "beta_relative_value", "panel", "시장중립 basket 원형은 3단계 포트폴리오 검증 대상. 여기서는 BTC beta residual 이벤트로 1차 확인."),
]


def fmt_pct(v: float) -> str:
    if not np.isfinite(v):
        return "-"
    return f"{v:+.2f}%"


def fmt_pctp(v: float) -> str:
    if not np.isfinite(v):
        return "-"
    return f"{v:+.2f}"


def metric_cell(stats: StrategyStats, h: int) -> str:
    hs = stats.per_horizon[h]
    return f"{fmt_pct(hs.avg_return_pct)} / {fmt_pctp(hs.edge_pctp)} / {fmt_pct(hs.win_rate_pct)}"


def write_header() -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        "작성 중 — 1차 스크리닝\n\n"
        "# 신규전략100 1차 스크리닝\n\n"
        f"- 실행 데이터: Binance USDT-M 선물 일봉, since=`{SINCE}`.\n"
        "- 유니버스: `app/momentum_rotation_loop.py`의 45종목과 동일.\n"
        "- 체결 가정: 신호 확정 다음날 시가 진입, N일 후 종가 청산.\n"
        "- 비용 가정: 선물 편도 수수료 0.05%, 진입+청산 왕복 0.10%를 모든 이벤트 수익률에 차감.\n"
        "- 롱숏·시장중립 항목: 1차 이벤트스터디에서는 심볼별 롱/숏 방향 이벤트로 분해했다. 페어·basket의 동시 포트폴리오 검증은 3단계 대상이다.\n\n"
        "| 번호 | 전략명 | 방향성 | 상태 | 신호건수 | 5일 평균/엣지/승률 | 10일 평균/엣지/승률 | 20일 평균/엣지/승률 | 비고 |\n"
        "|---:|---|---|---|---:|---:|---:|---:|---|\n",
        encoding="utf-8",
    )


def append_row(strategy: CatalogStrategy, status: str, stats: StrategyStats | None = None, note: str = "") -> None:
    if stats is None:
        row = f"| {strategy.no} | {strategy.name} | {strategy.direction} | {status} | - | - | - | - | {note or strategy.reason} |\n"
    else:
        row = (
            f"| {strategy.no} | {strategy.name} | {strategy.direction} | {status} | {stats.signal_count} | "
            f"{metric_cell(stats, 5)} | {metric_cell(stats, 10)} | {metric_cell(stats, 20)} | {note or strategy.reason} |\n"
        )
    with REPORT_PATH.open("a", encoding="utf-8") as f:
        f.write(row)


def load_frames() -> dict[str, pd.DataFrame]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    exchange = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "future"}})
    frames: dict[str, pd.DataFrame] = {}
    for i, base in enumerate(UNIVERSE, start=1):
        cache_path = CACHE_DIR / f"{base}_{TIMEFRAME}_{SINCE.replace(':', '').replace('-', '')}.csv"
        if cache_path.exists():
            df = pd.read_csv(cache_path, parse_dates=["timestamp"]).set_index("timestamp")
        else:
            print(f"[data {i}/{len(UNIVERSE)}] fetch {base} since={SINCE}", flush=True)
            df = fetch_perp_ohlcv(f"{base}/USDT:USDT", TIMEFRAME, SINCE, exchange=exchange)
            if not df.empty:
                df.reset_index().to_csv(cache_path, index=False)
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
        if len(df) >= MIN_BARS:
            frames[base] = df
        else:
            print(f"[data] skip {base}: bars={len(df)}", flush=True)
    return frames


def run_single(strategy: CatalogStrategy, frames: dict[str, pd.DataFrame]) -> StrategyStats:
    func = SINGLE_SIGNALS[strategy.impl]
    results: dict[str, StrategyStats] = {}
    for sym, df in frames.items():
        stats = evaluate_direction_series(df, clean_direction(func(df), df.index), HORIZONS_DEFAULT)
        if stats is not None:
            results[sym] = stats
    return aggregate_symbol_stats(results, HORIZONS_DEFAULT)


def run_panel(strategy: CatalogStrategy, frames: dict[str, pd.DataFrame]) -> StrategyStats:
    direction_by_symbol = PANEL_SIGNALS[strategy.impl](frames)
    results: dict[str, StrategyStats] = {}
    for sym, direction in direction_by_symbol.items():
        if sym not in frames:
            continue
        stats = evaluate_direction_series(frames[sym], direction, HORIZONS_DEFAULT)
        if stats is not None:
            results[sym] = stats
    return aggregate_symbol_stats(results, HORIZONS_DEFAULT)


def finalize(rows: list[tuple[CatalogStrategy, str, StrategyStats | None]]) -> None:
    implemented = [(s, st) for s, status, st in rows if status == "완료" and st is not None]
    skipped = [s for s, status, st in rows if status != "완료"]

    def score(item: tuple[CatalogStrategy, StrategyStats]) -> float:
        stats = item[1]
        hs10 = stats.per_horizon[10]
        hs20 = stats.per_horizon[20]
        n_penalty = min(1.0, hs10.signal_n / 200) if hs10.signal_n else 0.0
        return (hs10.edge_pctp * 0.6 + hs20.edge_pctp * 0.4) * n_penalty

    ranked = sorted(
        [item for item in implemented if np.isfinite(item[1].per_horizon[10].edge_pctp) and item[1].per_horizon[10].signal_n >= 20],
        key=score,
        reverse=True,
    )
    with REPORT_PATH.open("a", encoding="utf-8") as f:
        f.write("\n## 요약\n\n")
        f.write(f"- 전체 처리: {len(rows)}개\n")
        f.write(f"- 숫자 산출 완료: {len(implemented)}개\n")
        f.write(f"- 구현 불가 또는 1차 범위 제외: {len(skipped)}개\n")
        f.write("- 비용 반영: FUTURES_FEE_ONE_WAY_PCT=0.05, 왕복 0.10% 차감.\n")
        f.write("- 데이터 시작 재확인: `since='2019-01-01T00:00:00Z'`로 호출. 시간 없는 날짜 문자열을 사용하지 않았다.\n\n")
        f.write("## 3단계(정밀검증) 후보\n\n")
        f.write("| 순위 | 번호 | 전략명 | 10일 엣지(%p) | 20일 엣지(%p) | 10일 신호수 | 비고 |\n")
        f.write("|---:|---:|---|---:|---:|---:|---|\n")
        for rank, (strategy, stats) in enumerate(ranked[:15], start=1):
            f.write(
                f"| {rank} | {strategy.no} | {strategy.name} | "
                f"{fmt_pctp(stats.per_horizon[10].edge_pctp)} | {fmt_pctp(stats.per_horizon[20].edge_pctp)} | "
                f"{stats.per_horizon[10].signal_n} | {strategy.reason} |\n"
            )

    text = REPORT_PATH.read_text(encoding="utf-8")
    REPORT_PATH.write_text(text.replace("작성 중 — 1차 스크리닝", "완료", 1), encoding="utf-8")


def main() -> None:
    write_header()
    frames = load_frames()
    if len(frames) < 10:
        raise RuntimeError(f"데이터 확보 실패: {len(frames)}개")

    rows: list[tuple[CatalogStrategy, str, StrategyStats | None]] = []
    for idx, strategy in enumerate(STRATEGIES, start=1):
        print(f"[screen {idx}/{len(STRATEGIES)}] {strategy.no} {strategy.name}", flush=True)
        if strategy.impl == "skip":
            append_row(strategy, "구현 불가 스킵", None, strategy.reason)
            rows.append((strategy, "구현 불가 스킵", None))
            continue
        try:
            stats = run_panel(strategy, frames) if strategy.kind == "panel" else run_single(strategy, frames)
            append_row(strategy, "완료", stats, strategy.reason)
            rows.append((strategy, "완료", stats))
        except Exception as exc:
            note = f"실행 실패: {type(exc).__name__}: {exc}"
            append_row(strategy, "실행 실패", None, note)
            rows.append((strategy, "실행 실패", None))
    finalize(rows)
    print(f"[done] report={REPORT_PATH}", flush=True)


if __name__ == "__main__":
    main()
