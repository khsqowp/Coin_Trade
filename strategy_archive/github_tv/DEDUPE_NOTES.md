# Dedupe notes (near-duplicates merged or cross-referenced)

Merged into a single entry (variants described inside the entry):
- futures/FSupertrendStrategy.py -> ft_supertrend_triple (same triple-Supertrend up/down logic as Supertrend.py; futures version adds shorts).
- berlinguyinca/MACDStrategy_crossed.py -> ft_macd_cci (same MACD+CCI idea; crossed variant uses explicit crossovers and CCI -50/+100).
- berlinguyinca/Scalp.py + SmoothScalp.py + ReinforcedSmoothScalp.py -> ft_smooth_scalp (same EMA5-hi/lo + fast-stoch cross; variants add MFI/CCI/ higher-TF SMA50).
- berlinguyinca/EMASkipPump.py -> ft_reinforced_quickie (same dip-below-EMA/BB-low/min logic; EMASkipPump adds a volume cap).
- paulcpk RSIDirectionalWithTrendSlow.py -> pk_rsi_directional (same, RSI10/EMA600 params).
- 3Commas grid scripts (XRP, FIL, XLM, BTCUSDT.P, TWT, ENA, NOT, EURUSD, TRX; ids 3VLM19TH, 7cAVZopZ, 9ht1ea8N, BR74LOKo, NjylXb5x, RnrrRYP6, SBFz8vXU, kxCXnuU6, tgRchEEL) -> tv_3commas_grid. They differ only in hard-coded high/low/levels/dates. Matching "Grid Indicator" variants (study) were not archived separately.
- Other dip-buy ensembles in the Cluc/BinH family (ClucMay72018, BinHV45, BigZ04, CombinedBinHClucAndMADV9) are kept as separate entries because rules differ, but are conceptually one family (BB-lower capitulation + volume filters). Do not treat their backtests as independent evidence.

Cross-referenced but kept separate (different implementation or parameters):
- Dual Thrust: jesse_dual_thrust (anchor-TF, ATR stop, reversal) vs jst_dual_thrust (minute data, flat EOD, no stop).
- Turtle / Donchian: jesse_turtle (full Faith rules), jesse_donchian (20-bar, SMA200 filter), tv_turtle_donchian_20_10, tv_channel_100_50_atr, tv_breakout_hunter_60.
- MACD+EMA trend: jesse_macd_ema, pk_macd_trend, tv_macd_pullback_adx.
- Supertrend flips: tv_st_ema200_btc1h, tv_supertrend_regime_switch, tv_supertrend_regime_score, tv_triple_supertrend, ft_supertrend_triple.
- RSI(2)-style: jesse_rsi2, jesse_ifr2, wk_kama_rsi2.
- Golden cross: jesse_sma_crossover, tv_golden_cross_avwap_kit, tv_ema50_200_rsi. These overlap the already-owned TRX golden-cross strategy; keep only as baselines (priority 3).

Excluded as already owned (per brief): BB+Stoch+STC, momentum rotation, funding-arb, TRX golden-cross.

Not archived because not mechanically specifiable or not applicable: ML indicators (e.g. kNN grader, "Machine Learning: Volume-Weighted Mean Reversion", Volume Profile ML), options straddle (je-suis-tm; needs paid options data), freqtrade execution algos (TWAP, AlmgrenChriss), placeholder/example strategies (DoesNothing, CustomStoplossWithPSAR, Freqtrade_backtest_validation, BreakEven, FixedRiskRewardLoss, InformativeSample), pure visual/volume-profile/footprint indicators with no signal rule.
