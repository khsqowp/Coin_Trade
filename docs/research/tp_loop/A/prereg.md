# PREREGISTRATION - BACKTESTER-A (fixed-threshold per-position take-profit)
Timestamp (UTC): 2026-10-30T13:55:00Z  (written BEFORE any TP backtest was run; only panel loading and code reading had happened)

## Question
Does a per-position take-profit improve the momentum L/S rotation (lb14, rebal3, K8/8, dollar-neutral, BTC crash filter, kill 35% / cool 14d) robustly?

## Data / engine
- Offline 45-symbol hourly panel (.rs_cache/vision), days 2022-01-01..2026-10-09. Panel HAS hourly H/L/C (no O) -> TP is INTRABAR on hourly high/low.
- New engine app/rs_tp_engine.py = copy of rs_final_engine._sim core (design 0 only) + TP. With TP off it MUST equal rs_final_engine.Sim.run bit-for-bit (asserted, 3 phases, both environments) and reproduce profit_protection.md V0 numbers.

## Environments (baseline V0 per environment)
- ENV-A (primary, "live"): lev 4.0, deploy 0.95 (gross ~3.8x), cost 0.001/side (fee 0.05% + slippage 0.05%), real funding, kill 0.35, cool 14, crash flat (BTC 14d < -10%), minn 0, eq0 1.
- ENV-B (research config, corroboration): lev 2.0, deploy 1.0, otherwise identical.
- ENV-C (diagnostic only): ENV-A with eq0=142 USDT and min notional 5 (+BTC 100 / ETH 20 generic floors, lot truncation as in rs_final_design). Reduce-only exits are assumed exempt from min notional.
Verdict is taken on ENV-A; ENV-B must agree or a "helps" is downgraded to "noise".

## TP definition (X = UNDERLYING price move from entry price, not margin PnL, unless stated)
Long: close when hourly HIGH >= entry*(1+X). Short: close when hourly LOW <= entry*(1-X). Entry price = original fill (quantity-keeping rebalances do not reset it). Checked on every hourly bar from the bar after entry. Nominal fill = threshold price; the usual 0.1%/side cost applies to the exit.
After a TP (no intra-cycle redeployment of freed slot in any case):
- REENTRY (case ii): symbol is eligible normally at the next rebalance.
- LOCKOUT (case i): symbol is excluded from selection at the next rebalance (flat through that rebalance), then eligible again.
PARTIAL: close 50% once at X (position then keeps remaining qty, no second TP; remaining qty kept at rebalances per live apply_targets).

## THE 12 CONFIGS (complete; nothing added after results; anything extra = EXPLORATORY and excluded from conclusions)
| id | side | type | X (underlying) | after TP |
|---|---|---|---|---|
| T01 | both | full | 15% | reentry |
| T02 | both | full | 25% | reentry |
| T03 | both | full | 40% | reentry |
| T04 | both | full | 60% | reentry |
| T05 | both | full | 100% | reentry (shorts can never reach 100%; effectively long-only) |
| T06 | both | partial 50% | 25% | n/a |
| T07 | both | partial 50% | 40% | n/a |
| T08 | long only | full | 40% | reentry |
| T09 | short only | full | 40% | reentry |
| T10 | both | full | 25% | lockout |
| T11 | both | full | 40% | lockout |
| T12 | both | full | margin-PnL +100% => underlying = 100%/lev (25% in ENV-A = identical to T02, asserted; 50% in ENV-B) | reentry |
Margin mapping at ENV-A (lev 4): underlying 15/25/40/60/100% = margin 60/100/160/240/400%. Per-position PnL as % of account equity = X*lev*deploy/16 = X*0.2375.

## Baseline = V0 (no TP). Trial count N = 12 TP configs (+V0 reference).

## Metrics (all on phase-mean over day offsets 0,1,2; also worst phase)
CAGR (365-day), close MDD, intraday MDD (hourly worst-case simultaneous, per rs_final_engine.window_metrics), Calmar_i = CAGR / intraday MDD (PRIMARY), Calmar_c = CAGR / close MDD, daily Sharpe*sqrt(365), end wealth, worst day, TP count/yr, kills.
Windows: IS 2022-01-01..2024-06-30; OOS 2024-07-01..end. Continuous path cut and rebased (as profit_protection.md). Representative config chosen on IS ONLY = argmax IS phase-mean Calmar_i among T01..T12 in ENV-A. OOS used only for diagnosis.
Anchored walk-forward, 4 test folds (train anchored at 2022-01-01): 2023-01..2023-12, 2024-01..2024-12, 2025-01..2025-06, 2025-07..end. Fold metrics computed per fold for every config; also report the WF-selected config per fold (argmax train Calmar_i).

## Pass test for a window W (IS, OOS, a fold, a neighbor, a stress): "PASS(W)" = Calmar_i(TP) > Calmar_i(V0) AND CAGR(TP) >= 0.9 * CAGR(V0) (relative), phase-mean.

## Verdict rule (helps / hurts / noise), on representative config R, ENV-A
helps only if ALL: (1) PASS(IS); (2) PASS(OOS); (3) PASS in >=70% of WF folds (>=3 of 4); (4) both neighbors X*0.75 and X*1.25 (same type/side/after-TP) PASS in IS and OOS (>=70% => 2/2); (5) at cost 2x (0.002/side, both V0 and TP) PASS(IS) and PASS(OOS), and also PASS with fill mode "next bar open" (proxy: close of the TP hour) at 1x cost; (6) deflated-Sharpe (haircut Sharpe = SR_hat - SR0, N=12 trials, full sample) of R > raw Sharpe of V0; (7) ENV-B corroborates (1),(2).
hurts if: R fails Calmar_i improvement in BOTH IS and OOS AND >=70% of the 12 configs have lower phase-mean Calmar_i than V0 in both IS and OOS.
otherwise: noise.

## Realism variants (diagnostic grid over all 12 configs)
- cost 2x: 0.002/side for everything.
- fill modes: 0 = threshold; 1 = threshold adverse by extra 0.30% slippage; 2 = close of the TP hourly bar (proxy for next-bar open, since panel has no open).
- ENV-C small account with min notional.
- Neighbors: each config's X scaled by 0.75 and 1.25 (diagnostic; not selectable; not counted in N, but DSR sensitivity shown for N=36).

## Multiple testing
Deflated Sharpe Ratio (Bailey & Lopez de Prado 2014) with N=12 (sensitivity N=36 and N_eff), SR variance across trials, skew/kurtosis of daily returns. PBO via CSCV (S=10 blocks, 252 splits) over V0+12 configs, metric = Sharpe. Effective independent bets = participation ratio of the correlation matrix of trial daily returns, and number of TP-independent events.

## Attribution
Trade log (net pnl / equity at entry). Share of total PnL from top 5 trades, top 5 symbols, top 5% trades, with and without TP, representative config. Post-TP 3-day continuation (signed underlying move after TP fill) to measure right-tail cut. Paired block bootstrap (block 10d, 2000 draws) of Calmar difference R vs V0.

## Conservative choices when ambiguous
Hourly adverse extreme assumed to precede TP within the TP bar; Calmar on intraday MDD; relative 10% CAGR tolerance; baseline cool=14 (research convention; the live "kill permanent" would be degenerate); verdict requires ENV-B agreement.
