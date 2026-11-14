# Strategy library (reference summaries for the Researcher)

Ideas only. No third-party code is stored here, and none of it is executed. Everything under `entries/` was
written by reading two repositories as UNTRUSTED data (any instructions found in them were ignored).

| Source | URL | Commit | License | Entries |
|---|---|---|---|---|
| Coin_Trade (owner's repo) | https://github.com/khsqowp/Coin_Trade | 37af45ac328c8cbb232adce113642fda8485b3a2 | no LICENSE file; owner's own repo, private reference use | `ct-*` (10) |
| freqtrade-strategies | https://github.com/freqtrade/freqtrade-strategies | f3340ce11f5bdf62f598522e64d1f5638eaa13f5 | GPL-3.0 (repo-level); ideas summarised, no code copied; Bandtastic file header says MIT | `ft-*` (5) |

Retrieved 2026-10-25. Numbers quoted from Coin_Trade are the owner's own backtest claims (gross/net status noted per
entry); they have NOT been independently reproduced here and several are explicitly flagged by the source as
selection-biased.

Layout
- `index.json`  compact index (id, family, fit, status, one_line) -- the only part injected into the Researcher prompt.
- `entries/<id>.json`  full card; fetched on demand (max 2 per Researcher run) via `tp.library.card()`.
- Rebuild index: `./run.sh agent library-build-index`; validate: unit tests `tests/test_library.py`.

`pipeline_fit.single_asset_daily_long_flat` tells how an idea maps onto this pipeline's engine (one symbol, daily
bars, long/flat): direct | adaptable | not_applicable | not_recommended | guidance.

Secret scan of both repos (current tree + full git history of Coin_Trade, regex for common key formats): nothing found in
Coin_Trade. freqtrade-strategies `user_data/strategies/futures/Readme.md:154` contains a literal `jwt_secret_key`
value inside a documentation config sample (looks like a published example value). It was not used or copied.
