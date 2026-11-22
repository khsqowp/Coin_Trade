# Slice 3 - harness issues (common/ was NOT modified; workarounds are in the plugins)

1. **Timestamps are dropped for train/test slices.** `common.protocol.evaluate()` does `iloc[...].reset_index(drop=True)` on both
   the 60% TRAIN and 40% TEST frames (protocol.py line ~69), so `signals()` receives a `RangeIndex` during evaluation although
   `check_no_lookahead` and the README contract use the UTC DatetimeIndex. Plugins that need clock time (UTC session rules in the
   7 session specs, UTC-day aggregation in four-lower-high-break-intraday, c4-upbit-larry-williams, jesse_dual_thrust) cannot work
   without it. Workaround: `_utc_index()` in those plugins restores the index from the cached `BTCUSDT_{15m,1h,4h}.parquet`
   index when `len(df)` equals the full / first-60% / last-40% length (all 9 cached symbols share an identical index at these
   timeframes; verified). Only timestamps are used. Side effect (a harness semantic, not fixable in plugins): TEST slices start
   cold, with no previous-day/previous-session history.
   Note: the 1h/15m cache has a real gap (2023-03-24 13:00 UTC missing hour; 15m also), so naive `date_range` reconstruction would
   shift all later timestamps; the reference-index approach preserves it.
2. **Flip/re-entry on the same bar is impossible.** After any exit fill the engine does `continue`, so a reverse entry can only
   fill one bar later (using the signal from the previous bar). Affects btc-adx-di-24-9, jesse_dual_thrust, turtle-system-2,
   crypto-15m-previous-candle-contrarian (only roughly every other interval can be traded). Session plugins avoid it through the
   `max_hold` exit at the close of the session's last bar.
3. **`max_hold` counts rows, not elapsed time.** Missing hourly bars (2023-03-24) can stretch a 12h session hold by one hour on that day.
4. **Stop-order (intrabar trigger) entries cannot be represented.** Only next-open fills exist; entries via buy/sell stops
   (four-lower-high, Larry Williams, Holy Grail, Turtle, Donchian) are approximated by the first bar that touches / closes beyond
   the trigger, filled at the following open (see each plugin's DEVIATIONS).
5. **Ladder add size is `base*add_size_mult` for every add** (no compounding), so tv_dca_rsi_martingale cannot reproduce x1.5^k sizing.
6. **Null-benchmark cost.** `protocol._null` sets entry flags with `r.iloc[...] = True` inside a python loop `4*n` times per repetition
   per symbol; for strategies with tens of thousands of test trades (crypto-15m-previous-candle-contrarian) this alone exceeds the
   600 s per-strategy timeout. Not fixable from a plugin without changing the strategy.
7. Minor: `--slice-file` entries must be spec JSON paths relative to `trading/`; a trailing `.` in the documented command line is a
   prose artefact and is rejected by argparse.
