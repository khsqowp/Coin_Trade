# KR 069500 compression-breakout test — results

Decision: reject this candidate. The reproducible, frozen-rule run does not support the proposed edge. It is a development-data result, not OOS validation.

## Frozen rule and data

The complete preregistration is [equity_kr_compression_breakout_preregistration_20261115.md](equity_kr_compression_breakout_preregistration_20261115.md). The only input is .kis-cache-local/KR_069500.csv. The parser reads the header and rows strictly before the 2024-11-12T00:00:00Z exclusive cutoff and stops at the first cutoff timestamp without parsing that row's OHLCV. It fingerprints the header and parsed pre-cutoff rows only.

On a signal close, require (a) the sample standard deviation of the latest 10 daily close-to-close returns to be at or below the 30th percentile of the prior 252 available 10-day-volatility observations, excluding the current observation, (b) a close above the previous 20-session maximum close after the previous session was not above its prior 20-session maximum, and (c) close above SMA200. Buy next session open; sell next session open after a close below SMA20 or after 10 completed holding sessions, whichever comes first. Cash return is 0%. One position at a time.

Base costs are 0.015% commission and 0.10% slippage per side; stress uses 0.015% commission and 0.15% slippage per side. ETF sell tax is set to 0. Costs apply multiplicatively to fills. No distributions, leverage, or liquidity constraints are modeled.

The 3,513 pre-cutoff rows span 2010-08-09 through 2024-11-11. All indicators first become eligible on 2011-08-26. There are 78 eligible signals; 50 complete, non-overlapping trades were executed in each cost case across 11 calendar years. Base exits: 23 below-SMA20, 27 ten-session expiry. No signal could complete only if it fell in the final 11 bars; none did.

## Results

| Portfolio | Cost | CAGR | MDD | Turnover | CAGR 95% six-month block CI |
|---|---:|---:|---:|---:|---:|
| Compression + breakout | Base | −0.004% | −15.932% | 100.51× | −2.770% to +3.491% |
| Compression + breakout | Stress | −0.381% | −18.661% | 100.69× | −3.174% to +3.082% |
| 069500 buy-and-hold | Base | +4.688% | −38.080% | 1.96× | −3.593% to +13.327% |
| 069500 buy-and-hold | Stress | +4.684% | −38.080% | 1.96× | −3.599% to +13.323% |
| SMA200 close-confirmed long/cash | Base | −1.204% | −41.692% | 141.88× | −7.917% to +7.022% |
| SMA200 close-confirmed long/cash | Stress | −1.755% | −45.170% | 142.66× | −8.568% to +6.554% |
| Cash | Both | 0.000% | 0.000% | 0.00× | 0.000% |

The paired six-month circular moving-block bootstrap (10,000 draws, seed 69500) gives the candidate-minus-buy-and-hold CAGR difference interval of **−11.666% to +2.630%** at base cost and **−12.089% to +2.309%** at stress cost. Both include zero. The stress CAGR is negative. The candidate fails the frozen gate: only 50 trades versus the required 100, the paired interval does not establish excess CAGR, and stress CAGR is non-positive. Its lower measured drawdown does not offset its lack of return evidence.

## Reproducibility and mismatch audit

Run from the repository root:

    PYTHONDONTWRITEBYTECODE=1 /opt/anaconda3/bin/python3 scripts/research/equity_kr_compression_breakout.py --output /tmp/equity_kr_compression_breakout_20261115.json --trades /tmp/equity_kr_compression_breakout_trades_20261115.json
    PYTHONDONTWRITEBYTECODE=1 /opt/anaconda3/bin/python3 -m pytest -p no:cacheprovider -q tests/test_equity_kr_compression_breakout.py

The reproducible output is retained in [the result JSON](equity_kr_compression_breakout_20261115.json) and [the trade-level JSON](equity_kr_compression_breakout_trades_20261115.json). Source is [equity_kr_compression_breakout.py](../../scripts/research/equity_kr_compression_breakout.py); the four focused causal/execution/cutoff tests are in tests/test_equity_kr_compression_breakout.py.

An agent's initial in-memory summary reported 51 trades and evaluation start 2012-08-16 but provided no code or saved event list. That start date is the first eligibility date for a 252-day volatility feature, while this preregistration explicitly uses 10-day volatility compared with the trailing distribution of 10-day volatility. The two are different strategies. The agent run is therefore not incorporated as a reproduction or combined with this result. Until an exact independent implementation and its signal/trade list are supplied, its metrics remain unverified.

## Limitations

This is a single fixed hypothesis on an already-inspected historical series. It is not a sealed OOS test. Current cached history may contain survivorship and corporate-action adjustment issues; distribution reinvestment is omitted. The return path assumes all NAV is invested while in a position, fractional shares, zero-yield cash, and idealized next-open fills. A 50-trade sample is insufficient under the preregistered gate. Do not tune this same history or promote the rule to paper/live trading based on the drawdown comparison.
