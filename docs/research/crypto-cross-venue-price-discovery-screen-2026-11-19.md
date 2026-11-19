# Crypto cross-venue price-discovery screen — 2026-11-19

## Decision

Do not register or backtest a Coinbase-to-Binance 10/20-minute target-first signal yet. The literature supports venue-level price-discovery differences and a New York fixing-time activity concentration, but does not establish a causal directional forecast at the requested horizon. A BTC-only experiment would not satisfy the frozen requirement of at least 20 symbols and non-overlapping N≥200. No performance claim is made.

## Hypothesis screened

At 15:00–16:00 New York time, a Coinbase BTC-USD move might lead a Binance BTCUSDT perpetual move over the following 10–20 minutes. One reviewer rejected opening this candidate. A second proposed a BTC-only falsification design using completed 1-minute bars, a one-tick Coinbase move, next-Binance-BBO entry, ATR(14) 1R stop/target, and 10/20-minute expiries. Those thresholds are an unvalidated design sketch, not evidence-backed parameters. Since they do not establish transfer to 20 symbols, they are not promoted to preregistration.

## Evidence and interpretation

- A 2026 *Journal of Banking & Finance* study reports Binance leadership over Coinbase in BTC price discovery in its overall sample (59% at 10 ms; 75% at 1 s). This does not prove the reverse lead in a particular fixing window. [Article](https://doi.org/10.1016/j.jbankfin.2026.107849)
- A 2025 Fribourg study reports that Coinbase's *relative price-discovery contribution* rises during the 15:00–16:00 New York fixing window. Relative contribution is not a next-period directional prediction. [Study chapter](https://folia.unifr.ch/documents/332575/files/2025ECO005.pdf)
- A 2026 *Finance Research Letters* paper reports concentrated Bitcoin activity around the fixing window; activity concentration alone has no directional sign. [Article](https://www.sciencedirect.com/science/article/pii/S1544612326014601)
- Independent agent reviews agree that the cited findings do not establish the required target-first rate, broad-symbol generalization, or a qualifying independent strategy family. The venue-level question is related to the existing BTC lead/lag family and must share its multiple-testing budget.

## Admission gates before any future test

1. Confirm the data license and storage/derived-output rights before acquiring data.
2. Obtain synchronized Coinbase spot and Binance perpetual trades plus best bid/offer with exchange and local receipt timestamps, sequence/gap/reconnect information, fixed symbol mapping, and basis fields.
3. Specify the signal using only completed data; freeze NY daylight-saving handling, entry at executable quotes, spread/fees/slippage, latency, stop/target tie-break, and expiry before outcomes are viewed.
4. Establish outcome-blind feed integrity and executable-fill checks, then register as a lead/lag-family subhypothesis with multiplicity control.
5. Require the existing crypto gate: all-issued target-first M2≥80%, separately non-overlapping N≥200 across ≥20 symbols, with deadline-direction accuracy separately reported. A BTC-only study can only falsify mechanism plausibility, not pass the product gate.

## Scope boundary

This was a literature and prior-record screen only. No Coinbase or Tardis account was created, no API key was used, no historical data was downloaded, and no strategy backtest or trading action was performed. The US and KR data-access choices remain subject to the user's pending authorization response.
