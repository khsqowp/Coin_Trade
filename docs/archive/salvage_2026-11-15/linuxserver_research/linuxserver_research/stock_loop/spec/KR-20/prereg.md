# KR-20 - concentrated weekly reversal: every 5th bar buy the 3 worst 5d performers among liquid (>=2e10) names, hold 5 (KR Round 2, Stage 1 prereg)
Written 2026-11-13T16:21:15 BEFORE any Round-2 run.

## Signal
Bars with index%5==4: rank liquid(20d value>=2e10) names by 5d return ascending (exclude ret_t<=-25%); buy lowest 3 at close t, sell close t+5.

## Portfolio slots N
3

## Defaults (fixed)
{'k': 3, 'lb': 5, 'h': 5, 'thr': 20000000000.0}

## Stage-2 grid
{'k': (2, 3, 4), 'lb': (3, 5, 10), 'h': (3, 5, 7)}

## Round-2 common (inherits spec/KR-01/prereg.md 'Common' section unchanged: universe, liquidity>=2e9, costs A/B/tax18/2x, dev data only, holdout locked)
- Why Round 2: Round-1 audit found the KRX opening price is systematically elevated (all-liquid-stock open->close mean -0.14%/day, overnight +0.11..0.17%/day; same sign in KOSPI/KOSDAQ index data and every year). Buying at the next OPEN therefore carries a structural ~0.14%/day drag. Round 2 uses CLOSE entries (MOC) for non-gap ideas. Caveat: signal uses close_t and fills at close_t (closing-auction indicative price 15:20-15:30); survivors get a +1 bar lag robustness check (buy close t+1).
- Trials counted for BH: 12 (Round 1) + 12 (this round) + every Stage-2 grid cell.
- Gate (Stage 1, unchanged): net(B) mean>0, |t|>=3 clustered by entry date, same sign in both dev halves, n>=30. One Stage-2 grid run for all survivors (<=3 params x 3 values), plateau rule + BH q<0.10 as in Round 1. Random-entry baseline for survivors.
- Reported per strategy: n, net mean/trade, t, portfolio Sharpe (N slots as stated), break-even round-trip cost (=gross mean), A(Prime) vs B(no Prime), tax 0.18%, 2x cost.
- Long-only, no shorting. Defaults below are fixed; no search in Stage 1.
