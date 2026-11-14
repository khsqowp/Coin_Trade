# Oracle KR/US Research Log — 2026-11-07

## Workspace migration

- The complete local `docs/research/kr_us_loop_v1/` tree was moved to `/home/opc/isolated_research/kr_us_loop_v1/` on `opc@152.67.206.89`.
- The transfer contained 6,158 filesystem entries and 526,769,845 bytes. A checksum-mode rsync verification reported 0 files needing transfer and 0 unmatched data before the local source was removed.
- The server root XFS volume is 173 GiB with about 138 GiB available. `/var/oled` is a separate 15 GiB volume and is not larger. Existing home/trading folders are already on the largest volume; they were not moved.
- No existing trading containers, services, or the `/home/opc/trading/pipeline` repository were modified.
- Isolated Python environment: `/home/opc/isolated_research/venv`; installed `numpy==2.5.2`, `pandas==3.0.5`, and `pyarrow==26.0.1`.

## Agent round: 3 backtest roles + data lead

### Agent 1 — Gen12 downside-semivariance candidate

- Synthetic tests: 18/18 passed on Oracle.
- Market-performance run: **NO-GO**. `FREEZE.json` remains `DATA_BLOCKED` and `PENDING_ROOT_REVIEW`; input-data and authoritative calendar hashes are absent.
- Implementation defect: the runner loads the complete price parquet before validating the exchange calendar, conflicting with its stated pre-performance gate. Add a date-index-only calendar validation path and a test proving mismatch fails before any price-value read.
- This is not a strategy rejection and does not count as a performance trial.

### Agent 2 — next candidate scouting

- VIX/realized-volatility exposure filter was proposed as a distinct lead, not registered or tested.
- Official VIX signal history may be available, but the current SPY series is an unofficial Yahoo-derived snapshot and the required full-range authoritative NYSE Arca calendar is missing. No candidate is currently eligible for a defensible market test.
- PEAD remains blocked by missing timestamped point-in-time earnings/surprise data and delisted-complete coverage.

### Agent 3 — Gen13 DMI + Choppiness trend candidate

- Synthetic tests: 14/14 passed on Oracle.
- Market-performance run: **NO-GO**. The preregistration requires an authoritative NYSE Arca calendar matching the full SPY date span; none is present.
- This is not a strategy rejection and does not count as a performance trial.

### Data lead — official-source and storage check

- Current NYSE trading-information page exposes calendars for 2026–2028, not the historical span needed by the frozen candidates.
- NYSE's Closing Prices specification describes historical NYSE Arca files from 2008 onward through its entitled FTP path; this is not a verified free full-span calendar source.
- `agent-reach` is not installed on the workstation, so public-source checks used the web search fallback and official sources. No external data was downloaded in this cycle.

## Cycle disposition

No market-performance backtest ran; no result is classified as profitable or unprofitable. The two synthetic suites only validate code mechanics. Next work is to obtain and provenance-pin an authoritative full-span session calendar and to correct the Gen12 runner's read-order gate before root authorization. Preserve the frozen registrations; do not relax coverage, calendar, or OOS requirements to force a result.

## Continuation — public-source recovery (2026-11-07)

### Isolated research tooling

- Installed Agent Reach 1.6.1 from its official GitHub release in `/home/opc/isolated_research/agent_reach_env/`; `uv`, the tool environment, cache, and home are all under this isolated directory. No global PATH, user home, account login, API key, or live trading service was changed.
- `agent-reach doctor --text` reported web as unverified before a live check; `agent-reach check web --search` passed against Exa (2 search items). The installed version is current according to `agent-reach update --check` (1.6.1). Its older `doctor --json`/`check-update` skill examples do not match the installed CLI; corrected to `doctor --text`/`update --check`.
- This round's search/collection is using Agent Reach's web route; source verification remains separate from a data-rights or performance gate.

### Data source findings to date

- The official CFTC COT/TFF feed is a plausible free positioning signal, but CFTC's historical special-announcement archive documents corrections to past reports. Current historical rows alone therefore do not establish the exact as-published vintage required for point-in-time signals. Source: https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalSpecialAnnouncements/index.htm.
- The KRX Open API catalog lists daily KOSPI/KOSDAQ stock and index data starting in 2010, but use requires terms/key steps; the public service description does not establish delisted PIT membership, full corporate-action adjustments, or correction vintages. Source: https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd.
- Searches found no verified official, freely downloadable full-span S&P 500 total-return OHLC feed. FRED's `SP500` is a price-only series. S&P DJI describes historical index APIs as subscriber services; NYSE Arca historical closing data is provided via entitlement. SSGA exposes SPY distribution records, but distribution records alone do not provide the required executable historical market OHLC/calendar. Sources: https://fred.stlouisfed.org/series/SP500, https://www.spglobal.com/spdji/en/landing/topic/api-data-solutions/, https://www.nyse.com/publicdocs/nyse/data/TAQ_Closing_Prices_Client_Spec_v1.2.pdf, https://www.ssga.com/us/en/intermediary/resources/documents/etf-dividend-distributions.
- Agent Reach search surfaced Stooq daily market archives and community-built Yahoo-derived adjusted series, but neither has yet passed primary-source reuse terms, PIT/corporate-action provenance, and authoritative-calendar checks. They are not substituted into a frozen candidate.
- Agent A inspected SSGA's official no-auth SPY XLSX endpoints at schema level. The NAV-history workbook has `Date/NAV/Shares Outstanding/Total Net Assets`; a separate workbook has distribution event fields. The product-data workbook's high/low/closing fields are current snapshot fields, not historical daily OHLC. SSGA's page restricts copying/reproduction/transmission absent express written consent; no private-backtest permission was verified. No numeric rows were read. Report: `round_20261107/agent_a_us_macro/SSGA_DATA_GATE.md` (SHA-256 `701b4748ce1c0535d011eb840ea28256ec64b99c9d8bfdb0c2d835d705404056`).
- Existing historical price mirrors and earlier candidate scripts remain research inputs, not newly validated data: the prior report identifies the SPY mirror as Yahoo-derived and specifically rejects it for the frozen official-source/calendar gates.
- Agent C's narrower Korean index/ETF audit found KRX TR index families and ETF pages, but no verified per-series API ID, total-return sample, fully adjusted ETF daily history, or compatible download/reuse terms without an account/key. No sign-up or key request was attempted. Report: `round_20261107/agent_c_kr_data/agent_c_index_etf_data.md` (SHA-256 `85a17f595c4568c8c20a37625e5f90c2eb3388701029a954430df12f48d1cd19`).
- Agent B checked issuer/exchange ETF alternatives beyond SPY. Vanguard VTI is the closest public history path found, but its public terms permit personal/noncommercial download while prohibiting copying, modifying, and derivative works; this does not clearly authorize a private backtest. Its full daily range/distribution vintage was also not verified. QQQ's official terms prohibit automated access/derivative use. Report: `round_20261107/agent_b_factor_rotation/FEASIBILITY_public_etf_alternatives_20261107.md` (SHA-256 `9adf0950aeb1e2997a3462046397eb02ae2ff63505df97183616477d965fcf54`).

### Candidate and agent status

- Agent A's US CFTC-positioning/SPY rule is frozen for source-feasibility checks only. After the freeze, 11 official CFTC TFF ZIPs were downloaded to the agent's isolated `raw/cftc/` directory; all 11 passed archive integrity checks and are recorded with hashes in `DATA_GATE.md`. The exact frozen market label has 246 report rows (2022-02-08–2026-10-20); the 156-report warm-up leaves at most 90 signal dates. The different earlier label cannot be merged without a new preregistration. No SPY price values were opened and `performance_run_authorized=false` remains.
- Agent B's separate CFTC candidate review is `FEASIBILITY_BLOCKED`; no performance values or backtest. Its follow-up checked the Stooq SPY endpoint and received HTML browser-verification content rather than CSV, and stopped without bypassing it. The official Stooq reuse/adjustment terms remain unverified. Yahoo's official terms prohibit automated collection without prior permission; FRED's `SP500TR` direct series was not found and its `SP500` is price-only. Report: `round_20261107/agent_b_factor_rotation/ADDENDUM_stooq_yahoo_fred_20261107.md`.
- Agent B independently audited Agent A's CFTC metadata: the frozen exact-label count and 90-signal warm-up reproduce, with no duplicate/missing/nonfinite/nonpositive-OI rows. The initial `DATA_GATE.md` alias count is wrong: it states 494 legacy-label rows but the independent scan found 526 in 2012-01-10–2022-02-01, plus 290 before 2012. The alias remains excluded from the frozen rule. Agent B also flags an undefined empty-window pass condition; resolve transparently by dated addendum before any future root GO. Review: `round_20261107/agent_b_factor_rotation/REVIEW_agent_a_cftc_prereg_20261107.md` (SHA-256 `5892d68a07a6128ae8bb797264923121b3166846fb8e49d70d89ddc791adf4f9`).
- Agent C's KRX review is `DATA_BLOCKED`; it is checking whether official KRX total-return indices or single-index ETFs offer a narrower admissible alternative.
- Agent C completed a non-price-input candidate catalog: SEC Form 4 public-market insider-buy clusters (US), OpenDART ownership-increase filings (KR), KRX reported short-balance pressure (KR), and KRX actual buyback-execution progress (KR). These are untested hypotheses, not strategies; all require point-in-time issuer mappings plus valid executable price/corporate-action data. SEC is the only drafted signal path currently identified as public without an API key, but its required compliant contact User-Agent and full filing/amendment dataset have not been acquired. Report: `round_20261107/agent_c_kr_data/agent_c_distinct_candidates_20261107.md` (SHA-256 `0ba8446876530ae6d57dcfe0f7b920cd594cb9a3814c70b28b341ced3bfb51b7`). The report explicitly does not claim a complete audit of all Gen01–13 preregistrations.
- No new market-price performance values have been opened and no strategy has been accepted or rejected by returns in this continuation. CFTC signal-source rows were inspected only for exact-label and date coverage. No live order or live-service operation occurred.

### Next gates

1. Finish source/rights/PIT/calendar checks for the current A/B/C data paths and preserve reports/hashes under the corresponding isolated agent directories.
2. If a source passes, download only to the isolated research data directory; record URL, retrieval timestamp, coverage/schema, license/terms, raw SHA-256, and any vintage/corporate-action limits before exposing performance values.
3. Independently review the preregistration and read-order gate before one authorized performance run. If no free source satisfies the frozen gate, record `DATA_BLOCKED`; do not silently substitute Yahoo, Stooq, a price-only index, or a synthetic calendar.

## Continuation — survivor-cohort execution audit (2026-11-07)

### Frozen screen and boundary clarification

- Base registration: `trading/docs/research/PREREG_survivor_cohort_screen_20261107.md`, SHA-256 `c7629106db58f414caad82e78fccb27494ef5403b5a2cbcc6232cf262092adab`.
- Arithmetic semantics: `ADDENDUM_survivor_cohort_screen_20261107_v2.md`, SHA-256 `34373a8424a5fbf2fab7a35cbadc903bccf7f8efc89411458289cf195283d8c0`.
- The OOS boundary was ambiguous about executing a December 2022 signal in a separately reset OOS account. `ADDENDUM_survivor_cohort_screen_20261107_oos_boundary_v4.md`, SHA-256 `e0728ddd5b09d7eaa9246d9fffb1f7fd16e79348363792d6401fe3bdaa71c676`, chooses independent cash reset with no pre-OOS pending order. The seeded alternative is retained only as a boundary sensitivity.
- All following results are from current/survivor-cohort screens, not valid historical S&P 500/KOSPI index OOS evidence.

### US strict rerun — seven-name current top-cohort intersection

All three fixed rules and the same-cohort equal-weight buy-and-hold were rerun under v2 cost-iteration tolerance (relative `1e-10`, maximum 20 iterations), with 8 bp base and 36 bp stress one-way friction. Correct MOM12 is `Close[t-21] / Close[t-252] - 1`.

| Rule | Cost | OOS CAGR | MDD | Sharpe | Ending NAV | Comparison |
|---|---:|---:|---:|---:|---:|---|
| Cohort B&H | 8 bp | 50.8162% | -30.6094% | 1.54370 | 4.82504 | Baseline |
| MOM12 skip 1m | 8 bp | 45.3196% | -38.5446% | 1.23194 | 4.18546 | Lower CAGR/Sharpe; deeper drawdown |
| MOM6 + SMA200 | 8 bp | 49.6452% | -31.5110% | 1.36937 | 4.68312 | Lower CAGR/Sharpe; deeper drawdown |
| Donchian 126/63 | 8 bp | 3.4680% | -13.9774% | 0.44006 | 1.13949 | Lower CAGR/Sharpe |
| Cohort B&H | 36 bp | 50.7062% | -30.6094% | 1.54117 | 4.81158 | Baseline |
| MOM12 skip 1m | 36 bp | 43.8639% | -38.7416% | 1.20344 | 4.02713 | Lower CAGR/Sharpe; deeper drawdown |
| MOM6 + SMA200 | 36 bp | 46.9980% | -31.8391% | 1.31515 | 4.37366 | Lower CAGR/Sharpe; deeper drawdown |
| Donchian 126/63 | 36 bp | 2.4144% | -14.9254% | 0.32145 | 1.09568 | Lower CAGR/Sharpe |

- MOM12 was independently reproduced by A and C across all 962 OOS dates. Full daily NAV SHA-256 at 17 significant digits: `831e35600e9758ba60b7f8249d6c36235df9681b0000ed296c8c6b58eb8d62cd`; at 12 decimals: `c92270868621662ff5dc5dd99247397d677c04feb6979e2f9b34ef683367f89d`.
- MOM6+SMA200 and Donchian were independently reproduced by C; their 12-decimal NAV hashes match A's strict v2 runs: MOM6 base `ed9817ce25e0d429cbec717e7ef3d4bfa7797a1668e10ffc45249d4f3b5a25b6`, stress `7006e14a0d6b90af6f8ea3764c8ca7b5bbf95c1447b81c882b392694a98be46a`; Donchian base `4ec6b88c298b8a387ed835428801c5c051e4ca66041955ac35a30db12c4ca19d`, stress `ec3c798abfc390a56525108be903e32038a3aa35cb64d21fe1110e5a3da10c1a`.
- Earlier MOM12 output with `t-273` in place of `t-252`, and earlier runs using absolute `1e-12`/100 cost iteration instead of relative `1e-10`/20, are superseded and invalid.

### KR corrected MOM12 — 21-name current KODEX 200 top-holdings intersection

- One earlier audit implementation multiplied held share counts by daily price returns, applying returns twice. All performance, contribution, and leave-one-out figures from that implementation are discarded.
- Corrected fixed-share accounting was independently reproduced by B and C under the no-seed OOS boundary: MOM12 final NAV `7.59809`, CAGR `69.7343%`, MDD `-49.7390%`, Sharpe `1.41764`; fixed 21-name equal-weight B&H final NAV `4.63878`, CAGR `49.2313%`, MDD `-48.4437%`, Sharpe `1.27045`. OOS is 2023-01-02–2026-11-02. These are not index results.
- Seeded boundary sensitivity, executing the December 2022 signal on the first OOS day, produces final NAV `8.49457` and CAGR `74.7457%`; it is not canonical under addendum v4.
- KIS adjusted-price and corporate-action behavior remain unverified. On 2026-07-31, several large holdings show coherent, broad price-limit-sized gaps that added approximately 24.11% to the portfolio that day. Cache-only evidence cannot distinguish a real broad repricing from adjusted-series/corporate-action effects. This result remains provisional and exploratory.
- KR MOM6 and Donchian have not yet been rerun with corrected fixed-share accounting; prior faulty-path numbers are discarded.

### Disposition and next screen

- Strict US survivor-cohort screen: 0/3 candidates beat the same-cohort B&H on the preregistered OOS metrics in both cost cases.
- Corrected KR MOM12 beats its fixed survivor-cohort B&H numerically, but the adjusted-price provenance issue and current-only cohort prevent it from counting as a valid strategy.
- Valid strategy passes: **0 of 2**. Research remains active; the pass gate is not relaxed.
- A distinct daily opening-gap acceptance/rejection battery is preregistered in `PREREG_opening_gap_acceptance_screen_20261107.md`, SHA-256 `e90c5eb0f9db42c0d2acc2039534754bdc696d017a68da611a28333237a3b7ef`. It uses 54 US and 64 KR current-cache symbols; input manifest SHA-256 is `f29dadb38ffc051144d1f12f41b220004bd27fe9b80f3de1d50dfb668f50f336`. It is not yet performance-tested. The strategy named “gap” in existing catalog code uses close-to-close returns; this new screen uses adjusted `Open[t]/Close[t-1]`, making it adjacent to, but not an exact duplicate of, that family. Data-quality audit is required before the performance run.

### Continuation — opening-gap data gate and KIS parameter clarification (2026-11-07)

- The opening-gap preregistration remains frozen at SHA-256 `e90c5eb0f9db42c0d2acc2039534754bdc696d017a68da611a28333237a3b7ef`; no performance run was started.
- Agent B's read-only scan of all 118 manifest CSVs found 35 OHLC invariant violations, all in US `Open`: 22 on 2021-05-05 and 13 on 2023-06-05. In each affected row, `Open` alone fell outside `[Low, High]`; `High` and `Low` remained consistent with `Close`. Violation magnitude was 0.0195%–1.9444%; same-symbol prior/next closes did not show broad scale jumps. The cause cannot be determined from cached OHLCV alone. No arbitrary correction or exclusion was applied.
- A premature initial conclusion that KR `FID_ORG_ADJ_PRC=0` meant “unadjusted” is corrected. The local endpoint is specifically `/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice` (`FHKST03010100`); the official KIS config for that exact endpoint says `0=adjusted, 1=raw`. A different endpoint, `/inquire-daily-price`, documents the opposite mapping. The local parameter therefore matches the adjusted-price flag for its endpoint, but the cache itself has no request provenance/response metadata to prove how each existing CSV was produced. Sources: https://github.com/koreainvestment/open-trading-api/blob/main/MCP/Kis%20Trading%20MCP/configs/domestic_stock.json (exact `inquire_daily_itemchartprice` entry); local `trading/app/kis_data.py`.
- US local code sends `MODP=1` to KIS overseas daily-price endpoint, matching KIS's official provider example's “adjusted price” setting. This verifies current code intent, not vintage, all-field adjustment semantics, dividends, cache-generation provenance, or the cause of the 35 US `Open` anomalies. Source: https://github.com/koreainvestment/open-trading-api/blob/main/backtester/kis_backtest/providers/kis/data.py.
- The `agent-reach` executable is absent locally. Its configured Exa route via `mcporter` failed network negotiation; official-source review continued with the available web research tool. No downloads, account creation, key use, or server access occurred.
- Alternative-data agent review confirms current-cache cohort work is exploratory only. US PIT candidates require licensed CRSP-like prices/delistings plus S&P constituent history; Korea requires KRX price/constituent/corporate-action evidence. No free authoritative source has yet passed all rights, vintage, universe, and calendar gates.
- Status: **valid strategy passes remain 0/2.** The gap hypothesis is not rejected on performance; it is held at the data-quality gate. Next action is to continue with separately preregistered close-only or adjusted-consistent candidates on the already frozen survivor cohorts while keeping those outcomes explicitly exploratory, and to retain the gap experiment until its `Open` provenance/invalid-bar policy is resolved.

## Continuation — Gen14 independent close-only candidate test (2026-11-07)

### Registration and test boundary

- Registration: `PREREG_survivor_closeonly_gen14_20261107.md`, SHA-256 `1524185587405bde943c3b947701a3e4bcf3bf15378b2bca7cdf7ca7236e3893`.
- Addenda: v1 SHA-256 `eda5028211d69b55faf28522989bdb39baff5ce8f592b1fa064eb13874416248`; v2 SHA-256 `7bf48257b3b4a8aaed2af371b1c45fd29cb8d9f42b45b48e717df3eaec437768`.
- Three rules were frozen before market-performance values were opened: C1 KAMA adaptive trend; C2 Vortex trend state plus SMA100; C3 risk-adjusted 126-day momentum above SMA200.
- Data-input manifest SHA-256: `395e3acc608493164700e2fcdfebebe9bca541bfa6e952a3cebdb15ab81a85b4`. Inputs are the current-cache US 7-name and KR 21-name survivor cohorts, not historical point-in-time index constituents. Results are exploratory and cannot qualify as valid index strategies.
- OOS: US 962 sessions (2023-01-03–2026-11-02); KR 934 sessions (2023-01-02–2026-11-02). Same-cohort buy-and-hold is the baseline. Base and stress costs were both applied; independent 2023–2025 diagnostic cutoffs were also reported but were not pass gates.

### Independent reproduction and correction record

- Agents A and B independently reproduced 16 OOS daily NAV paths (buy-and-hold and C1–C3, both markets, both cost cases). Root compared dates and unrounded daily NAV values: maximum absolute difference was `1.24e-14`, below the preregistered `1e-10` tolerance. Fill counts, turnover, and costs matched. Two 12-decimal path hashes differed only at a floating-point rounding boundary; hashes are not claimed identical for those cells.
- Agent C's first KR-stress output used an incorrect sell-cost value (`0.00345` instead of the registered `0.00295`). All first-pass KR-stress metrics and hashes from C are discarded. C corrected the cost and reran; corrected stress paths matched A. Only corrected A/B results are used below.
- A/B OOS candidate values (CAGR / Sharpe / MDD; base then stress):

| Market | Candidate | Base | Stress |
|---|---|---|---|
| US | C1 KAMA | 36.57% / 1.346 / -16.49% | 32.97% / 1.241 / -17.21% |
| US | C2 Vortex + SMA100 | 27.24% / 1.074 / -30.50% | 23.63% / 0.959 / -31.33% |
| US | C3 risk-adjusted MOM126 + SMA200 | 26.39% / 1.009 / -29.29% | 21.13% / 0.847 / -31.20% |
| KR | C1 KAMA | 19.19% / 0.669 / -55.80% | 18.53% / 0.654 / -55.89% |
| KR | C2 Vortex + SMA100 | 37.42% / 1.012 / -50.92% | 36.69% / 0.999 / -50.92% |
| KR | C3 risk-adjusted MOM126 + SMA200 | 12.23% / 0.509 / -45.21% | 11.36% / 0.487 / -45.37% |

- Matching OOS cohort B&H (CAGR / Sharpe / MDD): US base `50.78% / 1.543 / -30.61%`, stress `50.56% / 1.538 / -30.61%`; KR base `49.14% / 1.269 / -48.44%`, stress `49.10% / 1.268 / -48.44%`.
- Frozen gate required a candidate-market combination to beat same-cohort B&H on CAGR and Sharpe, with no worse MDD, in both costs. Result: **0/6 candidate-market combinations passed; 0/12 candidate-cost cells passed.** None of these outcomes counts toward the requested two valid strategies.
- 2023–2025 diagnostic also did not reveal a candidate that beat its market's B&H across all registered metrics and both cost cases. This diagnostic is secondary and does not change the frozen OOS disposition.
- Data-quality caveat remains: the cache has no vintage/request provenance; 21 >20% close-to-close moves were observed, several in KR on 2026-07-31. This cannot be classified as bad data from cache-only evidence and no observations were removed after seeing results.

### Disposition and continuation

- Gen14 produced no valid strategy. Its losses and failures remain recorded; it is not a reason to stop the search or relax gates.
- Next generation must be materially distinct from the tested single-rule trend/momentum family, preregister its full candidate set and accounting before exposing performance values, and use the currently available survivor cohorts only with an explicit exploratory label. Data research continues in parallel for authoritative PIT constituents, corporate actions, and source-rights evidence. The count remains **0 of 2 valid strategies**.

## Continuation — Gen15 preregistration and source lead review (2026-11-07)

### Candidate-family review

- Three agents independently reviewed the local candidate catalogue before proposing any new test. Gen15 candidate is classified as a **conditional short-horizon reversal variant**, not a novel independent family: it overlaps the already tested `cs_reversal`/RSI2/R12 rebound family, while adding a market-panic trigger plus close-location-value (CLV) and volume confirmation. This family overlap is included in accumulated selection burden; it is not counted as three independent strategy families.
- The alternative SUE/earnings-drift and Form 4 insider-buy hypotheses are genuinely different inputs, but both are currently data-blocked for a valid performance test. Local price caches contain neither original filing-vintage data nor a historical issuer/security map with delisted coverage. No performance test was run for these blocked candidates.

### Source research (no download or account actions)

- Data lead review: SEC EDGAR submissions/XBRL is a public, no-key research route for US issuer filings; requests must obey SEC rate/identification guidance, and latest-restated company facts cannot be backfilled as if originally known. As-filed accession-level snapshots and acceptance times would be required. Non-standard/custom taxonomy EPS can be missing.
- OpenDART has filings/financial statements and original submission identifiers, but this review found an API key/member requirement; no key/account/terms were requested or accepted. Neither source fixes missing point-in-time security membership, delisted security prices, price rights/vintage, or a verified execution calendar.
- Data-lead proposal SHA-256: `004dc341c3b93958b91dcd4769abe62ed3cb4b0236370845a9e6010f2072cfe2` (`/private/tmp/gen15_data_lead.md`). Candidate proposals: A `d6ad977d6d93fb998e06a256bd3eb8590a23c4cb9d9fda65cd0bff4eff7b1574`; B `feabe0968c8a5669c42aab3360e767aa615c39256c210f248e9f09e51ae6c670`; red-team C `d627db20d65472a63a235173062c749aed659038fbf9f9984f50640589a0ba67`.

### Frozen Gen15 conditional panic-reversal test

- Preregistration: `PREREG_conditional_panic_reversal_gen15_20261107.md`, current SHA-256 `8b2d1026a3cf764b5f9436ea10dc548e9a0319fbf30f153f9d802dd7d86eadb7`. Clarifications fix fifth-subsequent-valid-ticker-close expiry, missing-calendar behavior, fee-inclusive per-slot sizing (`NAV_batch/K` total spend), non-terminal stale mark-to-market only, execution-time ranked fallback, and Gen14-matched delayed-start handling for same-cohort B&H.
- Frozen input manifest SHA-256: `395e3acc608493164700e2fcdfebebe9bca541bfa6e952a3cebdb15ab81a85b4`; US 7 fixed names/K=2, KR 21 current KODEX200 holdings/cache intersection/K=5. This is not PIT index data.
- One fixed hypothesis: market equal-weight proxy 5-session panic at `-2 ×` preceding 247-session population volatility `× sqrt(5)`, combined with a negative individual 5-session return, `CLV >= 0.60`, and volume at least `2×` the median of the prior 20 observed bars. Rank by CLV; next-union-session close entry, five subsequent observed ticker closes held, then close exit. No parameter grid and no post-result changes.
- US one-way base/stress cost: 0.08%/0.36%. KR base buy 0.065%, sell 0.245%; KR stress buy 0.115%, sell 0.295%. Full missing-bar, slot, cash, boundary, terminal liquidation, B&H, and metric definitions are in the frozen document.
- The current cohort, price/volume adjustment and vintage, rights, union calendar, and actual execution are unresolved. Any performance screen is exploratory only and **cannot** increase the valid-strategy count.
- The local environment does not have the Oracle `trials.sqlite` databases. Server access is not retried. Global cumulative N is not guessed; therefore this run will not claim DSR/PSR/Bonferroni/BH significance. A global multiple-testing gate remains open.
- Three independent implementations are currently building/running synthetic tests only. Real-price results remain sealed until the independent code, accounting, prefix-replay, and future-data-mutation tests pass and the root explicitly opens the frozen input for performance calculation.

### Gen15 input gate disposition (2026-11-07)

- The frozen preregistration SHA-256 remained `8b2d1026a3cf764b5f9436ea10dc548e9a0319fbf30f153f9d802dd7d86eadb7`; the 28-file input manifest reproduced exactly as `395e3acc608493164700e2fcdfebebe9bca541bfa6e952a3cebdb15ab81a85b4`.
- Before any market performance values were opened, a read-only schema/field-quality scan covered all 58,796 rows. Dates were sorted and unique; OHLC relationships and positive finite OHLC prices passed. Three KR files contained 30 rows with zero volume: 005930 (3 rows, 2018-04-30 through 2018-05-03), 017670 (24 rows, 2021-10-26 through 2021-11-26), and 035420 (3 rows, 2018-10-08 through 2018-10-11). These source bars cannot satisfy Gen15's positive-volume signal/history requirements and trigger the preregistered Section 7 data-quality stop.
- Therefore Gen15 is **DATA_BLOCKED before performance**. No IS/OOS returns, candidate metrics, or signal-performance comparison were calculated. The candidate is neither passed nor performance-rejected. No zero-volume row was repaired, removed, or silently reinterpreted.
- Synthetic implementation validation completed independently: A 15/15 tests, B 24/24, C 24/24; all three runners compile and embed the exact frozen prereg SHA. These tests validate mechanics only and do not substitute for market evidence.
- Current local data's source/vintage and PIT universe remain unresolved. The next step is to identify a no-cost, rights-compatible data source with adequate history and corporate-action/universe metadata; if unavailable, register a materially distinct close-only exploratory candidate with its own explicit data-validity rules. No metric gate will be relaxed to force a positive result.

### No-cost authoritative data-source feasibility (2026-11-07)

- No single no-cost source was confirmed to provide the required US/KR historical daily data, price adjustments/corporate actions, point-in-time index membership including delisted securities, explicit historical vintage, and reusable rights.
- Korea: the [Financial Supervisory Service stock-price OpenAPI](https://www.data.go.kr/data/15094808/openapi.do) is free but requires a service key. Its published license is attribution/non-commercial/no-derivatives; historical full-range, adjustment-vintage, and PIT membership fields were not established, so permission for derived return backtests is unclear. KRX/Koscom official market data and index constituents carry market-data usage/contract conditions. The official KODEX 200 product page provides fund NAV/market-price history and current holdings, not a verified historical PIT holdings + component OHLCV package.
- US: FRED's official S&P 500 series is an index close, not OHLCV or constituent data, excludes dividends, and has usage restrictions. Historical S&P constituent/corporate-action data is licensed. SEC EDGAR is public filings/XBRL, not prices or PIT index membership. Alpha Vantage's current public docs describe free-tier request limits, while full daily history is premium; Polygon's free US stock tier is limited to two years. None closes the full 2018+ US/KR equity PIT gap for this loop.
- No API key/account was created; no data was downloaded; no server or local source data was modified by this source review. This finding does not prove that no free source exists; it means none has passed all gates in this review.

### Gen16 calendar-only close strategy preregistration — review revision

- The first Gen16 draft was rejected by three independent prereg readers before performance: retrospective fifth-to-last union-date selection, overlapping windows, conflicting entry exceptions, ambiguous UTC/month-end semantics, and unspecified metrics. Those findings were preserved; the draft was replaced, not silently amended after results.
- Revised rules remove reverse-counting and test two fixed hypotheses: (C1) buy at first observed union session close and sell at fourth session close of that UTC month, skipping months with fewer than four sessions; (C2) five-year same-calendar-month cross-sectional scores with OOS-only evaluation, ranked entries, and exit on the first observed session close of the next month. C2 January 2023 remains cash because the January 2018 return requires unavailable December 2017 close history.
- Current revised preregistration is `PREREG_calendar_closeonly_gen16_20261107.md`; its hash is recorded after remaining independent review. Both rules remain survivor-cohort exploratory only, with explicit close-fill and immediate same-day proceeds assumptions; they cannot count as valid strategies.
- Current close-only input review has not yet opened performance output. The saved market snapshot remains fixed by the Gen15 manifest; rights and adjusted-price vintage are unresolved.

### Gen16 frozen specification and close-only input gate (2026-11-07)

- Final preregistration: `PREREG_calendar_closeonly_gen16_20261107.md`, SHA-256 `d43cb7cb869e19ad138b7a099583b2b288527572b3f2b6857447a92e6b0954ab`. Three independent readers identified and blocked issues in prior drafts; final revision was reviewed again, and no remaining rule-level blocker was reported. This is document review, not a test pass.
- Frozen candidates: C1 first union-session close entry, exit at the fourth observed union-session close of the same UTC month, with an online next-month-first-session exit if a fourth session is not observed before the month changes; C2 exact five-year same-calendar-month cross-sectional ranking with OOS-only scoring, full-list fallback, and next-month-first-session close exit. No parameter grid.
- OOS alone determines candidate screen outcomes; C1 IS is descriptive. Initial NAV time, CAGR annualization, daily turnover denominator, close-fill/settlement simplifications, UTC parsing, missing-entry fallback, and terminal-price failures are explicit in the frozen document.
- Close-only input gate read 28 files / 58,796 rows without calculating returns or signal/benchmark performance. Exact manifest matched `395e3acc608493164700e2fcdfebebe9bca541bfa6e952a3cebdb15ab81a85b4`; all timestamps parsed as explicit UTC offsets, dates sorted and unique, and all closes were finite and positive. US union coverage: 2,221 dates, 2018-01-02–2026-11-02; KR: 2,166 dates, same endpoints. No close/timestamp input-gate issue found.
- The three runner agents are building independently and synthetic-only. No Gen16 performance values have been opened or calculated. If their synthetic gates and daily-path reconciliation pass, only a local exploratory screen is contemplated; source rights/vintage remain unresolved, so no derived performance numbers or pass/fail claims will be published to Coin_Trade. Its record may contain only method/status/hashes until rights are verified.

### Gen16 implementation, market-screen and reconciliation record (2026-11-07)

- Final preregistration SHA-256: `1d85c35f9696ee3c982f62027f96599aeed7f3d3d3e99dc8efbabf250a350342`. Frozen 28-file input manifest reproduced exactly: `395e3acc608493164700e2fcdfebebe9bca541bfa6e952a3cebdb15ab81a85b4`.
- Independent synthetic suites: A 31/31, B 29/29, C 16/16; all three modules and tests compiled. Runner hashes: A `af0bc17f4826821abb75036af47bee43b0fdfaef778c33609b47f5bf8635a077`, B `b0de6de99120f775173269378a720e5e9f940401f023c78e4aa3851c781a7e78`, C `b1ca9d196aa245aecad1359df5c025cb3727c843c670dcac6ea6a7c43aa83918`. Test hashes: A `0db3c43270eff605efaeade6160042ddc14fedc36d48ebba4353a6a7d7613e91`, B `3f1ade6a7ecec6be393936154bf7ba22f3d13f49568abc450837ab609cf096c6`, C `3449f996ab89dac798e31ed78d7b0b6afc48857c67f5f6bd4adf5e768cdcb540`.
- A/B ran all 20 registered market/candidate/segment/cost cells independently after the preregistration and input manifest checks passed. Daily path dates, fills, shares, gross notionals, fees and cash matched within `1e-10`; maximum absolute daily NAV difference was `6.22e-15`. A/B reconciled on the same frozen local snapshot. No Oracle connection, server process, live order, or remote dataset was used.
- A separate first synthetic comparison appeared to diverge because A saw data through 2025 while B/C were deliberately truncated at 2024-12-05. At that boundary B/C liquidated terminally while A correctly continued using its later rows. After using the same terminal input date, all three engines agreed for C1, C2 and buy-and-hold in both markets; maximum NAV difference was `1.04e-14`. This was a comparison-fixture boundary error, not a strategy or runner defect.
- CAGR annualization day-count basis was not frozen: preregistration specifies elapsed calendar days but not whether to use 365.2425 or 365.25. A uses 365.2425; B/C use 365.25. Neither value is declared the preregistered one. Displayed CAGR values below use A's 365.2425 convention; all candidate/benchmark pairs in each OOS segment share the same start/end, so the strict CAGR ordering is equivalently determined by terminal NAV and is unchanged by this small convention difference. Freeze the day-count basis before any later generation's performance output.
- Gen16 OOS screen disposition: **0/4 candidate-market combinations passed** (C1/C2 × US/KR; each must pass both base and stress). C1 and C2 failed to exceed same-cohort buy-and-hold in both CAGR and Sharpe for every OOS cost case. The registered MDD comparison does not rescue any candidate. These are exploratory survivor-cohort results only and cannot count toward the two valid strategies because source rights/vintage, PIT membership, exchange-calendar validation, settlement realism, and global multiple-testing burden remain unresolved.
- All values are NAV multiples/return percentages from this fixed snapshot, with no claim of executable or total-return performance. `CAGR / Sharpe / MDD` (C1 IS is descriptive; C1/C2 OOS screened; buy-and-hold is the cost-matched comparator):

| Market | Cell | Cost | CAGR | Sharpe | MDD | Terminal NAV | Turnover | Costs | Fills |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| US | C1 IS | Base | 3.6224% | 0.332369 | -19.9332% | 1.194466 | 119.9520 | 0.114377 | 840 |
| US | C1 IS | Stress | -3.1202% | -0.168639 | -23.6528% | 0.853591 | 119.7848 | 0.433489 | 840 |
| US | C1 OOS | Base | 2.1007% | 0.246469 | -17.5118% | 1.082949 | 91.9632 | 0.078929 | 644 |
| US | C1 OOS | Stress | -4.5355% | -0.368015 | -25.9379% | 0.837015 | 91.8350 | 0.313209 | 644 |
| US | C2 OOS | Base | 30.7137% | 0.933378 | -39.6876% | 2.791688 | 83.0374 | 0.171232 | 166 |
| US | C2 OOS | Stress | 23.0063% | 0.761236 | -40.6924% | 2.211557 | 82.8148 | 0.674180 | 166 |
| US | B&H IS | Base | 21.5535% | 0.717292 | -56.5530% | 2.650472 | 1.9992 | 0.002921 | 14 |
| US | B&H IS | Stress | 21.4172% | 0.714220 | -56.5530% | 2.635671 | 1.9964 | 0.013110 | 14 |
| US | B&H OOS | Base | 50.7392% | 1.542963 | -30.6094% | 4.821183 | 1.9992 | 0.004659 | 14 |
| US | B&H OOS | Stress | 50.5191% | 1.537840 | -30.6094% | 4.794260 | 1.9964 | 0.020909 | 14 |
| KR | C1 IS | Base | 1.8879% | 0.326563 | -17.6290% | 1.097848 | 109.5131 | 0.177610 | 2300 |
| KR | C1 IS | Stress | 0.7749% | 0.153628 | -19.3114% | 1.039281 | 109.4834 | 0.228166 | 2300 |
| KR | C1 OOS | Base | 5.2170% | 0.456401 | -14.1381% | 1.215394 | 91.9701 | 0.151803 | 1932 |
| KR | C1 OOS | Stress | 3.9616% | 0.364767 | -14.2240% | 1.160704 | 91.9472 | 0.195957 | 1932 |
| KR | C2 OOS | Base | 9.0758% | 0.461016 | -35.9891% | 1.395465 | 87.8591 | 0.153802 | 440 |
| KR | C2 OOS | Stress | 7.8310% | 0.418760 | -36.5631% | 1.335358 | 87.8159 | 0.198424 | 440 |
| KR | B&H IS | Base | -0.3834% | 0.072655 | -41.6944% | 0.981008 | 1.9873 | 0.003059 | 42 |
| KR | B&H IS | Stress | -0.4034% | 0.071566 | -41.6939% | 0.980026 | 1.9869 | 0.004048 | 42 |
| KR | B&H OOS | Base | 49.0921% | 1.268816 | -48.4437% | 4.627413 | 1.9994 | 0.012015 | 42 |
| KR | B&H OOS | Stress | 49.0532% | 1.268127 | -48.4437% | 4.622784 | 1.9989 | 0.014826 | 42 |

- Next action: do not mutate Gen16 after observing results. Continue with a new, materially different and separately preregistered family or improve price/universe provenance; carry forward all 20 cells and the failed disposition to prevent duplicate testing. No Ochestration commit/push.

## 2026-11-07 — Gen17 low-skew factor: exploratory screen and procedural deviation

### Frozen inputs and implementation evidence

- Final preregistration SHA-256: `ecd75ddbae7b59813bbc4837aba2f58d139adb8ec117c89087d07e7334e6cc58`. Frozen 28-file input manifest: `395e3acc608493164700e2fcdfebebe9bca541bfa6e952a3cebdb15ab81a85b4`.
- The hypothesis is one 63-return cross-sectional low-G1 ranking rule with fixed K, 21-union-session cadence, frozen costs and same-cohort B&H. It is a known factor variant, not an independent new strategy family. This is the same current survivor cohort and reused OOS period as prior generations.
- Independent synthetic test suites passed: A 29/29, B 39/39, C 14/14. Runner hashes: A `bccc570cbb1b23bad75e34073084606962e760e105d5f81e1842faeba81289ec`, B `7048279846ba373498c5664d9731dcf42ab27c6c0a4579a40076aaebfe01349b`, C `9d54c7dca38361c1d012efefa6a9df0582d40221ba8b10c616c15cf838c067ec`. Test hashes: A `5f6486013afe2a5391232fe7014bbb661d31b6d4924453bed4b9f94aaad6627c`, B `90af1c01daed01e977aca50d465c621fbb9c58ab566b0f18bc122fffc49e9377`, C `cae73d9afcdacbd4daab2224a30ccd76646777dc5f1958255ef485a979ff9a25`.
- Before performance output, all 91 registered overlap dates were cross-checked: eligible symbols and the three preregistered Spearman diagnostics matched across A/B/C exactly. The per-date results and medians are in `GEN17_overlap_diagnostics_20261107.md` (SHA-256 `73d3ab9ac37c9652378675e0059314e59b0ad24ff16fe9eb130daf42930cd57c`).
- **Process deviation:** performance metrics were exposed before the complete required A/B/C per-union-date post-simulation reconciliation had been run. After exposure, an audit compared score/rank/eligibility on all 91 dates and candidate/benchmark paths under both costs in both markets. Maximum US differences were: score `0`, NAV `2.31e-14`, cash `9.77e-15`, shares `1.39e-17`, fill field `1.15e-14`, daily gross flow/fees `2.13e-14`. Maximum KR differences were: score `5.27e-16`, NAV `8.44e-15`, cash `2.22e-15`, shares `1.02e-20`, fill field `1.89e-15`, daily gross flow/fees `7.99e-15`. These are below `1e-10`, but the after-the-fact audit does not erase the sequencing deviation or retroactively satisfy the preregistered pre-performance gate. Treat all performance output as exploratory and non-confirmatory.

### Numerical screen (exploratory only; NAV units start at 1.0)

MDD is shown as a positive drawdown magnitude. The preregistered numerical screen requires both base and stress CAGR/Sharpe to exceed same-cohort B&H and MDD to be no worse.

| Market | Portfolio | Cost | CAGR | Sharpe | MDD | Terminal NAV | Turnover | Costs | Fills | Avg cash share |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| US | Low G1 | Base | 68.0149% | 1.872293 | 26.4050% | 7.307585 | 91.9273 | 0.287718 | 184 | 0.2079% |
| US | B&H | Base | 50.7392% | 1.542963 | 30.6094% | 4.821183 | 1.9992 | 0.004659 | 14 | 0.1040% |
| US | Low G1 | Stress | 57.0945% | 1.645209 | 27.6311% | 5.648056 | 91.6736 | 1.110390 | 184 | 0.2079% |
| US | B&H | Stress | 50.5191% | 1.537840 | 30.6094% | 4.794260 | 1.9964 | 0.020909 | 14 | 0.1040% |
| KR | Low G1 | Base | 28.8312% | 1.002532 | 31.8987% | 2.642525 | 89.8630 | 0.226558 | 450 | 0.2141% |
| KR | B&H | Base | 49.0921% | 1.268816 | 48.4437% | 4.627413 | 1.9994 | 0.012015 | 42 | 0.1071% |
| KR | Low G1 | Stress | 27.3273% | 0.962937 | 32.7256% | 2.526145 | 89.8187 | 0.291139 | 450 | 0.2141% |
| KR | B&H | Stress | 49.0532% | 1.268127 | 48.4437% | 4.622784 | 1.9989 | 0.014826 | 42 | 0.1071% |

The US survivor-cohort screen numerically exceeds its same-cohort B&H comparator in both registered cost cases. The KR screen fails CAGR and Sharpe in both cost cases, although its drawdown magnitude is lower. This is not a valid strategy result: source rights, price adjustment/vintage, point-in-time membership and global cumulative testing count remain unresolved; OOS is reused; and the pre-performance sequencing gate was violated. No DSR/PSR or Bonferroni/BH claim is made. The valid-strategy count remains **0/2**.

### Preserved outputs and next step

- Complete registered overlap output: `GEN17_overlap_diagnostics_20261107.md`.
- Full date-by-date NAV paths for candidate and B&H, base and stress, US and KR: `GEN17_daily_nav_paths_20261107.md` (SHA-256 `1f91e0dc84d6c4ebdab72833801d8d9969720c92ac889398411f9ebc9e465cb1`).
- Full decision-date rank, G1 score, intended top-K, actual filled ranks, and unused execution slots: `GEN17_signal_rank_ledger_20261107.md` (SHA-256 `5510884fe314b939e5282b67e5f0518656c922a6135de458258c5ee9766b4e0a`).
- Do not tune Gen17 after these results. Continue with a materially distinct preregistered hypothesis or, preferably, improve the admissible PIT/source-rights evidence. Any future performance opening must complete and record every independent per-date gate before metrics are exposed. No Oracle access, paid API/account action, live order, Ochestration commit or push occurred.

## 2026-11-07 — Gen18 candidate-family feasibility (no performance run)

- Three independent strategy reviews found no sufficiently distinct, ready-to-test close-only idea. Already tested/registered families include trend/momentum, direction/trend state, reversal/rebound, calendar, low-risk/downside-semivariance, gap acceptance, panic reversal, and low skew. Do not add renamed OHLC indicator variants to inflate the search count.
- Low-beta ranking is computable but overlaps the existing low-risk family and has weak estimates on the 7-name US / 21-name KR survivor cohort. It is not selected as a new independent family.
- More distinct leads are filing-derived information/ownership signals: US 13F institutional ownership flow and as-filed earnings drift (PEAD/SUE), plus Korean DART filings. These remain feasibility leads, not preregistered tests.
- Source investigation was blocked by the approved research route: `agent-reach` is not installed; documented Exa call through `mcporter` failed MCP version negotiation. No fallback web tool was used because the skill provides no alternate retry route. No official-source terms, coverage, amendment-vintage, security-map or PIT-price gate was newly verified; no account/key, download, market-data read, or performance calculation occurred.
- Disposition: `FEASIBILITY_BLOCKED`; do not preregister Gen18 until official source/data-rights and PIT gates are checked. Prioritize restoring an approved source-research path and establishing a lawful PIT/prospective dataset. Count remains **0/2**.
- Detailed review: `GEN18_candidate_feasibility_20261107.md`.

### Official-source follow-up: 13F source lead (2026-11-07)

- Clarification: after Agent Reach/Exa failed, the root used the available web search/read tool as an announced fallback and consulted official SEC/DART pages only. No ZIP, API endpoint, or market-price data was downloaded or called.
- SEC's official 13F dataset page documents as-filed structured data from July 2013 through August 2026, quarterly updates, and a warning that flattened compilations can contain extraction errors and omit filing metadata. Some filings after 5:30 p.m. Eastern on a quarter's last business day are placed in the next quarterly dataset: https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets
- SEC says data.sec.gov submissions/XBRL APIs require no authentication/API key and are updated as filings are disseminated; bulk archives are available: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- SEC Form 13F filings are due within 45 days after quarter-end and include original `13F-HR` and amended `13F-HR/A` forms. Signal availability must follow accepted filing timestamps, not quarter-end: https://www.sec.gov/rules-regulations/staff-guidance/frequently-asked-questions-about-form-13f
- SEC fair-access guidance limits requests to no more than 10 per second across a user’s requests: https://www.sec.gov/about/developer-resources
- DART documents disclosure XML and structured financial access; its portal provides an API-key application. No account/key was created or requested: https://opendart.fss.or.kr/intro/main.do and https://opendart.fss.or.kr/
- Updated disposition: `SOURCE LEAD PASS / STRATEGY DATA GATE BLOCKED`. A 13F institutional ownership-breadth hypothesis is distinct enough for future US-only work, but no historical point-in-time CUSIP/security map, split/corporate-action treatment, complete PIT manager/security coverage, nor admissible PIT price panel is present. SEC's flattened-data disclaimer, amendments, joint-manager overlaps, notices/missing reports, and omitted metadata require raw-filing resolution. Three independent reviewers agree that a price-performance test is not yet responsible. No Gen18 rule was frozen and no Gen18 price data/performance test ran.
- Candidate rule sketch (not frozen): at a fixed report-period-plus-60-day information cutoff, compare only original reports actually accepted by SEC by that cutoff, calculate split-adjusted share-count direction by comparable manager/security, rank by cross-manager breadth, then enter after the filing cutoff. This remains a concept only; don't implement until identifiers, shared-manager deduplication, missing/late filing rules, prices, costs and benchmark are frozen and validated.
