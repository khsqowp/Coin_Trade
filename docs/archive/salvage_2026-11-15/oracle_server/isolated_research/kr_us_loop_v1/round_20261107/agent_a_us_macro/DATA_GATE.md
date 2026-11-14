# Agent A — data gate and terminal status

Candidate: `A-US-TFF-Emini-LeveragedFunds-Z156-SPY-20261107`  
Frozen preregistration SHA-256: `515e709454c355a34be37266742553c84b1f695b0b13201999610ec60afc3c40`  
Freeze timestamp: `2026-11-07T03:56:50Z`  
Terminal status: **DATA_BLOCKED**  
Performance price values opened: **no**  
Market backtests: **0**

## Official public source and terms

The CFTC historical-compressed page offers annual TFF Futures-Only text ZIPs, with historical TFF coverage dating to June 2006. Its variable dictionary identifies `Report_Date_as_YYYY-MM-DD`, `Open_Interest_All`, `Lev_Money_Positions_Long_All`, and `Lev_Money_Positions_Short_All`. CFTC says reports generally use Tuesday positions and are published Friday at 3:30 p.m. ET; holidays can delay publication. CFTC also states that historical data are not updated after publication. Its Web Policy says government information on the CFTC website is public domain and may be copied with appropriate acknowledgement.

Sources reviewed:

- https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed/index.htm
- https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalViewable/cotvariablestfm.html
- https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm
- https://www.cftc.gov/MarketReports/CommitmentsofTraders/ReleaseSchedule/index.htm
- https://www.cftc.gov/WebPolicy/index.htm

The CFTC ZIP files were fetched directly from `https://www.cftc.gov/files/dea/history/`. Download time: 2026-11-07 03:57 UTC. HTTP HEAD returned 200 for the 2006–2016 archive and 2026 archive; all 11 downloaded ZIPs passed `unzip -tq`. The data are under `raw/cftc/` in this agent-owned directory. No credentials or API keys were used.

| File | Bytes | SHA-256 |
|---|---:|---|
| `fin_fut_txt_2006_2016.zip` | 3,166,765 | `c3a8d01765133a24ce9c082de88933816497d06f1b03eec8c53750bdd818f14b` |
| `fut_fin_txt_2017.zip` | 395,830 | `e6e2dd537efcc57cdd6cdcc4e45e567fd47e65d8afc8369d8383bf09195ae7f5` |
| `fut_fin_txt_2018.zip` | 458,570 | `6843d130a25a17c6248df67463810f02077ef4eeafdd629299d21c18f5125e40` |
| `fut_fin_txt_2019.zip` | 454,803 | `631b31880d513072aa50d63117c896184dd35db3cc8fcdd6debd80197ee7a661` |
| `fut_fin_txt_2020.zip` | 430,721 | `c90d98d94db708772d669f263fb8061c75f8a7f681ba231fb21247e5c9798e6b` |
| `fut_fin_txt_2021.zip` | 466,549 | `5c929991038c70ae2501661b6d442b9e784d3c29d3166ceac2e21b45ac93d56a` |
| `fut_fin_txt_2022.zip` | 494,559 | `94c9c1fdee9dfbe377a09923ddfe26b88d3460605dd076081f221ad367d88601` |
| `fut_fin_txt_2023.zip` | 506,931 | `43c3dbdd4d01fceefad5e457003751cdc0974c7cf46097b322e26e9e2fe44d7a` |
| `fut_fin_txt_2024.zip` | 563,591 | `3f00585741a7cf76c207df640951d644dd91ff22a1106b38ca37a2469c765637` |
| `fut_fin_txt_2025.zip` | 627,068 | `2ea0cda6395f7dd6501c27422be3763e1f2f5b41b768cfd36b871f092a07d438` |
| `fut_fin_txt_2026.zip` | 632,015 | `89deacd0816c7ba75e838cba3d5b228796864077f7315a2d71ca7767a7e928ef` |

## Candidate-data preflight

The frozen exact contract label was `E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE`. A metadata-only CFTC scan, limited to report dates at or before the preregistered cutoff 2026-10-20, found 246 rows for that exact label from 2022-02-08 through 2026-10-20. The required rolling rule needs 156 preceding reports, leaving at most 90 signal observations. That is not enough to populate the preregistered historical evaluation windows or support the registered test design.

The files also contain a prior label, `E-MINI S&P 500 STOCK INDEX - CHICAGO MERCANTILE EXCHANGE`, from 2012-01-10 through 2022-02-01 (494 rows). Its CFTC contract code is also `13874A`. Combining this differently named history could extend the series, but that is a post-freeze identity/mapping change. The frozen candidate explicitly requires one exact name; this attempt cannot silently substitute a code-based alias rule. A stable-code mapping would require a new dated preregistration and a new dependent candidate attempt.

## Official market-data and calendar gate

NYSE documentation confirms its Closing Prices product includes daily Open/High/Low/Last for NYSE Arca securities from 2008-12-05 onward. The official NYSE historical pricing schedule lists TAQ Closing Prices at $500/month and the broader NYSE Arca TAQ historical products as paid. No free official bulk SPY price source with the required open/adjustment provenance was found; no purchase was made. The NYSE official holidays page presently lists 2026–2028 only, not a complete historical session calendar for the needed span.

Sources:

- https://www.nyse.com/publicdocs/nyse/data/TAQ_Closing_Prices_Client_Spec_v2.0.pdf
- https://www.nyse.com/publicdocs/nyse/data/NYSE_Historical_Market_Data_Pricing.pdf
- https://www.nyse.com/trade/hours-calendars

The existing Yahoo-derived SPY mirror and synthetic weekday calendars are explicitly disallowed by the preregistration. FRED's daily S&P 500 close is an index close series, not a tradeable SPY open/adjusted-price history. No alternative was substituted.

## Decision and execution accounting

Terminal status is `DATA_BLOCKED` because (1) the frozen exact-name COT history does not provide the registered 156-report warm-up plus meaningful evaluation span, and (2) the required free official NYSE Arca SPY executable-price history and full historical session calendar are unavailable in the permitted scope. No market-price parquet or price field was opened, no date calendar was inferred from the price mirror, no performance metric was computed, and no backtest code was run.

Verification counts:

- Official CFTC ZIPs downloaded: 11; ZIP integrity checks passed: 11/11.
- CFTC schema/contract/date coverage preflights: 1; required exact-name warm-up gate: failed.
- Unit tests: 0 (no strategy/backtest implementation was created or run).
- Performance backtests: 0.
- Files outside this assigned directory changed: 0.
- `/home/opc/trading/pipeline`, existing research directories, containers, services, secrets, and order/live-trading paths touched: 0.
