# Regime-adaptive layer research (axis: follow the market flow)

Scripts: app/rs_regime_lib.py (engine+detectors), rs_regime_run.py (1302-config grid, diagnostics, folds),
rs_regime_extra.py / rs_regime_extra2.py (controls, episodes), rs_regime_wf.py (phase-averaged walk-forward).
Data: local data.binance.vision cache (.rs_cache/vision), 45-name live UNIVERSE, daily UTC closes 2022-01..2026-10-09, funding included.
Costs 0.05% fee + 0.05% slippage per side on all turnover (incl. regime switches). Regime known at close t applied from t+1.

## Key facts
* Baseline at the stated rules (14/2/12, 0.10%/side, funding) is NOT +28.9%. The +28.9% is 14/3/8 at 0.04%/side.
  Independent re-implementation matches: 14/3/8 @0.04% -> +30.3% / MDD 19.8%. Live 14/2/12 @0.10% -> +12% (start phase 0) .. +21% (phase 1).
* Rebalance-phase noise is huge (same config, start day shifted by 1-2 days: 12% vs 21% CAGR). All tables in rs_regime_wf.py are averaged over phases.
* Gross-exposure scaling (btc trend / vol / breadth / corr / dispersion / funding) never beats baseline: returns fall ~proportionally, 49/288 beat baseline on both FULL and OOS Calmar; no consistent winner.
* Diagnostics: baseline PnL is weak when BTC < SMA50/200 and BTC 14d < -10% (4 of 5 years negative) -> motivates (a) lookback switch (b) crash reversal.

## Survivors (K=12 R=2 live params, phase-averaged, with funding) CAGR/MDD/Calmar
| design | TRAIN 22-01..24-06 | OOS 24-07..26-09 | FULL | ex-2024 | yrs 22/23/24/25/26YTD |
|---|---|---|---|---|---|
| baseline 14/2/12 | 15.0/18.7/0.85 | 17.9/13.1/1.53 | 16.4/18.7/0.94 | 11.8/19.1 | +8/+10/+35/+27/0 |
| A crash-reversal: BTC 14d<-10% -> 5d reversal sleeve | 28.2/12.8/2.20 | 25.3/16.6/1.61 | 26.8/16.6/1.68 | 22.3/16.6 | +22/+22/+45/+43/0 |
| A' crash-flat: BTC 14d<-10% -> flat | 22.3/15.2/1.53 | 23.1/12.3/2.07 | 22.6/15.2/1.57 | 17.6/15.2 | +16/+16/+44/+35/+1 |
| B trend: BTC>SMA200 -> L28 else L14 | 19.3/12.5/1.58 | 20.4/12.7/1.60 | 19.8/12.8/1.56 | 17.8/12.8 | +8/+29/+28/+34/-1 |
| C = A + B | 31.4/10.8/3.09 | 28.8/16.6/1.80 | 30.1/16.6/1.84 | 29.1/16.6 | +22/+42/+34/+52/-1 |
Turnover/yr (x equity): base 92, A 122, B 79, C 108. Trades = rebalances 182/yr + ~17 regime flips/yr (A).

## Robustness
* A neighbours (thr -0.05..-0.15 x Lrev 3/5/7): FULL CAGR 17-29%; degrades monotonically as flag gets rare (-0.15 ~ baseline). Not a knife edge, but -0.10/-0.075 are the sweet spot.
* A vs base across 2 phases x K{12,8} x R{2,3,4,5} (44 combos): CAGR higher in every combo (+1..+17pp, typical +8pp); MDD about equal (not reduced at R>=3).
* 42 flagged episodes (K12,R3): reversal beats momentum in 64%; sum +0.41 vs -0.32; large wins 2022-06, 2022-11 (FTX), 2025-02, 2026-06.
* B: good at SMA 100-250 x L28/35, collapses at L42 and is weak at K8 R3 (OOS Calmar 0.69 vs 0.72). Inverse control (L28 when BTC<SMA) = 1.3% CAGR, i.e. the sign matters.
* Walk-forward (family of 34 designs, pick by train Calmar with MDD<=25%; test = OOS 24-07+, 2023, 2024, 2025+):
  CAGR >= baseline in all 4 windows for K12R2, K12R3, K8R3. Calmar beats baseline in 1/4 (K12R2: OOS pick 24.9/19.1 vs 17.9/13.1 and 2025+ 23.6/19.1 vs 14.7/12.9 -> more return, MORE drawdown), 3/4 (K12R3), 4/4 (K8R3).
  => the layer reliably adds return; drawdown reduction is only reliable for B (trend switch) at K12.

## Failures
market_mom<-10% sleeve (OOS Calmar 0.36, threshold 0 collapses), dispersion/corr filters (in market 10-12% of days, 2024 carries), pure gross scaling, vol targeting (btc_vol/strategy_vol, median Calmar ~0.56 = baseline), btc_slope tilt, breadth, funding level.

## Caveats / unverified
* Survivorship: universe = coins listed today; a sleeve that buys crash losers is upward-biased (dead coins missing). Largest threat to A.
* 2022-01..2026-10 contains only ~40 crash episodes in ~15 clusters; thresholds chosen on grid of 3-6 values; 1302+~100 configs tried.
* Daily-bar model: constant weights between rebalances, no intraday liquidation, no borrow/ADL; funding NaN->0 before listing.
* R=2 base is itself a poor phase draw; 14/3/12 static beats it (cadence axis) - combine layers only after that is settled.
* Last bar 2026-10-09 UTC assumed complete.
