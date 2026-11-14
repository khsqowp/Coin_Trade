# Pre-registration, research round 3: small-capital long-only rotation (written BEFORE any rotation backtest was run)
Scope: backtest + forward PAPER only. No orders, no keys. The owner's separate live logic is not touched or connected.
Owner facts (recorded as decisions, not as approval of live trading): capital about 128.88 USDT; intent to use all of it if live trading is ever approved
(live switch needs a separate explicit owner approval; checklist in research/LIVE_CHECKLIST.md, nothing implemented); strategy style = hold,
track, cut a persistent loser, rotate into a new symbol, with a re-evaluation cadence that may be hourly, multi-hour or daily; leverage not stated -> 1x long-only
(2x / 3x sensitivity only, with liquidation modelled).

## Data and universe
* Binance USDT-M perpetuals, public endpoints only (exchangeInfo, ticker/24hr, klines, fundingRate; low rate, niced). Universe = top 25 USDT perpetual
  symbols (status TRADING, contractType PERPETUAL) by 24h quote volume at fetch time, plus BTC and ETH. 1h klines for up to 730 days, real 8h funding.
* SURVIVORSHIP BIAS (cannot be removed with public data): the universe is chosen from today's liquid symbols, so past delisted / collapsed symbols are absent.
  Direction of bias: results are optimistic. Mitigation: point-in-time eligibility (a symbol is tradable only after 30 days of its own history and only while it
  is in the top 20 by trailing 30-day dollar volume among the fetched symbols). New listings therefore enter late, as they would live.
* Exchange filters read from public exchangeInfo (minNotional, stepSize/minQty of MARKET_LOT_SIZE, tickSize) as of fetch time and applied to every order: quantity is floored
  to stepSize, an order with notional < minNotional or qty < minQty is REJECTED (stay in cash, counted). Filters are assumed constant over history (limitation).

## Strategy family (deterministic, parameters fixed here; no tuning)
Decision at the close of a clock bar, fill at the next 1h open: price*(1+slip) for buys, *(1-slip) for sells, taker fee on notional, real funding on notional every 8h.
* Eligible = point-in-time liquid set, 7-day return > 0, not in cooldown (24h after being stopped), not already held. Rank by 7-day return, descending.
* BTC regime filter (variant): enter only while BTC close > 50-day mean (1200 hourly closes); when it turns off, exit everything at the next decision.
* Holding tracker, stop rules (variant), evaluated on the clock:
  trail10 = close <= 0.90 x highest close since entry; atr3 = close <= highest close since entry - 3 x ATR_c, ATR_c = SMA(hourly true range, 14*c hours) x sqrt(c);
  down4 = the last 4 clock-bar closes strictly declining AND close < entry price; loss7 = close <= 0.93 x entry price.
* After exits the freed slots are filled at the same decision with the next-ranked eligible symbols (cash split equally across free slots).
* No rank-based swapping of healthy holdings (rotation happens only after a stop or a filter exit).
* Clock c in {1h, 4h, 1d, adaptive}. Adaptive rule: label of the deterministic BTC 4h regime classifier (tp.regime_det): high_vol -> 1h, trend_up or trend_down -> 4h,
  range or unknown -> 1d; re-evaluated at each 4h boundary.
* Positions n in {1 (all-in), 3 (equal split)}; leverage 1 (long only).
Variant grid: 4 clocks x 2 n x 4 stops x 2 BTC filter = 64 variants (all logged as selection trials in runs/research/trials.sqlite, study R3).
Reference rule (owner's repo, card ct-momentum-rotation, long leg only): rank by 14-day return, hold top K equal weight, rebalance every 72h, BTC 14-day return < -10% -> cash;
K = 8 and K = 3 (2 more selection trials; K = 8 mostly hits minNotional). Total selection trials = 66.
Benchmarks: BTC hold (1x, funding paid); universe equal-weight hold (point-in-time eligible set, daily rebalanced, fees on turnover).

## Costs (primary)
Futures taker 0.05%/side, no BNB, slippage 0.02%/side (= RiskConfig min_slippage, not relaxed), real funding. Sensitivity (selection=0): slippage 0.01% and 0.05%, 50% maker mix,
leverage 2x and 3x (isolated margin, liquidation when the bar low reaches entry x (1 - 1/L + mmr 0.5%), the position margin is lost), rebalance phase (4h clock +2h, 1d clock +12h).

## Evaluation
* Hourly equity returns -> annualised Sharpe (sqrt 8760), MDD, total return; trades, fees, slippage, funding, rejected orders, days with > 10 fills (RiskConfig max_trades_per_day), days with loss > 3%.
* Strict OOS: split in two halves by time; the variant selected by FIRST-half Sharpe is evaluated on the second half (and reported next to the best second-half variant, which is hindsight).
* Multiple testing: deflated Sharpe (null variance 1/years and the robust empirical variance) over the 66 R3 trials.
* Drawdown distribution: per-trade returns of each variant; 2000 block-bootstrap sequences of 100 trades: MDD P50 / P95 / P99 / max; longest losing streak; worst trade; worst rolling 30-day return.
* Gate: tp.risk.gate_numeric with the new profile crypto_small_rotation (only max_position_pct = 1.0 differs from RiskConfig defaults; whitelist = universe). Failures are reported as they are.

## Hypotheses (decided in advance)
H1 Full-invest rotation has a worse worst-case drawdown than 3-position split. H2 Adaptive clock >= best fixed clock in Sharpe, with fewer trades than the 1h clock.
H3 Faster clocks (1h) give more stop exits and more fee/slippage drag; net Sharpe falls with turnover. H4 Minimum-notional rejections matter for n = 3 (positions of ~43 USDT) in high-priced symbols (BTC/ETH minNotional is far above 43 USDT?) - measured, not assumed.
H5 Beating BTC hold on risk-adjusted terms (Sharpe and MDD) in the second half is the bar; absolute return alone is not.
Forward-candidate rule: a variant goes to the forward tracker only if ALL hold: numeric gate passes; second-half Sharpe >= 0.5 and > BTC-hold second-half Sharpe; null-variance DSR >= 0.90; full-period MDD <= 35%.
Failing everything is a valid, reportable outcome; nothing will be re-tuned afterwards.
