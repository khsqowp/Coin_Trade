# Pre-registration, research round 2 (written BEFORE the adaptive/overlay results were computed)
Purpose: measure, with correct futures costs, whether adaptive selection (timeframe / strategy / side / risk multiplier by a deterministic regime) beats fixed
strategies, and which "AI roles" have a deterministic substitute. News/LLM judgements are NEVER mixed into these backtests (the model's knowledge of
the past contaminates them); the LLM regime agent is evaluated forward only (runs/regime_log.sqlite).

## Fixed protocol
* Data: Binance USDT-M perpetual last-price OHLCV (source `binanceusdm`) BTC/USDT, ETH/USDT; 5m (180d), 15m (365d), 1h (730d), 4h (1095d); real 8h funding history.
* Primary cost model (futures): taker 0.05% per side (official "Regular User" example), no BNB discount, slippage 0.02% per side, real funding, isolated margin,
  maintenance margin rate 0.5%, liquidation = loss of the position margin. Sensitivity grid: maker mix {taker, 50/50, maker} x BNB {off,on} x slippage {0.01,0.02,0.05}%.
* Execution: signal at bar close, fill at next open. Strategy code = frozen pool modules (no parameter tuning). Shorts = the same code on the inverse-price mirror.
  Variants per (strategy, symbol, tf): side in {long, short, ls}.
* Sizing: "unit" (lev 1, notional = equity) for strategy comparison; leverage study lev in {1,2,3,5,10} with full-equity margin and the Risk-Engine cap (notional 25%).
* Multiple testing: every (strategy, side, symbol, tf) baseline variant and every adaptive/overlay variant evaluated is logged in `runs/research/trials.sqlite`;
  the number of selection trials N and the cross-trial Sharpe variance feed the Deflated Sharpe Ratio (Bailey & Lopez de Prado). Headline claims use DSR>0.95
  AND a positive walk-forward OOS delta whose block-bootstrap 90% CI excludes 0; otherwise the result is reported as "not demonstrated".
* Walk-forward: W15 = 15m clock, 365d, train 120d / test 30d (rolling, 8 folds); W5 = 5m clock, 180d, train 60d / test 20d (6 folds). Configs are
  chosen on TRAIN only; trades/labels that are not finished before the test start are excluded from training (embargo 1 day). Fold returns are concatenated.

## Hypotheses (decided in advance; thresholds fixed)
H1  Fixed single strategies on futures with correct costs: most have Sharpe <= buy&hold; we expect the median variant Sharpe < 0 at <=15m.
H2  A1 (rule table, no fitting; regime from BTC 4h price classifier): trend_up -> trend_mtf long @1h w1.0; trend_down -> trend_mtf short @1h w1.0;
    range -> mean_reversion ls @15m w0.7; high_vol -> breakout_squeeze ls @15m w0.5. Success = OOS Sharpe(A1) > OOS Sharpe(walk-forward best fixed) with CI excluding 0.
H3  A2 (table learned on train): same success test. We expect A2 <= A1 (fitting noise).
H4  Overlays on each base config (trend_mtf@1h ls and mean_reversion@15m ls, BTC and ETH): (a) FOMC +-6h flat filter; (c) logistic meta-label p>=0.5;
    (d) vol-target clip(median_rv/rv, .25, 2); (e) retirement when 30d rolling shadow Sharpe < 0. Success per overlay = improves OOS Sharpe on >=3 of 4 bases AND
    beats the placebo distribution (for (a): 500 random window sets) at p<0.10.
H5  Leverage: with the 25% notional cap the leverage level is irrelevant for return (only liquidation tail); with full-equity margin liquidations appear for lev>=5 on 15m-1h.
H6  Funding is a material drag for long-biased 4h holds (> 5% per year) and negligible for <=15m strategies.
Decision rule for forward candidates: only configurations that pass H2/H3/H4 style success tests OR are needed as no-AI baselines are listed; each gets pre-registered
forward success/failure criteria (see FORWARD_CANDIDATES.md).
