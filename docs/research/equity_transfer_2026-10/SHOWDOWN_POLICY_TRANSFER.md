# Crypto strategy showdown grid: US/KR equity transfer

## Outcome

The source `crypto_strategy_showdown.py` has 112 declared regime × stop-mode × drawdown-trigger × leverage combinations. All 112 were transferred to each stock market under two cost cases, producing 448 curves. Curve metrics were independently recalculated, and a future-data perturbation left all 448 pre-cutoff account prefixes unchanged. The result does not establish a deployable stock strategy: this adaptation retains a synthetic crypto liquidation barrier and maps BTC regime to a synthetic equal-weight stock proxy.

## Method

- Source grid: 4 regimes (`neutral`, `regime_tilt`, `regime_longonly`, `regime_cash`), 3 stop modes (`none`, `flatten`, `delever`), 4 drawdown triggers (0%, 15%, 20%, 25%), and leverage 1.0×/1.5×/2.0×/2.5×. The source filters remove nonzero stop levels for `none` and zero stop for the other modes, leaving 28 per regime and 112 total.
- Signal: 14-day cross-sectional momentum, rebalance every 3 daily bars, long the top 8 and short the bottom 8, each side initially 50% gross exposure. Holdings are determined using completed daily observations and earn subsequent daily returns.
- Market regime: source BTC/SMA200 is replaced by the causal synthetic equal-weight stock proxy SMA200. It is not a benchmark index and has survivorship limitations.
- Stock costs: two local equity cost schedules per market; one-way fees and security-level slippage apply to turnover; KR sell tax applies to reductions of long exposure; borrow expense assumes 1% annual US and 3% annual KR on short notional. The source 4% annual funding-drag assumption on leverage above 1× is retained as an explicitly synthetic financing proxy, not a stock broker quote.
- Drawdown controls: `flatten` pauses for at least five bars and until the proxy bull regime returns; `delever` halves leverage after the trigger until the account recovers its peak. No position redistribution occurs during a pause.
- Liquidation: source's daily threshold `1/leverage - 0.5%` is retained for comparable stress accounting. This is not an actual US or KR broker maintenance margin, margin-call, forced-sale, or overnight-gap model.
- Market data: US 54 symbols, 1,955 sessions from 2019-01-02 to 2026-10-12; KR 64 symbols, 1,903 sessions from 2019-01-02 to 2026-10-02.
- Validation: save and reconcile each curve and its CAGR/MDD/Sharpe/final NAV. For prefix tests, prices after US 2022-11-16 and KR 2022-11-09 were multiplied by 3 and volume by 7; all 448 saved-vs-perturbed prefixes had maximum difference 0.

## Result distribution

| Market | Cost case | CAGR median | MDD median | Sharpe median | Proxy liquidations |
|---|---|---:|---:|---:|---:|
| US | KIS 0.36% one-way | -11.09% | 67.21% | -0.81 | 0/112 |
| US | low 0.08% one-way | 1.52% | 43.94% | 0.22 | 0/112 |
| KR | base | 2.11% | 46.56% | 0.25 | 0/112 |
| KR | 2× slippage | -1.22% | 49.92% | 0.10 | 0/112 |

The best full-sample CAGR rows were all `regime_cash` with no stop: US 2.5× 50.45% CAGR / 59.57% MDD, KR 2.5× 31.87% CAGR / 81.58% MDD. These are ex-post maxima across the grid, not out-of-sample evidence. The high drawdowns and sensitivity to assumed execution costs dominate the apparent returns. Zero synthetic liquidation events only says no single simulated day breached the inherited threshold; it does not validate broker margin safety.

## Limitations

1. Current cached constituents are not point-in-time universes. Delisted securities and historical inclusion/exclusion are unavailable, creating survivorship bias.
2. The crypto signal ranks the crypto universe; the equity adaptation ranks only current cached stocks. It is a new cross-sectional equity experiment, not a literal asset-for-asset replication.
3. The BTC 200-day regime maps to a synthetic equal-weight stock basket. It is not BTC, S&P 500, Nasdaq, KOSPI, or KOSDAQ.
4. Stock-specific borrow availability, borrow recalls, locate failures, short-sale restrictions, borrow fee variation, broker margin tiers, margin calls, and liquidation execution are absent. The leverage and liquidation outputs are only scenario arithmetic.
5. The source crypto funding-drag assumption is not directly transferable. Retaining its 4% excess-leverage charge provides a controlled placeholder, not a stock financing estimate.
6. Daily bars cannot determine intraday stop ordering, actual fill prices, overnight margin events, or market impact. KR price limits and tick-size rules are not simulated.
7. The top CAGR is selected from 112 configurations and two cost cases in each market. No multiple-testing correction or untouched forward period was applied.

## Artifacts

- Runner: `app/rs_equity_showdown_transfer.py`
- Validator: `app/rs_equity_showdown_validate.py`
- Raw daily returns, account equity, and policy metrics: `full_runs/showdown_policy_transfer.json`
- Prefix and curve-metric validation: `full_runs/showdown_prefix_validation.json`
