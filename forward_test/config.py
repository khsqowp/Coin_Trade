"""Frozen configuration for the L5 4h combined forward test."""
SYMBOLS = ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT")
SIGNAL = dict(bb_depth_pct=0, bb_use="close", bb_window=4, stc_lag=4,
              stc_level=40, stc_lookback=5, stc_turn_type=1,
              stoch_cross_lag=4, stoch_level=30, stoch_min_cross_age=0)
MANAGEMENT = dict(n_adds=2, add_spacing_pct=2, add_size_mult=1.0,
                  atr_mult=4.0, sl_pct=None, tp_pct=2, max_hold_bars=48,
                  bb_mid_exit=False, opp_exit=False)
BOOKS = ("combined", "long_only", "short_only")
CAPITAL, BASE_NOTIONAL, FEE, SLIPPAGE = 10000.0, 1000.0, .0004, .0002
INTERVAL_MS = 14_400_000
BACKTEST_TRADES, BACKTEST_DAYS, BACKTEST_RETURN = 255, 1.9 * 365.25, 20.6
