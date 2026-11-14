# trader_skill v1: SEC fundamentals/screener factors on the point-in-time S&P 500

**No edge. None of the 12 pre-registered trials pass all three gates (G1 beat both benchmarks OOS, G2 DSR >= 0.90, G3 null p <= 0.05 after BH correction). The pre-registration-selected strategy (`xbrl_value`, a pure earnings-yield factor) narrowly loses to SPY buy-and-hold out of sample and has DSR 0.567 — well short of 0.90. Three other trials (not selected; selection is fixed to the highest in-sample Sharpe, decided before any OOS number was seen) happen to edge out SPY OOS risk-adjusted, but all three also fail the DSR gate (max 0.641). The programme's "no edge in this dataset" finding (US v1, US v2, MA40) extends to SEC fundamentals and rule-based screening.**

## 0. Scope and what this round adds

Prior rounds (`research/us_daily_v1`, `research/us_daily_v2`, `REPORT_ma40_us.md`) tested only price-derived signals (momentum, mean-reversion, breakout, trend, moving averages) on this point-in-time S&P 500 panel and all found no exploitable edge. This round adds genuinely different inputs from the `trader-skill` repository (https://github.com/Jakeschincariol/trader-skill, 11 Claude skills, pure Python/stdlib; 175/175 of its own unit tests pass): SEC XBRL company fundamentals and a fixed rule-based screener. Full methodology, fixed formulas and gates are in `PREREG_trader_skill_v1.md` (hash-locked before any factor or performance number was computed: `PREREG_trader_skill_v1.timestamp`).

## 1. Server network / feasibility findings (checked before anything else)

- SSH access and general outbound network confirmed from the Oracle Cloud research server.
- `trader-skill` cloned and unit-tested on the server: **175/175 tests pass**.
- Live SEC smoke tests found a **partial, IP-range-specific SEC block**: `www.sec.gov/Archives/edgar/data/...` (needed for actual 13F-HR holdings/information-tables) and `www.sec.gov/files/company_tickers.json` return **HTTP 403** ("Your Request Originates from an Undeclared Automated Tool" — an Akamai bot-management block), reproduced with both `curl` and Python `urllib`, with a correct, declared SEC User-Agent (`SEC_USER_AGENT`), repeated after pauses, on two different occasions. `data.sec.gov` (XBRL companyfacts API) and `efts.sec.gov` (EDGAR full-text search) are **not** blocked from this server.
- **Decision: the 13F-copycat feature (institutional-holdings reconstruction, `trader-copycat/edgar13f.py holdings`) is infeasible from this server and was dropped.** No proxy/VPN/workaround was used to route around the block, per standing instruction. This round uses only the two feature families that are technically reachable: SEC XBRL fundamentals (`data.sec.gov/api/xbrl/companyfacts/`) and a fixed rule-based screener built on those fundamentals (reimplemented directly/vectorised, in the spirit of `trader-screener/screen.py`'s pass/fail semantics, for performance over a 20-year daily backtest loop rather than one `screen.py` subprocess call per decision date).

## 2. Data pipeline built this round

1. **CIK resolution** (707 PIT-universe symbols with cached price data, after v2's existing `REUSED_TICKER_EXCLUDE`): since `company_tickers.json` is blocked, CIKs are resolved via EDGAR full-text search on the symbol's cached Yahoo vendor `longName`, accepted only if the candidate's `display_names` lists the exact ticker. Bare-ticker search was tried first and rejected as unreliable (tested on `F`, `A`, `BRK-B`, `MMM` — bare-ticker search mismatched `F` to Carnival/Tech Data; name-based search resolved all four correctly). **635 / 707 (90%) resolved.**
2. **XBRL companyfacts fetch**: one `data.sec.gov` call per unique CIK (full history per call). **632 / 632 fetched, 0 errors.**
3. **Point-in-time factor extraction** (`build_fundamentals.py`): revenue, cost-of-revenue, gross-profit and diluted-EPS quarterly facts, visible from `filed`+1 day (hard PIT rule, no same-day lookahead), earliest-`filed` kept per fiscal quarter (not a later restatement). Two data-quality fixes made **before looking at any strategy performance** (both are data-correctness fixes, not signal choices):
   - Found that many companies changed their primary XBRL revenue/EPS tag around the ASC 606 transition (fiscal years beginning after 2017-12-15); picking only the first tag with >= 8 rows (as first coded) silently truncated pre-2018 history for exactly these companies (caught via a GME audit: PIT spell 2007-2016, but the newer tag alone only had data from 2019). Fixed by merging facts across every tag in the priority list instead of picking one. Coverage of eligible-days-with-a-value rose from 23-38% to **42-60%** (`factor_coverage.json`) after the fix.
   - Found implausible outliers from mixing differently-defined revenue concepts across a company's history (e.g. STI: `rev_growth_yoy`=30.2, `gross_margin`=-1.88). Fixed, pre-decided sanity bounds applied (data-quality gate, not a performance choice): `rev_growth_yoy` in [-0.95, 10], `gross_margin` and `margin_chg` in [-0.5, 1.0] / [-1, 1] — out-of-range values excluded (set to missing), not clipped to the boundary.
4. **Ticker-reuse audit beyond v2's own list**: while reviewing CIK resolution output, found an additional reuse case not in v2's `REUSED_TICKER_EXCLUDE` — `COMS` resolves to a 2018-founded microcap ("COMSovereign Holding Corp"), not whatever company actually held that S&P 500 slot historically (almost certainly 3Com, delisted 2010). Added an automatic point-in-time-overlap check (a resolved company's fundamentals must have at least one `filed` date inside `[spell_start, spell_end+400d]` for some PIT membership spell of that ticker) and applied it conservatively (exclude on failure rather than risk contamination). **This excluded 48 symbols.** Several of the 48 (e.g. `CAR`, `CCK`, `DDS`, `TKR`, `WEN`) are very plausibly real, continuously-operating companies that were penalised only because the check cannot distinguish "ticker legitimately reused by an unrelated new company" from "same company, renamed, whose SEC filings don't happen to overlap an old, pre-2009-XBRL-era membership spell" — **this is a disclosed, conservative judgment call (err toward exclusion over risking misattributed company identity), not a fully-resolved audit**; a manual, name-by-name adjudication of all 48 was not done given the time budget.
   - **581 / 678 symbols (86%) end up with usable fundamental-factor matrices.**

## 3. Strategies (12, fixed before any result was seen — see PREREG for exact formulas)

`xbrl_growth`, `xbrl_margin`, `xbrl_margin_chg`, `xbrl_value` (pure fundamental factors, top 50) · `quality_composite` (rank-sum of growth+margin_chg+earnings_yield, top 50) · `screener_ew`, `screener_mom`, `screener_lowvol`, `screener_trend_breadth` (fixed screener pass/fail — positive earnings yield, positive revenue growth, margin not down >2pp — used as a universe filter, with/without momentum or low-vol ranking inside it) · `mom_quality`, `value_momentum` (blended rank composites with v2's own `mom12_1`) · `xbrl_growth_mkt` (growth factor + v2's SPY-200dma market filter).

All 12 reuse v2's exact panel, eligibility, cost model (10bp/side), decision/fill timing (close t -> open t+1), IS (2008-01-02..2016-12-30) and OOS (2017-01-03..2026-11-02) windows and benchmarks (`spy_bh`, `ew_univ`), via unmodified imports of `usbt2.py` and `research/us_daily_v1/usbt.py`. `usbt2.py`'s and v2's own files were not modified; v2's `panel.pkl` was not read or overwritten (an incompatible-pickle issue was found and fixed by forcing a fresh, cache-free panel load for this round, see `ts_bt.py`).

## 4. Results

Selected by highest in-sample (2008-2016) excess Sharpe, exactly as pre-registered: **`xbrl_value`** (IS Sharpe 1.081). All trials' IS/OOS/null/DSR numbers (not just the selected one) are reported below for transparency — no re-selection was made after seeing them.

| trial | IS Sharpe | OOS Sharpe | OOS CAGR | OOS MDD | DSR (n=28) OOS | null p (OOS, 200 draws) | BH q |
|---|---|---|---|---|---|---|---|
| xbrl_growth | 0.549 | 0.514 | 0.119 | 0.398 | 0.333 | 0.244 | 0.266 |
| xbrl_margin | 0.921 | 0.668 | 0.139 | 0.327 | 0.519 | 0.010 | 0.013 |
| xbrl_margin_chg | 0.695 | 0.733 | 0.165 | 0.405 | 0.598 | 0.005 | 0.007 |
| **xbrl_value (selected)** | **1.081** | **0.707** | **0.175** | **0.466** | **0.567** | **0.005** | **0.007** |
| quality_composite | 0.646 | 0.770 | 0.176 | 0.404 | 0.641 | 0.005 | 0.007 |
| screener_ew | 0.737 | 0.660 | 0.137 | 0.367 | 0.509 | 0.005 | 0.007 |
| screener_mom | 0.792 | 0.640 | 0.147 | 0.349 | 0.484 | 0.005 | 0.007 |
| screener_lowvol | 0.834 | 0.619 | 0.112 | 0.310 | 0.458 | 0.015 | 0.018 |
| mom_quality | 0.721 | 0.751 | 0.169 | 0.379 | 0.619 | 0.005 | 0.007 |
| xbrl_growth_mkt | 0.504 | 0.114 | 0.031 | 0.381 | 0.046 | 0.945 | 0.945 |
| value_momentum | 1.029 | 0.693 | 0.151 | 0.387 | 0.550 | 0.005 | 0.007 |
| screener_trend_breadth | 0.755 | 0.592 | 0.116 | 0.331 | 0.425 | 0.005 | 0.007 |

Benchmarks, OOS (2017-01-03..2026-11-02): **`spy_bh`** Sharpe 0.724, CAGR 14.9%, MDD 33.7%. **`ew_univ`** (equal-weight of the full eligible set) Sharpe 0.598, CAGR 12.6%, MDD 39.7%.

### Gate-by-gate for the selected strategy (`xbrl_value`)
- **G1** (OOS excess Sharpe >= both benchmarks): 0.707 < `spy_bh`'s 0.724 — **FAILS** (beats `ew_univ`'s 0.598, but G1 requires both).
- **G2** (DSR, n=28 cumulative-programme trials, >= 0.90): 0.567 — **FAILS**, by a wide margin. (DSR at this round's own n=12 only: 0.846 in-sample per `is_selection.json`'s `dsr_emp_n12` — still short of 0.90, and the honest, programme-cumulative n=28 is the pre-registered primary metric.)
- **G3** (OOS random-null p <= 0.05 and BH q <= 0.05): p=0.005, BH q=0.007 — **PASSES**. The strategy is clearly not statistically indistinguishable from a random N=50 portfolio of the same eligible universe (unlike v2's selected rule, which had null p=0.66). It is, however, indistinguishable from "no edge over simply owning the market", which is the decision-relevant comparison.

**Overall: FAIL** (G1 and G2 fail; success requires all three). Cost sensitivity (5/20/40bp) and decision-phase shifts (-5, -10 trading days) on `xbrl_value` show the ~0.67-0.76 OOS Sharpe range is stable and not an artifact of the exact cost or phase assumption — the shortfall vs SPY is not a cost-timing fragility, it is a genuine Sharpe gap, further eroded by the multiple-testing deflation (DSR).

### Secondary, non-selected observation (disclosed, not a success claim)
Three trials not chosen by the pre-registered IS-selection rule (`quality_composite` 0.770, `mom_quality` 0.751, `xbrl_margin_chg` 0.733) have OOS Sharpe above `spy_bh`'s 0.724 and above `ew_univ`'s 0.598 — i.e. they would pass G1 had they been the selected strategy. **None of them come close to passing G2**: their DSR(n=28) values are 0.641, 0.619 and 0.598 respectively, all far short of 0.90. Reported for completeness only; picking the best-looking-OOS trial after the fact instead of the pre-registered IS winner would itself be exactly the kind of post-hoc selection bias the DSR gate and the pre-registration discipline exist to prevent, and it would not change the round's conclusion even if done, since G2 still fails universally.

### Concentration check (`xbrl_value`, OOS)
Top-10 P&L contributors (`KLAC`, `NVDA`, `LRCX`, `UAL`, `AVGO`, `GM`, `MPC`, `ORLY`, `VLO`, `CMG`) account for 0.49 of 1.89 total OOS P&L units (~26%) — concentrated in a handful of semiconductor/cyclical names during the 2017-2026 window, not a broad-based factor return. Consistent with a "value" (low-price-relative-to-earnings) screen disproportionately catching semiconductor-cycle and energy/auto-cycle troughs rather than a persistent structural premium.

## 5. Multiple-testing accounting
This round: 12 selection trials (`n=12`). Cumulative US daily programme (`trials.sqlite`-logged, `selection=1`): 7 (v1) + 9 (v2) + 12 (this round) = **28**. `REPORT_ma40_us.md`'s single hypothesis (never logged to `tcon()`) and the uncommitted, differently-engineered `research/us_daily_v3_exploratory_20261108/` round are disclosed but excluded from `n` for the methodological reasons stated in `PREREG_trader_skill_v1.md` — a disclosed limitation, not a hidden one. Trial budget used: 12 selection-trials + 5 sensitivity trials (cost x3, phase x2, `selection=0`) = 17 logged rows, well inside the 40-trial cap for this round; **no second addendum batch was needed** because every one of the 12 trials — including the three that happen to edge out SPY OOS — fails the DSR gate by a wide margin, so there is no ambiguity that would justify spending more of the budget on a second, equally pre-registered batch.

## 6. Conclusion
**No edge.** The programme's standing finding — no exploitable edge on this point-in-time S&P 500 dataset after costs, DSR deflation and null-testing — now extends from price-only signals (US v1, US v2, MA40) to SEC fundamentals and a rule-based screener (this round). The most interesting positive finding is methodological, not a trading edge: fundamental/screener-filtered portfolios reliably beat a random same-size portfolio of the same universe (G3 passes for 10 of 12 trials, several at p=0.005, the floor achievable with 200 draws) — these are not noise — but reliably beating random stock-picking inside a large-cap index is a much lower bar than beating the index itself, and none of the 12 trials clear that higher, decision-relevant bar once multiple-testing (DSR) is accounted for. The 13F-copycat feature family could not be tested at all from this server (SEC Akamai block on `www.sec.gov/Archives`); if a future round has access to a server/IP without that block (or a paid 13F data vendor), it remains the one largely-untested hypothesis class from the original `trader-skill` brief.

## Files (server, this subfolder only; nothing in `research/us_daily_v2/`'s existing files was modified)
- `PREREG_trader_skill_v1.md` + `.timestamp` (hash-locked before any computation).
- `resolve_ciks.py`, `cik_map.json` (635/707 resolved CIKs).
- `fetch_xbrl.py`, `xbrl_cache/` (gitignored-size raw SEC companyfacts JSON, 632 files).
- `build_fundamentals.py`, `fundamentals_pit.json` (point-in-time quarterly factor rows, 629 symbols).
- `ts_bt.py` (panel extension + 12 strategies + IS/OOS/null/sensitivity stages; imports `usbt2.py`/`usbt.py` unmodified).
- `factor_coverage.json`, `reuse_audit_fundamentals.json`, `is_selection.json`, `oos_results.json`, `null_results.json`, `sensitivity.json`, `equity_curves.csv`.
- `runs/research/us_daily_v2/trader_skill_v1/` (gitignored): `trials.sqlite` (study `US_TS1`), `panel_ts.pkl`.
