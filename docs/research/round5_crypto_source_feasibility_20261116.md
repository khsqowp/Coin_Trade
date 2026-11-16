# Round 5 — crypto historical source feasibility (2026-11-16)

## Verdict

Binance Vision now has enough public-index evidence to justify assembling a **development-only** 20+ symbol USDT-M sample. It does **not** yet qualify a confirmatory OOS or prospective manual-signal test. No strategy outcomes were calculated. A bounded 2021-01 archive sample was downloaded and structurally audited after the initial metadata-only source audit; the exact scope and limitations are recorded below.

## User-fixed outcome contract

The primary criterion is target-first precision ≥80% on at least 200 non-overlapping OOS events per claim. A target counts only if it is touched before stop/invalidation and before the registered deadline. Deadline-close direction accuracy is a separate secondary metric. For the MTF protocol, additional gates remain: at least 10% coverage, at least 20 symbols, clustered Wilson 95% lower bound above registered baselines, and positive net expectancy after costs. Ten-bar and twenty-bar horizons remain separate claims.

The underlying `chart_predictor/SPEC.md` had stale language saying the accuracy definition still awaited user confirmation. Section 5 now records the user's actual target-first definition and execution labels; earlier 75% tests remain historical experiments and are not retroactively reclassified. The 10% coverage and other MTF conditions are expressly additional protocol constraints, not replacements for the user's 80% target-first criterion.

## Archive metadata observations

The checks below read only object metadata or directory names. They did not retrieve candle rows, use API credentials, or make account/trading requests.

### Downloaded development sample (2026-11-16)

- Downloaded the Binance Vision USD-M monthly 1m kline archives for the fixed 2021-01 cohort of 86 symbols found in the metadata inventory. This is historical research data only; no Binance REST/API key, account, order endpoint, or live signal path was used.
- SQLite contains 86 manifest rows and 3,645,000 candle rows. The sum of manifest row counts equals the candle count, every candle maps to a manifest row, and `PRAGMA integrity_check` returned `ok`.
- Monthly nominal capacity is 44,640 minutes per continuously traded instrument. Several contracts have fewer rows because their observed archive starts later in January or has intervals with no rows. Missing minutes were not synthesized. This check does not classify each absence as pre-listing, no-trade, archive omission, or post-delisting; those are unresolved until checked against dated contract status and source files.
- Two names, `DEFIUSDT` and `DOTECOUSDT`, are composite index contracts rather than single-coin underlyings. Excluding those leaves 84 candidate coin-underlying symbols, not a verified complete historical universe. Binance identifies [DEFI](https://www.binance.com/en/support/announcement/detail/ebee6da5df3946519fdb9ab27706d1a4) and [DOTECO](https://www.binance.com/en/support/announcement/detail/9381a09f6dae4899b8c00046a4afc08b) as composite baskets, not individual tokens.
- The sample is development-only and cannot support a sealed OOS claim: its performance history has not been tested, and the fixed cohort itself was chosen from archive-file availability rather than an independently proven historical listing census. No signal labels, strategy returns, hit rates, or parameters were calculated from this download.

| Check | Observed result | What it establishes | What it does not establish |
|---|---|---|---|
| Binance Vision S3 index, prefix `data/futures/um/monthly/klines/` | 1,080 distinct symbol directories over 2 pages as observed 2026-11-16. The prefix includes BTCUSDT, ETHUSDT, and known contracts later delisted in May 2024 (STPTUSDT, SNTUSDT, MBLUSDT, RADUSDT, CVXUSDT). | The archive index includes far more than 20 symbols and retains at least some folders for historically delisted contracts. | All directories are not necessarily USDT crypto underlyings; folders do not prove full lifespan or complete delisting/settlement rows. |
| Monthly 1m klines object HEAD for preselected symbol set | 32/37 checked objects existed for 2021-01; the five later-delisted candidates were absent then. 32/37 existed for 2022-01; 37/37 existed for 2024-05, including those five delisted later in May. | A large, time-specific multi-symbol monthly sample is technically available; at least five later-delisted contracts have a May 2024 1m archive object. | HTTP 200 proves object existence, not that every minute exists, the correct final settlement is present, or the candidate universe is complete/unbiased. |
| Representative market-specific monthly objects | BTCUSDT 1m klines: 2020-01 and 2023-01 returned HTTP 200. BTCUSDT mark-price 1m klines for 2023-01 returned HTTP 200. STPTUSDT 1m klines and mark-price 1m klines for 2024-05 returned HTTP 200. | Kline and mark-price object paths exist for an active and a subsequently delisted symbol. | No row counts, checksums, continuity, price path, fillability, or funding data were validated. |

The current Binance archive downloader documentation describes USDⓈ-M (`um`), multiple symbols, date ranges, 1m klines, aggTrades, mark/index/premium price klines, and optional checksum downloads. Its current documented downloader defaults to available data beginning 2020-01-01. It does not document a complete dated historical contract-universe snapshot. [Official download README](https://github.com/binance/binance-public-data/blob/master/python/README.md)

Binance Vision terms permit purely personal, non-production historical backtesting and expressly govern derived data; they prohibit live proprietary execution, commercial order generation, and compensated third-party signal distribution. This project continues to use Vision only for historical research under the user's prior consent; Vision-derived outputs are not approved as a real-time/manual signal feed. [Current Vision terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md)

Archive completeness needs explicit audits. An upstream report about missing 2026-10-28 USDⓈ-M 1m/5m daily and monthly klines records that a maintainer later said the missing files were added. This demonstrates that checksums alone cannot prove temporal coverage; expected-bar counts and duplicates must be independently validated. The report is upstream repository evidence, not a general Binance completeness guarantee. [Upstream issue #530](https://github.com/binance/binance-public-data/issues/530)

## Other exchange archives

- OKX's official archive lists OHLC candles from July 2023, perpetual funding rates from March 2022, tick trades from September 2021, and L2 order-book data from March 2023. Its historical-data terms allow only personal use, including development of one's own strategy, but say the data should not be relied on for investment/trading decisions; OKX also disclaims completeness and accuracy. The public pages do not establish date-by-date ≥20-instrument USDT-perpetual coverage or delisted-instrument retention. [OKX historical archive](https://www.okx.com/en-us/historical-data), [terms](https://www.okx.com/zh-hans-eu/help/historicaldata-terms-and-conditions)
- Bybit's official materials say public OHLCV, trades, funding, and order-book data may be downloaded as CSV for backtesting. The reviewed official pages did not establish one-minute perpetual coverage over multiple years, dated instrument membership, delisted-product retention, or a data-specific license sufficient for this OOS design. [Bybit market-data guide](https://www.bybit.com/en/learn/bybit-guide/how-to-create-and-set-up-a-bybit-api-key)

Neither source is yet approved as a substitute for a verified OOS panel. A cross-exchange price panel would also not establish Binance execution prices or fills.

## Research candidate review

The four-role review found no new candidate with primary evidence strong enough to promote directly to a strategy test. A quarter-hour-boundary order-flow paper was identified, but its reported predictive horizon concentrates at 4–12 hours, and its event trigger overlaps materially with the already-run L2 pilot. It is not registered as a new candidate for the 10/20-bar target-first mandate. No performance result was inferred from the paper. [Paper](https://arxiv.org/abs/2607.09426)

The agent-proposed spot/perpetual price-discovery and open-interest expansion/collapse candidates were not promoted. Spot/perpetual premium mean reversion overlaps the existing R018 basis/premium family, while OI-history coverage and PIT availability have not been established for the fixed cohort. Renaming the basis reference or describing falling OI as liquidation evidence does not establish a distinct mechanism.

An independent red-team review called attention to stale contract language. Direct inspection of this active checkout confirmed and corrected three state-description conflicts: stale `SPEC.md` accuracy-definition wording, stale MDD status in the strategy-lab README, and stale MDD status in R024. SPEC now separates the fixed primary metric from the stronger MTF-specific coverage, uncertainty, symbol-diversity, and cost gates. No historical run result or threshold was rewritten.

## Next eligible technical step

1. Build an explicit dated contract-status map for the fixed 84-symbol candidate panel, excluding composite indexes and distinguishing pre-listing, active, no-trade, archive gap, and delisting periods. Do not infer instrument type or listing history from a `USDT` suffix.
2. Before any performance metric, validate monthly object checksums, OHLCV schema, expected minute counts, duplicates, timestamp continuity, listing/delisting boundary handling, mark-price alignment, and the 2026-06-25 metrics timestamp-convention anomaly if metrics are used.
3. Register one genuinely distinct, macro-to-micro candidate and its TP/stop/10-bar/20-bar labels, baselines, coverage, non-overlap, cost assumptions, and trial count before running a development screen. Do not reuse the exposed six-symbol winner table as validation.
4. Reserve a truly future cohort for confirmation. The present research scope does not authorize beginning a new live prospective capture; obtain separate authorization and freeze the capture/score contract before that step.

No new API keys, exchange account, purchase, vendor contact, or Oracle action occurred. No historical strategy trial was run in this feasibility audit.
