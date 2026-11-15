"""Causal deterministic price-action setup signals for P5."""
from dataclasses import dataclass
import numpy as np
import pandas as pd
from . import indicators

SETUPS = ("supertrend", "trendline_breakout", "sr_retest", "sweep_choch_retest",
          "avwap_hl", "rsi_divergence", "candle_reversal", "fibonacci_pocket",
          "order_block", "fabio_liquidity_mss", "fvg_fill",
          "frvp_breakout", "frvp_breakout_strong",
          "heikin_ashi_reversal", "heikin_ashi_reversal_strict",
          "bb_squeeze_breakout", "bb_squeeze_breakout_strict",
          "orb_funding_session", "orb_funding_session_strong",
          "vwap_band_fade", "vwap_band_fade_stretch",
          "volume_climax_exhaustion", "volume_climax_exhaustion_strict",
          "engulfing_rsi_extreme", "engulfing_rsi_extreme_strict",
          "pinbar_stochastic_cross", "pinbar_stochastic_cross_strict",
          "doji_macd_flip", "doji_macd_flip_strict")

SESSION_MS=28_800_000
OR_WINDOW_MS=1_800_000

@dataclass(frozen=True)
class Signal:
    index: int
    side: str
    stop: float

def generate_signals(frame, setup, prepared=None):
    """Emit closed-bar signals; any pivot is consumed only at confirmation index."""
    if setup not in SETUPS:
        raise ValueError(f"unknown setup: {setup}")
    o,h,l,c,v = (frame[x].to_numpy(float) for x in ("o","h","l","c","v"))
    n=len(c)
    prepared=prepared or {}
    a=prepared["atr"] if "atr" in prepared else indicators.atr(h,l,c,14)
    swings=prepared.get("swings")
    sh,sl=swings if swings is not None else indicators.confirmed_swings(h,l,3)
    out=[]
    def emit(i, side, stop):
        if i+1<n and np.isfinite(stop) and stop>0 and ((side=="long" and stop<c[i]) or (side=="short" and stop>c[i])):
            out.append(Signal(i,side,float(stop)))
    if setup=="supertrend":
        direction=indicators.supertrend_direction(h,l,c,a)
        for i in range(1,n):
            mid=(h[i]+l[i])/2
            if direction[i]!=direction[i-1] and direction[i]: emit(i,"long" if direction[i]>0 else "short", mid-3*a[i] if direction[i]>0 else mid+3*a[i])
    elif setup=="trendline_breakout":
        # Fixed-window O(n) regression: equivalent to polyfit over x=0..19,
        # while avoiding millions of tiny LAPACK calls on 1m data.
        coeff=np.arange(20,dtype=float)-9.5
        weighted=np.convolve(c,coeff[::-1],mode="valid")
        sums=np.convolve(c,np.ones(20),mode="valid")
        slopes=weighted/665.0; intercepts=sums/20-slopes*9.5
        lines=intercepts+slopes*20; prev_lines=intercepts+slopes*19
        for i in range(30,n):
            if not np.isfinite(a[i]): continue
            k=i-20
            if c[i]>lines[k] and c[i-1]<=prev_lines[k]: emit(i,"long",c[i]-3*a[i])
            if c[i]<lines[k] and c[i-1]>=prev_lines[k]: emit(i,"short",c[i]+3*a[i])
    elif setup=="sr_retest":
        for side in ("long","short"):
            level=None; broken=False; known=[]
            for i in range(10,n):
                for pivot in (sh[i],sl[i]):
                    if np.isfinite(pivot): known.append(float(pivot))
                known=known[-60:]
                if not broken:
                    known_arr=np.asarray(known,float)
                    cand=known_arr[known_arr<c[i]] if side=="long" else known_arr[known_arr>c[i]]
                    if len(cand): level=float(cand[-1])
                    if level and ((c[i]>level and c[i-1]<=level) if side=="long" else (c[i]<level and c[i-1]>=level)): broken=True
                elif level and ((l[i]<=level*1.003 and c[i]>level and c[i]>o[i]) if side=="long" else (h[i]>=level*.997 and c[i]<level and c[i]<o[i])):
                    emit(i,side,l[i] if side=="long" else h[i]); broken=False; level=None
    elif setup=="sweep_choch_retest":
        for side in ("long","short"):
            sweep=None; choch=None
            for i in range(3,n):
                piv=sl[i-3] if side=="long" else sh[i-3]
                if np.isfinite(piv) and ((l[i]<piv<c[i]) if side=="long" else (h[i]>piv>c[i])): sweep=(i,float(l[i] if side=="long" else h[i]))
                if sweep and i>sweep[0] and ((c[i]>max(h[sweep[0]:i]) if side=="long" else c[i]<min(l[sweep[0]:i]))): choch=(i,sweep[1],float((o[i-1]+c[i-1])/2))
                if choch and i>choch[0] and ((l[i]<=choch[2]<=c[i]) if side=="long" else (h[i]>=choch[2]>=c[i])): emit(i,side,choch[1]); sweep=choch=None
    elif setup=="avwap_hl":
        prev_lows=[]; prev_highs=[]
        for i in range(3,n):
            if np.isfinite(sl[i]) and i>0:
                if prev_lows and sl[i]>prev_lows[-1]:
                    anchor=i-3; p=(h[anchor:i+1]+l[anchor:i+1]+c[anchor:i+1])/3; vw=np.average(p,weights=np.maximum(v[anchor:i+1],1e-12))
                    if l[i]<=vw*1.003 and c[i]>vw and c[i]>o[i]: emit(i,"long",sl[i])
            if np.isfinite(sh[i]):
                if prev_highs and sh[i]<prev_highs[-1]:
                    anchor=i-3; p=(h[anchor:i+1]+l[anchor:i+1]+c[anchor:i+1])/3; vw=np.average(p,weights=np.maximum(v[anchor:i+1],1e-12))
                    if h[i]>=vw*.997 and c[i]<vw and c[i]<o[i]: emit(i,"short",sh[i])
            if np.isfinite(sl[i]): prev_lows.append(float(sl[i]))
            if np.isfinite(sh[i]): prev_highs.append(float(sh[i]))
    elif setup=="rsi_divergence":
        r=prepared["rsi"] if "rsi" in prepared else indicators.rsi(c,14); lows=[]; highs=[]
        for i in range(n):
            if np.isfinite(sl[i]):
                if lows and sl[i]<lows[-1][1] and r[i]>lows[-1][2]: emit(i,"long",sl[i])
                lows.append((i,sl[i],r[i]))
            if np.isfinite(sh[i]):
                if highs and sh[i]>highs[-1][1] and r[i]<highs[-1][2]: emit(i,"short",sh[i])
                highs.append((i,sh[i],r[i]))
    elif setup=="candle_reversal":
        pat=prepared["patterns"] if "patterns" in prepared else indicators.candle_patterns(o,h,l,c)
        vw=prepared["vwap"] if "vwap" in prepared else indicators.vwap(h,l,c,v,frame.t_open_ms)
        zones=[]
        for i in range(1,n):
            if np.isfinite(sh[i]): zones.append(float(sh[i]))
            if np.isfinite(sl[i]): zones.append(float(sl[i]))
            near=abs(c[i]-vw[i])<=.5*a[i] or (bool(zones) and np.min(np.abs(c[i]-np.asarray(zones[-60:])))<=.5*a[i])
            if near and (pat["bull_engulfing"][i-1] or pat["hammer_pin"][i-1]) and c[i]>h[i-1]: emit(i,"long",l[i-1])
            if near and (pat["bear_engulfing"][i-1] or pat["shooting_star_pin"][i-1]) and c[i]<l[i-1]: emit(i,"short",h[i-1])
    elif setup in ("engulfing_rsi_extreme","engulfing_rsi_extreme_strict"):
        # Engulfing + RSI exhaustion confirmation (P9-A): reuse the shared
        # candle-pattern and Wilder RSI arrays so every setup reads identical
        # indicator definitions. Causal alignment follows candle_reversal's
        # one-bar lag: both the engulfing pattern and RSI threshold are read at
        # i-1, the just-closed engulfing bar; signal i is emitted on the next
        # closed bar. Using RSI[i] would let the follow-up bar, rather than the
        # engulfing reversal bar, determine whether prior-move exhaustion existed.
        # RSI <30 confirms bullish exhaustion; RSI >70 confirms bearish exhaustion.
        # Stops are the engulfing bar's low/high, and emit() suppresses stops
        # already invalidated by the signal bar's close.
        pat=prepared["patterns"] if "patterns" in prepared else indicators.candle_patterns(o,h,l,c)
        r=prepared["rsi"] if "rsi" in prepared else indicators.rsi(c,14)
        # The sole P9-A refinement follows the base run's stop-dominated failures:
        # test only deeper RSI exhaustion (<20/>80), leaving the candle geometry
        # and alignment unchanged so the rerun changes one predeclared condition.
        low_rsi,high_rsi=(20,80) if setup=="engulfing_rsi_extreme_strict" else (30,70)
        for i in range(1,n):
            if pat["bull_engulfing"][i-1] and np.isfinite(r[i-1]) and r[i-1]<low_rsi:
                emit(i,"long",l[i-1])
            if pat["bear_engulfing"][i-1] and np.isfinite(r[i-1]) and r[i-1]>high_rsi:
                emit(i,"short",h[i-1])
    elif setup in ("pinbar_stochastic_cross", "pinbar_stochastic_cross_strict"):
        # P9-B pin-bar plus stochastic confirmation: the pattern bar j itself must
        # have %K < 20 for a hammer or %K > 80 for a shooting star; oversold/overbought
        # is not carried from adjacent bars. A bullish cross is %K[j-1] <= %D[j-1]
        # and %K[j] > %D[j], with bearish cross the exact inverse. Confirmation may
        # occur at j, j+1, or j+2; the pattern remains pending only through j+2 and
        # the signal is emitted at the actual cross bar i, never backdated to j.
        # This uses only closed data through i. The stop remains the original pin
        # bar's low/high, even for delayed confirmation; emit() suppresses it when
        # that stop is no longer on the valid side of the confirming close.
        # One bounded strict refinement requires %K < 10 / > 90 at pattern bar j.
        pat=prepared["patterns"] if "patterns" in prepared else indicators.candle_patterns(o,h,l,c)
        k,d=prepared["stochastic"] if "stochastic" in prepared else indicators.stochastic(h,l,c)
        strict=setup=="pinbar_stochastic_cross_strict"
        extreme=10.0 if strict else 20.0
        for i in range(1,n):
            bullish=k[i-1]<=d[i-1] and k[i]>d[i]
            bearish=k[i-1]>=d[i-1] and k[i]<d[i]
            if not (bullish or bearish): continue
            for j in range(max(0,i-2),i+1):
                if bullish and pat["hammer_pin"][j] and np.isfinite(k[j]) and k[j]<extreme:
                    emit(i,"long",l[j]); break
                if bearish and pat["shooting_star_pin"][j] and np.isfinite(k[j]) and k[j]>100-extreme:
                    emit(i,"short",h[j]); break
    elif setup=="fibonacci_pocket":
        lastlo=lasthi=None
        for i in range(n):
            if np.isfinite(sl[i]): lastlo=(i,float(sl[i]))
            if np.isfinite(sh[i]): lasthi=(i,float(sh[i]))
            if lastlo and lasthi and lastlo[0]<lasthi[0] and i>lasthi[0]:
                lo,hi=lastlo[1],lasthi[1]; z1=hi-.786*(hi-lo); z2=hi-.618*(hi-lo)
                if z1<=l[i]<=z2 and c[i]>o[i]: emit(i,"long",lo-.886*(hi-lo))
            if lastlo and lasthi and lasthi[0]<lastlo[0] and i>lastlo[0]:
                hi,lo=lasthi[1],lastlo[1]; z1=lo+.618*(hi-lo); z2=lo+.786*(hi-lo)
                if z1<=h[i]<=z2 and c[i]<o[i]: emit(i,"short",hi+.886*(hi-lo))
    elif setup=="order_block":
        zones=[]
        for i in range(n):
            remaining=[]
            for low,high,born,side in zones:
                invalid=(i-born>60 or (c[i]<low if side=="long" else c[i]>high))
                if invalid: continue
                if l[i]<=high and h[i]>=low and (c[i]>high if side=="long" else c[i]<low):
                    emit(i,side,low if side=="long" else high)
                    # Port semantics: signal-fired zones are dropped because the original
                    # remaining-list branch appends only in its `else` arm.
                else: remaining.append((low,high,born,side))
            zones=remaining
            if i>=14 and np.isfinite(a[i-1]):
                if c[i]-o[i]>1.5*a[i-1] and c[i]>h[i-1]:
                    for j in range(i-1,max(-1,i-6),-1):
                        if c[j]<o[j]: zones.append((l[j],h[j],i,"long")); break
                # Symmetric short side is an extension; the cited source defines long only.
                if o[i]-c[i]>1.5*a[i-1] and c[i]<l[i-1]:
                    for j in range(i-1,max(-1,i-6),-1):
                        if c[j]>o[j]: zones.append((l[j],h[j],i,"short")); break
    elif setup=="fabio_liquidity_mss":
        if n>=2:
            bar_minutes=round((int(frame.t_open_ms.iloc[1])-int(frame.t_open_ms.iloc[0]))/60000)
            if bar_minutes>0:
                htf_minutes=60 if bar_minutes<60 else 4*bar_minutes
                bar_length=max(1,round(htf_minutes/bar_minutes))
                last_hi=pd.Series(h).rolling(bar_length,min_periods=bar_length).max().shift(1).to_numpy()
                last_lo=pd.Series(l).rolling(bar_length,min_periods=bar_length).min().shift(1).to_numpy()
                mss_hi=pd.Series(h).rolling(4,min_periods=4).max().shift(1).to_numpy()
                mss_lo=pd.Series(l).rolling(4,min_periods=4).min().shift(1).to_numpy()
                state="waiting"; locked_high=locked_low=grab_level=None; entry_type=None
                for i in range(n):
                    if state=="waiting":
                        if np.isfinite(last_hi[i]) and h[i]>last_hi[i]:
                            locked_high,locked_low,grab_level,entry_type=mss_hi[i],mss_lo[i],last_hi[i],"short"; state="waiting_for_mss"
                        elif np.isfinite(last_lo[i]) and l[i]<last_lo[i]:
                            locked_high,locked_low,grab_level,entry_type=mss_hi[i],mss_lo[i],last_lo[i],"long"; state="waiting_for_mss"
                    elif entry_type=="short" and np.isfinite(locked_low) and l[i]<locked_low:
                        emit(i,"short",grab_level); state="waiting"
                    elif entry_type=="long" and np.isfinite(locked_high) and h[i]>locked_high:
                        emit(i,"long",grab_level); state="waiting"
                    # The Pine armed state has no timeout/opposite-grab reset; this port likewise waits
                    # indefinitely, then resets after one entry so a continuing inequality cannot re-fire.
    elif setup=="fvg_fill":
        zones=[]
        for i in range(n):
            remaining=[]
            for low,high,born,side in zones:
                # Single refinement: only accept fills within 12 bars of formation.
                invalid=(i-born>12 or (c[i]<low if side=="long" else c[i]>high))
                if invalid: continue
                if l[i]<=high and h[i]>=low:
                    emit(i,side,low if side=="long" else high)
                else: remaining.append((low,high,born,side))
            zones=remaining
            if i>=2:
                if l[i]>h[i-2]: zones.append((h[i-2],l[i],i,"long"))
                # Symmetric short side is an extension; the cited source defines long only.
                if h[i]<l[i-2]: zones.append((h[i],l[i-2],i,"short"))
    elif setup in ("frvp_breakout","frvp_breakout_strong"):
        # Fixed-range volume profile, ported from the daily-candle rule in
        # app/technical_signal_common.py's `frvp` branch (and
        # docs/전략-백테스트-종합.md 13-8): a rolling volume-weighted histogram of
        # typical price proxies true volume-at-price (daily/intraday OHLCV has no
        # tick-level volume-at-price; this is the same documented proxy, not a new
        # limitation). Lookback is a FIXED 60-bar window on every timeframe -- same
        # convention as this file's other fixed-bar-count windows (order_block's
        # 60-bar zone expiry, trendline_breakout's 20-bar fit) -- so it spans 60
        # minutes on 1m vs 60 hours on 60m; bar-count is kept constant rather than
        # time-scaled for consistency with the rest of this module, at the cost of
        # a much narrower real-time profile on faster timeframes.
        # Causal boundary: the histogram at bar i uses only typical[i-60:i], i.e.
        # bars i-60..i-1 (current bar i is never in its own profile). The "yesterday"
        # test reads c[i-1] (the last bar inside that window) and the breakout test
        # reads c[i] (today, the signal bar itself, closed) -- matching every other
        # setup here that emits at the closed signal bar and enters next bar's open.
        # "_strong" is the single bounded P7-B refinement: require the breakout
        # close to clear the POC by >=0.25*ATR[i-1] (same ATR already shared by
        # every other setup here) instead of by an arbitrarily thin margin, on the
        # judgment that a breakout that barely pokes through the POC bin is harder
        # to distinguish from noise than one with real thrust behind it. It does
        # not touch the POC/LVN geometry itself, which stays exactly as specified.
        window=60; bins=24; typical=(h+l+c)/3.0; idx=np.arange(bins)
        buffer=lambda i:0.25*a[i-1] if setup=="frvp_breakout_strong" and np.isfinite(a[i-1]) else 0.0
        for i in range(window,n):
            seg_p=typical[i-window:i]; seg_v=v[i-window:i]
            if not np.any(seg_v>0): continue
            hist,edges=np.histogram(seg_p,bins=bins,weights=np.maximum(seg_v,0.0))
            poc=int(np.argmax(hist))
            if hist[poc]<=0: continue
            centers=(edges[:-1]+edges[1:])/2; poc_price=float(centers[poc]); buf=buffer(i)
            below=np.flatnonzero((idx<poc)&(hist>0)&(hist<.5*hist[poc]))
            if len(below):
                lvn=float(centers[below[-1]])
                if lvn<=c[i-1]<poc_price and c[i]>poc_price+buf: emit(i,"long",lvn)
            # Symmetric short side (nearest low-volume node ABOVE the POC, mirrored
            # thresholds) is an extension: the cited daily-candle source and the
            # app/technical_signal_common.py port both define the long case only.
            above=np.flatnonzero((idx>poc)&(hist>0)&(hist<.5*hist[poc]))
            if len(above):
                lvn_up=float(centers[above[0]])
                if poc_price<c[i-1]<=lvn_up and c[i]<poc_price-buf: emit(i,"short",lvn_up)
    elif setup=="heikin_ashi_reversal":
        hc=(o+h+l+c)/4; ho=np.empty(n,float)
        if n:
            ho[0]=(o[0]+c[0])/2
            for i in range(1,n): ho[i]=(ho[i-1]+hc[i-1])/2
        # HA_Open is the recursive midpoint broken by the flip; emit() suppresses anchors on the wrong side of price.
        for i in range(1,n):
            if hc[i-1]<=ho[i-1] and hc[i]>ho[i]: emit(i,"long",ho[i])
            # Symmetric short-side flip is this research port's extension; the cited source defines long only.
            if hc[i-1]>=ho[i-1] and hc[i]<ho[i]: emit(i,"short",ho[i])
    elif setup in ("volume_climax_exhaustion","volume_climax_exhaustion_strict"):
        # Volume climax exhaustion reversal (P8-D): a volume spike far above the
        # recent trailing average, landing on a bar that pushes to a new local
        # extreme but closes back away from that extreme (a rejection wick),
        # marks one-sided crowd capitulation/blow-off that tends to reverse.
        # This is a volume-primary trigger -- distinct from this file's other
        # SMC/trend-following/pattern setups -- geometry only confirms exhaustion.
        #
        # Causal boundary: the rolling volume baseline at bar i is the trailing
        # mean of bars i-20..i-1 (pandas rolling(20) ending at i-1, produced by
        # rolling(20).mean().shift(1)) -- the signal bar's own volume is never
        # part of its own baseline. The "new local high/low" check uses a 10-bar
        # window i-9..i that DOES include the signal bar itself (the bar must be
        # the extreme of its own recent window to count as a fresh push); both
        # windows only read bars already closed by bar i.
        #
        # "_strict" is the single bounded P8-D refinement: raise the climax
        # volume multiple from 3x to 5x the trailing mean. A rarer, more extreme
        # spike is less likely to be ordinary noise than a 3x bar; the rejection
        # wick geometry and 10-bar extreme window are left untouched so only one
        # parameter changes.
        k=5.0 if setup=="volume_climax_exhaustion_strict" else 3.0
        vol_ma=pd.Series(v).rolling(20,min_periods=20).mean().shift(1).to_numpy()
        climax=(vol_ma>0)&(v>k*vol_ma)
        span=np.maximum(h-l,1e-12)
        roll_max=pd.Series(h).rolling(10,min_periods=10).max().to_numpy()
        roll_min=pd.Series(l).rolling(10,min_periods=10).min().to_numpy()
        for i in range(20,n):
            if not(np.isfinite(vol_ma[i]) and climax[i]): continue
            if h[i]>=roll_max[i] and (c[i]-l[i])/span[i]<0.5: emit(i,"short",h[i])
            if l[i]<=roll_min[i] and (h[i]-c[i])/span[i]<0.5: emit(i,"long",l[i])
    elif setup=="heikin_ashi_reversal_strict":
        hc=(o+h+l+c)/4; ho=np.empty(n,float)
        if n:
            ho[0]=(o[0]+c[0])/2
            for i in range(1,n): ho[i]=(ho[i-1]+hc[i-1])/2
        # One conviction filter, fixed before the rerun: require a flip-bar HA body >= 0.5 ATR14.
        # Half an ATR removes marginal flips while retaining a scale-normalized, causal threshold.
        for i in range(1,n):
            if not np.isfinite(a[i]) or abs(hc[i]-ho[i])<0.5*a[i]: continue
            if hc[i-1]<=ho[i-1] and hc[i]>ho[i]: emit(i,"long",ho[i])
            if hc[i-1]>=ho[i-1] and hc[i]<ho[i]: emit(i,"short",ho[i])
    elif setup in ("bb_squeeze_breakout","bb_squeeze_breakout_strict"):
        # Bollinger Band squeeze breakout (P8-A): a volatility-regime setup, deliberately
        # distinct from this file's momentum/SMC-structure rules. mid/upper/lower are a
        # rolling 20-bar SMA +/- 2x population stdev (standard conventions, not tuned).
        # width = (upper-lower)/mid is each bar's own normalized band width. "Squeeze" is
        # width sitting in the bottom decile (<=10th percentile) of its own trailing
        # 120-bar history (both window lengths are the suggested defaults). Percentile
        # rank is fully causal (indicators.rolling_percentile_rank): bar i's rank uses
        # only width[i-119..i], itself included (same convention bollinger() already uses
        # for its own rolling window), and is NaN until 120 consecutive finite width
        # values exist, i.e. never a future bar.
        # A signal requires the squeeze to have been active at ANY point in the four
        # bars strictly before the signal bar (i-4..i-1) -- "within a few bars of exiting
        # a squeeze" -- so a breakout bar whose own width has already expanded past the
        # threshold still counts; a real squeeze-breakout reads as contraction-then-
        # expansion, and the expansion bar's width is expected to jump. The breakout
        # test itself compares the signal bar's own close to its own band (band at bar i
        # already incorporates c[i], the same causal convention as bollinger() and
        # standard Bollinger-band breakout usage -- not a lookahead: everything is known
        # as of bar i's close). Stop is the opposite band at the signal bar, already a
        # volatility-scaled invalidation level.
        # "_strict" is the single bounded P8-A refinement, chosen from the base rule's own
        # Stage C diagnostics rather than a priori: base-rule trades are dominated by
        # `timeout` (roughly three in four), not `stop`, meaning most breakouts drift
        # sideways without enough thrust to reach the R target OR the stop within the
        # 12-bar holding window -- a "fakeout/no-follow-through" failure mode, not a
        # wrong-direction one. That points at breakout *strength*, not squeeze *purity*,
        # so the refinement reuses this file's existing ATR-buffer convention (same as
        # frvp_breakout_strong) instead of tightening the percentile: require the close to
        # clear the band by >=0.25*ATR14 rather than by an arbitrarily thin margin. The
        # squeeze detection and band geometry are otherwise untouched.
        mid,upper,lower=indicators.bollinger(c,20,2)
        width=(upper-lower)/mid
        pct=indicators.rolling_percentile_rank(width,120)
        squeeze=np.where(np.isfinite(pct),pct<=0.10,False)
        strong=setup=="bb_squeeze_breakout_strict"
        lag=4
        for i in range(lag,n):
            if not (np.isfinite(upper[i]) and np.isfinite(lower[i])): continue
            if not np.any(squeeze[i-lag:i]): continue
            buf=0.25*a[i] if strong and np.isfinite(a[i]) else 0.0
            if c[i]>upper[i]+buf: emit(i,"long",lower[i])
            elif c[i]<lower[i]-buf: emit(i,"short",upper[i])
    elif setup in ("orb_funding_session","orb_funding_session_strong"):
        # The first 30 minutes after each 8-hour Binance funding boundary define
        # the range; only closed bars at/after that window can break it. This is
        # time-based, so 60m bars use the first full bar as the range (a known
        # coarse-timeframe limitation). The first data session may be partial,
        # affecting at most one session per symbol. The strong variant requires
        # a 0.25*ATR14 clearance at the signal bar, filtering marginal breaks.
        t=frame.t_open_ms.to_numpy(np.int64); session=None; or_high=-np.inf; or_low=np.inf; triggered=False
        for i in range(n):
            current=int(t[i]//SESSION_MS*SESSION_MS)
            if current!=session:
                session=current; or_high=-np.inf; or_low=np.inf; triggered=False
            elapsed=int(t[i])-current
            if elapsed<OR_WINDOW_MS:
                or_high=max(or_high,h[i]); or_low=min(or_low,l[i])
                continue
            if triggered or not (np.isfinite(or_high) and np.isfinite(or_low)): continue
            strong=setup=="orb_funding_session_strong"
            if strong and not np.isfinite(a[i]): continue
            buf=.25*a[i] if strong else 0.0
            if c[i]>or_high and (not strong or c[i]>=or_high+buf):
                emit(i,"long",or_low); triggered=True
            elif c[i]<or_low and (not strong or c[i]<=or_low-buf):
                emit(i,"short",or_high); triggered=True
    elif setup in ("vwap_band_fade","vwap_band_fade_stretch"):
        # P8-C: mean-reversion fade, the opposite directional bet from every
        # continuation/breakout rule above. Rolling 20-bar VWAP of typical price
        # (h+l+c)/3 weighted by volume -- the same fixed 20-bar rolling convention
        # as app/technical_signal_common.py's `vwap` branch (20-day rolling window
        # there; 20 bars here on whatever timeframe is being evaluated, consistent
        # with this file's other fixed-bar-count windows: trendline_breakout's 20,
        # order_block/fvg_fill's zone-expiry windows). Causal: the window ending at
        # bar i includes bar i's own closed OHLCV, matching vwap()/avwap_hl/
        # candle_reversal above, which all read the current closed bar's own price
        # and volume into their reference level.
        # Bands are VWAP +/- 2 * rolling stdev of (close - VWAP) over the same
        # 20-bar window (population stdev, ddof=0, same convention as
        # indicators.bollinger). This is a band-extreme fade, structurally distinct
        # from avwap_hl (swing-retest continuation off an anchored VWAP) and
        # rsi_divergence (price/RSI divergence at swing pivots) already in this
        # file -- no band, no extreme-piercing/rejection logic, no stretch measure.
        # Signal (fade, not breakout-confirmation): once a bar's high pierces above
        # the upper band, track the running extreme high while price stays outside;
        # the bar whose CLOSE first comes back inside the band is the rejection
        # signal bar (short), stop = that tracked extreme high. Mirror for the lower
        # band (long), tracking the running extreme low. A same-bar pierce-and-close
        # -back-inside also qualifies. "_stretch" is the single bounded P8-C
        # refinement: additionally require the tracked extreme to clear the band
        # edge recorded at the moment of first piercing by >=0.5*ATR14 (same ATR
        # already shared by every other setup here, same 0.5 threshold this file
        # already uses for heikin_ashi_reversal_strict's conviction filter) before
        # the rejection counts as a valid "stretch" rather than a marginal wick.
        typical=(h+l+c)/3.0
        vw=(pd.Series(typical*v).rolling(20,min_periods=20).sum()/pd.Series(v).rolling(20,min_periods=20).sum()).to_numpy()
        dev=pd.Series(c-vw).rolling(20,min_periods=20).std(ddof=0).to_numpy()
        upper=vw+2*dev; lower=vw-2*dev
        stretch=setup=="vwap_band_fade_stretch"
        # Both sides are tracked in a single chronological pass (rather than two
        # separate full side-loops like sr_retest/avwap_hl above) so that emit()
        # calls are appended to `out` in non-decreasing bar order regardless of
        # which side fires first -- required for the shared causality test, which
        # inspects insertion order.
        state={"long":[False,None,None],"short":[False,None,None]}
        for i in range(n):
            for side in ("long","short"):
                edge=lower[i] if side=="long" else upper[i]
                if not np.isfinite(edge): continue
                extended,extreme,pierce_edge=state[side]
                pierced=(l[i]<edge) if side=="long" else (h[i]>edge)
                back_inside=(c[i]>=edge) if side=="long" else (c[i]<=edge)
                if not extended:
                    if pierced:
                        extreme=l[i] if side=="long" else h[i]; pierce_edge=edge
                        if back_inside:
                            ok=(not stretch) or (np.isfinite(a[i]) and abs(pierce_edge-extreme)>=0.5*a[i])
                            if ok: emit(i,side,extreme)
                            extended=False; extreme=pierce_edge=None
                        else: extended=True
                else:
                    extreme=min(extreme,l[i]) if side=="long" else max(extreme,h[i])
                    if back_inside:
                        ok=(not stretch) or (np.isfinite(a[i]) and abs(pierce_edge-extreme)>=0.5*a[i])
                        if ok: emit(i,side,extreme)
                        extended=False; extreme=pierce_edge=None
                state[side]=[extended,extreme,pierce_edge]
    elif setup in ("doji_macd_flip","doji_macd_flip_strict"):
        # P9-C: candlestick pattern (doji = indecision) gated by an independent
        # momentum indicator (standard 12/26/9 MACD histogram) flipping sign --
        # a confluence/confirmation hypothesis, structurally distinct from this
        # file's standalone pattern rules (candle_reversal) and standalone
        # indicator rules (rsi_divergence, supertrend): both conditions must
        # fire on/around the same bar.
        #
        # Doji: indicators.significant_doji(), a small body relative to the
        # bar's own high-low range (same 10% body/range constant as
        # indicators.candle_patterns()'s existing "doji" key, kept as a
        # standalone helper rather than edited into that key so features.py's
        # LLM feature snapshot pipeline, which already reads that key, is
        # untouched) AND a range >= 0.5*ATR14 so dead-flat non-moves don't
        # count as meaningful indecision.
        #
        # MACD histogram flip: histogram[i-1] and histogram[i] straddle zero on
        # the doji bar itself -- the most literal reading of "the histogram is
        # flipping direction" (a same-bar sign change), not a longer lookback
        # window. Direction follows the histogram's new sign: turning positive
        # -> long, turning negative -> short. Stop is the doji bar's own low
        # (long) / high (short), the natural invalidation level for an
        # indecision-bar reversal.
        #
        # "_strict" is the single bounded P9-C refinement (see HYPOTHESES /
        # docs/chart_predictor/rounds.md): tighten the doji body threshold from
        # 10% to 5% of range. The 0.5-ATR range floor and the flip/stop logic
        # are left untouched so only one parameter changes.
        strict=setup=="doji_macd_flip_strict"
        doji=indicators.significant_doji(o,h,l,c,a,body_ratio=0.05 if strict else 0.10)
        hist=prepared["macd_hist"] if "macd_hist" in prepared else indicators.macd(c)[2]
        for i in range(1,n):
            if not doji[i] or not (np.isfinite(hist[i-1]) and np.isfinite(hist[i])): continue
            if hist[i-1]<=0<hist[i]: emit(i,"long",l[i])
            elif hist[i-1]>=0>hist[i]: emit(i,"short",h[i])
    return out
