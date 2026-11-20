"""Frozen configurations for independent PAPER forward-test profiles."""
from dataclasses import dataclass
import os

SYMBOLS = ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT")
BOOKS = ("combined", "long_only", "short_only")


@dataclass(frozen=True)
class Profile:
    name: str
    interval: str
    interval_ms: int
    signal: dict
    management: dict
    capital: float
    base_notional: float
    fee: float
    slippage: float
    backtest: dict

    @property
    def db_path(self):
        return "/app/data/forward.db"


L5_4H = Profile(
    "l5_4h", "4h", 14_400_000,
    dict(bb_depth_pct=0, bb_use="close", bb_window=4, stc_lag=4,
         stc_level=40, stc_lookback=5, stc_turn_type=1,
         stoch_cross_lag=4, stoch_level=30, stoch_min_cross_age=0),
    dict(n_adds=2, add_spacing_pct=2, add_size_mult=1.0, atr_mult=4.0,
         sl_pct=None, tp_pct=2, max_hold_bars=48, bb_mid_exit=False, opp_exit=False),
    10000.0, 1000.0, .0004, .0002,
    dict(test_trades=255, test_days=1.9 * 365.25, test_return_pct=20.6),
)
L5_12H = Profile(
    "l5_12h", "12h", 43_200_000,
    dict(bb_depth_pct=0, bb_use="close", bb_window=4, stc_lag=4,
         stc_level=40, stc_lookback=5, stc_turn_type=1,
         stoch_cross_lag=4, stoch_level=25, stoch_min_cross_age=0),
    dict(n_adds=2, add_spacing_pct=2, add_size_mult=1.0, atr_mult=2.0,
         sl_pct=None, tp_pct=10, max_hold_bars=60, bb_mid_exit=False, opp_exit=False),
    10000.0, 1000.0, .0004, .0002,
    dict(train_return_pct=114.0, train_trades=174, test_return_pct=48.8,
         test_trades=78, walk_forward_return_pct=-10.2, plateau="FRAGILE"),
)
PROFILES = {p.name: p for p in (L5_4H, L5_12H)}


def get_profile(name=None):
    name = name or os.getenv("FORWARD_PROFILE", "l5_4h")
    try:
        return PROFILES[name]
    except KeyError as exc:
        raise ValueError(f"unknown FORWARD_PROFILE {name!r}; choose from {', '.join(PROFILES)}") from exc


# Preserve the existing module-level 4h API and defaults for callers/tests.
_DEFAULT = get_profile()
SIGNAL, MANAGEMENT = _DEFAULT.signal, _DEFAULT.management
INTERVAL, INTERVAL_MS = _DEFAULT.interval, _DEFAULT.interval_ms
CAPITAL, BASE_NOTIONAL, FEE, SLIPPAGE = _DEFAULT.capital, _DEFAULT.base_notional, _DEFAULT.fee, _DEFAULT.slippage
BACKTEST_TRADES = _DEFAULT.backtest["test_trades"]
BACKTEST_DAYS = _DEFAULT.backtest.get("test_days", 0.0)
BACKTEST_RETURN = _DEFAULT.backtest["test_return_pct"]
