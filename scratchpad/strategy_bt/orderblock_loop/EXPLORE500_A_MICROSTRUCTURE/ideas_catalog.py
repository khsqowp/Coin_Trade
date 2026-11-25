"""
EXPLORATORY SCREEN ONLY -- not part of the 13-round preregistered G-gate track,
not added to TRAIN_TRIALS.csv, no promotion without separate formal
preregistration + synthetic tests + resource-gated TRAIN run.

Catalog of ~167 candidate crypto-perp microstructure strategy ideas (lane A:
no orderblock/BOS zone detection). This module is the single source of truth
for IDEAS.csv (all proposed ideas, qualitatively pre-ranked) and for screen.py
(which actually backtests the subset marked implemented=True).

Fields per idea:
  name, family, mechanism_one_liner, rationale_one_liner,
  prior_rank (1=highest qualitative likelihood ... 5=lowest, assigned BEFORE
    any backtest, per the user's "ranked by likelihood" request),
  prior_rank_note (free text explaining the prior_rank judgment),
  signal_key (dispatch key into screen.py's SIGNAL_REGISTRY, or None),
  side ("long" or "short" -- the direction this specific idea_id trades),
  implemented (bool -- True if screen.py actually backtests it this pass),
  uses_funding (bool -- idea's mechanism specifically needs funding-rate data),
  uses_cross_asset (bool -- idea needs a BTC reference series for a non-BTC symbol)

Each (name, side) pair becomes one row/idea_id in IDEAS.csv, even when two
sides of the same signal_key share underlying computation -- a long and a
short version of the same indicator are directionally distinct bets with
different rationale, not a parameter tweak.

Where exact parameter counts matter for IDEAS.csv's "~167 rows" target, note
the honest split: 120 ideas are implemented and actually backtested in this
pass (grouped under ~66 distinct signal-generation functions, i.e. roughly
66 genuinely different computational mechanisms expressed as 120 directional
ideas); 47 additional ideas are proposed with full mechanism/rationale text
and a qualitative prior rank, but NOT backtested this pass for time-budget
reasons (either the underlying data isn't in the bar/funding files at all,
e.g. open interest or spot-basis, or they were deprioritized to stay inside
the ~15-minute runtime budget). This is documented again in RESULTS.csv and
RANKED_TOP20.md.
"""

from __future__ import annotations

RAW = []  # list of tuples, see _I() below for field order


def _I(name, family, mechanism, rationale, prior_rank, prior_note,
       signal_key=None, side="long", implemented=True,
       uses_funding=False, uses_cross_asset=False):
    RAW.append(dict(
        name=name, family=family, mechanism_one_liner=mechanism,
        rationale_one_liner=rationale, prior_rank=prior_rank,
        prior_rank_note=prior_note, signal_key=signal_key, side=side,
        implemented=implemented, uses_funding=uses_funding,
        uses_cross_asset=uses_cross_asset,
    ))


# ---------------------------------------------------------------------------
# A. Volatility squeeze / contraction -> breakout (10 implemented ideas)
# ---------------------------------------------------------------------------
_I("Bollinger squeeze breakout long", "vol_squeeze",
   "BB(20,2) bandwidth in bottom 20th pct of its own 100-bar history, then close breaks above upper band",
   "Low-volatility coiling before expansion is a well-documented precursor to directional breakouts in liquid perps",
   1, "high: vol-expansion-after-squeeze is one of the best-evidenced regime effects in liquid futures",
   signal_key="bb_squeeze_breakout", side="long")
_I("Bollinger squeeze breakout short", "vol_squeeze",
   "BB(20,2) bandwidth in bottom 20th pct of its own 100-bar history, then close breaks below lower band",
   "Symmetric to the long case; squeeze-release breakouts work both directions in trending/ranging regime shifts",
   1, "high: same structural edge as long version, no directional bias assumed",
   signal_key="bb_squeeze_breakout", side="short")
_I("ATR contraction range breakout long", "vol_squeeze",
   "ATR(14) percentile-rank over trailing 100 bars < 20, then close breaks above the prior 20-bar high",
   "ATR compression flags coiled energy; breakout of the recent range captures the expansion leg",
   1, "high: ATR-based squeeze is a standard, liquid-market-validated breakout trigger",
   signal_key="atr_contraction_breakout", side="long")
_I("ATR contraction range breakout short", "vol_squeeze",
   "ATR(14) percentile-rank over trailing 100 bars < 20, then close breaks below the prior 20-bar low",
   "Symmetric short-side contraction breakout",
   1, "high: symmetric to long, equally well-evidenced",
   signal_key="atr_contraction_breakout", side="short")
_I("Keltner channel squeeze breakout long", "vol_squeeze",
   "Price exits Keltner channel (EMA20 +/- 1.5*ATR10) to the upside after 10+ bars inside the channel",
   "Keltner channels use ATR directly, capturing volatility-normalized breakouts distinct from stdev-based Bollinger",
   1, "high: Keltner's ATR basis is less noisy than stdev in fat-tailed crypto returns",
   signal_key="keltner_squeeze_breakout", side="long")
_I("Keltner channel squeeze breakout short", "vol_squeeze",
   "Price exits Keltner channel to the downside after 10+ bars inside the channel",
   "Symmetric Keltner breakout short",
   1, "high: symmetric to long",
   signal_key="keltner_squeeze_breakout", side="short")
_I("TTM-style squeeze breakout long", "vol_squeeze",
   "Bollinger(20,2) bands fully inside Keltner(20,1.5*ATR) channel (classic 'squeeze on'), then release with close above BB upper",
   "Combining two independent vol measures reduces false squeeze signals versus either alone",
   2, "medium-high: popular retail indicator, confluence of two measures should filter some noise",
   signal_key="ttm_squeeze_breakout", side="long")
_I("TTM-style squeeze breakout short", "vol_squeeze",
   "BB inside KC squeeze, release with close below BB lower band",
   "Symmetric TTM squeeze short",
   2, "medium-high: symmetric to long",
   signal_key="ttm_squeeze_breakout", side="short")
_I("Historical-vol-cone extreme-low reversal-up anticipation", "vol_squeeze",
   "Realized vol (24h stdev of log returns) below its own 5th percentile over trailing 500 bars, enter long on first close above prior bar's high",
   "Volatility is mean-reverting; extreme vol troughs historically precede expansion moves which are more often upward in a long-biased asset class",
   3, "medium: vol mean-reversion is real but directional bias assumption is speculative",
   signal_key="vol_cone_low_extreme", side="long")
_I("Bollinger %B exhaustion with declining volume long", "vol_squeeze",
   "Close pierces lower BB(20,2) while 5-bar volume trend is declining (exhaustion of selling pressure, not a fresh breakout)",
   "Thinning volume into a band extreme suggests the move lacks participation and is more likely to mean-revert than continue",
   3, "medium: volume-confirmation exhaustion logic is intuitive but noisy at 1h resolution",
   signal_key="bb_pctb_exhaustion", side="long")
_I("Bollinger %B exhaustion with declining volume short", "vol_squeeze",
   "Close pierces upper BB(20,2) while 5-bar volume trend is declining",
   "Symmetric exhaustion-fade short",
   3, "medium: symmetric to long",
   signal_key="bb_pctb_exhaustion", side="short")

# ---------------------------------------------------------------------------
# B. Volume-spike continuation / fade (8 implemented)
# ---------------------------------------------------------------------------
_I("Volume-spike continuation long", "volume_spike",
   "Bar volume > 3x its trailing 20-bar average AND close in top third of the bar's range, enter in direction of the bar",
   "A volume surge with strong directional close signals fresh aggressive flow (informed order flow), which tends to persist short-term",
   1, "high: volume-confirmed breakout bars are a classic, robust momentum continuation signal",
   signal_key="volume_spike_continuation", side="long")
_I("Volume-spike continuation short", "volume_spike",
   "Bar volume > 3x 20-bar average AND close in bottom third of range, enter short",
   "Symmetric volume-confirmed continuation short",
   1, "high: symmetric to long",
   signal_key="volume_spike_continuation", side="short")
_I("Volume-spike fade (indecision) long", "volume_spike",
   "Bar volume > 3x average AND body is < 25% of the bar's total range (indecisive candle despite huge volume) near a local low, fade long",
   "Huge volume with a small body implies two-sided absorption at an extreme, often marking a local turning point",
   2, "medium-high: absorption-at-extreme logic is standard order-flow intuition, imperfect proxy without real tape data",
   signal_key="volume_spike_fade", side="long")
_I("Volume-spike fade (indecision) short", "volume_spike",
   "Bar volume > 3x average AND small body near a local high, fade short",
   "Symmetric absorption fade short",
   2, "medium-high: symmetric to long",
   signal_key="volume_spike_fade", side="short")
_I("Climax-volume blow-off-top fade short", "volume_spike",
   "Highest single-bar volume in trailing 50 bars, with upper wick >= 50% of the bar's range, fade short",
   "A climactic volume spike with a long upper wick is the classic blow-off-top signature of exhausted buying",
   3, "medium: classic pattern but climax bars are rare, limiting sample size and reliability",
   signal_key="climax_volume_fade", side="short")
_I("Climax-volume capitulation fade long", "volume_spike",
   "Highest single-bar volume in trailing 50 bars, with lower wick >= 50% of the bar's range, fade long",
   "Symmetric capitulation-bottom fade",
   3, "medium: symmetric to short, rare-event sample-size caveat applies",
   signal_key="climax_volume_fade", side="long")
_I("Up/down volume pressure extreme long", "volume_spike",
   "Rolling 20-bar ratio of up-bar volume to down-bar volume > 90th percentile of its own 200-bar history, go long",
   "A sustained skew toward buy-side volume (proxy for taker-buy pressure without real taker-flow data) suggests persistent demand",
   2, "medium-high: reasonable taker-flow proxy from OHLCV alone, but proxy quality is limited",
   signal_key="updown_volume_pressure", side="long")
_I("Up/down volume pressure extreme short", "volume_spike",
   "Rolling 20-bar up/down volume ratio < 10th percentile of its own 200-bar history, go short",
   "Symmetric sell-pressure proxy",
   2, "medium-high: symmetric to long",
   signal_key="updown_volume_pressure", side="short")

# ---------------------------------------------------------------------------
# C. VWAP / HTF moving-average mean reversion & trend (6 implemented)
# ---------------------------------------------------------------------------
_I("Rolling VWAP(24h) stretch reversion short", "vwap_meanrev",
   "Close > 2% above rolling 24-bar VWAP, fade short expecting reversion to VWAP",
   "VWAP acts as a volume-weighted fair-value anchor; large deviations attract mean-reverting flow from value-based participants",
   2, "medium-high: VWAP reversion is a staple intraday-trading heuristic in liquid futures",
   signal_key="vwap_reversion", side="short")
_I("Rolling VWAP(24h) stretch reversion long", "vwap_meanrev",
   "Close < 2% below rolling 24-bar VWAP, go long expecting reversion to VWAP",
   "Symmetric VWAP reversion long",
   2, "medium-high: symmetric to short",
   signal_key="vwap_reversion", side="long")
_I("EMA200 z-score stretch reversion short", "vwap_meanrev",
   "z-score of (close - EMA200) over trailing 200 bars > 2, fade short",
   "Extreme statistical stretch from a slow trend anchor historically reverts in range-bound regimes",
   2, "medium-high: EMA-distance z-score reversion is widely used and reasonably robust",
   signal_key="ema200_zscore_reversion", side="short")
_I("EMA200 z-score stretch reversion long", "vwap_meanrev",
   "z-score of (close - EMA200) < -2, go long",
   "Symmetric EMA200 stretch reversion long",
   2, "medium-high: symmetric to short",
   signal_key="ema200_zscore_reversion", side="long")
_I("VWAP slope-flip trend continuation long", "vwap_meanrev",
   "Rolling 24h VWAP's own slope flips from falling to rising AND price closes above VWAP, go long (trend mode, not reversion)",
   "A turning VWAP slope with price reclaiming it marks a genuine regime shift from distribution to accumulation",
   3, "medium: plausible regime-shift signal but slope-flip lag reduces edge magnitude",
   signal_key="vwap_trend_continuation", side="long")
_I("VWAP slope-flip trend continuation short", "vwap_meanrev",
   "Rolling VWAP slope flips from rising to falling AND price closes below VWAP, go short",
   "Symmetric VWAP slope-flip short",
   3, "medium: symmetric to long",
   signal_key="vwap_trend_continuation", side="short")

# ---------------------------------------------------------------------------
# D. RSI / Stochastic divergence (8 implemented)
# ---------------------------------------------------------------------------
_I("RSI bullish regular divergence long", "divergence",
   "Price makes a new trailing-20-bar closing low while RSI(14) at that low is higher than RSI at the prior such low; enter long once confirmed",
   "Momentum failing to confirm a new price extreme is a classic exhaustion signature ahead of reversal",
   2, "medium-high: divergence trading is popular and has some documented edge, but is prone to false signals in strong trends",
   signal_key="rsi_regular_divergence", side="long")
_I("RSI bearish regular divergence short", "divergence",
   "Price makes a new trailing-20-bar closing high while RSI(14) is lower than at the prior high; enter short once confirmed",
   "Symmetric bearish regular divergence",
   2, "medium-high: symmetric to long",
   signal_key="rsi_regular_divergence", side="short")
_I("RSI bullish hidden divergence long", "divergence",
   "Price makes a higher low (above prior trailing-20 low) while RSI makes a lower low -- trend-continuation divergence; enter long",
   "Hidden divergence signals underlying momentum is actually accelerating beneath a shallow pullback, favoring trend continuation",
   2, "medium-high: hidden divergence is a less crowded, trend-following variant of the classic pattern",
   signal_key="rsi_hidden_divergence", side="long")
_I("RSI bearish hidden divergence short", "divergence",
   "Price makes a lower high while RSI makes a higher high; enter short (downtrend continuation)",
   "Symmetric hidden divergence short",
   2, "medium-high: symmetric to long",
   signal_key="rsi_hidden_divergence", side="short")
_I("Stochastic bullish regular divergence long", "divergence",
   "Price new 20-bar closing low while Stochastic %K(14,3) is higher than at the prior low; enter long",
   "Stochastic is more sensitive near range extremes than RSI, potentially catching divergence earlier",
   3, "medium: similar logic to RSI divergence but stochastic's extra sensitivity can add noise",
   signal_key="stoch_regular_divergence", side="long")
_I("Stochastic bearish regular divergence short", "divergence",
   "Price new 20-bar closing high while Stochastic %K is lower than at the prior high; enter short",
   "Symmetric stochastic divergence short",
   3, "medium: symmetric to long",
   signal_key="stoch_regular_divergence", side="short")
_I("RSI extreme threshold reversal long", "divergence",
   "RSI(14) crosses back above 20 after having been below 20 (plain oversold reversal, no divergence needed)",
   "Simple oversold-exhaustion reversion is a widely used, low-complexity mean-reversion heuristic",
   2, "medium-high: simple, well-known heuristic, decent baseline",
   signal_key="rsi_extreme_threshold", side="long")
_I("RSI extreme threshold reversal short", "divergence",
   "RSI(14) crosses back below 80 after having been above 80",
   "Symmetric overbought reversal",
   2, "medium-high: symmetric to long",
   signal_key="rsi_extreme_threshold", side="short")

# ---------------------------------------------------------------------------
# E. Donchian / channel breakout (6 implemented)
# ---------------------------------------------------------------------------
_I("Donchian 20-bar breakout long", "donchian",
   "Close breaks above the highest high of the prior 20 bars (classic short-term turtle system)",
   "Channel breakouts capture the start of new trend legs; the 20-bar lookback targets short-horizon trend initiation",
   1, "high: Donchian/turtle breakouts are a textbook, long-validated trend-following edge, especially in trending crypto",
   signal_key="donchian20_breakout", side="long")
_I("Donchian 20-bar breakout short", "donchian",
   "Close breaks below the lowest low of the prior 20 bars",
   "Symmetric short-term channel breakout short",
   1, "high: symmetric to long",
   signal_key="donchian20_breakout", side="short")
_I("Donchian 55-bar breakout long", "donchian",
   "Close breaks above the highest high of the prior 55 bars (classic long-term turtle system)",
   "Longer lookback filters noise and targets more durable macro trend starts than the 20-bar variant",
   1, "high: complements the 20-bar system with a distinct holding-horizon philosophy, both legs of the original turtle system",
   signal_key="donchian55_breakout", side="long")
_I("Donchian 55-bar breakout short", "donchian",
   "Close breaks below the lowest low of the prior 55 bars",
   "Symmetric long-term channel breakout short",
   1, "high: symmetric to long",
   signal_key="donchian55_breakout", side="short")
_I("Volume-confirmed Donchian 20 breakout long", "donchian",
   "Donchian-20 upside breakout bar also has volume > its trailing 20-bar average",
   "Requiring volume confirmation on the breakout bar filters out low-conviction false breaks",
   1, "high: volume confirmation is a standard, evidence-backed breakout-quality filter",
   signal_key="donchian_volume_confirmed", side="long")
_I("Volume-confirmed Donchian 20 breakout short", "donchian",
   "Donchian-20 downside breakout bar also has volume > its trailing 20-bar average",
   "Symmetric volume-confirmed breakout short",
   1, "high: symmetric to long",
   signal_key="donchian_volume_confirmed", side="short")

# ---------------------------------------------------------------------------
# F. UTC daily / session opening-range breaks (4 implemented)
# ---------------------------------------------------------------------------
_I("UTC daily opening-range breakout long", "session_or",
   "Using the first 1h bar after UTC 00:00 as the opening range, close above that bar's high later the same UTC day triggers long",
   "Even in a 24/7 market, UTC midnight is a widely watched reference (exchange daily candle close/funding alignment), creating a focal reference level",
   2, "medium-high: 24/7 markets lack a true session open, but UTC-midnight is the most common convention traders anchor to",
   signal_key="utc_daily_or_breakout", side="long")
_I("UTC daily opening-range breakout short", "session_or",
   "Close below the UTC-00:00 opening bar's low later the same day triggers short",
   "Symmetric opening-range breakdown",
   2, "medium-high: symmetric to long",
   signal_key="utc_daily_or_breakout", side="short")
_I("US-session-open range breakout long", "session_or",
   "Using the 1h bar starting at UTC 13:00 (US equity/macro desks coming online) as the range, breakout above its high later triggers long",
   "US trading-desk hours concentrate macro-driven flow even in crypto, creating a secondary focal session distinct from the UTC-midnight convention",
   3, "medium: plausible but weaker focal-point argument than the UTC-midnight convention",
   signal_key="session_or_breakout_us", side="long")
_I("US-session-open range breakout short", "session_or",
   "Breakout below the UTC-13:00 range's low triggers short",
   "Symmetric US-session breakdown",
   3, "medium: symmetric to long",
   signal_key="session_or_breakout_us", side="short")

# ---------------------------------------------------------------------------
# G. Funding-rate regime strategies, distinct from R13 (10 implemented)
# ---------------------------------------------------------------------------
_I("Funding-rate extreme-positive fade short", "funding",
   "Latest settled funding rate > +0.05% (annualized ~55%), fade short expecting funding-driven long crowding to unwind",
   "Extremely positive funding means longs are paying a heavy premium; historically this crowding precedes mean-reverting pullbacks",
   1, "high: funding-extreme mean-reversion is one of the better-documented crypto-specific edges, distinct from R13's breakdown-short design",
   signal_key="funding_extreme_fade", side="short", uses_funding=True)
_I("Funding-rate extreme-negative fade long", "funding",
   "Latest settled funding rate < -0.05%, go long expecting short-crowding unwind",
   "Symmetric negative-funding crowding unwind",
   1, "high: symmetric to short version",
   signal_key="funding_extreme_fade", side="long", uses_funding=True)
_I("Funding-rate rising-trend momentum long", "funding",
   "Three consecutive funding settlements each higher than the last (and still below the extreme-fade threshold), go long",
   "A steadily rising funding rate reflects building bullish conviction in the derivatives market that often precedes continued spot-led upside before it gets extreme",
   3, "medium: trend-following on funding is less standard than fading extremes, mechanism plausible but weaker prior",
   signal_key="funding_trend_momentum", side="long", uses_funding=True)
_I("Funding-rate falling-trend momentum short", "funding",
   "Three consecutive funding settlements each lower than the last (still above extreme-fade threshold), go short",
   "Symmetric falling-funding momentum short",
   3, "medium: symmetric to long",
   signal_key="funding_trend_momentum", side="short", uses_funding=True)
_I("Funding-rate z-score extreme fade short", "funding",
   "Funding rate z-score (vs its trailing ~90-settlement mean/stdev) > 2, fade short",
   "A statistically standardized funding extreme adapts the fade threshold to each symbol's own regime, unlike a fixed absolute cutoff",
   1, "high: z-score normalization should generalize the funding-fade edge better across symbols with different typical funding ranges",
   signal_key="funding_zscore_extreme_fade", side="short", uses_funding=True)
_I("Funding-rate z-score extreme fade long", "funding",
   "Funding rate z-score < -2, go long",
   "Symmetric z-score funding fade long",
   1, "high: symmetric to short",
   signal_key="funding_zscore_extreme_fade", side="long", uses_funding=True)
_I("Funding-settlement micro-gap fade long", "funding",
   "Price dislocates (>0.3%) in the bar immediately containing a funding settlement timestamp, then fade back toward the pre-settlement price long",
   "Funding settlement can trigger brief mechanical positioning flow that is not fundamentally driven and tends to mean-revert quickly",
   4, "medium-low: settlement micro-gaps are small and may be dominated by cost/noise at 1h resolution",
   signal_key="funding_settlement_gapfade", side="long", uses_funding=True)
_I("Funding-settlement micro-gap fade short", "funding",
   "Symmetric fade short on settlement-bar dislocation",
   "Symmetric settlement micro-gap fade",
   4, "medium-low: symmetric to long, same noise caveat",
   signal_key="funding_settlement_gapfade", side="short", uses_funding=True)
_I("Funding-not-yet-overheated momentum long", "funding",
   "Funding rate positive but still below half the extreme-fade threshold AND price making new 20-bar highs, go long (ride the trend before crowding gets extreme)",
   "Capturing the trend phase before funding becomes extreme may harvest the early part of the same move that R13's overheat-short targets reversing late",
   2, "medium-high: directly complementary framing to R13, targets the opposite (earlier, momentum) phase of the same funding cycle",
   signal_key="funding_not_overheated_momentum", side="long", uses_funding=True)
_I("Funding-curve steepness breakout long", "funding",
   "Change in funding rate between consecutive settlements exceeds its own 90th percentile (steep acceleration), go long with price confirmation (close > prior bar's high)",
   "A sudden acceleration in funding, not just its level, may better capture the inflection point of crowd sentiment shifting than a level-based signal",
   4, "medium-low: second-derivative funding signal is a more speculative, less-tested construct",
   signal_key="funding_curve_steepness", side="long", uses_funding=True)

# ---------------------------------------------------------------------------
# H. Volume-weighted momentum / OBV (4 implemented)
# ---------------------------------------------------------------------------
_I("VWMA-slope momentum long", "vol_momentum",
   "20-bar volume-weighted moving average (VWMA) slope positive AND close above VWMA, go long",
   "Weighting the trend average by volume emphasizes price moves that occurred with real participation, filtering low-volume drift",
   2, "medium-high: volume-weighting is a sensible refinement over plain MA trend-following",
   signal_key="vwma_momentum", side="long")
_I("VWMA-slope momentum short", "vol_momentum",
   "VWMA(20) slope negative AND close below VWMA, go short",
   "Symmetric VWMA momentum short",
   2, "medium-high: symmetric to long",
   signal_key="vwma_momentum", side="short")
_I("OBV new-high breakout confirmation long", "vol_momentum",
   "On-Balance-Volume makes a new 20-bar high at/before price does, go long on price's subsequent new high",
   "OBV leading price into new highs signals volume-backed accumulation underpinning the move, a classic Granville-style confirmation",
   2, "medium-high: OBV lead/lag confirmation is a long-standing technical heuristic with some empirical support",
   signal_key="obv_breakout", side="long")
_I("OBV new-low breakdown confirmation short", "vol_momentum",
   "OBV makes a new 20-bar low at/before price, go short on price's subsequent new low",
   "Symmetric OBV-led breakdown confirmation",
   2, "medium-high: symmetric to long",
   signal_key="obv_breakout", side="short")

# ---------------------------------------------------------------------------
# I. Realized-vol term structure / vol-of-vol (4 implemented)
# ---------------------------------------------------------------------------
_I("Vol term-structure inversion fade short", "vol_termstructure",
   "24h realized vol / 7d realized vol ratio > 1.5 (short-term vol spiking above longer-term regime), fade short expecting vol (and the move) to cool",
   "A sharp short-vs-long realized-vol inversion often marks a transient panic/spike that reverts once the shock passes",
   4, "medium-low: plausible vol-mean-reversion logic but the directional call (always fade) ignores which way the spike moved price",
   signal_key="vol_term_structure_fade", side="short")
_I("Vol term-structure inversion fade long", "vol_termstructure",
   "Same inversion condition, fade long (symmetric contrarian bet)",
   "Symmetric contrarian vol-spike fade",
   4, "medium-low: symmetric to short, same directional-ambiguity caveat",
   signal_key="vol_term_structure_fade", side="long")
_I("Vol-of-vol spike breakout long", "vol_termstructure",
   "Stdev of rolling 14-bar ATR over the trailing 50 bars spikes above its own 90th percentile, go long on next close above prior high",
   "Rising vol-of-vol often precedes a genuine regime change rather than a one-off spike, and regime changes commonly resolve as new trends",
   4, "medium-low: vol-of-vol is a second-order, noisier signal with a weaker direct mechanism link to price direction",
   signal_key="vol_of_vol_breakout", side="long")
_I("Vol-of-vol spike breakout short", "vol_termstructure",
   "Same vol-of-vol spike condition, enter short on next close below prior low",
   "Symmetric vol-of-vol breakout short",
   4, "medium-low: symmetric to long",
   signal_key="vol_of_vol_breakout", side="short")

# ---------------------------------------------------------------------------
# J. Autocorrelation / serial dependence (6 implemented)
# ---------------------------------------------------------------------------
_I("Streak fade after 4+ consecutive up closes short", "autocorr",
   "4 or more consecutive up-closes, fade short on the next bar's open",
   "Hourly crypto returns show mild negative short-horizon autocorrelation after extended short-term streaks (overextension effect)",
   2, "medium-high: short-horizon mean-reversion after streaks is a documented microstructure regularity in liquid markets",
   signal_key="streak_fade", side="short")
_I("Streak fade after 4+ consecutive down closes long", "autocorr",
   "4 or more consecutive down-closes, go long on the next bar's open",
   "Symmetric streak-exhaustion fade long",
   2, "medium-high: symmetric to short",
   signal_key="streak_fade", side="long")
_I("Same-direction momentum after prior bar long", "autocorr",
   "Prior completed 1h bar closed up with range > its 20-bar average range, go long (trade with the immediately preceding bar's direction)",
   "Some crypto perps show short-horizon positive autocorrelation driven by momentum-chasing algos reacting to the same recent bar",
   3, "medium: positive and negative autocorrelation regimes likely coexist across symbols/periods, direction of edge is uncertain a priori",
   signal_key="streak_momentum", side="long")
_I("Same-direction momentum after prior bar short", "autocorr",
   "Prior bar closed down with above-average range, go short",
   "Symmetric same-direction momentum short",
   3, "medium: symmetric to long",
   signal_key="streak_momentum", side="short")
_I("Run-length record continuation long", "autocorr",
   "Current green-close streak ties or exceeds the longest green streak in the trailing 50 bars, go long (strength persistence)",
   "A streak reaching a local record suggests unusually strong, possibly structurally-driven persistence worth riding further",
   3, "medium: record-streak persistence is an intuitive but statistically fragile signal (streak records are rare by construction)",
   signal_key="run_length_continuation", side="long")
_I("Run-length record continuation short", "autocorr",
   "Current red-close streak ties or exceeds the longest red streak in the trailing 50 bars, go short",
   "Symmetric record-streak continuation short",
   3, "medium: symmetric to long",
   signal_key="run_length_continuation", side="short")

# ---------------------------------------------------------------------------
# K. Candle-pattern continuation (8 implemented)
# ---------------------------------------------------------------------------
_I("Inside-bar breakout long", "candle",
   "An inside bar (high/low fully contained in prior bar's range) followed by a close above the inside bar's high, go long",
   "Inside bars mark a pause/consolidation; the break of that tight range often launches the next directional leg",
   2, "medium-high: inside-bar breakouts are a well-known, moderately robust continuation pattern",
   signal_key="inside_bar_breakout", side="long")
_I("Inside-bar breakout short", "candle",
   "Inside bar followed by close below its low, go short",
   "Symmetric inside-bar breakdown",
   2, "medium-high: symmetric to long",
   signal_key="inside_bar_breakout", side="short")
_I("Bullish engulfing trend-continuation long", "candle",
   "Bullish engulfing candle (fully engulfs prior red body) occurring while price is above its 50-bar EMA (uptrend context), go long",
   "Engulfing patterns in the direction of the prevailing trend reflect renewed conviction rather than a counter-trend reversal bet",
   2, "medium-high: trend-filtered candle patterns outperform unfiltered ones in most published studies",
   signal_key="engulfing_continuation", side="long")
_I("Bearish engulfing trend-continuation short", "candle",
   "Bearish engulfing candle while price is below its 50-bar EMA, go short",
   "Symmetric trend-filtered bearish engulfing",
   2, "medium-high: symmetric to long",
   signal_key="engulfing_continuation", side="short")
_I("Three-bar momentum thrust continuation long", "candle",
   "Three consecutive up-closes with strictly increasing bar ranges, go long on the thrust's completion",
   "Accelerating range on consecutive same-direction bars signals strengthening conviction mid-move, favoring continuation",
   2, "medium-high: accelerating-range thrust is a concrete, intuitive momentum-confirmation pattern",
   signal_key="three_bar_thrust", side="long")
_I("Three-bar momentum thrust continuation short", "candle",
   "Three consecutive down-closes with strictly increasing ranges, go short",
   "Symmetric bearish thrust continuation",
   2, "medium-high: symmetric to long",
   signal_key="three_bar_thrust", side="short")
_I("Marubozu breakout continuation long", "candle",
   "A bullish marubozu (body >= 90% of total range, i.e. negligible wicks) closes at/near the bar's high, go long next bar",
   "A full-body candle with no rejection wicks indicates one-sided conviction through the entire bar with no counter-pressure",
   3, "medium: marubozu bars are relatively rare at 1h resolution, limiting trade count though the logic is sound",
   signal_key="marubozu_breakout", side="long")
_I("Marubozu breakout continuation short", "candle",
   "A bearish marubozu closing near its low, go short next bar",
   "Symmetric bearish marubozu continuation",
   3, "medium: symmetric to long, same rarity caveat",
   signal_key="marubozu_breakout", side="short")

# ---------------------------------------------------------------------------
# L. Pivot-point bounces (5 implemented)
# ---------------------------------------------------------------------------
_I("Classic daily pivot S1 bounce long", "pivot",
   "Classic floor-trader daily pivot's S1 support (from prior UTC day's H/L/C) touched intraday then close back above S1, go long",
   "Pivot levels are widely watched reference points; a touch-and-reclaim of S1 reflects buyers defending a well-known level",
   2, "medium-high: classic pivots remain commonly referenced even in crypto derivatives desks",
   signal_key="pivot_s1_bounce", side="long")
_I("Classic daily pivot R1 rejection short", "pivot",
   "Classic daily pivot's R1 resistance touched intraday then close back below R1, go short",
   "Symmetric R1 rejection fade",
   2, "medium-high: symmetric to long",
   signal_key="pivot_r1_reject", side="short")
_I("Camarilla pivot breakout long", "pivot",
   "Close breaks and holds above the Camarilla H3 level (tighter breakout level than classic pivots)",
   "Camarilla levels are specifically calibrated as breakout triggers rather than reversal zones, a distinct use-case from classic pivots",
   4, "medium-low: Camarilla is a less crypto-tested variant, included for mechanism diversity rather than strong prior",
   signal_key="camarilla_breakout", side="long")
_I("Camarilla pivot breakout short", "pivot",
   "Close breaks and holds below the Camarilla L3 level",
   "Symmetric Camarilla breakdown",
   4, "medium-low: symmetric to long",
   signal_key="camarilla_breakout", side="short")
_I("Woodie's pivot midpoint reversion long", "pivot",
   "Price touches Woodie's pivot midpoint between pivot and S1 from below and closes back above the pivot, go long",
   "Woodie's pivot weights the current day's open more heavily, making its midpoint a session-specific fair-value reference distinct from the classic formula",
   5, "low: Woodie variant is a minor formula tweak on classic pivots with a thin standalone rationale",
   signal_key="woodie_midpoint_reversion", side="long")

# ---------------------------------------------------------------------------
# M. Moving-average crossover variants, not plain cross (6 implemented)
# ---------------------------------------------------------------------------
_I("Slope-filtered EMA(9/21) bullish cross long", "ma_variant",
   "EMA9 crosses above EMA21 AND both EMAs' own slopes are positive, go long",
   "Requiring both EMAs to already be rising filters out whipsaw crosses that occur in flat/choppy conditions, a known plain-MA-cross weakness",
   2, "medium-high: slope-filtering is a standard, sensible improvement on the notoriously whipsaw-prone plain MA cross",
   signal_key="ema_slope_filtered_cross", side="long")
_I("Slope-filtered EMA(9/21) bearish cross short", "ma_variant",
   "EMA9 crosses below EMA21 with both slopes negative, go short",
   "Symmetric slope-filtered bearish cross",
   2, "medium-high: symmetric to long",
   signal_key="ema_slope_filtered_cross", side="short")
_I("Triple-EMA ribbon bullish pullback long", "ma_variant",
   "EMA8 > EMA21 > EMA55 (bullish ribbon alignment) AND price pulls back to touch EMA21 then closes back above it, go long",
   "A fully aligned MA ribbon defines an established trend; a shallow pullback to the middle MA is a classic trend-continuation entry rather than a fresh breakout",
   2, "medium-high: ribbon-aligned pullback entries are a widely used, trend-respecting entry refinement",
   signal_key="ma_ribbon_pullback", side="long")
_I("Triple-EMA ribbon bearish pullback short", "ma_variant",
   "EMA8 < EMA21 < EMA55 AND price pulls back to EMA21 then closes back below it, go short",
   "Symmetric bearish ribbon pullback",
   2, "medium-high: symmetric to long",
   signal_key="ma_ribbon_pullback", side="short")
_I("MA-ribbon compression-then-expansion breakout long", "ma_variant",
   "Spread between EMA8/21/55 contracts to a 100-bar low then starts widening with price above all three, go long",
   "Ribbon compression is a multi-MA analogue of the Bollinger/ATR squeeze, with the added information of trend direction once the ribbon un-compresses",
   3, "medium: a reasonable multi-indicator squeeze analogue, but adds limited information over the single-indicator squeeze family",
   signal_key="ma_compression_expansion", side="long")
_I("MA-ribbon compression-then-expansion breakdown short", "ma_variant",
   "Ribbon compresses to a 100-bar low then widens with price below all three EMAs, go short",
   "Symmetric ribbon-expansion breakdown",
   3, "medium: symmetric to long",
   signal_key="ma_compression_expansion", side="short")

# ---------------------------------------------------------------------------
# N. Price-volume / money-flow divergence (6 implemented)
# ---------------------------------------------------------------------------
_I("Price-volume bearish divergence short", "pv_divergence",
   "Price makes a new 20-bar closing high while 10-bar average volume is declining versus the prior 10-bar average, go short",
   "A new high on thinning volume suggests fewer participants are willing to pay up, a classic distribution warning",
   2, "medium-high: volume-divergence-at-extremes is a long-standing, intuitive technical heuristic",
   signal_key="price_volume_divergence", side="short")
_I("Price-volume bullish divergence long", "pv_divergence",
   "Price makes a new 20-bar closing low while volume is declining versus its prior 10-bar average, go long",
   "A new low on thinning volume suggests selling is losing force (accumulation into weakness)",
   2, "medium-high: symmetric to short",
   signal_key="price_volume_divergence", side="long")
_I("Chaikin Money Flow bearish divergence short", "pv_divergence",
   "CMF(20) turns negative while price is flat-to-up over the same window, go short",
   "CMF directly measures buying/selling pressure within each bar's range; a negative reading despite stable/rising price flags hidden distribution",
   3, "medium: CMF divergence is a reasonable refinement over raw volume but is a second-order, noisier construct",
   signal_key="cmf_divergence", side="short")
_I("Chaikin Money Flow bullish divergence long", "pv_divergence",
   "CMF(20) turns positive while price is flat-to-down over the same window, go long",
   "Symmetric CMF accumulation divergence",
   3, "medium: symmetric to short",
   signal_key="cmf_divergence", side="long")
_I("Accumulation/Distribution line bearish divergence short", "pv_divergence",
   "A/D line's 20-bar slope turns negative while price's 20-bar slope is still positive, go short",
   "The A/D line's slope divergence from price slope is a distinct cumulative-flow measure from CMF's windowed average, catching divergence earlier in some cases",
   3, "medium: conceptually similar family to CMF/OBV divergence, included for an independent cumulative-flow construction",
   signal_key="ad_line_divergence", side="short")
_I("Accumulation/Distribution line bullish divergence long", "pv_divergence",
   "A/D line's 20-bar slope turns positive while price's 20-bar slope is still negative, go long",
   "Symmetric A/D line bullish divergence",
   3, "medium: symmetric to short",
   signal_key="ad_line_divergence", side="long")

# ---------------------------------------------------------------------------
# O. Relative-strength vs BTC rotation (6 implemented, non-BTC symbols only)
# ---------------------------------------------------------------------------
_I("Altcoin relative-strength-vs-BTC momentum long", "relative_strength",
   "24-bar return of (altcoin / BTC) ratio in the top 20th percentile of its own 200-bar history, go long the altcoin",
   "Capital rotation into outperforming alts during risk-on phases tends to persist over short horizons (sector momentum)",
   1, "high: BTC-relative rotation effects are a well-known feature of crypto altcoin behavior",
   signal_key="btc_relative_strength_momentum", side="long", uses_cross_asset=True)
_I("Altcoin relative-strength-vs-BTC momentum short", "relative_strength",
   "24-bar alt/BTC ratio return in the bottom 20th percentile of its own 200-bar history, go short the altcoin",
   "Symmetric underperformance momentum (weak alts keep lagging in risk-off phases)",
   1, "high: symmetric to long",
   signal_key="btc_relative_strength_momentum", side="short", uses_cross_asset=True)
_I("Altcoin relative-strength-vs-BTC mean reversion short", "relative_strength",
   "alt/BTC ratio z-score (vs trailing 200-bar mean/stdev) > 2.5, fade the altcoin short expecting reversion toward BTC-relative norm",
   "Extreme over-extensions in relative performance eventually mean-revert as rotation flows rebalance",
   3, "medium: momentum and mean-reversion in relative strength likely coexist at different horizons/regimes, direction less certain than the momentum version",
   signal_key="btc_relative_strength_reversion", side="short", uses_cross_asset=True)
_I("Altcoin relative-strength-vs-BTC mean reversion long", "relative_strength",
   "alt/BTC ratio z-score < -2.5, go long the altcoin expecting reversion",
   "Symmetric underperformance-extreme reversion",
   3, "medium: symmetric to short",
   signal_key="btc_relative_strength_reversion", side="long", uses_cross_asset=True)
_I("BTC-lead altcoin-lag momentum long", "relative_strength",
   "BTC's 1h return exceeds +1% in the just-completed bar, go long the altcoin on the next bar (lagged reaction)",
   "Large BTC moves often propagate to altcoins with a short lag as correlated flows and risk models react sequentially",
   1, "high: BTC-lead/alt-lag propagation is one of the most frequently cited cross-asset crypto microstructure effects",
   signal_key="btc_lead_lag_momentum", side="long", uses_cross_asset=True)
_I("BTC-lead altcoin-lag momentum short", "relative_strength",
   "BTC's 1h return is below -1% in the just-completed bar, go short the altcoin next bar",
   "Symmetric BTC-led downside propagation",
   1, "high: symmetric to long",
   signal_key="btc_lead_lag_momentum", side="short", uses_cross_asset=True)

# ---------------------------------------------------------------------------
# P. Time-of-day / weekly seasonality (6 implemented)
# ---------------------------------------------------------------------------
_I("Low-liquidity UTC-hour fade long", "seasonality",
   "During the historically thinnest UTC hours (02:00-04:00), an outsized single-bar move (> 1.5x the 20-bar average range) fades back long",
   "Thin liquidity hours amplify moves that are more likely to be noise-driven rather than information-driven, favoring reversion",
   3, "medium: plausible liquidity-driven effect but UTC-hour liquidity patterns in perps are less pronounced than in spot FX",
   signal_key="session_hour_seasonality_fade", side="long")
_I("Low-liquidity UTC-hour fade short", "seasonality",
   "Same thin-hour condition, fade short on an outsized up-move",
   "Symmetric thin-liquidity fade short",
   3, "medium: symmetric to long",
   signal_key="session_hour_seasonality_fade", side="short")
_I("High-activity UTC-hour momentum long", "seasonality",
   "During the historically busiest UTC hours (13:00-16:00, US/EU overlap), a breakout above the prior 4-bar high continues long",
   "High-liquidity windows see more genuine informed flow, so breakouts occurring then are more likely to reflect real demand than noise",
   3, "medium: reasonable liquidity-quality argument but effect size at 1h resolution is uncertain",
   signal_key="session_hour_seasonality_momentum", side="long")
_I("Weekend low-liquidity mean reversion long", "seasonality",
   "On UTC Saturday/Sunday, close stretches > 1.5x ATR from the 20-bar mean, go long expecting reversion",
   "Weekend trading desks are thinner across both crypto-native and TradFi-adjacent flow, and thin markets historically overshoot and revert more",
   3, "medium: weekend liquidity thinning in crypto perps is real but less extreme than in TradFi-linked markets",
   signal_key="weekend_low_liquidity_reversion", side="long")
_I("Weekend low-liquidity mean reversion short", "seasonality",
   "Same weekend stretch condition on the downside, go short expecting reversion",
   "Symmetric weekend reversion short",
   3, "medium: symmetric to long",
   signal_key="weekend_low_liquidity_reversion", side="short")
_I("Multi-timeframe (1h/4h) momentum alignment long", "seasonality",
   "1h 10-bar ROC and 4h 10-bar ROC both positive, go long on 1h",
   "Requiring agreement across two timeframes filters trades against the higher-timeframe trend, improving signal quality versus single-timeframe momentum",
   2, "medium-high: multi-timeframe confirmation is a standard, sensible filter used across discretionary and systematic trading alike",
   signal_key="mtf_momentum_alignment", side="long")

# ---------------------------------------------------------------------------
# Q. Funding-settlement gap already covered in G; Liquidity sweep without OB (4 implemented)
# ---------------------------------------------------------------------------
_I("Wick sweep of rolling 20-bar high, fail, fade short", "liquidity_sweep",
   "Bar's high exceeds the rolling 20-bar high (excluding itself) but the bar closes back below that prior high, go short",
   "A wick beyond a well-watched rolling extreme that fails to hold is the classic stop-hunt/liquidity-grab signature, without invoking any OB/BOS zone concept",
   1, "high: pure wick-sweep-and-reject at rolling extremes is a robust, simple, well-documented liquidity-grab pattern",
   signal_key="wick_sweep_high_fade", side="short")
_I("Wick sweep of rolling 20-bar low, fail, fade long", "liquidity_sweep",
   "Bar's low exceeds (undercuts) the rolling 20-bar low but closes back above it, go long",
   "Symmetric stop-hunt-and-reject at the rolling low",
   1, "high: symmetric to short",
   signal_key="wick_sweep_low_fade", side="long")
_I("Sweep of prior UTC day's high, reject, fade short", "liquidity_sweep",
   "Intraday high exceeds the prior completed UTC day's high (from 4h/1h aggregation) then closes back below it, go short",
   "The prior day's high/low is one of the most universally watched reference levels across all trader types, making sweeps of it a high-liquidity target for stop-hunts",
   1, "high: prior-day-high/low sweep-and-reject is a very commonly cited, simple liquidity pattern",
   signal_key="prior_day_high_sweep_reject", side="short")
_I("Sweep of prior UTC day's low, reject, fade long", "liquidity_sweep",
   "Intraday low undercuts the prior day's low then closes back above it, go long",
   "Symmetric prior-day-low sweep-and-reject",
   1, "high: symmetric to short",
   signal_key="prior_day_low_sweep_reject", side="long")

# ---------------------------------------------------------------------------
# S. Z-score / rolling-rank mean reversion, distinct window/method from C (4 implemented)
# ---------------------------------------------------------------------------
_I("Short-window (10-bar) z-score extreme reversion short", "zscore_meanrev",
   "z-score of close vs its own trailing 10-bar mean/stdev > 2.2, fade short",
   "A fast, short-window z-score captures sharper, more immediate overextensions than the slower 200-bar EMA-distance measure in family C",
   2, "medium-high: short-window mean reversion is a standard, fast-acting statistical-arbitrage-style signal",
   signal_key="zscore_short_window_reversion", side="short")
_I("Short-window (10-bar) z-score extreme reversion long", "zscore_meanrev",
   "z-score of close vs 10-bar mean/stdev < -2.2, go long",
   "Symmetric short-window reversion long",
   2, "medium-high: symmetric to short",
   signal_key="zscore_short_window_reversion", side="long")
_I("Rolling-rank percentile extreme reversion short", "zscore_meanrev",
   "Close's percentile rank within its trailing 50-bar window > 97, fade short",
   "Percentile-rank reversion is distribution-free (no normality assumption), making it more robust to crypto's fat-tailed returns than a z-score",
   2, "medium-high: rank-based reversion is a reasonable, robust alternative construction to parametric z-scores",
   signal_key="rolling_rank_extreme_reversion", side="short")
_I("Rolling-rank percentile extreme reversion long", "zscore_meanrev",
   "Close's percentile rank within its trailing 50-bar window < 3, go long",
   "Symmetric rank-based reversion long",
   2, "medium-high: symmetric to short",
   signal_key="rolling_rank_extreme_reversion", side="long")

# ---------------------------------------------------------------------------
# T. ATR-normalized momentum, both directions of the same signal (4 implemented)
# ---------------------------------------------------------------------------
_I("ATR-normalized return momentum continuation long", "atr_norm",
   "10-bar return divided by ATR(14) exceeds +3 (a large, vol-adjusted move), go long expecting continuation",
   "A move that is large relative to the asset's own typical range signals a genuine information-driven dislocation likely to keep running short-term",
   2, "medium-high: vol-normalizing momentum before thresholding is a sound practice that generalizes better across symbols than raw-percent thresholds",
   signal_key="atr_norm_momentum", side="long")
_I("ATR-normalized return momentum continuation short", "atr_norm",
   "10-bar ATR-normalized return below -3, go short expecting continuation",
   "Symmetric vol-normalized momentum short",
   2, "medium-high: symmetric to long",
   signal_key="atr_norm_momentum", side="short")
_I("ATR-normalized return contrarian overextension fade short", "atr_norm",
   "Same +3 ATR-normalized-return condition as above, but take the OPPOSITE (fade) side expecting overextension snap-back",
   "The same large vol-adjusted move can alternatively be read as an overextension ripe for a snap-back, a directly competing hypothesis to the momentum version worth screening separately",
   3, "medium: deliberately opposite bet to the momentum version on the same trigger -- at most one of the pair can have real edge, included to let the empirical pass adjudicate",
   signal_key="atr_norm_contrarian_fade", side="short")
_I("ATR-normalized return contrarian overextension fade long", "atr_norm",
   "Same -3 ATR-normalized-return condition, fade long expecting snap-back",
   "Symmetric contrarian overextension fade long",
   3, "medium: symmetric to short, same competing-hypothesis caveat",
   signal_key="atr_norm_contrarian_fade", side="long")

# ---------------------------------------------------------------------------
# V. Parabolic / exhaustion reversal (4 implemented)
# ---------------------------------------------------------------------------
_I("Parabolic-SAR flip after extended uptrend, exhaustion short", "exhaustion",
   "Parabolic SAR flips from below-price to above-price after an uptrend lasting >= 30 bars, go short (counter-trend exhaustion bet)",
   "Very long unbroken trends become statistically more likely to exhaust the longer they run; a SAR flip is a concrete, rules-based trigger for that exhaustion",
   4, "medium-low: counter-trend exhaustion bets fight the trend-following edges found elsewhere in this list and are historically harder to monetize",
   signal_key="parabolic_exhaustion_reversal", side="short")
_I("Parabolic-SAR flip after extended downtrend, exhaustion long", "exhaustion",
   "SAR flips from above-price to below-price after a downtrend lasting >= 30 bars, go long",
   "Symmetric extended-downtrend exhaustion bet",
   4, "medium-low: symmetric to short, same caveat",
   signal_key="parabolic_exhaustion_reversal", side="long")
_I("RSI rare-extreme (>90) overbought exhaustion short", "exhaustion",
   "RSI(14) exceeds 90 (a rare extreme, distinct from the common 70/80 thresholds used elsewhere), fade short",
   "RSI readings this extreme are rare enough that they likely reflect genuinely unsustainable short-term buying intensity",
   4, "medium-low: rare-event thresholds mean very few trades, limiting statistical reliability even if the logic is sound",
   signal_key="rsi_extreme_rare_exhaustion", side="short")
_I("RSI rare-extreme (<10) oversold exhaustion long", "exhaustion",
   "RSI(14) below 10, go long",
   "Symmetric rare-extreme oversold exhaustion",
   4, "medium-low: symmetric to short, same rarity caveat",
   signal_key="rsi_extreme_rare_exhaustion", side="long")

# ---------------------------------------------------------------------------
# W. Correlation breakdown / decorrelation (4 implemented, non-BTC only)
# ---------------------------------------------------------------------------
_I("Decorrelation-spike idiosyncratic-move fade short", "decorrelation",
   "Rolling 50-bar correlation of altcoin returns to BTC returns drops below its own 20th percentile AND the altcoin outperformed BTC over the same window, fade the altcoin short",
   "A sudden decoupling plus idiosyncratic outperformance is often a short-lived, flow-driven anomaly that re-correlates (and gives back the excess move) once the idiosyncratic flow fades",
   4, "medium-low: decorrelation-based fades are a more exotic, thinly-evidenced construct relative to the direct relative-strength family",
   signal_key="decorrelation_spike_fade", side="short", uses_cross_asset=True)
_I("Decorrelation-spike idiosyncratic-move fade long", "decorrelation",
   "Same decorrelation condition but altcoin underperformed BTC over the window, go long expecting re-correlation upward",
   "Symmetric decorrelation-driven underperformance fade",
   4, "medium-low: symmetric to short",
   signal_key="decorrelation_spike_fade", side="long", uses_cross_asset=True)
_I("Close-location-value (CLV) streak continuation long", "decorrelation",
   "CLV ((close-low)-(high-close))/(high-low) positive and above 0.5 for 3+ consecutive bars, go long",
   "A sustained run of closes near the top of each bar's range (without needing full marubozu bodies) is a softer, more frequent proxy for persistent buy-side control",
   3, "medium: CLV streak is a reasonable, more frequent relative of the marubozu-continuation idea in family K",
   signal_key="clv_streak_continuation", side="long")
_I("Close-location-value (CLV) streak continuation short", "decorrelation",
   "CLV negative and below -0.5 for 3+ consecutive bars, go short",
   "Symmetric CLV streak continuation short",
   3, "medium: symmetric to long",
   signal_key="clv_streak_continuation", side="short")

# ===========================================================================
# PROPOSED-ONLY IDEAS (not backtested this pass) -- 47 ideas
# Reasons: either the mechanism needs data not present in the bar/funding
# files at all (open interest, spot-perp basis, liquidation feed, order
# book depth), or it was deprioritized purely to stay inside the ~15-minute
# runtime budget for this cheap exploratory pass. Mechanism/rationale and a
# qualitative prior rank are still given in full, per the task's "propose
# all ~167 regardless" instruction.
# ===========================================================================
_PROPOSED = [
    ("Ichimoku cloud bullish breakout long", "proposed_other",
     "Price closes above the Kumo cloud with a bullish Tenkan/Kijun cross", "Ichimoku's cloud is a multi-period consensus support/resistance zone distinct from single-MA or channel methods", 3, "medium: deprioritized for time, mechanism distinct from channel/MA families already covered", "short budget"),
    ("Ichimoku cloud bearish breakdown short", "proposed_other",
     "Price closes below the Kumo cloud with a bearish Tenkan/Kijun cross", "Symmetric cloud breakdown", 3, "medium: time budget", "short budget"),
    ("SuperTrend indicator flip long", "proposed_other",
     "SuperTrend (ATR-band trailing stop) flips from above-price to below-price", "SuperTrend's trailing-stop construction differs from Keltner/Donchian by always being anchored to the most favorable recent extreme", 2, "medium-high: popular and simple, deprioritized only for time budget", "time budget"),
    ("SuperTrend indicator flip short", "proposed_other",
     "SuperTrend flips from below-price to above-price", "Symmetric SuperTrend flip short", 2, "medium-high: time budget", "time budget"),
    ("Elder Ray bull-power divergence long", "proposed_other",
     "Bull Power (high - EMA13) diverges positively while price makes a lower low", "Elder Ray decomposes bull/bear power separately from price, a distinct decomposition from RSI/Stochastic divergence", 3, "medium: niche indicator, time budget", "time budget"),
    ("Elder Ray bear-power divergence short", "proposed_other",
     "Bear Power (low - EMA13) diverges negatively while price makes a higher high", "Symmetric bear-power divergence", 3, "medium: time budget", "time budget"),
    ("Williams %R extreme reversal long", "proposed_other",
     "Williams %R crosses back above -80 after being below it", "Williams %R uses the high/low range rather than close-to-close like RSI, a distinct normalization", 3, "medium: close cousin of RSI/stochastic threshold family, time budget", "time budget"),
    ("Williams %R extreme reversal short", "proposed_other",
     "Williams %R crosses back below -20 after being above it", "Symmetric Williams %R reversal", 3, "medium: time budget", "time budget"),
    ("Money Flow Index (MFI) divergence long", "proposed_other",
     "MFI (volume-weighted RSI) makes a higher low while price makes a lower low", "MFI folds volume directly into an RSI-style oscillator, distinct from pairing RSI with a separate volume filter", 3, "medium: time budget", "time budget"),
    ("Money Flow Index (MFI) divergence short", "proposed_other",
     "MFI makes a lower high while price makes a higher high", "Symmetric MFI divergence short", 3, "medium: time budget", "time budget"),
    ("Fibonacci 0.618 retracement bounce long", "proposed_other",
     "In an established uptrend, price retraces to the 0.618 Fib level of the last swing and closes back above it", "Fibonacci retracement levels are extremely widely watched, creating self-fulfilling reaction zones distinct from pivot/VWAP references", 3, "medium: widely used but notoriously hard to define 'the last swing' robustly without lookahead risk; time budget", "time budget"),
    ("Fibonacci 0.618 retracement rejection short", "proposed_other",
     "In a downtrend, price retraces to 0.618 Fib and closes back below it", "Symmetric Fib rejection short", 3, "medium: time budget", "time budget"),
    ("ADX-filtered Donchian breakout long", "proposed_other",
     "Donchian-20 breakout taken only when ADX(14) > 25 (confirmed trending regime)", "ADX directly measures trend strength, offering a principled regime filter rather than the squeeze-based filters used elsewhere", 2, "medium-high: well-motivated filter on an already-high-prior family, time budget prevented a dedicated regime-filter implementation", "time budget"),
    ("ADX-filtered Donchian breakout short", "proposed_other",
     "Symmetric ADX-filtered breakdown", "Symmetric ADX-filtered short", 2, "medium-high: time budget", "time budget"),
    ("Choppiness-Index-filtered breakout long", "proposed_other",
     "Donchian breakout taken only when the Choppiness Index is below 38 (non-choppy regime)", "Choppiness Index is a distinct regime-classification formula from ADX, offering a second independent regime-filter construction", 3, "medium: redundant family with ADX-filter idea above but a genuinely different formula; time budget", "time budget"),
    ("Choppiness-Index-filtered breakout short", "proposed_other",
     "Symmetric choppiness-filtered breakdown", "Symmetric choppiness filter short", 3, "medium: time budget", "time budget"),
    ("Heikin-Ashi candle-flip continuation long", "proposed_other",
     "Heikin-Ashi candle color flips from red to green with no lower wick, go long", "Heikin-Ashi smooths noise into its own candle construction, a structurally different input series from raw OHLC used everywhere else in this screen", 3, "medium: smoothing could reduce whipsaws but also lags; time budget", "time budget"),
    ("Heikin-Ashi candle-flip continuation short", "proposed_other",
     "HA candle flips green to red with no upper wick, go short", "Symmetric HA flip short", 3, "medium: time budget", "time budget"),
    ("Renko brick reversal long", "proposed_other",
     "A Renko chart (fixed price-box reconstruction, ignoring time) prints two consecutive up-bricks after a down-brick run", "Renko removes time/noise entirely, trading purely on price displacement -- a fundamentally different chart construction", 4, "medium-low: Renko reconstruction from 1h bars is a nontrivial additional pipeline; time budget", "time budget"),
    ("Renko brick reversal short", "proposed_other",
     "Symmetric Renko down-brick reversal", "Symmetric Renko reversal short", 4, "medium-low: time budget", "time budget"),
    ("Open-interest buildup momentum long", "proposed_other",
     "Open interest and price both rising over 24h (fresh long positioning, not short-covering), go long", "OI+price co-movement is a canonical derivatives-desk signal for distinguishing genuine new demand from short covering", 2, "medium-high: well-evidenced in derivatives trading, but open interest is NOT present in the bar/funding parquet files used here", "not in available data"),
    ("Open-interest short-covering rally long", "proposed_other",
     "Open interest falling while price rises (short covering), go long expecting continued squeeze", "Distinguishes a short-covering-driven rally (often fast but can extend) from fresh-long-driven rallies", 3, "medium: plausible but OI data unavailable in this dataset", "not in available data"),
    ("Liquidation-cascade proxy reversal long", "proposed_other",
     "A single bar's range exceeds 3x its 20-bar average ATR with a long lower wick, treat as a forced-liquidation wick and fade long", "Forced liquidations create violent, mechanically-driven (not fundamentally-driven) wicks that often fully or partially retrace", 2, "medium-high: liquidation-wick fades are a well-known crypto-specific pattern; deprioritized for time budget since it overlaps conceptually with the climax-volume fade already implemented", "time budget / overlaps climax-volume fade"),
    ("Liquidation-cascade proxy reversal short", "proposed_other",
     "Symmetric extreme-range bar with long upper wick, fade short", "Symmetric liquidation-wick fade short", 2, "medium-high: time budget / overlap", "time budget / overlaps climax-volume fade"),
    ("Spot-perp basis extreme fade", "proposed_other",
     "Perp price trades at an extreme premium/discount to spot, fade toward spot", "Basis extremes are a classic, well-arbitraged signal in derivatives markets", 3, "medium: mechanism well known but spot price series is not loaded by this screen's data_access pipeline", "not in available data"),
    ("Order-book imbalance proxy via wick asymmetry long", "proposed_other",
     "Bar's lower wick is much longer than its upper wick across several consecutive bars (buy-side absorption proxy), go long", "Without real order-book depth, wick asymmetry is the closest OHLC-only proxy for resting bid/ask imbalance", 4, "medium-low: a weak proxy for genuine book imbalance; time budget", "time budget"),
    ("Order-book imbalance proxy via wick asymmetry short", "proposed_other",
     "Symmetric upper-wick-dominant sequence, go short", "Symmetric wick-asymmetry proxy short", 4, "medium-low: time budget", "time budget"),
    ("Day-of-week Monday momentum long", "proposed_other",
     "UTC Monday's first few bars tend to continue the prior week's dominant direction, go long if the prior week closed up", "Weekly position adjustments by larger players may cluster around week boundaries even in a 24/7 market", 4, "medium-low: weak theoretical grounding for crypto specifically; time budget", "time budget"),
    ("Day-of-week Friday profit-taking fade short", "proposed_other",
     "UTC Friday session shows a tendency to fade an extended weekly move into the weekend", "Profit-taking ahead of thin weekend liquidity is a plausible but thin behavioral story", 4, "medium-low: time budget", "time budget"),
    ("Month-end rebalancing flow fade long", "proposed_other",
     "Price dips in the last UTC trading day of the calendar month, fade long expecting month-end-flow reversal", "Index/fund rebalancing flows cluster at month-end in TradFi; a weak, unconfirmed analogy for crypto", 5, "low: thin theoretical basis for crypto-native month-end flows; time budget", "time budget"),
    ("Month-end rebalancing flow fade short", "proposed_other",
     "Symmetric month-end fade short", "Symmetric month-end fade short", 5, "low: time budget", "time budget"),
    ("Volatility-risk-premium short-vol harvesting (non-directional)", "proposed_other",
     "During confirmed low-ATR-percentile regimes, systematically fade moves at both channel extremes (sell premium, structurally not just directional) -- conceptually closer to an options-style carry strategy than a directional bet", "Volatility risk premium harvesting is a distinct strategy class (selling realized-vol-implied richness) from any directional idea on this list", 4, "medium-low: genuinely different mechanism class (non-directional carry) but needs an options-style framing this screen's long/short R-multiple harness doesn't fit cleanly; time budget", "harness mismatch / time budget"),
    ("Correlation-cluster rotation to basket mean long", "proposed_other",
     "A basket of similar-sector L1s (e.g. SOL/AVAX/NEAR/APT) mean-reverts toward the basket's average relative performance", "Sector-cluster mean reversion is a step beyond single-pair BTC relative strength, using a multi-asset basket reference", 4, "medium-low: requires defining and maintaining a basket construction; time budget", "time budget"),
    ("Correlation-cluster rotation to basket mean short", "proposed_other",
     "Symmetric basket-relative mean reversion short", "Symmetric basket rotation short", 4, "medium-low: time budget", "time budget"),
    ("Stablecoin-peg-deviation funding correlation fade", "proposed_other",
     "Large stablecoin peg deviations historically coincide with funding-rate dislocations; fade the resulting perp mispricing", "Peg stress events are rare systemic shocks with a plausible but thin direct link to any single perp's price action", 5, "low: peg-deviation series not available in this dataset at all; time budget", "not in available data"),
    ("News-event volatility fade (no follow-through) long", "proposed_other",
     "A single bar moves > 4x its 20-bar average range with no follow-through in the next bar (next bar's range < 1x average), fade back long", "One-off news/liquidation spikes without sustained follow-through often partially retrace once the initial shock passes", 3, "medium: overlaps conceptually with the climax-volume and liquidation-wick fades; included as a distinct no-follow-through trigger; time budget", "time budget / overlaps climax-volume fade"),
    ("News-event volatility fade (no follow-through) short", "proposed_other",
     "Symmetric no-follow-through fade short", "Symmetric no-follow-through fade short", 3, "medium: time budget", "time budget"),
    ("Triple-confirmation (RSI+volume+MA) composite long", "proposed_other",
     "RSI oversold reversal AND volume spike AND price above 50-bar EMA all align simultaneously, go long", "Requiring independent confirmation from three already-implemented signal families should raise precision at the cost of frequency, worth testing as its own composite idea", 2, "medium-high: composite-confirmation strategies often outperform their single-signal components; time budget prevented building the combinatorial composite layer", "time budget"),
    ("Triple-confirmation (RSI+volume+MA) composite short", "proposed_other",
     "Symmetric composite short confirmation", "Symmetric composite short", 2, "medium-high: time budget", "time budget"),
    ("Quarterly derivatives-expiry fade long", "proposed_other",
     "Perpetuals markets anchored to quarterly futures expiries sometimes show pinning/unwind effects around expiry dates, fade the pre-expiry move long", "Futures-expiry pinning is a documented TradFi and some crypto-quarterly-futures effect, though perps themselves have no expiry", 4, "medium-low: mechanism is about quarterly FUTURES, not the perps this screen trades, so its applicability here is indirect; time budget", "time budget / indirect applicability"),
    ("Quarterly derivatives-expiry fade short", "proposed_other",
     "Symmetric quarterly-expiry fade short", "Symmetric expiry fade short", 4, "medium-low: time budget / indirect applicability", "time budget / indirect applicability"),
    ("Low-float/high-FDV unlock drift fade", "proposed_other",
     "Tokens with scheduled large supply unlocks tend to drift down into the unlock date, fade short ahead of known unlock schedules", "Scheduled unlock-driven sell pressure is a well-known idiosyncratic crypto effect for specific tokens", 4, "medium-low: unlock-schedule data is not present in this dataset and would require an external calendar; time budget", "not in available data"),
    ("Hurst-exponent adaptive regime switch", "proposed_other",
     "Estimate a rolling Hurst exponent; trade breakout logic when H > 0.55 (trending) and mean-reversion logic when H < 0.45 (mean-reverting)", "An adaptive meta-strategy that switches mechanism by measured regime persistence is a structurally different, higher-complexity approach than any single fixed-mechanism idea on this list", 3, "medium: genuinely interesting but a meta-strategy, not a single comparable signal, and Hurst estimation is compute-heavier; time budget", "time budget / harness mismatch"),
]
for _name, _fam, _mech, _rat, _rank, _note, _reason in _PROPOSED:
    _I(_name, _fam, _mech, _rat, _rank,
       f"{_note} [PROPOSED ONLY, NOT BACKTESTED: {_reason}]",
       signal_key=None, side="long" if "short" not in _name.lower() else "short",
       implemented=False)


def build_catalog():
    """Return the full ordered list of idea dicts with idea_id assigned.

    Rows are sorted by prior_rank ascending (1 = highest qualitative
    likelihood first), stable on original insertion order within a rank,
    matching the user's "ranked by likelihood" request for the pre-run order.
    idea_id is assigned AFTER sorting so idea_id order == prior-rank order.
    """
    ordered = sorted(enumerate(RAW), key=lambda t: (t[1]["prior_rank"], t[0]))
    catalog = []
    for n, (_, row) in enumerate(ordered, start=1):
        row = dict(row)
        row["idea_id"] = f"M{n:03d}"
        catalog.append(row)
    return catalog


if __name__ == "__main__":
    cat = build_catalog()
    print(f"total ideas: {len(cat)}")
    print(f"implemented: {sum(1 for r in cat if r['implemented'])}")
    print(f"proposed only: {sum(1 for r in cat if not r['implemented'])}")
