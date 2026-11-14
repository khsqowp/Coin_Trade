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
