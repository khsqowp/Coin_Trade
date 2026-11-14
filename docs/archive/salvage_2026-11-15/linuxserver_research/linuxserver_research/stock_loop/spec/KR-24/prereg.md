# KR-24 - post-crash rebound with volume dry-up: day t-1 ret<=-15%, day t volume<0.5x that day, buy close t, hold 3 (KR Round 2, Stage 1 prereg)
Written 2026-11-13T16:21:15 BEFORE any Round-2 run.

## Signal
ret_{t-1}<=-15% AND volume_t<0.5*volume_{t-1} AND ret_t>-3%. Buy close t, sell close t+3.

## Portfolio slots N
5

## Defaults (fixed)
{'r': 0.15, 'dry': 0.5, 'h': 3}

## Stage-2 grid
{'r': (0.1, 0.15, 0.2), 'dry': (0.3, 0.5, 0.7), 'h': (2, 3, 5)}

## Round-2 common (inherits spec/KR-01/prereg.md 'Common' section unchanged: universe, liquidity>=2e9, costs A/B/tax18/2x, dev data only, holdout locked)
- Why Round 2: Round-1 audit found the KRX opening price is systematically elevated (all-liquid-stock open->close mean -0.14%/day, overnight +0.11..0.17%/day; same sign in KOSPI/KOSDAQ index data and every year). Buying at the next OPEN therefore carries a structural ~0.14%/day drag. Round 2 uses CLOSE entries (MOC) for non-gap ideas. Caveat: signal uses close_t and fills at close_t (closing-auction indicative price 15:20-15:30); survivors get a +1 bar lag robustness check (buy close t+1).
- Trials counted for BH: 12 (Round 1) + 12 (this round) + every Stage-2 grid cell.
- Gate (Stage 1, unchanged): net(B) mean>0, |t|>=3 clustered by entry date, same sign in both dev halves, n>=30. One Stage-2 grid run for all survivors (<=3 params x 3 values), plateau rule + BH q<0.10 as in Round 1. Random-entry baseline for survivors.
- Reported per strategy: n, net mean/trade, t, portfolio Sharpe (N slots as stated), break-even round-trip cost (=gross mean), A(Prime) vs B(no Prime), tax 0.18%, 2x cost.
- Long-only, no shorting. Defaults below are fixed; no search in Stage 1.
