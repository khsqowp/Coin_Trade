# Community4 sources and access notes

## Collected source

- Repository: [hasnocool/tradingview-pine-scripts](https://github.com/hasnocool/tradingview-pine-scripts)
- Source form: 80 individual Pine strategy files plus one separately sourced Upbit volatility-breakout article from the cloned repository. Each JSON `source_url` points to the corresponding file page; each selected local file was opened and inspected for its strategy declaration and entry/exit code before recording. The article record documents explicit K=0.5 entry and next-open exit rules.
- Additional article source: [InvestFactCheck Larry Williams volatility breakout](https://www.investfactcheck.com/articles/larry-williams-volatility-breakout/), opened 2026-11-20. It specifies K=0.5, Upbit daily bars, entry trigger, next-open exit, costs, and reported backtest results; results are attributed to the article with fill/slippage caveats.
- Repository license file: GPL-3.0. Individual scripts may retain separate authorship or terms; the repository license is recorded as repository-level context, not a guarantee about every contributor's rights.
- The collection intentionally stores paraphrased rules and source pointers, not copies of the scripts.
- Claimed performance is `null` where the source offered no performance claim suitable for recording. No backtests were run.
- Mechanical completeness is false when entry/exit logic is missing, implicit, stateful, or not fully represented by the extracted condition. The 36 records marked true have an identifiable source rule and exit rule; this status is documentation-level and does not assert causal correctness or backtest readiness.

## Excluded or blocked sources

- Forex Factory: reported blocked in task instructions; no records sourced from it.
- Alpha Architect: reported blocked in task instructions; no records sourced from it.
- Naver blogs: reported blocked in task instructions; no records sourced from them.
- TradingView script detail pages, QuantPedia, Reddit, Korean Tistory/Velog/Brunch blogs, and Medium were not used for this pass. No tag pages or QuantConnect Strategy Library pages were used.
- GitHub code search (`gh search code`) was not used. Repositories were shallow-cloned to `/tmp/c4_work` and treated as untrusted source data; no cloned source was executed.
