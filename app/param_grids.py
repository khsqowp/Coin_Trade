"""Parameter grids for app/full_search.py's Backtest.optimize() sweeps — approach 1
(파라미터 최적화) from the strategy-improvement discussion. Kept separate from the
strategy classes so grids can be tuned without touching strategy logic. Only
thresholds/multipliers are swept here; indicator *periods* (ADX/RSI/EMA/ATR/BB length)
stay fixed in app/indicators.py and app/more_indicators.py — deliberately deferred.
"""
from __future__ import annotations

PARAM_GRIDS: dict[str, dict[str, list]] = {
    "regime_switch": {
        "TREND_ADX_MIN": [18, 20, 22, 25],
        "MEANREV_ADX_MAX": [14, 16, 18],
        "TREND_STOP_ATR": [1.0, 1.3, 1.6],
        "MEANREV_STOP_ATR": [0.8, 1.0, 1.2],
    },
    "ema_cross": {
        "STOP_PCT": [0.01, 0.02, 0.03, 0.04],
    },
    "rsi2_meanrev": {
        "RSI_ENTRY": [5, 10, 15, 20],
        "STOP_ATR_MULT": [1.0, 1.5, 2.0],
        "MAX_HOLD_BARS": [21, 42, 63],
    },
    "bb_macd_adx": {
        "ADX_ENTRY_MIN": [20, 25, 30, 35],
        "STOP_ATR_MULT": [1.5, 2.0, 2.5, 3.0],
    },
    "dual_thrust": {
        "K1": [0.5, 0.6, 0.71, 0.85, 1.0],
        "STOP_ATR_MULT": [1.5, 2.0, 2.5],
    },
    "donchian_trend": {
        "STOP_ATR_MULT": [1.5, 2.0, 2.5, 3.0],
        "TRAIL_ATR_MULT": [2.0, 2.5, 3.0, 3.5, 4.0],
    },
    "ma_pullback_swing": {
        "RSI_ENTRY": [25, 30, 35, 40, 45],
        "STOP_ATR_MULT": [1.5, 2.0, 2.5, 3.0],
    },
    "donchian_trend_fast": {
        "STOP_ATR_MULT": [1.5, 2.0, 2.5, 3.0],
        "TRAIL_ATR_MULT": [2.0, 2.5, 3.0, 3.5, 4.0],
    },
    "ma_pullback_fast": {
        "RSI_ENTRY": [35, 40, 45, 50, 55],
        "STOP_ATR_MULT": [1.5, 2.0, 2.5, 3.0],
    },
    "supertrend": {
        "VOLUME_CONFIRM_MULTIPLIER": [0.0, 1.0, 1.5, 2.0],
    },
    "range_reversion": {
        "ENTRY_BAND_PCT": [0.1, 0.15, 0.2, 0.25, 0.3],
        "EXIT_BAND_PCT": [0.4, 0.5, 0.6, 0.7],
        "STOP_ATR_MULT": [1.0, 1.5, 2.0],
    },
    "gap_momentum": {
        "ENTRY_GAP_PCT": [0.05, 0.07, 0.10, 0.15, 0.20],
        "TP_PCT": [0.03, 0.05, 0.08],
        "SL_PCT": [0.02, 0.03, 0.05],
        "MAX_HOLD_DAYS": [3, 5, 10],
    },
    # 추가 19개 전략 (app/broad_strategies.py) 그리드 — 대부분 STOP_ATR_MULT 단일 축으로 통일
    "golden_cross": {"STOP_ATR_MULT": [1.5, 2.0, 2.5, 3.0]},
    "macd_zero_cross": {"STOP_ATR_MULT": [1.5, 2.0, 2.5, 3.0]},
    "stochastic_cross": {"OVERSOLD": [15, 20, 25, 30]},
    "williams_r": {"ENTRY_LEVEL": [-90, -80, -70]},
    "adx_di_cross": {"ADX_MIN": [15, 20, 25, 30]},
    "cci_meanrev": {"ENTRY_LEVEL": [-150, -100, -80]},
    "keltner_breakout": {"STOP_ATR_MULT": [1.5, 2.0, 2.5, 3.0]},
    "tema_cross": {"STOP_ATR_MULT": [1.5, 2.0, 2.5, 3.0]},
    "awesome_osc": {"STOP_ATR_MULT": [1.5, 2.0, 2.5, 3.0]},
    "roc_momentum": {"ENTRY_LEVEL": [3.0, 5.0, 8.0, 10.0]},
    "obv_trend": {"STOP_ATR_MULT": [1.5, 2.0, 2.5, 3.0]},
    "bb_breakout": {"STOP_ATR_MULT": [1.5, 2.0, 2.5, 3.0]},
    "volume_spike_breakout": {"VOLUME_MULTIPLIER": [1.2, 1.5, 2.0, 2.5]},
    "ichimoku_cross": {"STOP_ATR_MULT": [1.5, 2.0, 2.5, 3.0]},
    "stochrsi_cross": {"OVERSOLD": [15, 20, 25, 30]},
    "trix_momentum": {"STOP_ATR_MULT": [1.5, 2.0, 2.5, 3.0]},
    "aroon_cross": {"STRONG_TREND": [60, 70, 80]},
    "cmf_trend": {"STOP_ATR_MULT": [1.5, 2.0, 2.5, 3.0]},
}

# Daily technical/ICT research: full Cartesian products, 32 + 16 configurations.
TECHNICAL_COARSE_GRID = {
    'timing': ['next_open', 'confirm_open'],
    'stop': ['none', 'pct10'],
    'tp': ['none', 'pct20'],
    'hold_days': [10, 20],
    'selection': ['rank', 'all'],
}
TECHNICAL_FINE_GRID = {
    'stop': ['atr1', 'atr2', 'pct5', 'structure'],
    'tp': ['none', 'pct30'],
    'hold_days': [5, 40],
}
