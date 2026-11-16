# R022 — KRX / US stock-and-ETF public sample and price follow-up

Status: source-access audit only; no market-data acquisition or strategy performance test.

## Question

Can an eligible, survivorship-aware daily history source for Korean and US stocks/ETFs be obtained from public official information, including a usable sample and a transparent price, without account creation, purchase, or vendor contact?

## Scope and permissions

- User allowed lookup of publicly available samples and pricing information.
- Do not create KRX, WRDS, or CRSP accounts; request API keys; download restricted data; submit forms; contact vendors; purchase data; or disclose user identity.
- Search official KRX, CRSP/Morningstar, and WRDS catalog pages only. Treat catalogue/sample metadata as distinct from a file actually downloaded and inspected.
- No backtest metrics are authorized or possible in this audit.

## Checks and decision criteria

1. Identify an official daily equity/ETF product and earliest stated date.
2. Identify whether active and inactive securities, delisting, corporate actions, and permanent identifiers are stated.
3. Establish whether sample files are directly public or require sign-in, subscription, or contact.
4. Record public price/quote availability without inferring a numeric price from an absent page.
5. Decide whether the source is suitable to request/obtain later; do not claim universe completeness unless product schema and actual sample rows are inspected.

## Safety

Read public pages only. No account or request workflow was initiated. If access requires a credential, purchase, or contact, leave it as an explicit user decision for a separate turn.
