# US-33 - Market-regime conditioning of the US-18 cell (US, Round 6 prereg)

## Signal (fixed defaults)
Three conditions (each a separate trial family, evaluated on DYN, F14, F18 = 9 trials): (a) SPY close_t > SMA200(SPY)_t; (b) SPY 10-day realized vol (annualized std of daily returns t-9..t) < median of the same quantity over the trailing 250 bars; (c) SPY close_t >= 0.90 x max(SPY close over t-251..t). Entry/exit as the base signal.

## Common (Round 6 US hypotheses; written 2026-11-13 BEFORE any run of them)
- Base signal = the US-18 Stage 2 candidate cell (126-day return top quartile of the universe AND RSI(2)<5; buy close t; exit first close > SMA5 within 5 bars else t+5). Universes: DYN = dynamic PIT top-100 (original), F14 / F18 = frozen top-100 at 2014-12-31 / 2018-12-31. Dev only; holdout locked; derived from dev data (US-18 dev year 2022: -0.37%/trade over 353 trades) and first principles.
- Round-5 finding (dev only, recorded before this round): US-18 mechanism at fixed holds 5/10/20 is Stage-1 positive on DYN (t 4.3 / 4.5 / 6.3) but noise on F14/F18 (t 1.0..2.2) => the edge depends on the survivorship-laden dynamic universe. NEW STRICTER GATE (added now, before any Stage 2 is run, applies to every candidate from here): a Stage 1 survivor enters Stage 2 only if the same specification also has net mean>0, 2x-cost mean>0 and clustered t>=2 on BOTH frozen universes F14 and F18 (or, for ETF/no-universe ideas, passes on its own), plus top-5 symbol share <= 40%.
- Verdict rule: PLAN Stage 1 (net>0, t>=3, both halves>0; halves = midpoint of each universe's event window). Cumulative BH list: 129 trials so far.
