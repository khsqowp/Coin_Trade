# Phase 8 — Round R: selective prediction and M2 adaptation panel

Date: 2026-11-21. Scope: four-source search for new short-horizon crypto
perpetual setups, then an independent four-role review of whether recent
selective-prediction methods justify one M2 adaptation. The fixed Coin_Trade
M2/Core gates were not changed. No new market outcomes were scored and no
backtest was run in this round.

## Four source lanes

| Lane | Closest lead | Disposition |
|---|---|---|
| Academic / SNS | Hao, Chen and Qi, [Coverage-Constrained Selective Prediction for Short-Horizon Cryptocurrency Event Contracts via Adaptive Quantile Thresholds](https://www.mdpi.com/1999-4893/19/8/704); Cohen, [Intraday trading of cryptocurrencies using polynomial auto regression](https://www.aimspress.com/aimspress-data/math/2023/4/PDF/math-08-04-493.pdf); Pindza, [Microstructure alpha: hierarchical learning and cross-asset transfer](https://www.frontiersin.org/journals/blockchain/articles/10.3389/fbloc.2026.1811716/full) | No source-defined M2 candidate. The first predicts fixed-horizon close direction under fixed-odds event contracts, not target-before-invalidation. The second reports selected 45–80-minute spot-crypto settings, without a Coin_Trade M2 barrier contract. The third studies 5-minute returns and reports no strategy surviving realistic exchange fees. |
| TradingView / Pine | [TP-SL Toolkit](https://es.tradingview.com/script/iILE5e3m-TP-SL-Toolkit-AxeAlgo/) with EMA-cross entries; [PineStats](https://www.tradingview.com/script/LntmXNJu-PineStats/) probability/first-passage library | No eligible candidate. The toolkit is an EMA trend system with selectable rather than source-fixed exits and overlaps the excluded trend family. PineStats is a calculation library, not an entry/side strategy. |
| Public communities | [Liquidation-heatmap post](https://www.reddit.com/r/algotrading/comments/1witlif/am_i_still_overfitting_or_is_this_a_genuine_edge/) with 3% initial stop and staged trailing exit; [liquidation flush discussion](https://www.reddit.com/r/algotradingcrypto/comments/1x437ph/how_can_i_improve_my_crypto_liquidation_flush/) | No eligible candidate. The heatmap post omits numeric trigger/price rules and fixed expiry, overlaps the Round Q liquidation family, and requires historical price-level liquidation data not present in the checked archive. |
| GitHub / skills | Nautilus [Hurst/VPIN directional example](https://github.com/nautechsystems/nautilus_trader/blob/develop/docs/tutorials/hurst_vpin_kraken.md); [qkt flow-imbalance DSL](https://github.com/elitekaycy/qkt/blob/dev/docs/reference/dsl/streams.md); [daily crypto-trading-system](https://github.com/jhadchiti/crypto-trading-system) | No eligible candidate. Hurst/VPIN has a time exit but no fixed target/invalidation and overlaps tested aggressor-flow families; qkt omits short and exits and needs liquidation events; the daily system overlaps breakout/momentum and is not M2. |

The source scan was bounded to these named leads and the four assigned source
lanes; it is not a claim that all public strategies were exhausted. Source
claims are not local evidence. The Nautilus/Hurst-VPIN and qkt sources require
trade/book/liquidation inputs not established for the required 20-symbol
universe. Round Q's completed liquidation/Kalman/POC leads were not promoted
again.

## Primary-source evidence and limits

The 2026 adaptive-quantile paper reports BTC/ETH 5- and 10-minute close-
direction forecasts on a fixed-odds contract. It uses daily trailing score
quantiles, emits about 0.75–0.77% of minute bars (roughly 10–11 trades/day per
configuration), and reports held-out selective win rates of 57.81–63.34% for
Jan 1–Jun 10, 2026. Those are the paper's reported outcomes under its 0.8
fixed-odds payout, not target-first M2 rates or Binance-perpetual trade PnL.
The authors state that their implementation code and frozen model
configurations are not publicly released. The paper's dataset includes
aggregate trades, order-book depth, OI/long-short metrics, and auxiliary price
series beyond ordinary minute candles.

The local NAS archive root was checked read-only. Its top-level market-data
directories include spot/perpetual/mark 1m klines, funding, USD-M metrics,
bookDepth, and BVOL; it has no aggregate-trade dataset directory. `um_bookDepth`
has two symbol subdirectories, and the metrics archive's historical OI first-
availability remains unresolved in the existing audit. A schema-only read of
`um_klines_1m/BTCUSDT/2026-10.parquet` confirms `taker_buy_volume` and
`taker_buy_quote_volume`, so minute-level kline-flow features are locally
available in that file. This one-file schema check does not prove every
symbol-month has those fields or complete rows. The broader archive audit
remains **FAIL** for known gaps/anomalies; the historical period is exposed and
cannot establish untouched OOS or Core status. See the [minute archive audit](phase8_full_minute_archive_timestamp_audit_20261121.md),
[book-depth audit](phase8_bookdepth_archive_audit_20261121.md), and
[OI-timing follow-up](usdm_oi_timestamp_followup_20261120.md).

## Candidate adaptation considered (not frozen)

The nearest methodological lead is a custom three-class target-first model:
at each completed 1-minute close, predict whether a hypothetical next-minute-
open long reaches an ATR target first, a short reaches its ATR target first,
or neither reaches a target within a fixed expiry; use a trailing score-quantile
rule to select directions. This changes the source label (fixed-horizon close
direction) into Coin_Trade's path-dependent M2 label. It is an adaptation, not
a reproduction of the paper.

The Blue reviewer sketched an illustrative `ATR14 × 1` symmetric target/stop,
10-minute expiry, a five-seed LightGBM ensemble, and 14/28-day trailing score
thresholds. These are researcher design choices, not source rules, and were
not frozen. The proposal still lacks a closed feature whitelist and exact
formula/missing-data contract; the source's reported operating point is below
Coin_Trade's fixed ≥10% coverage floor; the source evaluated only two assets;
and the local archive cannot reproduce its aggregate-trade/depth/OI feature
panel for ≥20 symbols. The local minute-kline flow columns make a smaller
price-action + kline-flow adaptation conceivable, but do not validate its
causality across all symbols or repair the target-label mismatch.

The 2026 Frontiers microstructure study is a negative prior rather than a
candidate: it reports weak short-horizon predictive information but no
strategy surviving realistic exchange fees. The polynomial autoregression
paper reports profitable spot-crypto cases but selects settings on four
assets and does not provide the target-first barriers needed here. Neither
source result can be relabeled as Coin_Trade M2 performance.

## Adversarial four-role panel

| Role | Decision | Rationale |
|---|---|---|
| Blue | HOLD | A target-first multiclass adaptation is plausible, but its new label, local feature whitelist, and threshold-to-coverage rule are not frozen. |
| Red | REJECT current specification | The source is a fixed-odds direction classifier, not M2; reported <1% bar coverage is below the hard ≥10% requirement; changing labels/barriers and feature selection creates a new multi-choice experiment. |
| Data / Methods | HOLD | A ≥20-symbol price-action/kline-flow study appears technically conceivable, but source-replication data are incomplete; OI/depth inputs are not broadly eligible; funding/data gaps, point-in-time universe, and exposed history remain. |
| Judge | NO PREREGISTRATION / NO TEST | No source-defined M2 candidate passes the fixed gates; an adaptation requires a complete specification and a fresh independent review before scoring. |

No vote treats source direction accuracy, fixed-odds expected value, or
reported profitability as futures M2 evidence. The panel also noted that the
original model implementation is unavailable for direct reproduction.

## Decision and next gate

**Round R disposition: 0 eligible source-defined M2 candidates; 0
preregistered; 0 scored; no Core; Phase 9 not run.** This is a bounded search
result, not proof that no profitable strategy exists.

The next research action is specification-only, not another score sweep:

1. Decide whether the adaptive-selective M2 model remains worth pursuing as a
   clearly labeled new adaptation, rather than source replication.
2. If retained, freeze one feature whitelist/formula set using only locally
   verified causal fields; exclude historical OI, broad depth, and absent
   aggTrades unless their timestamp/data coverage gates are independently
   cleared.
3. Freeze the three-class first-hit label, next-minute-open entry, target and
   invalidation distances, 10-minute expiry, gap/non-execution and same-bar
   stop-first treatment, and treatment of missing future bars.
4. Freeze per-symbol versus pooled fitting, the ≥20-symbol universe and its
   point-in-time limitation, training/refit schedule, score-to-side mapping,
   quantile lookback, tie-breaking, and a coverage definition whose denominator
   is all eligible universe anchors (not just emitted predictions).
5. Freeze realized funding accounting, both existing round-trip cost
   scenarios, baseline comparisons, OOS/walk-forward splits, event purging,
   and a trial budget. Run synthetic causal tests and data-schema audits only.
6. Obtain a fresh Red/Data/Methods/Judge review. Only unanimous clearance of
   the exact preregistration can authorize one exposed-history development
   diagnostic; any result remains non-OOS. Prospective forward evidence is
   still required for Core review.

The panel search used the strategy registry for duplicate detection; its
metadata contains historical headline metrics, so this review is not claimed
to be outcome-blind. No new signal ledger or price-outcome dataset was opened
for this Round R panel, no backtest was run, and no external code/data was
downloaded or installed. A local one-file Parquet schema was read to verify
available kline column names only.
