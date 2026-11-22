# Free / public historical crypto data sources (catalog)

Compiled 2026-11-20 for personal backtesting research (not resold). Data lives OUTSIDE this repo at
`/Users/user/CODE/trading_data/external/crypto/` (see `MANIFEST.csv` there). Downloader: `.../external/crypto/scripts/dl.py`.
"Verified" = reachability confirmed by HEAD/range/API request on 2026-11-20 (V = yes, U = from knowledge only, not verified).
Value 1-5 = research value for our strategies (perp/funding/momentum/regime), given what we already hold.

Already held (do not re-download): Binance spot/perp/funding trade ticks 2026-10-28..11-11 (BTC ETH SOL BNB XRP DOGE);
15m/1h/4h/1d bars for ~20 USDT symbols; 2017+ bars BTC ETH BNB XRP; funding history for 5 majors.

## 1. Binance public dump (data.binance.vision; bucket listing: https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?prefix=...)

| Source | Dataset | Coverage | Size est | Access | License/ToS | Verified | Value | Priority |
|---|---|---|---|---|---|---|---|---|
| Binance | um futures klines 1m (monthly zip) | 2019-09/2020-01 -> 2026-10, daily files for current month; ~690 USDT-M symbols incl. delisted | ~100-150 MB zip per symbol full history | free | Binance public data terms: personal/research OK | V | 5 | P1 (downloaded, 36 symbols) |
| Binance | um markPriceKlines 1m | same as above | 30-90 MB/symbol | free | same | V | 4 | P1 (downloaded) |
| Binance | um premiumIndexKlines 1m | same | 40-65 MB/symbol | free | same | V | 5 (basis/funding predictor) | P1 (downloaded) |
| Binance | um indexPriceKlines 1m | same | ~97 MB/symbol (BTC) | free | same | V | 2 (mostly redundant with mark) | P3 |
| Binance | um fundingRate (monthly) | 2020-01 -> 2026-10 | ~1 KB/month | free | same | V | 5 | P1 (downloaded) |
| Binance | um metrics (OI, OI value, top-trader L/S count+position ratio, global L/S ratio, taker buy/sell vol ratio; 5 min) | BTC from 2020-09; most symbols from 2021-12 or listing; daily files only, up to 2026-11-19 | ~12 KB zip/day (~20 MB/symbol) | free | same | V | 5 (OI + L/S + taker; the "liquidation proxy" source) | P1 (downloaded) |
| Binance | spot klines 1m | 2017-08 -> 2026-10 | ~similar to perp; BTC ~150+ MB | free | same | V | 4 (spot-perp basis) | P1b (downloaded) |
| Binance | um bookDepth (+-1..5% depth/notional snapshots ~30s) | 2023-01-01 -> 2026-11-19 daily | ~0.5 MB zip/day, ~700 MB per symbol | free | same | V | 4 (liquidity/imbalance regimes) | P2 BTC/ETH |
| Binance | option BVOLIndex (1-second BTC/ETH implied vol index) | 2023-06-20 -> 2026-11-19 | ~540 MB zip BTC | free | same | V | 4 (implied vol history) | P2 |
| Binance | option EOHSummary (hourly option IV, greeks, OI) | 2023-05-18 -> 2023-10-23 only | ~56 MB BTC | free | same | V | 2 (short window) | P3 |
| Binance | um aggTrades (monthly/daily) | 2019-12 -> 2026-11-19 | ~550 MB zip/month BTC; 45 GB BTC full | free | same | V | 4 | P2 bounded window only |
| Binance | um trades (monthly) | 2019-09 -> 2026-10 | ~70 GB BTC full | free | same | V | 3 (aggTrades is enough) | skip |
| Binance | spot aggTrades / trades | 2017-08 -> 2026-10 | ~60 GB BTC full | free | same | V | 3 | skip |
| Binance | um bookTicker (monthly/daily) | 2023-05-16 -> 2024-04 only (discontinued) | ~2 GB zip per BTC month | free | same | V | 3 | skip (size) |
| Binance | cm (coin-margined) klines/funding/etc. | 2020+ | small | free | same | V (listing) | 2 | P3 |
| Binance | liquidationSnapshot | REMOVED from the bucket (listing returns nothing) | - | - | - | V (absent) | - | n/a. Use Bitfinex/OKX recent API, or paid Tardis/CoinGlass |
| Binance REST | openInterestHist, topLongShort*, takerlongshortRatio (fapi/futures/data) | only last ~30 days | tiny | free | Binance API ToS | V (31 daily rows) | 1 | not needed (metrics dump is superior) |

## 2. Other exchanges

| Source | Dataset | Coverage | Size est | Access | License/ToS | Verified | Value | Priority |
|---|---|---|---|---|---|---|---|---|
| Bybit | public.bybit.com/trading/<SYM>/ daily tick trades csv.gz (perp) | BTCUSDT from 2020-03-25 -> 2026-11-19; other symbols later | ~30 MB/day BTC (gz) | free, directory listing | Bybit public data; research use | V | 4 (cross-venue ticks) | P2 bounded window |
| Bybit | public.bybit.com/spot/, spot_index/, premium_index/, kline_for_metatrader4/ | directory listings reachable | small-medium | free | same | V (dirs) | 3 | P2 |
| Bybit | /orderbook/ | 404 at root (per-symbol paths may exist) | large | free | same | partial | 3 | check in P2 |
| Bybit REST v5 | open-interest, account-ratio (L/S), funding history, kline | OI/LSR limited depth (~months); funding long | tiny | free | API ToS | V | 3 | P2 (funding/OI cross-check) |
| OKX | okx.com/cdn/okex/traderecords/trades/daily/YYYYMMDD/<INST>-trades-YYYY-MM-DD.zip and aggtrades/ | 2021+ (check per inst); BTC-USDT 2024-11-01 trades 6.6 MB, aggtrades 3.2 MB | 3-7 MB/day/inst | free | OKX historical data page ToS | V (200 on 2024-11-01) | 3 | P2 |
| OKX REST | rubik OI/volume, long/short ratio, liquidation-orders | recent window only (~days-months) | tiny | free | API ToS | V | 2 | optional collector going forward |
| BitMEX | s3 public.bitmex.com/data/{trade,quote,liquidation,funding...}/YYYYMMDD.csv.gz | 2014+ (XBT) | ~tens MB/day | free (historically) | BitMEX ToS | **403 from direct S3 path now** - U | 3 (liquidations!) | re-check via https://public.bitmex.com/ browser; else skip |
| Deribit | public API: DVOL index (BTC/ETH), funding_rate_history, instruments | DVOL from 2021-03; funding from 2019 | KB-MB | free, no key | Deribit API ToS | V | 4 (IV regime, funding) | P1c (downloaded to misc/) |
| Deribit | history.deribit.com (tick options trades/book) | 404 at root; API host get_instruments 200 | big | free API | ToS | partial | 3 | P2 research |
| Hyperliquid | info API fundingHistory (since ~2023-05), candles | 2023+ | KB | free, no key | API ToS | V | 3 | P1c (downloaded) |
| Hyperliquid | hyperliquid-archive S3 (l2Book, asset_ctxs) | requester-pays / 403 | - | key/AWS requester pays | - | 403 | 3 | AWS phase 2 |
| dYdX v4 | indexer candles/funding | 2023+ | KB-MB | free | API ToS | V | 2 | P3 |
| Kraken | OHLCVT bulk download (support article; Google Drive link) + REST OHLC (720 candles only) | 2013+ spot | ~GB | free | Kraken ToS | V (article), bulk is Drive link | 2 | P3 |
| Coinbase | Exchange REST candles (300/request) | 2015+ spot | KB per call | free | API ToS | V | 2 | P3 (BTC/ETH long daily history) |
| Bitstamp | REST OHLC (1000/req) | 2011+ | small | free | ToS | V | 2 | P3 |
| Bitfinex | REST trades/hist, liquidations/hist, status/deriv (funding/OI of derivs) | trades full, liquidations recent (limit 2500/call) | small | free, no key | API ToS | V | 3 (liquidations) | collector going forward |

## 3. Aggregators / datasets / macro / on-chain

| Source | Dataset | Coverage | Size est | Access | License/ToS | Verified | Value | Priority |
|---|---|---|---|---|---|---|---|---|
| alternative.me | Fear & Greed index (daily) | 2018-02 -> now | <1 MB | free, no key | free w/ attribution | V | 3 | P1c (downloaded) |
| DefiLlama | stablecoin supply (total, USDT, USDC), stablecoin list, total chain TVL, yields | 2017/2019+ daily | ~MB | free, no key | free w/ attribution | V | 4 (liquidity regime) | P1c (downloaded) |
| CoinMetrics | community CSV on GitHub (coinmetrics/data) + community-api v4 | asset-level on-chain metrics, 2009+ BTC | ~MB each | free (community subset) | CC BY-NC 4.0 (non-commercial) | V | 4 | P1c (downloaded 15 assets) |
| Glassnode | metrics API | - | - | key/paywall (401) | - | V (401) | - | list only |
| CoinGecko | market_chart (365-day limit on free) | limited | small | free (limited) | attribution | V | 2 | P3 |
| blockchain.info | charts API (hash rate, etc.) | BTC full | small | free | ToS | V | 2 | P3 |
| Farside | spot ETF flows (BTC/ETH) | 2024-01 -> now | tiny | HTML, 403 to scripts (bot protection) | do not bypass | V (403) | 4 | manual CSV copy by user if wanted |
| CryptoDataDownload | exchange OHLC csv (Binance, Bitfinex, etc.) | hourly/daily/minute | MB-GB | free (site reachable) | personal-use; check site ToS | V (200) | 2 (redundant with Binance dump) | P3 |
| Kaggle / HuggingFace | various LOB, tick, sentiment datasets | varies | varies | Kaggle requires account/API key; HF open | per-dataset license | V (APIs reachable) | 2-3 | search later, verify license each |
| CFTC | COT financial futures (CME BTC) | weekly | small | free | public domain | V | 2 | P3 |
| Tardis.dev | free first-day-of-month sample files (datasets.tardis.dev/v1/<exch>/<type>/YYYY/MM/01/<SYM>.csv.gz) | many exchanges incl. liquidations, book snapshots, derivative_ticker; **only the 1st of each month free** | 10-500 MB/file | free for day 1 of month, otherwise API key | Tardis ToS: non-commercial sample use | V (binance-futures trades 2020-02-01: 200; bitmex 404 for that path) | 4 (liquidations + OI + book on 1st of month) | P2 targeted |
| CoinGlass / Laevitan / Coinalyze | liquidations, OI, options | - | - | key/paywall for history | - | U | - | list only |

## Downloads in phase 1 (location)

`/Users/user/CODE/trading_data/external/crypto/binance/<dataset>/<SYMBOL>/<YYYY-MM>.parquet` (zstd) plus
`misc/` (small API datasets, `MISC_MANIFEST.csv`) and `MANIFEST.csv` (path, rows, bytes, sha256, source_url, date_range).
Notes: kline `open_time` is ms for futures; Binance spot switched to microseconds in 2025 (kept raw; normalise on load).
Metrics are 5-minute rows, `create_time` as UTC string. Current month assembled from daily files up to 2026-11-19.
Row counts are verified (CSV data lines == parquet rows) and each zip is verified against Binance's .CHECKSUM (sha256).

## Phase 1 results (2026-11-20/21), 18.64 GB parquet + 45 MB misc, all row-count verified

| Dataset | Files (symbol-months) | Symbols | Rows | GB | Range |
|---|---|---|---|---|---|
| um_klines_1m | 2295 | 35 | 99.4 M | 4.33 | 2020-01..2026-11-19 |
| um_markPriceKlines_1m | 2295 | 35 | 99.3 M | 3.46 | same |
| um_premiumIndexKlines_1m | 2290 | 35 | 99.0 M | 3.59 | same |
| spot_klines_1m | 2442 | 33 | 105.8 M | 4.53 | 2017-08..2026-11-19 |
| um_metrics (5 min OI/LSR/taker) | 1892 | 35 | 16.5 M | 0.81 | 2020-09 (BTC) / 2021-12.. |
| um_fundingRate | 2256 | 35 | 0.2 M | 0.01 | 2020-01..2026-10 |
| um_bookDepth (BTC, ETH) | 94 | 2 | 83.3 M | 1.03 | 2023-01..2026-11-19 |
| opt_BVOLIndex (BTC, ETH, 1 s) | 84 | 2 | 210.8 M | 0.89 | 2023-06..2026-11-19 |

Symbols (35): BTC ETH BNB SOL XRP DOGE ADA AVAX LINK DOT LTC BCH TRX ATOM NEAR UNI APT ARB OP SUI AAVE FIL ETC INJ SEI WLD HBAR TON 1000PEPE 1000SHIB POL CRV RUNE TIA ENA (all *USDT).
Not downloaded (phase 2): um aggTrades (BTC/ETH window; monthly listing has an oddly named key that broke the planner, and one BTC month is ~3 GB CSV, memory heavy),
Bybit/OKX tick, Tardis day-1 samples, Binance indexPriceKlines, cm futures, option EOHSummary, BitMEX (S3 path 403), Hyperliquid funding only for 6 coins (AVAX/LINK/SUI/HYPE returned nothing).
