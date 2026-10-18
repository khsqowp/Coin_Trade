"""추가 19개 전략 아키타입 — 기존 11개(스윙/상한가따라잡기/크립토 비교군)에 이어 국내주식
일봉 스윕 폭을 넓히기 위한 전통적 기술적분석 지표 기반 전략들. 전부 스팟 롱 전용, 동일한
리스크 기반 포지션 사이징(app/strategies.py의 _risk_sized_fraction과 동일 로직)을 쓴다.
"""
from __future__ import annotations

import pandas as pd
import pandas_ta as ta
from backtesting import Strategy


def _risk_sized_fraction(entry: float, stop: float, risk_per_trade: float, max_fraction: float) -> float | None:
    stop_distance_pct = (entry - stop) / entry
    if stop_distance_pct <= 0:
        return None
    return min(risk_per_trade / stop_distance_pct, max_fraction)


def _first_matching(frame: pd.DataFrame, prefix: str) -> pd.Series:
    return frame[[c for c in frame.columns if c.startswith(prefix)][0]]


RISK_PER_TRADE = 0.0025
MAX_POSITION_FRACTION = 0.95


# ---------- 1. 골든크로스 (SMA50/SMA200, 가장 고전적인 추세추종) ----------

def add_golden_cross_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["SMA50"] = ta.sma(out["Close"], length=50)
    out["SMA200"] = ta.sma(out["Close"], length=200)
    out["ATR14"] = ta.atr(out["High"], out["Low"], out["Close"], length=14)
    return out


class GoldenCrossStrategy(Strategy):
    WARMUP_BARS = 205
    STOP_ATR_MULT = 2.5

    def init(self):
        pass

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return
        sma50, sma50_prev = self.data.SMA50[-1], self.data.SMA50[-2]
        sma200, sma200_prev = self.data.SMA200[-1], self.data.SMA200[-2]
        close, atr = self.data.Close[-1], self.data.ATR14[-1]
        crossed_up = sma50_prev <= sma200_prev and sma50 > sma200
        crossed_down = sma50_prev >= sma200_prev and sma50 < sma200

        if self.position:
            if crossed_down:
                self.position.close()
            return
        if crossed_up:
            stop = close - self.STOP_ATR_MULT * atr
            fraction = _risk_sized_fraction(close, stop, RISK_PER_TRADE, MAX_POSITION_FRACTION)
            if fraction:
                self.buy(size=fraction, sl=stop)


# ---------- 2. MACD 제로크로스 ----------

def add_macd_zero_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    macd = ta.macd(out["Close"], fast=12, slow=26, signal=9)
    out["MACD"] = _first_matching(macd, "MACD_")
    out["SMA200"] = ta.sma(out["Close"], length=200)
    out["ATR14"] = ta.atr(out["High"], out["Low"], out["Close"], length=14)
    return out


class MacdZeroCrossStrategy(Strategy):
    WARMUP_BARS = 205
    STOP_ATR_MULT = 2.0
    USE_TREND_FILTER = True

    def init(self):
        pass

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return
        macd, macd_prev = self.data.MACD[-1], self.data.MACD[-2]
        close, atr, sma200 = self.data.Close[-1], self.data.ATR14[-1], self.data.SMA200[-1]
        crossed_up = macd_prev <= 0 and macd > 0
        crossed_down = macd_prev >= 0 and macd < 0

        if self.position:
            if crossed_down:
                self.position.close()
            return
        if crossed_up and (not self.USE_TREND_FILTER or close > sma200):
            stop = close - self.STOP_ATR_MULT * atr
            fraction = _risk_sized_fraction(close, stop, RISK_PER_TRADE, MAX_POSITION_FRACTION)
            if fraction:
                self.buy(size=fraction, sl=stop)


# ---------- 3. 스토캐스틱 %K/%D 크로스 (과매도권) ----------

def add_stochastic_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    stoch = ta.stoch(out["High"], out["Low"], out["Close"], k=14, d=3, smooth_k=3)
    out["STOCH_K"] = _first_matching(stoch, "STOCHk_")
    out["STOCH_D"] = _first_matching(stoch, "STOCHd_")
    out["ATR14"] = ta.atr(out["High"], out["Low"], out["Close"], length=14)
    return out


class StochasticCrossStrategy(Strategy):
    WARMUP_BARS = 30
    OVERSOLD = 20
    STOP_ATR_MULT = 2.0

    def init(self):
        pass

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return
        k, k_prev = self.data.STOCH_K[-1], self.data.STOCH_K[-2]
        d, d_prev = self.data.STOCH_D[-1], self.data.STOCH_D[-2]
        close, atr = self.data.Close[-1], self.data.ATR14[-1]
        crossed_up = k_prev <= d_prev and k > d and k < self.OVERSOLD
        crossed_down = k_prev >= d_prev and k < d

        if self.position:
            if crossed_down:
                self.position.close()
            return
        if crossed_up:
            stop = close - self.STOP_ATR_MULT * atr
            fraction = _risk_sized_fraction(close, stop, RISK_PER_TRADE, MAX_POSITION_FRACTION)
            if fraction:
                self.buy(size=fraction, sl=stop)


# ---------- 4. 윌리엄스 %R 과매도 반등 ----------

def add_williams_r_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["WILLR"] = ta.willr(out["High"], out["Low"], out["Close"], length=14)
    out["SMA200"] = ta.sma(out["Close"], length=200)
    out["ATR14"] = ta.atr(out["High"], out["Low"], out["Close"], length=14)
    return out


class WilliamsRStrategy(Strategy):
    WARMUP_BARS = 205
    ENTRY_LEVEL = -80
    EXIT_LEVEL = -20
    STOP_ATR_MULT = 2.0

    def init(self):
        pass

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return
        willr = self.data.WILLR[-1]
        close, atr, sma200 = self.data.Close[-1], self.data.ATR14[-1], self.data.SMA200[-1]

        if self.position:
            if willr > self.EXIT_LEVEL:
                self.position.close()
            return
        if willr < self.ENTRY_LEVEL and close > sma200:
            stop = close - self.STOP_ATR_MULT * atr
            fraction = _risk_sized_fraction(close, stop, RISK_PER_TRADE, MAX_POSITION_FRACTION)
            if fraction:
                self.buy(size=fraction, sl=stop)


# ---------- 5. ADX +DI/-DI 크로스 (추세방향 전환) ----------

def add_adx_di_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    adx = ta.adx(out["High"], out["Low"], out["Close"], length=14)
    out["ADX14"] = _first_matching(adx, "ADX_")
    out["DI_PLUS"] = _first_matching(adx, "DMP_")
    out["DI_MINUS"] = _first_matching(adx, "DMN_")
    out["ATR14"] = ta.atr(out["High"], out["Low"], out["Close"], length=14)
    return out


class AdxDiCrossStrategy(Strategy):
    WARMUP_BARS = 30
    ADX_MIN = 20
    STOP_ATR_MULT = 2.0

    def init(self):
        pass

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return
        di_p, di_p_prev = self.data.DI_PLUS[-1], self.data.DI_PLUS[-2]
        di_m, di_m_prev = self.data.DI_MINUS[-1], self.data.DI_MINUS[-2]
        adx, close, atr = self.data.ADX14[-1], self.data.Close[-1], self.data.ATR14[-1]
        crossed_up = di_p_prev <= di_m_prev and di_p > di_m
        crossed_down = di_p_prev >= di_m_prev and di_p < di_m

        if self.position:
            if crossed_down:
                self.position.close()
            return
        if crossed_up and adx > self.ADX_MIN:
            stop = close - self.STOP_ATR_MULT * atr
            fraction = _risk_sized_fraction(close, stop, RISK_PER_TRADE, MAX_POSITION_FRACTION)
            if fraction:
                self.buy(size=fraction, sl=stop)


# ---------- 6. CCI 평균회귀 ----------

def add_cci_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["CCI"] = ta.cci(out["High"], out["Low"], out["Close"], length=20)
    out["SMA200"] = ta.sma(out["Close"], length=200)
    out["ATR14"] = ta.atr(out["High"], out["Low"], out["Close"], length=14)
    return out


class CciMeanReversionStrategy(Strategy):
    WARMUP_BARS = 205
    ENTRY_LEVEL = -100
    EXIT_LEVEL = 0
    STOP_ATR_MULT = 2.0

    def init(self):
        pass

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return
        cci = self.data.CCI[-1]
        close, atr, sma200 = self.data.Close[-1], self.data.ATR14[-1], self.data.SMA200[-1]

        if self.position:
            if cci > self.EXIT_LEVEL:
                self.position.close()
            return
        if cci < self.ENTRY_LEVEL and close > sma200:
            stop = close - self.STOP_ATR_MULT * atr
            fraction = _risk_sized_fraction(close, stop, RISK_PER_TRADE, MAX_POSITION_FRACTION)
            if fraction:
                self.buy(size=fraction, sl=stop)


# ---------- 7. 파라볼릭 SAR (라인 자체가 트레일링 스톱) ----------

def add_psar_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    psar = ta.psar(out["High"], out["Low"], out["Close"])
    long_col = _first_matching(psar, "PSARl_")
    short_col = _first_matching(psar, "PSARs_")
    out["PSAR"] = long_col.fillna(short_col)
    out["PSAR_BULLISH"] = long_col.notna()
    return out


class ParabolicSarStrategy(Strategy):
    WARMUP_BARS = 20

    def init(self):
        pass

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return
        close, psar, bullish = self.data.Close[-1], self.data.PSAR[-1], self.data.PSAR_BULLISH[-1]

        if self.position:
            for trade in self.trades:
                if trade.sl is None or (bullish and psar > trade.sl):
                    trade.sl = psar
            if not bullish:
                self.position.close()
            return
        if bullish and close > psar:
            fraction = _risk_sized_fraction(close, psar, RISK_PER_TRADE, MAX_POSITION_FRACTION)
            if fraction:
                self.buy(size=fraction, sl=psar)


# ---------- 8. 켈트너 채널 상단 돌파 ----------

def add_keltner_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    kc = ta.kc(out["High"], out["Low"], out["Close"], length=20, scalar=2)
    out["KC_UPPER"] = _first_matching(kc, "KCUe_")
    out["KC_LOWER"] = _first_matching(kc, "KCLe_")
    out["ATR14"] = ta.atr(out["High"], out["Low"], out["Close"], length=14)
    return out


class KeltnerBreakoutStrategy(Strategy):
    WARMUP_BARS = 30
    STOP_ATR_MULT = 2.0

    def init(self):
        pass

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return
        close, upper, lower, atr = self.data.Close[-1], self.data.KC_UPPER[-1], self.data.KC_LOWER[-1], self.data.ATR14[-1]

        if self.position:
            if close < lower:
                self.position.close()
            return
        if close > upper:
            stop = close - self.STOP_ATR_MULT * atr
            fraction = _risk_sized_fraction(close, stop, RISK_PER_TRADE, MAX_POSITION_FRACTION)
            if fraction:
                self.buy(size=fraction, sl=stop)


# ---------- 9. TEMA9/21 크로스 (EMA보다 지연 적은 추세추종) ----------

def add_tema_cross_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["TEMA9"] = ta.tema(out["Close"], length=9)
    out["TEMA21"] = ta.tema(out["Close"], length=21)
    out["SMA200"] = ta.sma(out["Close"], length=200)
    out["ATR14"] = ta.atr(out["High"], out["Low"], out["Close"], length=14)
    return out


class TemaTrendStrategy(Strategy):
    WARMUP_BARS = 205
    STOP_ATR_MULT = 2.0

    def init(self):
        pass

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return
        t9, t9_prev = self.data.TEMA9[-1], self.data.TEMA9[-2]
        t21, t21_prev = self.data.TEMA21[-1], self.data.TEMA21[-2]
        close, atr, sma200 = self.data.Close[-1], self.data.ATR14[-1], self.data.SMA200[-1]
        crossed_up = t9_prev <= t21_prev and t9 > t21
        crossed_down = t9_prev >= t21_prev and t9 < t21

        if self.position:
            if crossed_down:
                self.position.close()
            return
        if crossed_up and close > sma200:
            stop = close - self.STOP_ATR_MULT * atr
            fraction = _risk_sized_fraction(close, stop, RISK_PER_TRADE, MAX_POSITION_FRACTION)
            if fraction:
                self.buy(size=fraction, sl=stop)


# ---------- 10. 어썸 오실레이터 제로크로스 ----------

def add_awesome_osc_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["AO"] = ta.ao(out["High"], out["Low"])
    out["ATR14"] = ta.atr(out["High"], out["Low"], out["Close"], length=14)
    return out


class AwesomeOscillatorStrategy(Strategy):
    WARMUP_BARS = 40
    STOP_ATR_MULT = 2.0

    def init(self):
        pass

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return
        ao, ao_prev = self.data.AO[-1], self.data.AO[-2]
        close, atr = self.data.Close[-1], self.data.ATR14[-1]
        crossed_up = ao_prev <= 0 and ao > 0
        crossed_down = ao_prev >= 0 and ao < 0

        if self.position:
            if crossed_down:
                self.position.close()
            return
        if crossed_up:
            stop = close - self.STOP_ATR_MULT * atr
            fraction = _risk_sized_fraction(close, stop, RISK_PER_TRADE, MAX_POSITION_FRACTION)
            if fraction:
                self.buy(size=fraction, sl=stop)


# ---------- 11. ROC 모멘텀 ----------

def add_roc_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["ROC"] = ta.roc(out["Close"], length=12)
    out["SMA200"] = ta.sma(out["Close"], length=200)
    out["ATR14"] = ta.atr(out["High"], out["Low"], out["Close"], length=14)
    return out


class RocMomentumStrategy(Strategy):
    WARMUP_BARS = 205
    ENTRY_LEVEL = 5.0
    STOP_ATR_MULT = 2.0

    def init(self):
        pass

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return
        roc = self.data.ROC[-1]
        close, atr, sma200 = self.data.Close[-1], self.data.ATR14[-1], self.data.SMA200[-1]

        if self.position:
            if roc < 0:
                self.position.close()
            return
        if roc > self.ENTRY_LEVEL and close > sma200:
            stop = close - self.STOP_ATR_MULT * atr
            fraction = _risk_sized_fraction(close, stop, RISK_PER_TRADE, MAX_POSITION_FRACTION)
            if fraction:
                self.buy(size=fraction, sl=stop)


# ---------- 12. OBV 추세 확인 ----------

def add_obv_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    obv = ta.obv(out["Close"], out["Volume"])
    out["OBV"] = obv
    out["OBV_SMA20"] = obv.rolling(20).mean()
    out["SMA50"] = ta.sma(out["Close"], length=50)
    out["ATR14"] = ta.atr(out["High"], out["Low"], out["Close"], length=14)
    return out


class ObvTrendStrategy(Strategy):
    WARMUP_BARS = 55
    STOP_ATR_MULT = 2.0

    def init(self):
        pass

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return
        obv, obv_sma = self.data.OBV[-1], self.data.OBV_SMA20[-1]
        close, atr, sma50 = self.data.Close[-1], self.data.ATR14[-1], self.data.SMA50[-1]

        if self.position:
            if obv < obv_sma or close < sma50:
                self.position.close()
            return
        if obv > obv_sma and close > sma50:
            stop = close - self.STOP_ATR_MULT * atr
            fraction = _risk_sized_fraction(close, stop, RISK_PER_TRADE, MAX_POSITION_FRACTION)
            if fraction:
                self.buy(size=fraction, sl=stop)


# ---------- 13. 볼린저밴드 상단 돌파 (평균회귀 아닌 모멘텀 돌파) ----------

def add_bb_breakout_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    bb = ta.bbands(out["Close"], length=20, std=2)
    out["BB_UPPER"] = _first_matching(bb, "BBU_")
    out["BB_MID"] = _first_matching(bb, "BBM_")
    out["ATR14"] = ta.atr(out["High"], out["Low"], out["Close"], length=14)
    return out


class BollingerBreakoutStrategy(Strategy):
    WARMUP_BARS = 30
    STOP_ATR_MULT = 2.0

    def init(self):
        pass

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return
        close, upper, mid, atr = self.data.Close[-1], self.data.BB_UPPER[-1], self.data.BB_MID[-1], self.data.ATR14[-1]

        if self.position:
            if close < mid:
                self.position.close()
            return
        if close > upper:
            stop = close - self.STOP_ATR_MULT * atr
            fraction = _risk_sized_fraction(close, stop, RISK_PER_TRADE, MAX_POSITION_FRACTION)
            if fraction:
                self.buy(size=fraction, sl=stop)


# ---------- 14. 거래량 확인 N일 신고가 돌파 ----------

def add_volume_spike_breakout_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["HIGH20"] = out["High"].rolling(20).max()
    out["VOL_MEDIAN20"] = out["Volume"].rolling(20).median()
    out["ATR14"] = ta.atr(out["High"], out["Low"], out["Close"], length=14)
    return out


class VolumeSpikeBreakoutStrategy(Strategy):
    WARMUP_BARS = 25
    VOLUME_MULTIPLIER = 1.5
    STOP_ATR_MULT = 2.0
    MAX_HOLD_DAYS = 20

    def init(self):
        self.entry_bar: int | None = None

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return
        close = self.data.Close[-1]
        high20_prev = self.data.HIGH20[-2]
        volume, vol_median = self.data.Volume[-1], self.data.VOL_MEDIAN20[-1]
        atr = self.data.ATR14[-1]

        if self.position:
            held = i - (self.entry_bar if self.entry_bar is not None else i)
            if held >= self.MAX_HOLD_DAYS:
                self.position.close()
                self.entry_bar = None
            return
        if close > high20_prev and volume > vol_median * self.VOLUME_MULTIPLIER:
            stop = close - self.STOP_ATR_MULT * atr
            fraction = _risk_sized_fraction(close, stop, RISK_PER_TRADE, MAX_POSITION_FRACTION)
            if fraction:
                self.buy(size=fraction, sl=stop)
                self.entry_bar = i


# ---------- 15. 일목균형표 전환선/기준선 크로스 (직접 계산, 라이브러리 API 의존 없음) ----------

def add_ichimoku_cross_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["TENKAN"] = (out["High"].rolling(9).max() + out["Low"].rolling(9).min()) / 2
    out["KIJUN"] = (out["High"].rolling(26).max() + out["Low"].rolling(26).min()) / 2
    out["ATR14"] = ta.atr(out["High"], out["Low"], out["Close"], length=14)
    return out


class IchimokuCrossStrategy(Strategy):
    WARMUP_BARS = 30
    STOP_ATR_MULT = 2.0

    def init(self):
        pass

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return
        tenkan, tenkan_prev = self.data.TENKAN[-1], self.data.TENKAN[-2]
        kijun, kijun_prev = self.data.KIJUN[-1], self.data.KIJUN[-2]
        close, atr = self.data.Close[-1], self.data.ATR14[-1]
        crossed_up = tenkan_prev <= kijun_prev and tenkan > kijun
        crossed_down = tenkan_prev >= kijun_prev and tenkan < kijun

        if self.position:
            if crossed_down:
                self.position.close()
            return
        if crossed_up and close > kijun:
            stop = close - self.STOP_ATR_MULT * atr
            fraction = _risk_sized_fraction(close, stop, RISK_PER_TRADE, MAX_POSITION_FRACTION)
            if fraction:
                self.buy(size=fraction, sl=stop)


# ---------- 16. 스토캐스틱 RSI 크로스 ----------

def add_stochrsi_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    srsi = ta.stochrsi(out["Close"], length=14)
    out["STOCHRSI_K"] = _first_matching(srsi, "STOCHRSIk_")
    out["STOCHRSI_D"] = _first_matching(srsi, "STOCHRSId_")
    out["SMA200"] = ta.sma(out["Close"], length=200)
    out["ATR14"] = ta.atr(out["High"], out["Low"], out["Close"], length=14)
    return out


class StochRsiStrategy(Strategy):
    WARMUP_BARS = 205
    OVERSOLD = 20
    STOP_ATR_MULT = 2.0

    def init(self):
        pass

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return
        k, k_prev = self.data.STOCHRSI_K[-1], self.data.STOCHRSI_K[-2]
        d, d_prev = self.data.STOCHRSI_D[-1], self.data.STOCHRSI_D[-2]
        close, atr, sma200 = self.data.Close[-1], self.data.ATR14[-1], self.data.SMA200[-1]
        crossed_up = k_prev <= d_prev and k > d and k < self.OVERSOLD
        crossed_down = k_prev >= d_prev and k < d

        if self.position:
            if crossed_down:
                self.position.close()
            return
        if crossed_up and close > sma200:
            stop = close - self.STOP_ATR_MULT * atr
            fraction = _risk_sized_fraction(close, stop, RISK_PER_TRADE, MAX_POSITION_FRACTION)
            if fraction:
                self.buy(size=fraction, sl=stop)


# ---------- 17. TRIX 모멘텀 제로크로스 ----------

def add_trix_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    trix = ta.trix(out["Close"], length=15)
    out["TRIX"] = _first_matching(trix, "TRIX_")
    out["ATR14"] = ta.atr(out["High"], out["Low"], out["Close"], length=14)
    return out


class TrixMomentumStrategy(Strategy):
    WARMUP_BARS = 50
    STOP_ATR_MULT = 2.0

    def init(self):
        pass

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return
        trix, trix_prev = self.data.TRIX[-1], self.data.TRIX[-2]
        close, atr = self.data.Close[-1], self.data.ATR14[-1]
        crossed_up = trix_prev <= 0 and trix > 0
        crossed_down = trix_prev >= 0 and trix < 0

        if self.position:
            if crossed_down:
                self.position.close()
            return
        if crossed_up:
            stop = close - self.STOP_ATR_MULT * atr
            fraction = _risk_sized_fraction(close, stop, RISK_PER_TRADE, MAX_POSITION_FRACTION)
            if fraction:
                self.buy(size=fraction, sl=stop)


# ---------- 18. 아룬 상단/하단 크로스 ----------

def add_aroon_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    aroon = ta.aroon(out["High"], out["Low"], length=25)
    out["AROON_UP"] = _first_matching(aroon, "AROONU_")
    out["AROON_DOWN"] = _first_matching(aroon, "AROOND_")
    out["ATR14"] = ta.atr(out["High"], out["Low"], out["Close"], length=14)
    return out


class AroonCrossStrategy(Strategy):
    WARMUP_BARS = 30
    STRONG_TREND = 70
    STOP_ATR_MULT = 2.0

    def init(self):
        pass

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return
        up, up_prev = self.data.AROON_UP[-1], self.data.AROON_UP[-2]
        down, down_prev = self.data.AROON_DOWN[-1], self.data.AROON_DOWN[-2]
        close, atr = self.data.Close[-1], self.data.ATR14[-1]
        crossed_up = up_prev <= down_prev and up > down
        crossed_down = up_prev >= down_prev and up < down

        if self.position:
            if crossed_down:
                self.position.close()
            return
        if crossed_up and up > self.STRONG_TREND:
            stop = close - self.STOP_ATR_MULT * atr
            fraction = _risk_sized_fraction(close, stop, RISK_PER_TRADE, MAX_POSITION_FRACTION)
            if fraction:
                self.buy(size=fraction, sl=stop)


# ---------- 19. 차이킨 자금흐름(CMF) 추세 확인 ----------

def add_cmf_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["CMF"] = ta.cmf(out["High"], out["Low"], out["Close"], out["Volume"], length=20)
    out["SMA50"] = ta.sma(out["Close"], length=50)
    out["ATR14"] = ta.atr(out["High"], out["Low"], out["Close"], length=14)
    return out


class ChaikinMoneyFlowStrategy(Strategy):
    WARMUP_BARS = 55
    ENTRY_LEVEL = 0.0
    STOP_ATR_MULT = 2.0

    def init(self):
        pass

    def next(self):
        i = len(self.data.Close) - 1
        if i < self.WARMUP_BARS:
            return
        cmf, cmf_prev = self.data.CMF[-1], self.data.CMF[-2]
        close, atr, sma50 = self.data.Close[-1], self.data.ATR14[-1], self.data.SMA50[-1]
        crossed_up = cmf_prev <= self.ENTRY_LEVEL and cmf > self.ENTRY_LEVEL

        if self.position:
            if cmf < self.ENTRY_LEVEL:
                self.position.close()
            return
        if crossed_up and close > sma50:
            stop = close - self.STOP_ATR_MULT * atr
            fraction = _risk_sized_fraction(close, stop, RISK_PER_TRADE, MAX_POSITION_FRACTION)
            if fraction:
                self.buy(size=fraction, sl=stop)
