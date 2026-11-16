# R024 decision — NO-GO for new strategy performance trials

The current evidence does not support another strategy parameter grid. The binding issue is eligible data, not a lack of combinations to try.

## Crypto

The long-history repaired Binance Vision database contains 19,790,858 one-minute rows across six symbols from 2020-01-01 through 2026-06-30. It cannot satisfy M4's minimum 20-symbol requirement and does not establish a point-in-time contract universe. The 100-symbol local price database contains 17,142,161 one-minute rows over roughly four months (2026-07-16 through 2026-11-14), but it is price-only, already exposed to development work, and cannot be combined with the six-symbol archive as if it were one synchronized 20-symbol long-history panel.

Independent review confirmed the existing crypto results remain null/reject evidence, not candidates: R021b's highest target-first cell was 48.31% with mean net −1.308R; R023 was 30.03% and −0.453R versus its baseline at 29.15% and −0.438R, with paired event-cluster intervals crossing zero. R023 was post-hoc exploratory. No new strategy grid was run.

The applicable Binance Vision terms allow the agreed personal, non-production historical-backtest scope; they do not authorize using Vision-derived research as a real-time/manual trading signal. See [Binance Vision terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md) and the [official public-data repository](https://github.com/binance/binance-public-data).

## Korean equities

KRX's official catalogue lists daily stock and ETF data beginning 2010-01-04, but API access requires registration, an API key, service application, and administrator approval. Public delisting pages show useful components, but the audit did not verify a complete bulk point-in-time universe plus adjusted total-return price panel. Those access steps are outside the current approval. No Korean stock/ETF performance trial was run.

## US equities

Free official sources provide fragments, not the required complete investment-history panel. Nasdaq's individual historical quote page does not establish machine-readable market-wide delisted coverage and its terms restrict unapproved automated collection. SEC filings/directories can support event research but do not provide a complete stock/ETF price history, corporate-action adjustment, and delisting-return series. CRSP documentation describes stronger active/inactive and corporate-action coverage, but public sample/price was not verified; no account, contact, or purchase was attempted. No US stock/ETF performance trial was run.

## Research boundary incident

One US-source agent reported that a broad search emitted snippets containing validation-named code/data references. The agent stated that no sealed price rows were intentionally opened, stopped the search, and did not use those snippets for strategy conclusions. The exact search scope has not been independently verified. Do not use potentially implicated files as the final one-time sealed evaluation until an independent path-level audit establishes scope; if uncertain, use a newly accrued prospective boundary. This is not a claim that sealed values were accessed, nor a claim that the boundary was unaffected.

## Next action gate

Do not test another strategy until an authorized, synchronized data source can meet the exact track requirements. For crypto that means 20+ symbols, point-in-time listing/delisting coverage, aligned inputs, and a fresh unseen evaluation period. For KR/US equities it means authorized daily stock+ETF prices, point-in-time inactive/delisted membership, corporate actions/total-return treatment, and frozen tax/cost assumptions. The user's Round 0 decision on 2026-11-16 fixed KR/US MDD <=30%; benchmark, numerical costs/tax/slippage, position sizing, and data gates remain unresolved. Until those gates are met, more backtest cells would produce unqualified numbers, not evidence toward the requested deployment objectives.

## 2026-11-17 supersession note

A later aggregate-only audit of the expanded Binance Vision seed archive found 37 symbols with full monthly 1m archive counts in all 70 months from 2021-01 to 2026-10, so the earlier statement that no synchronized 20-symbol long-history *price panel* existed is superseded. This satisfies only structural OHLCV breadth for a survivor-conditioned seed cohort. It does not satisfy the decision's PIT contract-status, cost/funding, or fresh sealed-evaluation requirements; therefore the R024 **NO-GO for performance trials remains in force**. Details and auxiliary-archive probes are in [`round5_crypto_source_feasibility_20261116.md`](../../../../research/round5_crypto_source_feasibility_20261116.md) and [`round5_continuation_20261117.md`](../../../../research/round5_continuation_20261117.md).
