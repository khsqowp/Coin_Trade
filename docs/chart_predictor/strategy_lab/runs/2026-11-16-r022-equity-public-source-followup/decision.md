# R022 decision — data sources identified, no equity test yet

## KRX

KRX's official Open API catalogue lists KOSPI and KOSDAQ daily stock-trade records from 2010-01-04, plus ETF daily-trade records from the same date. It is therefore a plausible daily-bar source for the Korea stock/ETF track. The catalogue does not by itself establish inclusion of delisted securities, historical point-in-time universe membership, adjusted total-return behavior, or whether the API fields are sufficient for the intended corporate-action-aware backtest. The signed-in service area includes API key request; no account or key was created.

KRX's official purchase guide says the detailed product specification, period, fields, delivery, sample file, and price are available after sign-in. No numeric public quote was visible in the pages inspected. Unknown price is not zero.

## United States

The current CRSP/Morningstar product page describes daily and monthly market data and corporate actions for over 36,000 active and inactive US securities, with permanent PERMNO/PERMCO identifiers. Those are desirable properties for reducing delisting and ticker-history errors. The exact inclusion of ETFs in the proposed stock product and the delivered sample's coverage still need inspection.

CRSP's sample guide describes a promotional 25-security stock sample, with securities history through December 2019, and directs readers to request files or a web demo by email. WRDS has a public catalogue record for a 351.4 MiB “CRSP Sample,” but this audit did not verify a public file download or numeric license price. No email, phone call, account signup, or purchase was made.

## Decision and remaining gate

- Do not run KR/US stock/ETF strategy backtests from crypto candle data or current-survivor watchlists.
- KRX Open API is the first low-friction research candidate for daily Korean stock/ETF data if account/key setup is authorized separately; confirm delisted security support and adjusted-price fields before any strategy trial.
- CRSP is the stronger candidate for US survivorship-aware stock research; obtain exact quote, ETF product scope, sample, license terms, and access mode before choosing it. These require a future user-authorized transaction/contact or institutional entitlement.
- Equity agents produced hypotheses and a red-team checklist only. No stock/ETF performance result exists. The 20% CAGR objective remains an objective, not a proven result; maximum drawdown limit remains undefined.

### Supersession note — 2026-11-16

The preceding MDD sentence records the state before the user's Round 0 decision. It is superseded: the user fixed the KR and US stock/ETF portfolio maximum drawdown at **30%** on 2026-11-16. This does not resolve benchmark, costs, sizing, point-in-time universe, or data-rights gates. See [`round0_master_charter_20261116.md`](../../../../research/round0_master_charter_20261116.md).
