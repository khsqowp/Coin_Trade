# Crypto BTC 4h macro / 5m sweep-MSS: development probe

**Status: exploratory development only.** The input interval was previously exposed; this result is not a sealed/OOS evaluation, calibrated M4 result, or trading recommendation.

- Hypothesis trials: 1
- Window: `2026-07-17T00:00:00Z` to exclusive `2026-10-09T00:00:00Z` UTC
- Symbols in frozen cohort: 100; scored source rows: 11,958,105
- BTC-only pre-window warm-up rows: 350
- Fingerprint of used timestamp/OHLC rows: `3be6ccf7e5fae325d8c4187476880fac3ec782e76a24d761eb7c07b1e6fa7780`
- Coverage: 1.7688% (23,823 scored / 1,346,829 eligible anchors)
- Events emitted: 23,834; scored: 23,823; unscorable: 11; symbols with scored events: 100; largest-symbol share: 0.012299038744070855
- Assumed round-trip cost cases: base 0.10%, stress 0.30%. These are scenarios, not measured fills.
- Not modeled: funding, slippage, spread, depth, fill probability, leverage, liquidation.

## Candidate and matched baselines

|Rule|N|Target|Stop|Timeout|Target-first|Wilson 95%|Net-positive base|Mean net R base|Mean net R stress|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|candidate|23823|3188|8593|12042|13.38%|12.96%–13.82%|38.18%|-0.294|-0.910|
|momentum_5m|23823|3188|8593|12042|13.38%|12.96%–13.82%|38.18%|-0.294|-0.910|
|fixed_random|23823|2891|8942|11990|12.14%|11.73%–12.56%|37.85%|-0.323|-0.939|

## Dependence-aware interval

- `target_first`: 0.12353 to 0.14471
- `mean_net_r_base`: -0.35508 to -0.23796
- `mean_net_r_stress`: -1.02143 to -0.80238
- `momentum_target_first`: 0.12353 to 0.14471
- `random_target_first`: 0.11517 to 0.12833
- `paired_delta_precision_vs_momentum`: 0.00000 to 0.00000
- `paired_delta_net_r_vs_momentum`: 0.00000 to 0.00000
- `paired_delta_precision_vs_random`: 0.00503 to 0.02015
- `paired_delta_net_r_vs_random`: -0.01120 to 0.06939

## Per-symbol outcomes

|Symbol|Eligible anchors|Emitted|Scored|Coverage|Target-first|Mean base net R|
|---|---:|---:|---:|---:|---:|---:|
|1000BONKUSDT|13633|243|242|1.7751%|17.77%|0.039|
|1000PEPEUSDT|13633|277|276|2.0245%|17.39%|-0.531|
|1000SHIBUSDT|13633|246|246|1.8044%|12.20%|-0.377|
|AAVEUSDT|13633|258|258|1.8925%|9.69%|-0.321|
|ADAUSDT|13633|226|226|1.6577%|9.29%|-0.241|
|AEROUSDT|13633|252|252|1.8485%|12.70%|-0.243|
|AGTUSDT|13633|235|235|1.7238%|13.62%|-0.411|
|AINUSDT|13633|232|232|1.7018%|8.19%|-0.308|
|AIOTUSDT|13633|232|232|1.7018%|12.50%|-0.248|
|AKEUSDT|13633|254|253|1.8558%|12.25%|-0.176|
|APRUSDT|13633|193|193|1.4157%|10.88%|-0.194|
|APTUSDT|13633|263|263|1.9291%|12.17%|-0.280|
|ARBUSDT|13633|257|257|1.8851%|14.40%|-0.377|
|ARIAUSDT|13633|211|211|1.5477%|13.74%|-0.165|
|ASTERUSDT|13633|230|230|1.6871%|13.04%|-0.438|
|ATOMUSDT|13633|168|168|1.2323%|11.31%|-0.256|
|AVAXUSDT|13633|253|252|1.8485%|11.51%|-0.347|
|BARDUSDT|13633|180|180|1.3203%|8.33%|-0.265|
|BATUSDT|13633|233|233|1.7091%|12.02%|-0.406|
|BCHUSDT|13633|278|278|2.0392%|10.43%|-0.498|
|BEATUSDT|13633|230|230|1.6871%|13.04%|-0.091|
|BIRBUSDT|13633|236|236|1.7311%|14.83%|-0.211|
|BMTUSDT|13633|200|200|1.4670%|16.50%|-0.032|
|BNBUSDT|13633|272|272|1.9952%|17.28%|-1.083|
|BTCUSDT|13633|273|273|2.0025%|15.38%|-0.815|
|BTWUSDT|13633|253|253|1.8558%|15.42%|0.014|
|BULLAUSDT|13633|235|235|1.7238%|14.04%|-0.284|
|CAPUSDT|13633|258|258|1.8925%|10.47%|-0.251|
|CRVUSDT|13633|240|240|1.7604%|13.75%|-0.199|
|CYBERUSDT|13633|216|216|1.5844%|11.57%|-0.233|
|DASHUSDT|13633|242|242|1.7751%|11.57%|-0.278|
|DODOXUSDT|13633|270|270|1.9805%|10.74%|-0.297|
|DOGEUSDT|13633|265|265|1.9438%|12.45%|-0.442|
|DOTUSDT|13633|278|278|2.0392%|14.03%|-0.324|
|ENAUSDT|13633|254|254|1.8631%|14.96%|-0.110|
|ERAUSDT|13633|266|265|1.9438%|14.34%|-0.199|
|ETCUSDT|13633|248|248|1.8191%|14.52%|-0.314|
|ETHFIUSDT|13633|251|251|1.8411%|8.76%|-0.273|
|ETHUSDT|13633|273|273|2.0025%|18.68%|-0.651|
|FARTCOINUSDT|13633|225|225|1.6504%|13.78%|-0.147|
|FETUSDT|13633|196|196|1.4377%|11.22%|-0.244|
|FILUSDT|13633|251|251|1.8411%|17.93%|-0.230|
|GRAMUSDT|13633|151|151|1.1076%|13.25%|-0.160|
|HBARUSDT|13633|260|260|1.9071%|13.08%|-0.405|
|HUMAUSDT|13633|258|258|1.8925%|15.89%|-0.229|
|HUSDT|13633|247|247|1.8118%|10.93%|-0.206|
|HYPEUSDT|13633|293|293|2.1492%|15.70%|-0.314|
|ICPUSDT|13633|221|221|1.6211%|10.86%|-0.176|
|IDOLUSDT|13633|197|197|1.4450%|11.17%|-0.107|
|IMXUSDT|13633|164|164|1.2030%|7.93%|-0.304|
|INITUSDT|13633|269|269|1.9732%|14.50%|-0.155|
|INJUSDT|13633|254|254|1.8631%|12.99%|-0.344|
|JCTUSDT|13633|217|217|1.5917%|14.75%|-0.142|
|JUPUSDT|13633|206|205|1.5037%|11.22%|-0.172|
|KGENUSDT|13633|210|210|1.5404%|16.67%|-0.148|
|LINKUSDT|13633|282|282|2.0685%|17.02%|-0.231|
|LITUSDT|13633|250|250|1.8338%|15.60%|-0.163|
|LTCUSDT|13633|244|244|1.7898%|9.84%|-0.350|
|MAGMAUSDT|13633|245|245|1.7971%|16.33%|-0.024|
|NEARUSDT|13633|229|229|1.6797%|11.79%|-0.186|
|NIGHTUSDT|13633|210|210|1.5404%|13.81%|-0.211|
|ONDOUSDT|13633|258|258|1.8925%|13.57%|-0.122|
|ONEUSDT|13633|249|249|1.8265%|12.45%|-0.150|
|ONUSDT|13633|211|211|1.5477%|10.90%|-0.144|
|OPUSDT|13633|234|234|1.7164%|14.53%|-0.222|
|PAXGUSDT|13633|225|225|1.6504%|16.89%|-1.708|
|PENGUUSDT|13633|276|276|2.0245%|19.93%|0.005|
|PIEVERSEUSDT|13633|239|239|1.7531%|14.23%|-0.173|
|PLAYUSDT|13633|229|229|1.6797%|13.97%|-0.193|
|PLUMEUSDT|13633|203|203|1.4890%|14.78%|-0.134|
|PONSUSDT|4705|73|73|1.5515%|16.44%|-0.079|
|PUMPUSDT|13633|231|231|1.6944%|12.55%|-0.155|
|PYTHUSDT|13633|252|252|1.8485%|12.70%|-0.247|
|QNTUSDT|13633|244|244|1.7898%|11.48%|-0.355|
|QUSDT|13633|232|232|1.7018%|17.67%|-0.141|
|RENDERUSDT|13633|194|193|1.4157%|10.36%|-0.320|
|SOLUSDT|13633|248|248|1.8191%|14.11%|-0.284|
|SOPHUSDT|13633|246|246|1.8044%|15.85%|-0.127|
|STRKUSDT|13633|249|249|1.8265%|10.84%|-0.259|
|STXUSDT|13633|219|219|1.6064%|13.24%|-0.239|
|SUIUSDT|13633|270|270|1.9805%|17.04%|-0.254|
|TAOUSDT|13633|284|284|2.0832%|14.08%|-0.316|
|TIAUSDT|13633|254|254|1.8631%|12.60%|-0.231|
|TRUMPUSDT|13633|207|206|1.5110%|11.17%|-0.232|
|TRXUSDT|13633|223|223|1.6357%|12.11%|-1.194|
|UAIUSDT|13633|215|215|1.5771%|13.49%|-0.157|
|UNIUSDT|13633|245|245|1.7971%|12.24%|-0.253|
|USELESSUSDT|13633|244|243|1.7824%|10.29%|-0.129|
|VIRTUALUSDT|13633|269|268|1.9658%|14.93%|-0.204|
|VVVUSDT|13633|292|292|2.1419%|14.04%|-0.175|
|WLDUSDT|13633|260|260|1.9071%|13.46%|-0.158|
|WLFIUSDT|13633|261|261|1.9145%|9.96%|-0.335|
|XAUTUSDT|13633|220|220|1.6137%|15.91%|-1.450|
|XLMUSDT|13633|268|267|1.9585%|11.61%|-0.265|
|XMRUSDT|13633|260|260|1.9071%|11.54%|-0.466|
|XPLUSDT|13633|277|277|2.0318%|10.83%|-0.295|
|XRPUSDT|13633|260|260|1.9071%|14.62%|-0.440|
|ZECUSDT|13633|253|253|1.8558%|13.44%|-0.456|
|ZROUSDT|13633|284|284|2.0832%|14.79%|-0.095|
|牛来USDT|6090|116|116|1.9048%|16.38%|0.031|

## Interpretation

This single fixed rule is rejected as a development candidate: target-first is 13.38% (Wilson 95%: 12.96%–13.82%) and mean net return is -0.294R under the 0.10% round-trip fee-only assumption. The fixed-random target-first rate is 12.14%; the 7-day paired block interval for its precision difference is +0.50 to +2.01 percentage points, while the paired net-R interval (-0.011 to +0.069) includes zero. This small descriptive difference does not offset the candidate's low absolute target-first rate, 1.77% coverage, negative net expectancy, or development-only data boundary. The 5m momentum comparator exactly duplicates the candidate on every scored event and is structurally guaranteed to do so: long MSS requires the confirmation close to exceed the previous four-bar high, including the prior bar's high, and therefore exceed the prior close; short MSS symmetrically requires a lower close. This comparator cannot test whether the sweep/regime event timing adds value. Treat the identity as a design limitation, not independent confirmation.

A favorable development result would only permit consideration of prospective collection; it would not pass the user's goal. The final target still requires calibrated M4, at least 80% point precision, at least 10% coverage, N≥200 across at least 20 symbols, a dependence-aware lower bound above useful baselines, and positive expectancy after realistic costs. This run has no independent holdout and omits funding, slippage, spread, depth, fill probability, leverage, and liquidation. It is a rejection screen, not evidence that all possible strategies fail.

Raw per-event outcomes and baseline scores are in the adjacent JSON artifact. No rule or parameter change is allowed on this interval after inspecting results.
