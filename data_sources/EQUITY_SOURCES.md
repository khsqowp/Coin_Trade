# Equity / macro / cross-asset free data sources (catalog)

Compiled 2026-11-20. Personal backtesting research only, not for resale. Data lives OUTSIDE the repo:
`/Users/user/CODE/trading_data/external/equities/` (see `MANIFEST.csv` there). Never commit data.

Already held before this catalog (not re-downloaded):
- KR daily OHLCV csv, 184 tickers: `~/CODE/trading_data/market_data/kis-cache/KR_<code>.csv` (KIS API, e.g. 005930-type files from 2010-08 to 2026-11-17).
- `trading/.rs_cache` (2.5G, US/KR daily panels, funding, ohlcv, sl_* study outputs).
- KR price-only ticks 2026-10-18..11-11: `~/CODE/trading_data/tick/raw_kr` (tar.zst).
- Crypto under `external/crypto` (coingecko, defillama, deribit, metrics).

Verified column = reachability tested from this Mac on 2026-11-20 (Y = data actually fetched, H = HTTP 200 on landing/HEAD only, N = blocked, U = unverified/knowledge only).
Status column: DL = downloaded in phase 1, P2 = phase 2 candidate, SKIP = not done (reason).

## Table

| Source | Dataset | Coverage | Size est | Access | License / ToS note | Verified | Value | Priority | Status |
|---|---|---|---|---|---|---|---|---|---|
| FinanceDataReader (Naver fchart) | KR daily OHLCV, all ~2.8k current KRX stocks + 1.2k ETFs + KS11/KQ11/KS200 | listing to 2026-11, adjusted | ~130 MB parquet | free, no key | Naver ToS: personal use; scraping, keep rate low | Y | 4 | 1 | DL |
| FinanceDataReader (KRX KIND) | KRX delisting list (4229 rows, reason, dates) + current listing/marcap snapshot + ETF list | snapshot | <1 MB | free | KRX info | Y | 4 | 1 | DL |
| Naver delisted price history | prices of delisted codes | mostly absent (most delisted codes return nothing) | - | free | - | Y | 3 | - | DL: 1190 of 4229 delisted codes returned prices (2.35M rows, 1996+); rest empty, survivorship only partly solved |
| KRX data portal data.krx.co.kr (pykrx) | investor-type net buys (foreign/inst/indiv), short-selling balance, market cap, index constituents, PER/PBR | 1990s+ | ~1-3 GB | **login now required** (pykrx needs KRX_ID/KRX_PW env) | KRX ToS: personal; do not bypass login | H (login wall confirmed) | 5 | P2 if user supplies own KRX account | SKIP: login gate |
| Naver Finance HTML (frgn.naver / investor pages) | per-stock foreign/institution net buy daily | ~1y+ pages | MBs | free HTML scrape | gray; scraping HTML pages, keep tiny | U | 3 | P2 bounded | SKIP: HTML scrape ToS risk |
| OpenDART (opendart.fss.or.kr) | KR financial statements, disclosures, shareholders, treasury stock | 2015+ | ~GBs | free **API key** (instant w/ signup) | FSS terms; 20k req/day | H | 5 | P2 (get key) | SKIP: key |
| KOFIA freesis.kofia.or.kr | fund flows, customer deposits, credit balance (margin), investor deposits | 1990s+ | small | free, form/JS UI (no clean bulk API) | personal | H | 4 | P2 | SKIP: no bulk endpoint |
| BOK ECOS (ecos.bok.or.kr) | KR rates, FX, macro, CPI | long | small | free **API key** | BOK | H | 4 | P2 (key) | SKIP: key |
| KIS Open API (apiportal.koreainvestment.com) | KR minute bars (inquiry-time-itemchartprice: ~30 rows/call, only today/recent days), daily 100 rows/call, investor flows per stock | minute: ~1 month back max | - | account + app key (already have; used for kis-cache) | KIS ToS; rate 20 req/s real / 2 req/s paper | H | 4 | P2 (accrue minute bars forward) | SKIP: key/already held |
| Naver fchart minute (`sise.nhn timeframe=minute`) | KR minute bars | ~few days to weeks | small | free, undocumented | gray | H (200) | 2 | - | SKIP: short history, undocumented |
| Stooq | daily bulk (stooq.com/db/h/), per-symbol CSV | global stocks/idx/FX/cmdty | ~GB | free | **now behind JS proof-of-work bot check** (page returns "Please enable JavaScript"); not bypassed | N (challenge) | 4 | - | SKIP: bot challenge |
| Yahoo Finance (yfinance) | daily OHLCV + adj close + dividends/splits: ~1.5k US stocks (S&P 500/400/600/NDX/DJIA + extras), ~230 ETFs, ~60 global indices, ~35 futures, ~33 FX, 7 crypto | max history (1927 for SPX) | ~300-600 MB | free, no key, unofficial | Yahoo ToS: personal use only; rate-limited; survivors only | Y | 5 | 1 | DL |
| Yahoo intraday | 1m last 7 days (8 days max), 5m/15m last 60 days, 1h last 730 days | - | - | free | same | Y (documented limits) | 2 | - | SKIP: shallow history |
| FRED fredgraph.csv (keyless) | ~85 series: Treasury CMT 1M-30Y, TIPS, breakevens, FFR/SOFR, HY/IG OAS, DXY broad, USD pairs incl. KRW, WTI/Brent/NatGas, VIX family, NFCI, claims, CPI, M2, Fed balance sheet, KR macro (OECD-fed) | 1962+ | ~15 MB | free (csv endpoint works without key; API needs key) | FRED ToS: some series 3rd-party copyrighted (S&P/Nasdaq/DJIA limited to ~10y) | Y | 5 | 1 | DL |
| US Treasury par yield curve | official daily curve CSV | 1990+ | ~3 MB | free | public domain | Y | 4 | 1 | DL |
| CBOE indices | VIX, VIX9D, VIX3M, VIX6M, VIX1Y, VVIX, SKEW, VXN, RVX, OVX, GVZ, VXEEM, COR1M/3M, BXM/PUT, etc daily | 1990+ | ~5 MB | free | CBOE: personal, attribution | Y | 5 | 1 | DL |
| CBOE VX futures settlement by expiry | VIX futures daily settle/volume/OI per contract (term structure) | 2013+ | ~10 MB | free | same | Y | 5 | 1 | DL |
| Kenneth French Data Library | FF3/5/6 factors, momentum, industry portfolios (5-49), size/BM sorts, daily+monthly, intl | 1926+ | ~30 MB zst | free | academic, cite French; raw text csv kept as .zst | Y | 5 | 1 | DL |
| AQR Data Library | QMJ, BAB, VME, TSMOM, century of factor premia (xlsx) | 1920s+ | small | free, but xlsx behind page links (landing 200) | AQR terms: academic/personal | H | 4 | P2 | SKIP: xlsx links need manual page parse |
| CFTC COT | Legacy (fut-only, combined), Disaggregated, TFF financial futures, per year | 1986/2006+ | ~100 MB zst | free | public domain | Y | 4 | 1 | DL |
| SEC EDGAR companyfacts (XBRL) | all filers, key ~45 us-gaap/dei tags as long table with `filed` date (point-in-time) | 2009+ | zip 1.4 GB -> ~300 MB parquet | free, needs User-Agent w/ contact | SEC fair-access: <=10 req/s | Y | 5 | 1 | DL |
| SEC EDGAR full-index / submissions / Financial Statement Data Sets | filings index; FSDS zips returned 403 with generic UA | 1993+ | GBs | free w/ UA | same | H (403 on FSDS from this UA) | 3 | P2 | SKIP |
| FINRA Reg SHO daily short sale volume | per symbol per day short/total volume (consolidated NMS) | 2018-08+ | ~200 MB parquet (20.1M rows) | free | FINRA terms: personal; short VOLUME, not short interest | Y | 4 | 1 | DL (2018-08..2026-11-19) |
| FINRA/Nasdaq short interest (bi-monthly) | settlement-date short interest | 2007+ | small | FINRA API needs OAuth creds; nasdaq.com page JS | - | H | 4 | P2 (key) | SKIP: key |
| fja05680/sp500 (GitHub) | S&P 500 historical constituents with changes (delist-aware universe) | 1996+ | <5 MB | free | community data; verify; MIT | Y | 5 | 1 | DL |
| Dukascopy datafeed | tick bid/ask FX, metals, index/commodity CFDs | 2003+ | ~2-6 MB per symbol-day | free, no key | Dukascopy ToS: personal; hourly bi5 LZMA | H (HEAD ok; hourly GETs took 15-30 s and often failed with TLS/timeouts from this network) | 3 | bounded retry later | SKIP: attempted XAUUSD/EURUSD/USDJPY 2026-11-10..12, 0 usable files; decoder (20-byte BE records, 0-based month in URL) is in the session script, not kept |
| HistData.com | FX 1m / tick | 2000+ | large | free but **web form + token per file** | gray to automate | H | 3 | - | SKIP: form gate |
| Tiingo | EOD US + IEX intraday, fundamentals (some) | 30y | - | free key: 50 symbols/hr, 1000 req/day, 500 symbols/month | personal | H | 3 | P2 | SKIP: key |
| Alpha Vantage | daily/intraday/fundamentals | 20y | - | free key: 25 req/day | - | H | 2 | - | SKIP: key |
| Polygon.io | US aggregates, trades | 2y free | - | free key: 5 req/min, 2y history | - | H | 3 | P2 | SKIP: key |
| Finnhub | quotes, fundamentals, some candles | - | - | free key: 60 req/min; candles mostly paid now | - | H | 2 | - | SKIP: key |
| Alpaca | US 1m bars (IEX feed free, SIP delayed 15m), 2016+ | 2016+ | large | free key | Alpaca ToS | U | 4 | P2 (best free US minute) | SKIP: key |
| Nasdaq Data Link (Quandl) | most free sets retired; WIKI prices (to 2018) frozen | - | - | key | - | H | 2 | - | SKIP |
| EIA / LBMA / WGC | oil, gas stocks; gold fix | long | small | EIA key; FRED has WTI/Brent | - | U | 3 | P2 | SKIP: key |
| Binance data.binance.vision / Tardis free samples | crypto futures/spot klines, trades (first day of month free on Tardis) | 2017+ | large | free | already have crypto set | H | 2 for equities | - | SKIP: crypto, held |
| Kaggle / HuggingFace datasets | S&P minute bars, options chains, delisted tickers, tick samples | varies | varies | free but account/CLI token (Kaggle), HF often ok | per-dataset license | H (landing) | 3 | P2: survey HF with `huggingface_hub` for delisted/minute sets | SKIP: unvetted, license per set |
| ETF flows / shares outstanding | issuer pages (iShares/SPDR holdings, daily shares outstanding) | recent | small | free per-fund CSV, no history | issuer ToS | U | 3 | P2 (accrue daily forward) | SKIP |
| Crypto-equities (COIN, MSTR, MARA, RIOT, miners, IBIT/FBTC/GBTC) | via Yahoo | listing to now | included | free | - | Y | 4 | 1 | DL (inside Yahoo us_stocks / us_etf) |
| Japan / Europe / China / Korea ETFs & indices | EWJ, EWY, FXI, MCHI, EZU, VGK, ^N225, ^HSI, ^FTSE, ^GDAXI, 000300.SS etc | via Yahoo | included | free | - | Y | 4 | 1 | DL |

## Phase 1 output (all under external/equities/, ~1.0 GB total, cap 15 GB)
us 451 MB (Yahoo daily 6 groups, FINRA short volume, S&P500 constituents), cot 164 MB, kr 160 MB, sec 133 MB (23.8M fact rows; note `end` has a few bad filer dates e.g. 2215), factors 117 MB, macro 2.8 MB, vix 1.4 MB. MANIFEST.csv has path, rows, bytes, sha256, source URL, date range. Misses: Yahoo BFB BITF BRKB CWEN-A SQ RSX ERUS COW ^BVSP ^DJUSBK VX=F USDCNH=X; FRED WILL5000PR.

## Survivorship notes
- Yahoo/FDR only serve currently listed names; delisted KR codes (4229 listed) mostly return no prices. Use fja05680 constituents for index-membership-aware US universes, but prices of removed names are missing - treat any US/KR cross-sectional backtest as survivorship-biased unless corrected.
- Real delisted KR price history would need KRX portal (login) or a paid vendor.

## Phase 2 shortlist
1. KRX data portal via own account (investor flows, short balance, marcap, index constituents) - highest value for KR.
2. OpenDART key (fundamentals + disclosure events), BOK ECOS key.
3. Alpaca free key for US 1m bars (IEX) 2016+; Polygon 2y; Tiingo EOD for delisted tickers.
4. AQR xlsx datasets (manual links), FINRA short interest (OAuth), SEC FSDS with proper UA.
5. Dukascopy extension to longer windows only after a strategy needs it.
