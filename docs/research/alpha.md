# 암호화폐 무기한 선물 횡단면 신호 연구

## setup

자료: 로컬 Binance vision CSV; 2021-06-01~2026-10-09; 45개. IS=2022-01-01~2024-06-30, OOS=2024-07-01~자료 끝. UTC 일봉, 24개 시간봉이 없는 날짜 제외. 60일 연속 유효 종가를 확보한 종목만 적격.

고정 격자 5904개, 이웃 40개, 앙상블 9개: 총 5953회 평가. 최고 단일 구성은 IS Calmar와 IS MDD≤25%로 선택. OOS는 선택에 사용하지 않는다. 격자: K=4/6/8/10, R=1/3/5/7, 유동성 제외=0/20/33%, 가중=동일/30일 역변동성/순위 강도. 표의 신호별 최고값은 다중검정 결과이며 유의성 검정을 통과한 알파라는 뜻이 아니다.

누락 및 펀딩 자료: `{"missing": [], "load_failures": {}, "coverage": {"BTC": {"days": 1957, "funding_days": 1948}, "ETH": {"days": 1957, "funding_days": 1948}, "BNB": {"days": 1957, "funding_days": 1948}, "XRP": {"days": 1952, "funding_days": 1943}, "SOL": {"days": 1952, "funding_days": 1943}, "TRX": {"days": 1952, "funding_days": 1943}, "DOGE": {"days": 1957, "funding_days": 1948}, "ZEC": {"days": 1952, "funding_days": 1943}, "LINK": {"days": 1957, "funding_days": 1948}, "XMR": {"days": 1957, "funding_days": 1948}, "ADA": {"days": 1957, "funding_days": 1948}, "XLM": {"days": 1952, "funding_days": 1943}, "BCH": {"days": 1957, "funding_days": 1948}, "LTC": {"days": 1952, "funding_days": 1943}, "HBAR": {"days": 1952, "funding_days": 1943}, "AVAX": {"days": 1957, "funding_days": 1948}, "SUI": {"days": 1255, "funding_days": 1246}, "UNI": {"days": 1957, "funding_days": 1948}, "NEAR": {"days": 1952, "funding_days": 1943}, "TAO": {"days": 911, "funding_days": 902}, "AAVE": {"days": 1957, "funding_days": 1948}, "ONDO": {"days": 993, "funding_days": 984}, "THETA": {"days": 1957, "funding_days": 1948}, "DOT": {"days": 1957, "funding_days": 1948}, "ENA": {"days": 920, "funding_days": 911}, "WLD": {"days": 1173, "funding_days": 1164}, "ICP": {"days": 1930, "funding_days": 1464}, "ETC": {"days": 1957, "funding_days": 1948}, "POL": {"days": 756, "funding_days": 747}, "QNT": {"days": 1450, "funding_days": 1441}, "ALGO": {"days": 1957, "funding_days": 1948}, "ATOM": {"days": 1957, "funding_days": 1948}, "RENDER": {"days": 805, "funding_days": 796}, "JUP": {"days": 982, "funding_days": 973}, "ARB": {"days": 1296, "funding_days": 1287}, "FIL": {"days": 1952, "funding_days": 1943}, "VET": {"days": 1952, "funding_days": 1943}, "CAKE": {"days": 1072, "funding_days": 1063}, "LDO": {"days": 1478, "funding_days": 1469}, "CRV": {"days": 1957, "funding_days": 1948}, "INJ": {"days": 1514, "funding_days": 1505}, "OP": {"days": 1591, "funding_days": 1582}, "APT": {"days": 1451, "funding_days": 1442}, "IMX": {"days": 1696, "funding_days": 1687}, "STX": {"days": 1326, "funding_days": 1317}}, "cache": "/tmp/.rs_alpha_cache"}`

## baseline reproduction

|신호/구성|구간|Calmar|CAGR %|MDD %|Sharpe|회전/년|비용 %/년|
|---|---|---:|---:|---:|---:|---:|---:|
|{"k": 8, "liquidity": 0.0, "r": 3, "signal": "ret_14", "weighting": "equal"}|IS|0.81|13.66|16.83|0.69|83.0|8.30|
|{"k": 8, "liquidity": 0.0, "r": 3, "signal": "ret_14", "weighting": "equal"}|OOS|1.20|25.59|21.36|1.03|90.3|9.03|
|{"k": 8, "liquidity": 0.0, "r": 3, "signal": "ret_14", "weighting": "equal"}|full|0.90|19.20|21.36|0.86|86.5|8.65|

0.04% 비용 비교: `{"IS": {"CAGR": 0.19466808628824017, "MDD": 0.16255288324683292, "Calmar": 1.1975677231922182, "Sharpe": 0.9179604923758004, "worst_day": -0.061029440731136364, "turnover": 82.9954769736842, "fee_drag": 0.03319819078947368, "funding_drag": 0.006730461657529242, "missing_return_exposure": 0.375, "funding_coverage": 0.9851745248538013, "days": 912, "yearly": {"2022": -0.059583504758365935, "2023": 0.37368096075907564, "2024": 0.20727503636398725}}, "OOS": {"CAGR": 0.3258607640806732, "MDD": 0.1940782545015497, "Calmar": 1.6790173887207505, "Sharpe": 1.2511671050146451, "worst_day": -0.08622482059474879, "turnover": 90.31663658243082, "fee_drag": 0.03612665463297233, "funding_drag": 0.002921650131618532, "missing_return_exposure": 0.0, "funding_coverage": 0.9891696750902527, "days": 831, "yearly": {"2024": 0.3158510980371565, "2025": 0.41416604137304813, "2026": 0.02137534584580636}}, "full": {"CAGR": 0.2555128307571881, "MDD": 0.1940782545015498, "Calmar": 1.3165453873924229, "Sharpe": 1.0855707444468254, "worst_day": -0.08622482059474879, "turnover": 86.48594377510041, "fee_drag": 0.034594377510040165, "funding_drag": 0.004914556678738764, "missing_return_exposure": 0.375, "funding_coverage": 0.9870792694587875, "days": 1743, "yearly": {"2022": -0.059583504758365935, "2023": 0.37368096075907564, "2024": 0.5885941822323995, "2025": 0.41416604137304813, "2026": 0.02137534584580636}}}`

사용자 제시 기대값은 CAGR +28.9%, MDD 18.6%, Sharpe 1.2다. 다음 차이 때문에 강제 일치시키지 않는다: 45종목 루프 유니버스와 probe 유니버스 차이, 로컬 일봉과 기존 수집기 자료 차이, 60일 적격 조건, 달력 기준 리밸런스 시작 위상, 펀딩 포함, 비용을 포함한 일별 낙폭 산출. probe는 비용을 일별 daily_returns에 기록하지 않아 Sharpe/낙폭과 최종 equity의 비용 처리가 일치하지 않는다.

## single-signal table

|신호/구성|구간|Calmar|CAGR %|MDD %|Sharpe|회전/년|비용 %/년|
|---|---|---:|---:|---:|---:|---:|---:|
|{"k": 4, "liquidity": 0.2, "r": 5, "signal": "resid_14", "weighting": "score"}|IS|2.81|48.00|17.09|1.47|73.1|7.31|
|{"k": 4, "liquidity": 0.2, "r": 5, "signal": "resid_14", "weighting": "score"}|OOS|0.30|11.37|38.51|0.48|78.8|7.88|
|{"k": 4, "liquidity": 0.2, "r": 5, "signal": "resid_14", "weighting": "score"}|full|0.76|29.23|38.51|0.96|75.8|7.58|
|{"k": 8, "liquidity": 0.2, "r": 7, "signal": "resid_21", "weighting": "equal"}|IS|2.47|27.25|11.04|1.29|41.1|4.11|
|{"k": 8, "liquidity": 0.2, "r": 7, "signal": "resid_21", "weighting": "equal"}|OOS|-0.32|-14.68|46.50|-0.59|46.9|4.69|
|{"k": 8, "liquidity": 0.2, "r": 7, "signal": "resid_21", "weighting": "equal"}|full|0.11|5.17|46.50|0.34|43.9|4.39|
|{"k": 4, "liquidity": 0.2, "r": 3, "signal": "revmom_3", "weighting": "equal"}|IS|2.24|36.91|16.50|1.33|183.1|18.31|
|{"k": 4, "liquidity": 0.2, "r": 3, "signal": "revmom_3", "weighting": "equal"}|OOS|-0.32|-13.09|41.10|-0.41|194.1|19.41|
|{"k": 4, "liquidity": 0.2, "r": 3, "signal": "revmom_3", "weighting": "equal"}|full|0.25|10.24|41.10|0.50|188.4|18.84|
|{"k": 4, "liquidity": 0.2, "r": 3, "signal": "ret_14", "weighting": "inverse_vol"}|IS|2.05|37.90|18.48|1.23|105.9|10.59|
|{"k": 4, "liquidity": 0.2, "r": 3, "signal": "ret_14", "weighting": "inverse_vol"}|OOS|0.82|27.91|34.22|0.87|112.2|11.22|
|{"k": 4, "liquidity": 0.2, "r": 3, "signal": "ret_14", "weighting": "inverse_vol"}|full|0.97|33.05|34.22|1.04|108.9|10.89|
|{"k": 4, "liquidity": 0.0, "r": 7, "signal": "revmom_2", "weighting": "score"}|IS|2.02|35.28|17.50|1.29|86.9|8.69|
|{"k": 4, "liquidity": 0.0, "r": 7, "signal": "revmom_2", "weighting": "score"}|OOS|-0.45|-29.38|64.65|-1.16|89.0|8.90|
|{"k": 4, "liquidity": 0.0, "r": 7, "signal": "revmom_2", "weighting": "score"}|full|-0.01|-0.77|67.61|0.10|87.9|8.79|
|{"k": 8, "liquidity": 0.0, "r": 5, "signal": "ret_21", "weighting": "inverse_vol"}|IS|1.84|28.34|15.41|1.31|57.4|5.74|
|{"k": 8, "liquidity": 0.0, "r": 5, "signal": "ret_21", "weighting": "inverse_vol"}|OOS|-0.26|-12.41|46.93|-0.40|65.9|6.59|
|{"k": 8, "liquidity": 0.0, "r": 5, "signal": "ret_21", "weighting": "inverse_vol"}|full|0.15|6.97|46.93|0.41|61.4|6.14|
|{"k": 6, "liquidity": 0.0, "r": 7, "signal": "skip_14", "weighting": "inverse_vol"}|IS|1.78|29.57|16.58|1.21|63.2|6.32|
|{"k": 6, "liquidity": 0.0, "r": 7, "signal": "skip_14", "weighting": "inverse_vol"}|OOS|-0.03|-0.71|26.89|0.12|69.1|6.91|
|{"k": 6, "liquidity": 0.0, "r": 7, "signal": "skip_14", "weighting": "inverse_vol"}|full|0.53|14.13|26.89|0.63|66.0|6.60|
|{"k": 4, "liquidity": 0.0, "r": 5, "signal": "skip_21", "weighting": "inverse_vol"}|IS|1.78|35.13|19.73|1.11|72.2|7.22|
|{"k": 4, "liquidity": 0.0, "r": 5, "signal": "skip_21", "weighting": "inverse_vol"}|OOS|-0.20|-10.92|53.71|-0.15|75.8|7.58|
|{"k": 4, "liquidity": 0.0, "r": 5, "signal": "skip_21", "weighting": "inverse_vol"}|full|0.20|10.78|53.71|0.47|73.9|7.39|
|{"k": 6, "liquidity": 0.0, "r": 5, "signal": "volmom_21", "weighting": "inverse_vol"}|IS|1.53|19.21|12.58|0.96|66.7|6.67|
|{"k": 6, "liquidity": 0.0, "r": 5, "signal": "volmom_21", "weighting": "inverse_vol"}|OOS|-0.07|-2.91|42.36|0.02|73.0|7.30|
|{"k": 6, "liquidity": 0.0, "r": 5, "signal": "volmom_21", "weighting": "inverse_vol"}|full|0.19|8.10|42.36|0.45|69.7|6.97|
|{"k": 10, "liquidity": 0.2, "r": 3, "signal": "volmom_14", "weighting": "equal"}|IS|1.50|18.03|12.03|1.06|73.1|7.31|
|{"k": 10, "liquidity": 0.2, "r": 3, "signal": "volmom_14", "weighting": "equal"}|OOS|1.84|26.12|14.18|1.34|80.8|8.08|
|{"k": 10, "liquidity": 0.2, "r": 3, "signal": "volmom_14", "weighting": "equal"}|full|1.38|21.82|15.78|1.20|76.8|7.68|
|{"k": 4, "liquidity": 0.2, "r": 7, "signal": "sma_30", "weighting": "inverse_vol"}|IS|1.43|33.24|23.29|1.08|56.6|5.66|
|{"k": 4, "liquidity": 0.2, "r": 7, "signal": "sma_30", "weighting": "inverse_vol"}|OOS|-0.09|-4.44|52.15|0.05|60.3|6.03|
|{"k": 4, "liquidity": 0.2, "r": 7, "signal": "sma_30", "weighting": "inverse_vol"}|full|0.26|13.71|52.15|0.55|58.4|5.84|
|{"k": 10, "liquidity": 0.0, "r": 7, "signal": "carry_neg_30", "weighting": "inverse_vol"}|IS|1.41|19.96|14.12|1.35|20.4|2.04|
|{"k": 10, "liquidity": 0.0, "r": 7, "signal": "carry_neg_30", "weighting": "inverse_vol"}|OOS|0.73|14.73|20.23|0.96|22.3|2.23|
|{"k": 10, "liquidity": 0.0, "r": 7, "signal": "carry_neg_30", "weighting": "inverse_vol"}|full|0.86|17.44|20.23|1.15|21.3|2.13|
|{"k": 4, "liquidity": 0.2, "r": 7, "signal": "sma_21", "weighting": "inverse_vol"}|IS|1.33|30.40|22.93|1.04|66.6|6.66|
|{"k": 4, "liquidity": 0.2, "r": 7, "signal": "sma_21", "weighting": "inverse_vol"}|OOS|0.18|6.27|35.19|0.35|70.2|7.02|
|{"k": 4, "liquidity": 0.2, "r": 7, "signal": "sma_21", "weighting": "inverse_vol"}|full|0.52|18.28|35.19|0.69|68.3|6.83|
|{"k": 4, "liquidity": 0.0, "r": 5, "signal": "volmom_60", "weighting": "equal"}|IS|1.24|25.81|20.76|0.96|44.0|4.40|
|{"k": 4, "liquidity": 0.0, "r": 5, "signal": "volmom_60", "weighting": "equal"}|OOS|-0.06|-3.43|59.69|0.07|45.4|4.54|
|{"k": 4, "liquidity": 0.0, "r": 5, "signal": "volmom_60", "weighting": "equal"}|full|0.18|10.91|59.69|0.49|44.7|4.47|
|{"k": 10, "liquidity": 0.33, "r": 5, "signal": "taker", "weighting": "inverse_vol"}|IS|1.20|13.69|11.42|0.93|48.7|4.87|
|{"k": 10, "liquidity": 0.33, "r": 5, "signal": "taker", "weighting": "inverse_vol"}|OOS|-0.01|-0.16|20.62|0.07|58.7|5.87|
|{"k": 10, "liquidity": 0.33, "r": 5, "signal": "taker", "weighting": "inverse_vol"}|full|0.28|6.86|24.37|0.51|53.5|5.35|
|{"k": 10, "liquidity": 0.0, "r": 5, "signal": "ret_30", "weighting": "inverse_vol"}|IS|1.17|16.19|13.86|0.92|44.9|4.49|
|{"k": 10, "liquidity": 0.0, "r": 5, "signal": "ret_30", "weighting": "inverse_vol"}|OOS|0.08|1.98|23.42|0.20|51.9|5.19|
|{"k": 10, "liquidity": 0.0, "r": 5, "signal": "ret_30", "weighting": "inverse_vol"}|full|0.39|9.18|23.42|0.53|48.2|4.82|
|{"k": 10, "liquidity": 0.0, "r": 5, "signal": "skip_30", "weighting": "equal"}|IS|1.16|14.62|12.56|0.82|39.6|3.96|
|{"k": 10, "liquidity": 0.0, "r": 5, "signal": "skip_30", "weighting": "equal"}|OOS|-0.14|-4.24|31.38|-0.08|44.9|4.49|
|{"k": 10, "liquidity": 0.0, "r": 5, "signal": "skip_30", "weighting": "equal"}|full|0.17|5.21|31.38|0.35|42.1|4.21|
|{"k": 8, "liquidity": 0.2, "r": 7, "signal": "resid_30", "weighting": "equal"}|IS|0.96|13.76|14.28|0.74|33.6|3.36|
|{"k": 8, "liquidity": 0.2, "r": 7, "signal": "resid_30", "weighting": "equal"}|OOS|-0.14|-5.23|36.53|-0.12|38.0|3.80|
|{"k": 8, "liquidity": 0.2, "r": 7, "signal": "resid_30", "weighting": "equal"}|full|0.12|4.27|36.53|0.30|35.7|3.57|
|{"k": 6, "liquidity": 0.2, "r": 7, "signal": "sma_14", "weighting": "inverse_vol"}|IS|0.90|18.50|20.59|0.80|69.5|6.95|
|{"k": 6, "liquidity": 0.2, "r": 7, "signal": "sma_14", "weighting": "inverse_vol"}|OOS|-0.12|-3.48|29.08|0.01|75.7|7.57|
|{"k": 6, "liquidity": 0.2, "r": 7, "signal": "sma_14", "weighting": "inverse_vol"}|full|0.25|7.45|30.40|0.40|72.5|7.25|
|{"k": 4, "liquidity": 0.0, "r": 3, "signal": "volume", "weighting": "equal"}|IS|0.84|19.43|23.03|0.76|90.4|9.04|
|{"k": 4, "liquidity": 0.0, "r": 3, "signal": "volume", "weighting": "equal"}|OOS|1.58|62.51|39.51|1.63|96.6|9.66|
|{"k": 4, "liquidity": 0.0, "r": 3, "signal": "volume", "weighting": "equal"}|full|0.97|38.32|39.51|1.21|93.4|9.34|
|{"k": 6, "liquidity": 0.0, "r": 5, "signal": "volmom_30", "weighting": "score"}|IS|0.73|14.59|19.97|0.70|53.2|5.32|
|{"k": 6, "liquidity": 0.0, "r": 5, "signal": "volmom_30", "weighting": "score"}|OOS|0.01|0.32|36.69|0.15|57.3|5.73|
|{"k": 6, "liquidity": 0.0, "r": 5, "signal": "volmom_30", "weighting": "score"}|full|0.21|7.55|36.69|0.41|55.1|5.51|
|{"k": 10, "liquidity": 0.0, "r": 5, "signal": "ret_60", "weighting": "inverse_vol"}|IS|0.69|13.38|19.46|0.77|35.7|3.57|
|{"k": 10, "liquidity": 0.0, "r": 5, "signal": "ret_60", "weighting": "inverse_vol"}|OOS|-0.04|-1.26|28.11|0.07|38.4|3.84|
|{"k": 10, "liquidity": 0.0, "r": 5, "signal": "ret_60", "weighting": "inverse_vol"}|full|0.22|6.15|28.11|0.39|37.0|3.70|
|{"k": 8, "liquidity": 0.0, "r": 5, "signal": "sma_60", "weighting": "inverse_vol"}|IS|0.67|15.43|23.01|0.79|41.1|4.11|
|{"k": 8, "liquidity": 0.0, "r": 5, "signal": "sma_60", "weighting": "inverse_vol"}|OOS|-0.01|-0.26|29.93|0.13|47.2|4.72|
|{"k": 8, "liquidity": 0.0, "r": 5, "signal": "sma_60", "weighting": "inverse_vol"}|full|0.26|7.66|29.93|0.43|44.0|4.40|
|{"k": 8, "liquidity": 0.2, "r": 5, "signal": "skip_60", "weighting": "inverse_vol"}|IS|0.67|12.88|19.30|0.70|38.4|3.84|
|{"k": 8, "liquidity": 0.2, "r": 5, "signal": "skip_60", "weighting": "inverse_vol"}|OOS|-0.01|-0.21|20.62|0.12|41.6|4.16|
|{"k": 8, "liquidity": 0.2, "r": 5, "signal": "skip_60", "weighting": "inverse_vol"}|full|0.31|6.44|20.62|0.39|39.9|3.99|
|{"k": 4, "liquidity": 0.0, "r": 7, "signal": "carry_neg_7", "weighting": "score"}|IS|0.66|16.11|24.42|0.75|52.1|5.21|
|{"k": 4, "liquidity": 0.0, "r": 7, "signal": "carry_neg_7", "weighting": "score"}|OOS|1.32|30.18|22.84|1.23|57.1|5.71|
|{"k": 4, "liquidity": 0.0, "r": 7, "signal": "carry_neg_7", "weighting": "score"}|full|0.88|22.61|25.80|0.98|54.5|5.45|
|{"k": 6, "liquidity": 0.33, "r": 3, "signal": "rankblend", "weighting": "inverse_vol"}|IS|0.65|12.31|18.81|0.62|82.3|8.23|
|{"k": 6, "liquidity": 0.33, "r": 3, "signal": "rankblend", "weighting": "inverse_vol"}|OOS|-0.14|-3.57|25.65|-0.01|96.0|9.60|
|{"k": 6, "liquidity": 0.33, "r": 3, "signal": "rankblend", "weighting": "inverse_vol"}|full|0.16|4.43|28.47|0.30|88.8|8.88|
|{"k": 10, "liquidity": 0.2, "r": 7, "signal": "breakout", "weighting": "inverse_vol"}|IS|0.50|10.09|20.01|0.63|31.9|3.19|
|{"k": 10, "liquidity": 0.2, "r": 7, "signal": "breakout", "weighting": "inverse_vol"}|OOS|-0.24|-6.33|26.89|-0.17|33.0|3.30|
|{"k": 10, "liquidity": 0.2, "r": 7, "signal": "breakout", "weighting": "inverse_vol"}|full|0.07|1.93|26.89|0.20|32.4|3.24|
|{"k": 4, "liquidity": 0.33, "r": 7, "signal": "reversal_2", "weighting": "equal"}|IS|0.50|11.91|23.93|0.54|85.4|8.54|
|{"k": 4, "liquidity": 0.33, "r": 7, "signal": "reversal_2", "weighting": "equal"}|OOS|-0.50|-34.09|68.49|-1.09|86.7|8.67|
|{"k": 4, "liquidity": 0.33, "r": 7, "signal": "reversal_2", "weighting": "equal"}|full|-0.19|-13.05|68.49|-0.30|86.1|8.61|
|{"k": 4, "liquidity": 0.2, "r": 5, "signal": "revmom_1", "weighting": "equal"}|IS|0.49|10.71|21.84|0.52|108.2|10.82|
|{"k": 4, "liquidity": 0.2, "r": 5, "signal": "revmom_1", "weighting": "equal"}|OOS|-0.18|-7.14|40.08|-0.10|116.5|11.65|
|{"k": 4, "liquidity": 0.2, "r": 5, "signal": "revmom_1", "weighting": "equal"}|full|0.05|1.81|40.08|0.20|112.1|11.21|
|{"k": 6, "liquidity": 0.33, "r": 7, "signal": "reversal_3", "weighting": "equal"}|IS|0.31|7.40|23.62|0.43|76.3|7.63|
|{"k": 6, "liquidity": 0.33, "r": 7, "signal": "reversal_3", "weighting": "equal"}|OOS|-0.19|-8.94|48.15|-0.24|78.7|7.87|
|{"k": 6, "liquidity": 0.33, "r": 7, "signal": "reversal_3", "weighting": "equal"}|full|-0.02|-0.72|48.15|0.09|77.4|7.74|
|{"k": 10, "liquidity": 0.33, "r": 3, "signal": "idiovol", "weighting": "inverse_vol"}|IS|0.29|9.20|31.75|0.56|30.1|3.01|
|{"k": 10, "liquidity": 0.33, "r": 3, "signal": "idiovol", "weighting": "inverse_vol"}|OOS|-0.14|-4.18|29.23|-0.08|29.2|2.92|
|{"k": 10, "liquidity": 0.33, "r": 3, "signal": "idiovol", "weighting": "inverse_vol"}|full|0.07|2.60|39.15|0.23|29.7|2.97|
|{"k": 6, "liquidity": 0.0, "r": 5, "signal": "resid_60", "weighting": "score"}|IS|0.27|7.15|26.45|0.41|37.5|3.75|
|{"k": 6, "liquidity": 0.0, "r": 5, "signal": "resid_60", "weighting": "score"}|OOS|-0.13|-6.13|46.44|-0.07|39.3|3.93|
|{"k": 6, "liquidity": 0.0, "r": 5, "signal": "resid_60", "weighting": "score"}|full|0.01|0.60|46.44|0.15|38.4|3.84|
|{"k": 6, "liquidity": 0.2, "r": 7, "signal": "reversal_1", "weighting": "equal"}|IS|0.23|4.98|21.35|0.33|78.0|7.80|
|{"k": 6, "liquidity": 0.2, "r": 7, "signal": "reversal_1", "weighting": "equal"}|OOS|-0.54|-32.47|59.91|-1.38|84.5|8.45|
|{"k": 6, "liquidity": 0.2, "r": 7, "signal": "reversal_1", "weighting": "equal"}|full|-0.24|-14.94|61.98|-0.55|81.1|8.11|
|{"k": 8, "liquidity": 0.0, "r": 3, "signal": "volmom_7", "weighting": "inverse_vol"}|IS|0.16|3.68|23.49|0.29|129.1|12.91|
|{"k": 8, "liquidity": 0.0, "r": 3, "signal": "volmom_7", "weighting": "inverse_vol"}|OOS|0.36|7.14|20.03|0.42|141.9|14.19|
|{"k": 8, "liquidity": 0.0, "r": 3, "signal": "volmom_7", "weighting": "inverse_vol"}|full|0.23|5.32|23.49|0.36|135.2|13.52|
|{"k": 10, "liquidity": 0.2, "r": 7, "signal": "resid_7", "weighting": "inverse_vol"}|IS|0.06|1.23|21.72|0.16|71.6|7.16|
|{"k": 10, "liquidity": 0.2, "r": 7, "signal": "resid_7", "weighting": "inverse_vol"}|OOS|-0.33|-9.54|28.95|-0.40|77.2|7.72|
|{"k": 10, "liquidity": 0.2, "r": 7, "signal": "resid_7", "weighting": "inverse_vol"}|full|-0.13|-4.06|32.28|-0.14|74.2|7.42|
|{"k": 10, "liquidity": 0.0, "r": 3, "signal": "ret_7", "weighting": "inverse_vol"}|IS|-0.04|-0.90|21.43|0.04|117.1|11.71|
|{"k": 10, "liquidity": 0.0, "r": 3, "signal": "ret_7", "weighting": "inverse_vol"}|OOS|0.14|3.37|24.65|0.26|129.4|12.94|
|{"k": 10, "liquidity": 0.0, "r": 3, "signal": "ret_7", "weighting": "inverse_vol"}|full|0.04|1.11|31.17|0.16|122.9|12.29|
|{"k": 10, "liquidity": 0.33, "r": 7, "signal": "skip_7", "weighting": "inverse_vol"}|IS|-0.06|-1.18|21.07|0.01|64.8|6.48|
|{"k": 10, "liquidity": 0.33, "r": 7, "signal": "skip_7", "weighting": "inverse_vol"}|OOS|-0.42|-17.44|41.35|-0.89|73.8|7.38|
|{"k": 10, "liquidity": 0.33, "r": 7, "signal": "skip_7", "weighting": "inverse_vol"}|full|-0.20|-9.30|45.98|-0.46|69.1|6.91|
|{"k": 4, "liquidity": 0.33, "r": 7, "signal": "lowvol", "weighting": "score"}|IS|-0.10|-4.51|43.72|0.02|26.1|2.61|
|{"k": 4, "liquidity": 0.33, "r": 7, "signal": "lowvol", "weighting": "score"}|OOS|-0.33|-15.76|47.65|-0.30|22.0|2.20|
|{"k": 4, "liquidity": 0.33, "r": 7, "signal": "lowvol", "weighting": "score"}|full|-0.16|-10.05|61.55|-0.14|24.1|2.41|
|{"k": 10, "liquidity": 0.33, "r": 5, "signal": "carry_pos_7", "weighting": "equal"}|IS|-0.13|-3.02|23.01|-0.12|36.1|3.61|
|{"k": 10, "liquidity": 0.33, "r": 5, "signal": "carry_pos_7", "weighting": "equal"}|OOS|-0.54|-34.63|64.24|-2.71|51.0|5.10|
|{"k": 10, "liquidity": 0.33, "r": 5, "signal": "carry_pos_7", "weighting": "equal"}|full|-0.29|-19.65|68.83|-1.35|43.2|4.32|
|{"k": 6, "liquidity": 0.0, "r": 5, "signal": "sma_7", "weighting": "inverse_vol"}|IS|-0.15|-3.45|22.66|-0.04|115.3|11.53|
|{"k": 6, "liquidity": 0.0, "r": 5, "signal": "sma_7", "weighting": "inverse_vol"}|OOS|-0.20|-9.19|45.07|-0.20|121.6|12.16|
|{"k": 6, "liquidity": 0.0, "r": 5, "signal": "sma_7", "weighting": "inverse_vol"}|full|-0.14|-6.23|45.07|-0.13|118.3|11.83|
|{"k": 10, "liquidity": 0.33, "r": 5, "signal": "carry_pos_30", "weighting": "inverse_vol"}|IS|-0.28|-6.42|22.82|-0.41|22.7|2.27|
|{"k": 10, "liquidity": 0.33, "r": 5, "signal": "carry_pos_30", "weighting": "inverse_vol"}|OOS|-0.42|-18.69|44.99|-1.46|25.5|2.55|
|{"k": 10, "liquidity": 0.33, "r": 5, "signal": "carry_pos_30", "weighting": "inverse_vol"}|full|-0.22|-12.48|56.94|-0.90|24.0|2.40|

모든 격자의 세부 결과·연도별 수익률·최악 일간 수익률은 JSON all_grid에 포함한다. 신호별 IS MDD 제한을 통과한 구성이 없으면 해당 신호의 제한 없는 최고 IS Calmar를 표에 포함하되 추천 후보에서 제외한다.

## correlation

IS만 이용해 절대 상관≤0.7인 서로 다른 신호 슬리브를 순차 선택한다. 전체/OOS 행렬은 보고용이다.

### 전체

|슬리브|resid_14|resid_21|revmom_3|revmom_2|
|---|---:|---:|---:|---:|
|resid_14|1.000|0.701|0.435|0.363|
|resid_21|0.701|1.000|0.414|0.426|
|revmom_3|0.435|0.414|1.000|0.412|
|revmom_2|0.363|0.426|0.412|1.000|

### OOS

|슬리브|resid_14|resid_21|revmom_3|revmom_2|
|---|---:|---:|---:|---:|
|resid_14|1.000|0.705|0.386|0.282|
|resid_21|0.705|1.000|0.365|0.365|
|revmom_3|0.386|0.365|1.000|0.400|
|revmom_2|0.282|0.365|0.400|1.000|

## ensembles

|신호/구성|구간|Calmar|CAGR %|MDD %|Sharpe|회전/년|비용 %/년|
|---|---|---:|---:|---:|---:|---:|---:|
|{"components": ["resid_14", "resid_21"], "k": 8, "liquidity": 0.0, "r": 3, "signal": "score_blend_2", "weighting": "equal"}|IS|0.69|10.61|15.28|0.59|70.6|7.06|
|{"components": ["resid_14", "resid_21"], "k": 8, "liquidity": 0.0, "r": 3, "signal": "score_blend_2", "weighting": "equal"}|OOS|1.10|28.70|25.99|1.15|77.0|7.70|
|{"components": ["resid_14", "resid_21"], "k": 8, "liquidity": 0.0, "r": 3, "signal": "score_blend_2", "weighting": "equal"}|full|0.73|18.89|25.99|0.88|73.7|7.37|
|{"allocation": "equal", "components": ["resid_14", "resid_21"], "gross": "<=1 due to netting", "signal": "sleeve_equal_2"}|IS|2.80|38.13|13.64|1.52|56.2|5.62|
|{"allocation": "equal", "components": ["resid_14", "resid_21"], "gross": "<=1 due to netting", "signal": "sleeve_equal_2"}|OOS|-0.04|-1.73|39.11|0.07|62.3|6.23|
|{"allocation": "equal", "components": ["resid_14", "resid_21"], "gross": "<=1 due to netting", "signal": "sleeve_equal_2"}|full|0.45|17.43|39.11|0.77|59.1|5.91|
|{"allocation": "inverse_vol_60", "components": ["resid_14", "resid_21"], "gross": "<=1 due to netting", "signal": "sleeve_inverse_vol_60_2"}|IS|2.77|35.63|12.88|1.49|54.4|5.44|
|{"allocation": "inverse_vol_60", "components": ["resid_14", "resid_21"], "gross": "<=1 due to netting", "signal": "sleeve_inverse_vol_60_2"}|OOS|-0.11|-4.47|39.54|-0.05|60.3|6.03|
|{"allocation": "inverse_vol_60", "components": ["resid_14", "resid_21"], "gross": "<=1 due to netting", "signal": "sleeve_inverse_vol_60_2"}|full|0.37|14.76|39.54|0.70|57.2|5.72|
|{"components": ["resid_14", "resid_21", "revmom_3"], "k": 8, "liquidity": 0.0, "r": 3, "signal": "score_blend_3", "weighting": "equal"}|IS|0.72|13.48|18.70|0.72|77.5|7.75|
|{"components": ["resid_14", "resid_21", "revmom_3"], "k": 8, "liquidity": 0.0, "r": 3, "signal": "score_blend_3", "weighting": "equal"}|OOS|0.36|10.85|29.86|0.56|90.4|9.04|
|{"components": ["resid_14", "resid_21", "revmom_3"], "k": 8, "liquidity": 0.0, "r": 3, "signal": "score_blend_3", "weighting": "equal"}|full|0.41|12.22|29.86|0.64|83.6|8.36|
|{"allocation": "equal", "components": ["resid_14", "resid_21", "revmom_3"], "gross": "<=1 due to netting", "signal": "sleeve_equal_3"}|IS|3.12|39.23|12.56|1.67|94.2|9.42|
|{"allocation": "equal", "components": ["resid_14", "resid_21", "revmom_3"], "gross": "<=1 due to netting", "signal": "sleeve_equal_3"}|OOS|-0.12|-4.41|37.17|-0.09|102.0|10.20|
|{"allocation": "equal", "components": ["resid_14", "resid_21", "revmom_3"], "gross": "<=1 due to netting", "signal": "sleeve_equal_3"}|full|0.44|16.38|37.17|0.80|97.9|9.79|
|{"allocation": "inverse_vol_60", "components": ["resid_14", "resid_21", "revmom_3"], "gross": "<=1 due to netting", "signal": "sleeve_inverse_vol_60_3"}|IS|3.08|37.32|12.11|1.64|91.9|9.19|
|{"allocation": "inverse_vol_60", "components": ["resid_14", "resid_21", "revmom_3"], "gross": "<=1 due to netting", "signal": "sleeve_inverse_vol_60_3"}|OOS|-0.19|-7.27|37.52|-0.24|101.6|10.16|
|{"allocation": "inverse_vol_60", "components": ["resid_14", "resid_21", "revmom_3"], "gross": "<=1 due to netting", "signal": "sleeve_inverse_vol_60_3"}|full|0.37|13.88|37.52|0.72|96.5|9.65|
|{"components": ["resid_14", "resid_21", "revmom_3", "revmom_2"], "k": 8, "liquidity": 0.0, "r": 3, "signal": "score_blend_4", "weighting": "equal"}|IS|1.00|15.15|15.13|0.80|93.9|9.39|
|{"components": ["resid_14", "resid_21", "revmom_3", "revmom_2"], "k": 8, "liquidity": 0.0, "r": 3, "signal": "score_blend_4", "weighting": "equal"}|OOS|-0.19|-6.55|34.02|-0.19|112.4|11.24|
|{"components": ["resid_14", "resid_21", "revmom_3", "revmom_2"], "k": 8, "liquidity": 0.0, "r": 3, "signal": "score_blend_4", "weighting": "equal"}|full|0.12|4.23|34.02|0.30|102.7|10.27|
|{"allocation": "equal", "components": ["resid_14", "resid_21", "revmom_3", "revmom_2"], "gross": "<=1 due to netting", "signal": "sleeve_equal_4"}|IS|3.25|39.53|12.18|1.75|88.0|8.80|
|{"allocation": "equal", "components": ["resid_14", "resid_21", "revmom_3", "revmom_2"], "gross": "<=1 due to netting", "signal": "sleeve_equal_4"}|OOS|-0.26|-10.41|39.38|-0.43|94.7|9.47|
|{"allocation": "equal", "components": ["resid_14", "resid_21", "revmom_3", "revmom_2"], "gross": "<=1 due to netting", "signal": "sleeve_equal_4"}|full|0.33|12.96|39.38|0.70|91.2|9.12|
|{"allocation": "inverse_vol_60", "components": ["resid_14", "resid_21", "revmom_3", "revmom_2"], "gross": "<=1 due to netting", "signal": "sleeve_inverse_vol_60_4"}|IS|3.14|37.20|11.84|1.70|86.6|8.66|
|{"allocation": "inverse_vol_60", "components": ["resid_14", "resid_21", "revmom_3", "revmom_2"], "gross": "<=1 due to netting", "signal": "sleeve_inverse_vol_60_4"}|OOS|-0.34|-13.35|39.48|-0.61|94.8|9.48|
|{"allocation": "inverse_vol_60", "components": ["resid_14", "resid_21", "revmom_3", "revmom_2"], "gross": "<=1 due to netting", "signal": "sleeve_inverse_vol_60_4"}|full|0.26|10.20|39.48|0.59|90.5|9.05|

점수 앙상블은 단면 백분위 순위 평균이다. 슬리브 앙상블은 기존 목표 비중을 합산하며 60일 수익률 변동성은 close t까지 관측한 값으로 다음 날 배분을 결정한다. 합산 종목 비중의 회전율에 비용을 부과한다. 중복 롱/숏이 상쇄되므로 총 노출은 1 이하이고, 앙상블 간 성과 차이는 순노출 감소 효과를 포함한다. 60일 변동성 미확보 시 동일 배분을 사용한다.

## walk-forward

고정 단일 신호 격자에서 각 훈련 구간 Calmar 최대 구성을 선택하고 동일 테스트 구간의 기준 전략과 비교한다. 구간 경계에서 포지션을 리셋하지 않는다. 두 번째·세 번째 폴드 훈련에는 전역 OOS 일부가 들어가므로 별도의 순차 실험이며 전역 OOS의 독립 검증을 대체하지 않는다.

```json
[
  {
    "config": {
      "signal": "carry_neg_30",
      "k": 10,
      "r": 7,
      "liquidity": 0.0,
      "weighting": "inverse_vol"
    },
    "train": {
      "CAGR": 0.3368364415458236,
      "MDD": 0.06542988402509398,
      "Calmar": 5.148051942391316,
      "Sharpe": 2.2221345661797276,
      "worst_day": -0.030981774192907485,
      "turnover": 18.58476221194533,
      "fee_drag": 0.018584762211945327,
      "funding_drag": -0.0711591899792246,
      "missing_return_exposure": 0.3338719053631124,
      "funding_coverage": 0.9797892875205749,
      "days": 546,
      "yearly": {
        "2022": 0.29867666797329906,
        "2023": 0.1887711194717221
      }
    },
    "window": [
      "2022-01-01",
      "2023-06-30",
      "2023-07-01",
      "2024-06-30"
    ],
    "test": {
      "CAGR": 0.020573394631424158,
      "MDD": 0.14122795167382896,
      "Calmar": 0.1456750904306759,
      "Sharpe": 0.2096972381666026,
      "worst_day": -0.03743503132728887,
      "turnover": 23.029566700647038,
      "fee_drag": 0.02302956670064704,
      "funding_drag": -0.06561442787299196,
      "missing_return_exposure": 0.0,
      "funding_coverage": 1.0,
      "days": 366,
      "yearly": {
        "2023": 0.002933537397982189,
        "2024": 0.017645037787083373
      }
    },
    "baseline_test": {
      "CAGR": 0.3513542077729741,
      "MDD": 0.1139125057830569,
      "Calmar": 3.0844217266374434,
      "Sharpe": 1.4228450506567716,
      "worst_day": -0.039213381987012186,
      "turnover": 85.88968579234972,
      "fee_drag": 0.08588968579234971,
      "funding_drag": 0.0016270971994535516,
      "missing_return_exposure": 0.0,
      "funding_coverage": 1.0,
      "days": 366,
      "yearly": {
        "2023": 0.14930251421330842,
        "2024": 0.17677413243764661
      }
    },
    "note": "Continuous positions at boundaries; later training intentionally includes dates in global OOS. Not an independent global-OOS selection."
  },
  {
    "config": {
      "signal": "resid_14",
      "k": 10,
      "r": 7,
      "liquidity": 0.2,
      "weighting": "equal"
    },
    "train": {
      "CAGR": 0.33649564232338736,
      "MDD": 0.06957431887193544,
      "Calmar": 4.836492081837992,
      "Sharpe": 1.7291723845511027,
      "worst_day": -0.03515837720964177,
      "turnover": 45.49913793103449,
      "fee_drag": 0.04549913793103449,
      "funding_drag": -0.01272889357758621,
      "missing_return_exposure": 0.0,
      "funding_coverage": 1.0000000000000002,
      "days": 580,
      "yearly": {
        "2022": 0.16261946685731887,
        "2023": 0.2796419837058166,
        "2024": 0.06571612785057068
      }
    },
    "window": [
      "2022-07-01",
      "2024-01-31",
      "2024-02-01",
      "2025-01-31"
    ],
    "test": {
      "CAGR": 0.2500884597995714,
      "MDD": 0.17628731895736627,
      "Calmar": 1.4186412345408315,
      "Sharpe": 1.0982580007086382,
      "worst_day": -0.057631487669775994,
      "turnover": 48.965846994535525,
      "fee_drag": 0.04896584699453552,
      "funding_drag": -0.005261489959016396,
      "missing_return_exposure": 0.0,
      "funding_coverage": 1.0000000000000002,
      "days": 366,
      "yearly": {
        "2024": 0.26552136102053203,
        "2025": -0.011590622787707838
      }
    },
    "baseline_test": {
      "CAGR": 0.3218139599487959,
      "MDD": 0.1716617651894734,
      "Calmar": 1.8746979538139463,
      "Sharpe": 1.1378639348128343,
      "worst_day": -0.08622482059474879,
      "turnover": 88.88148907103825,
      "fee_drag": 0.08888148907103825,
      "funding_drag": 0.0004524921704234972,
      "missing_return_exposure": 0.0,
      "funding_coverage": 1.0,
      "days": 366,
      "yearly": {
        "2024": 0.42281005322408816,
        "2025": -0.07027313012824521
      }
    },
    "note": "Continuous positions at boundaries; later training intentionally includes dates in global OOS. Not an independent global-OOS selection."
  },
  {
    "config": {
      "signal": "resid_21",
      "k": 4,
      "r": 5,
      "liquidity": 0.0,
      "weighting": "equal"
    },
    "train": {
      "CAGR": 0.6508348290435635,
      "MDD": 0.12607451618655285,
      "Calmar": 5.1623028089239,
      "Sharpe": 1.8323643002141408,
      "worst_day": -0.06527147153502055,
      "turnover": 66.68818466353677,
      "fee_drag": 0.06668818466353676,
      "funding_drag": -0.006888759526604069,
      "missing_return_exposure": 0.0,
      "funding_coverage": 1.0,
      "days": 639,
      "yearly": {
        "2023": 0.7693520382481986,
        "2024": 0.3593027689887527
      }
    },
    "window": [
      "2023-01-01",
      "2024-09-30",
      "2024-10-01",
      null
    ],
    "test": {
      "CAGR": -0.08192173297833549,
      "MDD": 0.5386208956604922,
      "Calmar": -0.15209534876636693,
      "Sharpe": -0.06387481912521135,
      "worst_day": -0.07428156520834506,
      "turnover": 67.9127198917456,
      "fee_drag": 0.0679127198917456,
      "funding_drag": -0.004845040992895805,
      "missing_return_exposure": 0.0,
      "funding_coverage": 0.9878213802435724,
      "days": 739,
      "yearly": {
        "2024": 0.23987822009498672,
        "2025": -0.013976585148184895,
        "2026": -0.31201675864829626
      }
    },
    "baseline_test": {
      "CAGR": 0.28290602580680035,
      "MDD": 0.21361452224671884,
      "Calmar": 1.3243763711909613,
      "Sharpe": 1.106252585265553,
      "worst_day": -0.08622482059474879,
      "turnover": 89.83000676589987,
      "fee_drag": 0.08983000676589988,
      "funding_drag": 0.0013320252706359944,
      "missing_return_exposure": 0.0,
      "funding_coverage": 0.9878213802435724,
      "days": 739,
      "yearly": {
        "2024": 0.261988895436994,
        "2025": 0.3419985039889901,
        "2026": -0.02220020250962107
      }
    },
    "note": "Continuous positions at boundaries; later training intentionally includes dates in global OOS. Not an independent global-OOS selection."
  }
]
```

## robustness

IS MDD≤25% 후보의 상위 5개에 대해 한 번에 한 파라미터를 바꾼다: 각 신호의 lookback ±3일(최소 1일), K ±1/2, R ±1. rankblend는 각 구성 기간을 개별 ±3일, volume은 7일 분자와 30일 분모를 개별 ±3일, revmom은 반전과 모멘텀 기간을 개별 ±3일 변경한다. 승리 비율은 기준 전략 대비 Calmar 초과 비율이다. 이웃 결과를 보고 선택을 변경하지 않는다.

```json
[
  {
    "selected": {
      "signal": "resid_14",
      "k": 4,
      "r": 5,
      "liquidity": 0.2,
      "weighting": "score"
    },
    "neighbors": [
      {
        "config": {
          "signal": "resid_14_horizon11",
          "k": 4,
          "r": 5,
          "liquidity": 0.2,
          "weighting": "score"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.20568902191980598,
            "MDD": 0.20643762692361411,
            "Calmar": 0.9963736988505243,
            "Sharpe": 0.8012942973839897,
            "worst_day": -0.058267163380835374,
            "turnover": 84.26767203928867,
            "fee_drag": 0.08426767203928869,
            "funding_drag": 0.012899925041704664,
            "missing_return_exposure": 0.22619047619047616,
            "funding_coverage": 0.9923496642246642,
            "days": 912,
            "yearly": {
              "2022": 0.3340094674399712,
              "2023": 0.07826113487005704,
              "2024": 0.10941522541516147
            }
          },
          "OOS": {
            "CAGR": 0.28307837934521407,
            "MDD": 0.3203251123507689,
            "Calmar": 0.8837220949297033,
            "Sharpe": 0.9131603148221172,
            "worst_day": -0.1202348422670746,
            "turnover": 85.71744601461631,
            "fee_drag": 0.08571744601461634,
            "funding_drag": 0.005517402296356267,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902527,
            "days": 831,
            "yearly": {
              "2024": 0.5730940860540041,
              "2025": 0.20064382167890726,
              "2026": -0.06611698549889722
            }
          },
          "full": {
            "CAGR": 0.24198532591226618,
            "MDD": 0.320325112350769,
            "Calmar": 0.7554366379095574,
            "Sharpe": 0.8565598220673633,
            "worst_day": -0.1202348422670746,
            "turnover": 84.95887236831753,
            "fee_drag": 0.08495887236831752,
            "funding_drag": 0.009380202493578146,
            "missing_return_exposure": 0.22619047619047616,
            "funding_coverage": 0.9908335592500825,
            "days": 1743,
            "yearly": {
              "2022": 0.3340094674399712,
              "2023": 0.07826113487005704,
              "2024": 0.7452145300788604,
              "2025": 0.20064382167890726,
              "2026": -0.06611698549889722
            }
          }
        }
      },
      {
        "config": {
          "signal": "resid_14_horizon17",
          "k": 4,
          "r": 5,
          "liquidity": 0.2,
          "weighting": "score"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.1642010173516708,
            "MDD": 0.19611362212659522,
            "Calmar": 0.837274920380981,
            "Sharpe": 0.6544585885970736,
            "worst_day": -0.07179229947861576,
            "turnover": 68.71026810322064,
            "fee_drag": 0.06871026810322066,
            "funding_drag": -0.0010799935156314581,
            "missing_return_exposure": 0.23809523809523808,
            "funding_coverage": 0.9925022893772895,
            "days": 912,
            "yearly": {
              "2022": -0.012933997127817731,
              "2023": 0.36242291850933195,
              "2024": 0.08722981194053214
            }
          },
          "OOS": {
            "CAGR": 0.2049051398809243,
            "MDD": 0.37353160752305703,
            "Calmar": 0.5485617167438128,
            "Sharpe": 0.7099811761845684,
            "worst_day": -0.07030641899460721,
            "turnover": 72.91489432442926,
            "fee_drag": 0.07291489432442927,
            "funding_drag": 0.0044089530907798526,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902527,
            "days": 831,
            "yearly": {
              "2024": 0.39410516221079184,
              "2025": 0.2707124965910461,
              "2026": -0.13709391548353944
            }
          },
          "full": {
            "CAGR": 0.18343286031255812,
            "MDD": 0.3735316075230567,
            "Calmar": 0.49107721172226504,
            "Sharpe": 0.6814022821944766,
            "worst_day": -0.07179229947861576,
            "turnover": 70.71488335842683,
            "fee_drag": 0.07071488335842682,
            "funding_drag": 0.0015369397201274618,
            "missing_return_exposure": 0.23809523809523808,
            "funding_coverage": 0.9909134181939689,
            "days": 1743,
            "yearly": {
              "2022": -0.012933997127817731,
              "2023": 0.36242291850933195,
              "2024": 0.5157126933357643,
              "2025": 0.2707124965910461,
              "2026": -0.13709391548353944
            }
          }
        }
      },
      {
        "config": {
          "signal": "resid_14",
          "k": 2,
          "r": 5,
          "liquidity": 0.2,
          "weighting": "score"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.42842661761122103,
            "MDD": 0.29658653277779135,
            "Calmar": 1.4445248528267025,
            "Sharpe": 1.1020306424113702,
            "worst_day": -0.05267262377515236,
            "turnover": 87.16317767288642,
            "fee_drag": 0.08716317767288642,
            "funding_drag": -0.004857171021318267,
            "missing_return_exposure": 0.2391304347826087,
            "funding_coverage": 0.9930952834986015,
            "days": 912,
            "yearly": {
              "2022": 0.5425642203956704,
              "2023": 0.46247006762741005,
              "2024": 0.0804444968711695
            }
          },
          "OOS": {
            "CAGR": -0.016196676946960253,
            "MDD": 0.5628793692936778,
            "Calmar": -0.02877468571513725,
            "Sharpe": 0.19202197673417926,
            "worst_day": -0.1066569753840263,
            "turnover": 89.92743013771894,
            "fee_drag": 0.08992743013771895,
            "funding_drag": 0.012303806627712358,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902527,
            "days": 831,
            "yearly": {
              "2024": 0.5580490933294897,
              "2025": -0.0934282774607984,
              "2026": -0.31786411201040554
            }
          },
          "full": {
            "CAGR": 0.19576583145537763,
            "MDD": 0.5628793692936769,
            "Calmar": 0.3477935808893338,
            "Sharpe": 0.6319220631881952,
            "worst_day": -0.1066569753840263,
            "turnover": 88.48107428692877,
            "fee_drag": 0.08848107428692878,
            "funding_drag": 0.0033245687528323047,
            "missing_return_exposure": 0.2391304347826087,
            "funding_coverage": 0.9912236939476331,
            "days": 1743,
            "yearly": {
              "2022": 0.5425642203956704,
              "2023": 0.46247006762741005,
              "2024": 0.6833855687429613,
              "2025": -0.0934282774607984,
              "2026": -0.31786411201040554
            }
          }
        }
      },
      {
        "config": {
          "signal": "resid_14",
          "k": 3,
          "r": 5,
          "liquidity": 0.2,
          "weighting": "score"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.5885892884192965,
            "MDD": 0.22579758029551034,
            "Calmar": 2.6067121164406903,
            "Sharpe": 1.5480799090153092,
            "worst_day": -0.06998896886638684,
            "turnover": 77.48467503701333,
            "fee_drag": 0.07748467503701333,
            "funding_drag": -0.0009940210844400126,
            "missing_return_exposure": 0.3181818181818182,
            "funding_coverage": 0.9921465595807701,
            "days": 912,
            "yearly": {
              "2022": 0.6394643422599828,
              "2023": 0.6773082729689404,
              "2024": 0.1559494743254457
            }
          },
          "OOS": {
            "CAGR": 0.0625037540831841,
            "MDD": 0.4508248604471743,
            "Calmar": 0.13864309528357968,
            "Sharpe": 0.3497308400376112,
            "worst_day": -0.09021532623732786,
            "turnover": 81.6827250755898,
            "fee_drag": 0.0816827250755898,
            "funding_drag": 0.005947678388344508,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902527,
            "days": 831,
            "yearly": {
              "2024": 0.34637674394825435,
              "2025": 0.22413997487303217,
              "2026": -0.3034549163377195
            }
          },
          "full": {
            "CAGR": 0.3113840827398251,
            "MDD": 0.4508248604471756,
            "Calmar": 0.6906985618117012,
            "Sharpe": 0.9189060938540092,
            "worst_day": -0.09021532623732786,
            "turnover": 79.4861550037701,
            "fee_drag": 0.0794861550037701,
            "funding_drag": 0.00231553270895295,
            "missing_return_exposure": 0.3181818181818182,
            "funding_coverage": 0.9907272876291809,
            "days": 1743,
            "yearly": {
              "2022": 0.6394643422599828,
              "2023": 0.6773082729689404,
              "2024": 0.5563434894109931,
              "2025": 0.22413997487303217,
              "2026": -0.3034549163377195
            }
          }
        }
      },
      {
        "config": {
          "signal": "resid_14",
          "k": 5,
          "r": 5,
          "liquidity": 0.2,
          "weighting": "score"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.2711083053497776,
            "MDD": 0.18352258430960533,
            "Calmar": 1.4772476443139764,
            "Sharpe": 1.0320956109983543,
            "worst_day": -0.06530501698806934,
            "turnover": 70.43110112623926,
            "fee_drag": 0.07043110112623926,
            "funding_drag": -0.0016860564909444958,
            "missing_return_exposure": 0.38,
            "funding_coverage": 0.9913048245614035,
            "days": 912,
            "yearly": {
              "2022": 0.22148686530138928,
              "2023": 0.3742005162621267,
              "2024": 0.08486267247564472
            }
          },
          "OOS": {
            "CAGR": 0.1509720458283894,
            "MDD": 0.257550710997133,
            "Calmar": 0.5861837664663639,
            "Sharpe": 0.6081151605096556,
            "worst_day": -0.06403355819427459,
            "turnover": 75.89974884221274,
            "fee_drag": 0.07589974884221275,
            "funding_drag": 0.004173603465772343,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902527,
            "days": 831,
            "yearly": {
              "2024": 0.3777455735910724,
              "2025": 0.19902430240467006,
              "2026": -0.1662613822332356
            }
          },
          "full": {
            "CAGR": 0.21234309224797698,
            "MDD": 0.25755071099713267,
            "Calmar": 0.8244710000056689,
            "Sharpe": 0.8122608951330815,
            "worst_day": -0.06530501698806934,
            "turnover": 73.0383565777447,
            "fee_drag": 0.07303835657774468,
            "funding_drag": 0.001107619598574549,
            "missing_return_exposure": 0.38,
            "funding_coverage": 0.9902868617326448,
            "days": 1743,
            "yearly": {
              "2022": 0.22148686530138928,
              "2023": 0.3742005162621267,
              "2024": 0.49466474495749924,
              "2025": 0.19902430240467006,
              "2026": -0.1662613822332356
            }
          }
        }
      },
      {
        "config": {
          "signal": "resid_14",
          "k": 6,
          "r": 5,
          "liquidity": 0.2,
          "weighting": "score"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.1838094589038446,
            "MDD": 0.1856890026689102,
            "Calmar": 0.9898780017230374,
            "Sharpe": 0.8171397486073035,
            "worst_day": -0.053969984778379554,
            "turnover": 67.8821128475819,
            "fee_drag": 0.06788211284758189,
            "funding_drag": 0.00542095133319782,
            "missing_return_exposure": 0.33333333333333337,
            "funding_coverage": 0.9915297364223956,
            "days": 912,
            "yearly": {
              "2022": 0.2008234010512313,
              "2023": 0.1711420646457429,
              "2024": 0.08396536464118398
            }
          },
          "OOS": {
            "CAGR": 0.2513701986118613,
            "MDD": 0.23853191359263326,
            "Calmar": 1.0538220853799602,
            "Sharpe": 0.9327196801802797,
            "worst_day": -0.0601792250743336,
            "turnover": 71.96071075624653,
            "fee_drag": 0.07196071075624653,
            "funding_drag": 0.0028647597023075907,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902527,
            "days": 831,
            "yearly": {
              "2024": 0.3913834878443465,
              "2025": 0.412035883541384,
              "2026": -0.1519393912413547
            }
          },
          "full": {
            "CAGR": 0.21555252868734498,
            "MDD": 0.24471554731946976,
            "Calmar": 0.8808289095173294,
            "Sharpe": 0.8743252514201417,
            "worst_day": -0.0601792250743336,
            "turnover": 69.82664231522408,
            "fee_drag": 0.06982664231522406,
            "funding_drag": 0.004202250676129674,
            "missing_return_exposure": 0.33333333333333337,
            "funding_coverage": 0.990404543670238,
            "days": 1743,
            "yearly": {
              "2022": 0.2008234010512313,
              "2023": 0.1711420646457429,
              "2024": 0.5082115097569189,
              "2025": 0.412035883541384,
              "2026": -0.1519393912413547
            }
          }
        }
      },
      {
        "config": {
          "signal": "resid_14",
          "k": 4,
          "r": 4,
          "liquidity": 0.2,
          "weighting": "score"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.29845785054477636,
            "MDD": 0.1881870134808099,
            "Calmar": 1.5859641163560478,
            "Sharpe": 1.0286205902459027,
            "worst_day": -0.0634596652757834,
            "turnover": 83.79896724670154,
            "fee_drag": 0.08379896724670155,
            "funding_drag": 0.011464427084744067,
            "missing_return_exposure": 0.13095238095238096,
            "funding_coverage": 0.9912853046076731,
            "days": 912,
            "yearly": {
              "2022": 0.256433647078141,
              "2023": 0.3522824277057768,
              "2024": 0.13033531843890533
            }
          },
          "OOS": {
            "CAGR": 0.01563046081140662,
            "MDD": 0.41912934353779885,
            "Calmar": 0.037292690317200373,
            "Sharpe": 0.21091099346051673,
            "worst_day": -0.06089815277389388,
            "turnover": 87.85507040032948,
            "fee_drag": 0.08785507040032949,
            "funding_drag": 0.007605446349799492,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902527,
            "days": 831,
            "yearly": {
              "2024": 0.32372172382088427,
              "2025": -0.09818383448658285,
              "2026": -0.13219813429048388
            }
          },
          "full": {
            "CAGR": 0.15494383338080286,
            "MDD": 0.41912934353779796,
            "Calmar": 0.3696802330110054,
            "Sharpe": 0.6158224666716896,
            "worst_day": -0.0634596652757834,
            "turnover": 85.73277202046219,
            "fee_drag": 0.0857327720204622,
            "funding_drag": 0.009624603223161197,
            "missing_return_exposure": 0.13095238095238096,
            "funding_coverage": 0.990276648194032,
            "days": 1743,
            "yearly": {
              "2022": 0.256433647078141,
              "2023": 0.3522824277057768,
              "2024": 0.49624941621957563,
              "2025": -0.09818383448658285,
              "2026": -0.13219813429048388
            }
          }
        }
      },
      {
        "config": {
          "signal": "resid_14",
          "k": 4,
          "r": 6,
          "liquidity": 0.2,
          "weighting": "score"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.19270706165283147,
            "MDD": 0.21385834421691718,
            "Calmar": 0.901096762712088,
            "Sharpe": 0.750094306236675,
            "worst_day": -0.08590117510682915,
            "turnover": 68.00069433643951,
            "fee_drag": 0.06800069433643952,
            "funding_drag": 0.010677279454088272,
            "missing_return_exposure": 0.2619047619047619,
            "funding_coverage": 0.9920373851294904,
            "days": 912,
            "yearly": {
              "2022": 0.11732159089556315,
              "2023": 0.29564657381886383,
              "2024": 0.07291395404750167
            }
          },
          "OOS": {
            "CAGR": 0.08161782155354835,
            "MDD": 0.3647046237848339,
            "Calmar": 0.22379157331907235,
            "Sharpe": 0.40164604668372117,
            "worst_day": -0.056513706608593006,
            "turnover": 72.2924563108254,
            "fee_drag": 0.0722924563108254,
            "funding_drag": 0.003504339277161882,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902527,
            "days": 831,
            "yearly": {
              "2024": 0.35212260199546197,
              "2025": 0.0784855257592656,
              "2026": -0.18012824393622795
            }
          },
          "full": {
            "CAGR": 0.1383882476057292,
            "MDD": 0.36470462378483415,
            "Calmar": 0.3794529561198394,
            "Sharpe": 0.5726821020921768,
            "worst_day": -0.08590117510682915,
            "turnover": 70.04685279927065,
            "fee_drag": 0.07004685279927064,
            "funding_drag": 0.007257478371457272,
            "missing_return_exposure": 0.2619047619047619,
            "funding_coverage": 0.9906701636477884,
            "days": 1743,
            "yearly": {
              "2022": 0.11732159089556315,
              "2023": 0.29564657381886383,
              "2024": 0.45071120726394853,
              "2025": 0.0784855257592656,
              "2026": -0.18012824393622795
            }
          }
        }
      }
    ],
    "fraction_beating_baseline": {
      "IS": 1.0,
      "OOS": 0.0
    },
    "comparison": "Calmar",
    "lookback_applicable": true
  },
  {
    "selected": {
      "signal": "resid_14",
      "k": 4,
      "r": 5,
      "liquidity": 0.2,
      "weighting": "inverse_vol"
    },
    "neighbors": [
      {
        "config": {
          "signal": "resid_14_horizon11",
          "k": 4,
          "r": 5,
          "liquidity": 0.2,
          "weighting": "inverse_vol"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.17440328385339154,
            "MDD": 0.19934708562804404,
            "Calmar": 0.874872503422526,
            "Sharpe": 0.7415420973753275,
            "worst_day": -0.06900118141654155,
            "turnover": 90.01976527659045,
            "fee_drag": 0.09001976527659045,
            "funding_drag": 0.005157057898864408,
            "missing_return_exposure": 0.2464233281849731,
            "funding_coverage": 0.9919130250056473,
            "days": 912,
            "yearly": {
              "2022": 0.3255232751025814,
              "2023": 0.04265143237200508,
              "2024": 0.08123725203154386
            }
          },
          "OOS": {
            "CAGR": 0.21674723680261243,
            "MDD": 0.3176226318229223,
            "Calmar": 0.6824048889672671,
            "Sharpe": 0.7619341438314572,
            "worst_day": -0.13723007621122507,
            "turnover": 92.22956548820359,
            "fee_drag": 0.0922295654882036,
            "funding_drag": 0.007945784246109694,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902527,
            "days": 831,
            "yearly": {
              "2024": 0.561810935706069,
              "2025": 0.14154539400278576,
              "2026": -0.12329176842382816
            }
          },
          "full": {
            "CAGR": 0.19440434304134846,
            "MDD": 0.31762263182292205,
            "Calmar": 0.6120607398963023,
            "Sharpe": 0.74809653694421,
            "worst_day": -0.13723007621122507,
            "turnover": 91.07331890587933,
            "fee_drag": 0.09107331890587933,
            "funding_drag": 0.006486622783867756,
            "missing_return_exposure": 0.2464233281849731,
            "funding_coverage": 0.9906050939788584,
            "days": 1743,
            "yearly": {
              "2022": 0.3255232751025814,
              "2023": 0.04265143237200508,
              "2024": 0.688688164315642,
              "2025": 0.14154539400278576,
              "2026": -0.12329176842382816
            }
          }
        }
      },
      {
        "config": {
          "signal": "resid_14_horizon17",
          "k": 4,
          "r": 5,
          "liquidity": 0.2,
          "weighting": "inverse_vol"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.11655883447411797,
            "MDD": 0.2361835068553626,
            "Calmar": 0.49350962743345966,
            "Sharpe": 0.5205636867698475,
            "worst_day": -0.06844530455669784,
            "turnover": 75.80582847404804,
            "fee_drag": 0.07580582847404806,
            "funding_drag": -0.0031497482565509024,
            "missing_return_exposure": 0.22699724885511835,
            "funding_coverage": 0.9926849423994074,
            "days": 912,
            "yearly": {
              "2022": -0.0691385007388472,
              "2023": 0.2802215331543352,
              "2024": 0.10526964638301162
            }
          },
          "OOS": {
            "CAGR": 0.21547805329245096,
            "MDD": 0.3782807568782345,
            "Calmar": 0.5696246752562452,
            "Sharpe": 0.7362570912807318,
            "worst_day": -0.06932038694012688,
            "turnover": 78.90910109792958,
            "fee_drag": 0.07890910109792958,
            "funding_drag": 0.0034748379246310286,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902527,
            "days": 831,
            "yearly": {
              "2024": 0.3510059825034366,
              "2025": 0.24271404821443454,
              "2026": -0.0712125539760593
            }
          },
          "full": {
            "CAGR": 0.16267348194430298,
            "MDD": 0.3782807568782348,
            "Calmar": 0.43003372227222786,
            "Sharpe": 0.6300919799646149,
            "worst_day": -0.06932038694012688,
            "turnover": 77.28535776288658,
            "fee_drag": 0.07728535776288657,
            "funding_drag": 8.61727217094733e-06,
            "missing_return_exposure": 0.22699724885511835,
            "funding_coverage": 0.9910089887941822,
            "days": 1743,
            "yearly": {
              "2022": -0.0691385007388472,
              "2023": 0.2802215331543352,
              "2024": 0.49322590454290616,
              "2025": 0.24271404821443454,
              "2026": -0.0712125539760593
            }
          }
        }
      },
      {
        "config": {
          "signal": "resid_14",
          "k": 2,
          "r": 5,
          "liquidity": 0.2,
          "weighting": "inverse_vol"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.5316181136302842,
            "MDD": 0.279076507902731,
            "Calmar": 1.9049188970630728,
            "Sharpe": 1.2846936872507533,
            "worst_day": -0.052057369399460374,
            "turnover": 92.36604058761263,
            "fee_drag": 0.09236604058761262,
            "funding_drag": -0.005064303094181836,
            "missing_return_exposure": 0.24841138917507663,
            "funding_coverage": 0.9931897044524557,
            "days": 912,
            "yearly": {
              "2022": 0.8089806390994461,
              "2023": 0.4779857001595156,
              "2024": 0.08522165906909507
            }
          },
          "OOS": {
            "CAGR": 0.01124822014848803,
            "MDD": 0.5626691385617888,
            "Calmar": 0.019990824762913174,
            "Sharpe": 0.2491211971560795,
            "worst_day": -0.10780251603401736,
            "turnover": 94.767199167904,
            "fee_drag": 0.094767199167904,
            "funding_drag": 0.013871921060751052,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902527,
            "days": 831,
            "yearly": {
              "2024": 0.6769666239198768,
              "2025": -0.1719001758556543,
              "2026": -0.2613263044628453
            }
          },
          "full": {
            "CAGR": 0.2565893591935058,
            "MDD": 0.5626691385617882,
            "Calmar": 0.45602173925757084,
            "Sharpe": 0.752468400069981,
            "worst_day": -0.10780251603401736,
            "turnover": 93.51082703639183,
            "fee_drag": 0.09351082703639182,
            "funding_drag": 0.003963810659546926,
            "missing_return_exposure": 0.24841138917507663,
            "funding_coverage": 0.9912730983709922,
            "days": 1743,
            "yearly": {
              "2022": 0.8089806390994461,
              "2023": 0.4779857001595156,
              "2024": 0.8198805018138284,
              "2025": -0.1719001758556543,
              "2026": -0.2613263044628453
            }
          }
        }
      },
      {
        "config": {
          "signal": "resid_14",
          "k": 3,
          "r": 5,
          "liquidity": 0.2,
          "weighting": "inverse_vol"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.6277712567279425,
            "MDD": 0.19008606482828905,
            "Calmar": 3.3025632746673397,
            "Sharpe": 1.657652849029974,
            "worst_day": -0.05287445312304906,
            "turnover": 83.90989634670667,
            "fee_drag": 0.08390989634670667,
            "funding_drag": -0.0010702126244568327,
            "missing_return_exposure": 0.3137813705822714,
            "funding_coverage": 0.9918576748900498,
            "days": 912,
            "yearly": {
              "2022": 0.7142535374793497,
              "2023": 0.6420787587748835,
              "2024": 0.20011965088240014
            }
          },
          "OOS": {
            "CAGR": 0.05747762618548857,
            "MDD": 0.4206671071786461,
            "Calmar": 0.13663446750325398,
            "Sharpe": 0.3366538511154016,
            "worst_day": -0.08805715451339535,
            "turnover": 88.00490715159638,
            "fee_drag": 0.0880049071515964,
            "funding_drag": 0.005972012201253312,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902527,
            "days": 831,
            "yearly": {
              "2024": 0.43297561274337304,
              "2025": 0.14715553483772914,
              "2026": -0.3091282930864102
            }
          },
          "full": {
            "CAGR": 0.3252104821316577,
            "MDD": 0.42066710717864564,
            "Calmar": 0.7730827454345031,
            "Sharpe": 0.9556520550846328,
            "worst_day": -0.08805715451339535,
            "turnover": 85.86225089568164,
            "fee_drag": 0.08586225089568163,
            "funding_drag": 0.002287268058368831,
            "missing_return_exposure": 0.3137813705822714,
            "funding_coverage": 0.9905761328168247,
            "days": 1743,
            "yearly": {
              "2022": 0.7142535374793497,
              "2023": 0.6420787587748835,
              "2024": 0.7197421920885745,
              "2025": 0.14715553483772914,
              "2026": -0.3091282930864102
            }
          }
        }
      },
      {
        "config": {
          "signal": "resid_14",
          "k": 5,
          "r": 5,
          "liquidity": 0.2,
          "weighting": "inverse_vol"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.17112983300184492,
            "MDD": 0.143836934637252,
            "Calmar": 1.1897488877486437,
            "Sharpe": 0.7527180874688837,
            "worst_day": -0.054469698154879564,
            "turnover": 76.97596646286443,
            "fee_drag": 0.07697596646286443,
            "funding_drag": -0.002222822820617627,
            "missing_return_exposure": 0.3729057342803946,
            "funding_coverage": 0.9909880386494915,
            "days": 912,
            "yearly": {
              "2022": 0.14649191930720118,
              "2023": 0.27824141684799275,
              "2024": 0.01259259639388488
            }
          },
          "OOS": {
            "CAGR": 0.12290916169790522,
            "MDD": 0.29296786968469746,
            "Calmar": 0.4195311992068771,
            "Sharpe": 0.5353626179931461,
            "worst_day": -0.06278847821983158,
            "turnover": 82.91609578349298,
            "fee_drag": 0.08291609578349297,
            "funding_drag": 0.006104083472633533,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902527,
            "days": 831,
            "yearly": {
              "2024": 0.3936453833144984,
              "2025": 0.10998771135743035,
              "2026": -0.15831463141643842
            }
          },
          "full": {
            "CAGR": 0.14788698069829964,
            "MDD": 0.2929678696846967,
            "Calmar": 0.5047890775785799,
            "Sharpe": 0.6373568463732354,
            "worst_day": -0.06278847821983158,
            "turnover": 79.80800746426566,
            "fee_drag": 0.07980800746426565,
            "funding_drag": 0.0017471479938928236,
            "missing_return_exposure": 0.3729057342803946,
            "funding_coverage": 0.9901211080024878,
            "days": 1743,
            "yearly": {
              "2022": 0.14649191930720118,
              "2023": 0.27824141684799275,
              "2024": 0.4111949971427802,
              "2025": 0.10998771135743035,
              "2026": -0.15831463141643842
            }
          }
        }
      },
      {
        "config": {
          "signal": "resid_14",
          "k": 6,
          "r": 5,
          "liquidity": 0.2,
          "weighting": "inverse_vol"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.05357235133308835,
            "MDD": 0.25595203255591337,
            "Calmar": 0.20930621569252567,
            "Sharpe": 0.3440461872875916,
            "worst_day": -0.08844339344767582,
            "turnover": 73.02242569109673,
            "fee_drag": 0.07302242569109672,
            "funding_drag": 0.0031085501141008844,
            "missing_return_exposure": 0.29480629907038114,
            "funding_coverage": 0.9917460094227288,
            "days": 912,
            "yearly": {
              "2022": 0.13329060094767775,
              "2023": -0.0015584150626392068,
              "2024": 0.006852650145195094
            }
          },
          "OOS": {
            "CAGR": 0.2546630246667112,
            "MDD": 0.2731020498061719,
            "Calmar": 0.9324830218134671,
            "Sharpe": 0.9591320631128917,
            "worst_day": -0.050384867147187595,
            "turnover": 78.61543664431969,
            "fee_drag": 0.07861543664431968,
            "funding_drag": 0.004434859716055865,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902527,
            "days": 831,
            "yearly": {
              "2024": 0.4481570328967337,
              "2025": 0.36402403092945645,
              "2026": -0.1514446372269519
            }
          },
          "full": {
            "CAGR": 0.14507254230212507,
            "MDD": 0.2731020498061708,
            "Calmar": 0.5312026856081368,
            "Sharpe": 0.6649905646419806,
            "worst_day": -0.08844339344767582,
            "turnover": 75.688973081876,
            "fee_drag": 0.075688973081876,
            "funding_drag": 0.0037408870499727087,
            "missing_return_exposure": 0.29480629907038114,
            "funding_coverage": 0.9905177054466602,
            "days": 1743,
            "yearly": {
              "2022": 0.13329060094767775,
              "2023": -0.0015584150626392068,
              "2024": 0.45808074639847973,
              "2025": 0.36402403092945645,
              "2026": -0.1514446372269519
            }
          }
        }
      },
      {
        "config": {
          "signal": "resid_14",
          "k": 4,
          "r": 4,
          "liquidity": 0.2,
          "weighting": "inverse_vol"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.2863163074954169,
            "MDD": 0.1937694062526759,
            "Calmar": 1.477613587369203,
            "Sharpe": 1.0439296790752606,
            "worst_day": -0.06249012829263889,
            "turnover": 92.19932895815394,
            "fee_drag": 0.09219932895815396,
            "funding_drag": 0.0025355621332620406,
            "missing_return_exposure": 0.09755624144818432,
            "funding_coverage": 0.9913192102027008,
            "days": 912,
            "yearly": {
              "2022": 0.33895182746798147,
              "2023": 0.2263594803139064,
              "2024": 0.14244921149546275
            }
          },
          "OOS": {
            "CAGR": 0.008394986359998358,
            "MDD": 0.4066501031473483,
            "Calmar": 0.020644249921551016,
            "Sharpe": 0.18645549928957428,
            "worst_day": -0.06083098435547463,
            "turnover": 96.13693007566117,
            "fee_drag": 0.09613693007566118,
            "funding_drag": 0.009749314610833795,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902527,
            "days": 831,
            "yearly": {
              "2024": 0.36290712204603803,
              "2025": -0.17995781899135854,
              "2026": -0.08806568973452267
            }
          },
          "full": {
            "CAGR": 0.14536958936424726,
            "MDD": 0.40665010314734773,
            "Calmar": 0.35748076353388575,
            "Sharpe": 0.601194821029011,
            "worst_day": -0.06249012829263889,
            "turnover": 94.07663620350594,
            "fee_drag": 0.09407663620350594,
            "funding_drag": 0.005974821059746336,
            "missing_return_exposure": 0.09755624144818432,
            "funding_coverage": 0.9902943888151825,
            "days": 1743,
            "yearly": {
              "2022": 0.33895182746798147,
              "2023": 0.2263594803139064,
              "2024": 0.5570521669230475,
              "2025": -0.17995781899135854,
              "2026": -0.08806568973452267
            }
          }
        }
      },
      {
        "config": {
          "signal": "resid_14",
          "k": 4,
          "r": 6,
          "liquidity": 0.2,
          "weighting": "inverse_vol"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.13794680306631668,
            "MDD": 0.2668681069418657,
            "Calmar": 0.5169100371231954,
            "Sharpe": 0.5973790900195328,
            "worst_day": -0.14387624855285885,
            "turnover": 72.9306833249229,
            "fee_drag": 0.07293068332492289,
            "funding_drag": 0.0018657158148776515,
            "missing_return_exposure": 0.22342495319554184,
            "funding_coverage": 0.9922812856696509,
            "days": 912,
            "yearly": {
              "2022": 0.1714168337080244,
              "2023": 0.13445353747880184,
              "2024": 0.03927348282615317
            }
          },
          "OOS": {
            "CAGR": 0.06388196603222052,
            "MDD": 0.36097199149172565,
            "Calmar": 0.17697208519759863,
            "Sharpe": 0.35190834798021914,
            "worst_day": -0.05988908320329123,
            "turnover": 77.71866675852029,
            "fee_drag": 0.0777186667585203,
            "funding_drag": 0.00487132356128064,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902527,
            "days": 831,
            "yearly": {
              "2024": 0.2995016828501469,
              "2025": -0.048364953575124936,
              "2026": -0.06893206804311125
            }
          },
          "full": {
            "CAGR": 0.1020133394386511,
            "MDD": 0.36097199149172643,
            "Calmar": 0.28260735415254307,
            "Sharpe": 0.47186440318500694,
            "worst_day": -0.14387624855285885,
            "turnover": 75.21342241460702,
            "fee_drag": 0.07521342241460702,
            "funding_drag": 0.0032986819865706398,
            "missing_return_exposure": 0.22342495319554184,
            "funding_coverage": 0.9907977811421237,
            "days": 1743,
            "yearly": {
              "2022": 0.1714168337080244,
              "2023": 0.13445353747880184,
              "2024": 0.3505376398741189,
              "2025": -0.048364953575124936,
              "2026": -0.06893206804311125
            }
          }
        }
      }
    ],
    "fraction_beating_baseline": {
      "IS": 0.625,
      "OOS": 0.0
    },
    "comparison": "Calmar",
    "lookback_applicable": true
  },
  {
    "selected": {
      "signal": "resid_14",
      "k": 4,
      "r": 5,
      "liquidity": 0.2,
      "weighting": "equal"
    },
    "neighbors": [
      {
        "config": {
          "signal": "resid_14_horizon11",
          "k": 4,
          "r": 5,
          "liquidity": 0.2,
          "weighting": "equal"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.1931003850887545,
            "MDD": 0.208581774580209,
            "Calmar": 0.9257778416996773,
            "Sharpe": 0.7776003970106066,
            "worst_day": -0.0556668509412892,
            "turnover": 82.84539473684211,
            "fee_drag": 0.08284539473684212,
            "funding_drag": 0.010934657593201752,
            "missing_return_exposure": 0.25,
            "funding_coverage": 0.9917763157894737,
            "days": 912,
            "yearly": {
              "2022": 0.3257155724421912,
              "2023": 0.05845395352541116,
              "2024": 0.10780953945520078
            }
          },
          "OOS": {
            "CAGR": 0.28777846023449327,
            "MDD": 0.3134061506445338,
            "Calmar": 0.9182285020337474,
            "Sharpe": 0.9297414291892628,
            "worst_day": -0.1270876653134334,
            "turnover": 84.7713598074609,
            "fee_drag": 0.0847713598074609,
            "funding_drag": 0.005596366892298435,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902527,
            "days": 831,
            "yearly": {
              "2024": 0.5836748298707881,
              "2025": 0.22538723097191138,
              "2026": -0.08348969841272391
            }
          },
          "full": {
            "CAGR": 0.2373383545379757,
            "MDD": 0.31340615064453436,
            "Calmar": 0.7572868434454088,
            "Sharpe": 0.8537450459701827,
            "worst_day": -0.1270876653134334,
            "turnover": 83.76362593230064,
            "fee_drag": 0.08376362593230063,
            "funding_drag": 0.008389551699655766,
            "missing_return_exposure": 0.25,
            "funding_coverage": 0.9905335628227194,
            "days": 1743,
            "yearly": {
              "2022": 0.3257155724421912,
              "2023": 0.05845395352541116,
              "2024": 0.7544100839259493,
              "2025": 0.22538723097191138,
              "2026": -0.08348969841272391
            }
          }
        }
      },
      {
        "config": {
          "signal": "resid_14_horizon17",
          "k": 4,
          "r": 5,
          "liquidity": 0.2,
          "weighting": "equal"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.1468080229104427,
            "MDD": 0.20745389075847764,
            "Calmar": 0.7076657968365597,
            "Sharpe": 0.6075893152032406,
            "worst_day": -0.07728697539492568,
            "turnover": 67.73711622807018,
            "fee_drag": 0.06773711622807019,
            "funding_drag": -0.0017175486225328965,
            "missing_return_exposure": 0.25,
            "funding_coverage": 0.9924616228070176,
            "days": 912,
            "yearly": {
              "2022": -0.04564154797313269,
              "2023": 0.3434236138467257,
              "2024": 0.09829956192787814
            }
          },
          "OOS": {
            "CAGR": 0.2159069760514556,
            "MDD": 0.3669925159668658,
            "Calmar": 0.5883143842392387,
            "Sharpe": 0.7400147688056783,
            "worst_day": -0.06767460944674597,
            "turnover": 72.14350180505416,
            "fee_drag": 0.07214350180505416,
            "funding_drag": 0.0038732006844163654,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902527,
            "days": 831,
            "yearly": {
              "2024": 0.3800176128504247,
              "2025": 0.2920416268413968,
              "2026": -0.12474915494700245
            }
          },
          "full": {
            "CAGR": 0.17924793201463052,
            "MDD": 0.36699251596686633,
            "Calmar": 0.4884239438572469,
            "Sharpe": 0.6738839756253941,
            "worst_day": -0.07728697539492568,
            "turnover": 69.83792312105565,
            "fee_drag": 0.06983792312105566,
            "funding_drag": 0.0009479204962707963,
            "missing_return_exposure": 0.25,
            "funding_coverage": 0.9908921399885255,
            "days": 1743,
            "yearly": {
              "2022": -0.04564154797313269,
              "2023": 0.3434236138467257,
              "2024": 0.5156727396463792,
              "2025": 0.2920416268413968,
              "2026": -0.12474915494700245
            }
          }
        }
      },
      {
        "config": {
          "signal": "resid_14",
          "k": 2,
          "r": 5,
          "liquidity": 0.2,
          "weighting": "equal"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.44595523449490426,
            "MDD": 0.292538862339941,
            "Calmar": 1.5244307403393391,
            "Sharpe": 1.1354328062369332,
            "worst_day": -0.05361893098271675,
            "turnover": 86.64747807017544,
            "fee_drag": 0.08664747807017545,
            "funding_drag": -0.004943797930372808,
            "missing_return_exposure": 0.25,
            "funding_coverage": 0.9931469298245614,
            "days": 912,
            "yearly": {
              "2022": 0.5827515237164449,
              "2023": 0.4516345628100087,
              "2024": 0.09369868253024394
            }
          },
          "OOS": {
            "CAGR": -0.030605715972915726,
            "MDD": 0.5731951710588779,
            "Calmar": -0.0533949298916406,
            "Sharpe": 0.15787051606515531,
            "worst_day": -0.10685934038987144,
            "turnover": 89.8225030084236,
            "fee_drag": 0.0898225030084236,
            "funding_drag": 0.012011964425391096,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902527,
            "days": 831,
            "yearly": {
              "2024": 0.5465388578904318,
              "2025": -0.09941344401200203,
              "2026": -0.3310723887776531
            }
          },
          "full": {
            "CAGR": 0.19498553972170463,
            "MDD": 0.5731951710588777,
            "Calmar": 0.34017303279352995,
            "Sharpe": 0.631451336382711,
            "worst_day": -0.10685934038987144,
            "turnover": 88.16121629374642,
            "fee_drag": 0.08816121629374643,
            "funding_drag": 0.003140102538726333,
            "missing_return_exposure": 0.25,
            "funding_coverage": 0.9912507171543317,
            "days": 1743,
            "yearly": {
              "2022": 0.5827515237164449,
              "2023": 0.4516345628100087,
              "2024": 0.6914475113565937,
              "2025": -0.09941344401200203,
              "2026": -0.3310723887776531
            }
          }
        }
      },
      {
        "config": {
          "signal": "resid_14",
          "k": 3,
          "r": 5,
          "liquidity": 0.2,
          "weighting": "equal"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.6159945604178967,
            "MDD": 0.2178820483650964,
            "Calmar": 2.827192809320843,
            "Sharpe": 1.6050395461025282,
            "worst_day": -0.07662754404278083,
            "turnover": 76.30847953216374,
            "fee_drag": 0.07630847953216374,
            "funding_drag": -0.0007707970211988329,
            "missing_return_exposure": 0.3333333333333333,
            "funding_coverage": 0.992141812865497,
            "days": 912,
            "yearly": {
              "2022": 0.6846605572629159,
              "2023": 0.6832793200136311,
              "2024": 0.16989155639501896
            }
          },
          "OOS": {
            "CAGR": 0.05504248689204605,
            "MDD": 0.4513592395272735,
            "Calmar": 0.12194828879473972,
            "Sharpe": 0.33175907767360074,
            "worst_day": -0.08932263316955602,
            "turnover": 81.11111111111111,
            "fee_drag": 0.0811111111111111,
            "funding_drag": 0.005366879181708784,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902526,
            "days": 831,
            "yearly": {
              "2024": 0.3262395657074997,
              "2025": 0.23888761914314505,
              "2026": -0.3124170685407758
            }
          },
          "full": {
            "CAGR": 0.31873488149742446,
            "MDD": 0.45135923952727364,
            "Calmar": 0.7061667372340668,
            "Sharpe": 0.9360273538653666,
            "worst_day": -0.08932263316955602,
            "turnover": 78.59820233314208,
            "fee_drag": 0.0785982023331421,
            "funding_drag": 0.0021554272614266582,
            "missing_return_exposure": 0.3333333333333333,
            "funding_coverage": 0.9907248039778158,
            "days": 1743,
            "yearly": {
              "2022": 0.6846605572629159,
              "2023": 0.6832793200136311,
              "2024": 0.5515564696781983,
              "2025": 0.23888761914314505,
              "2026": -0.3124170685407758
            }
          }
        }
      },
      {
        "config": {
          "signal": "resid_14",
          "k": 5,
          "r": 5,
          "liquidity": 0.2,
          "weighting": "equal"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.22436910246251518,
            "MDD": 0.17737240979944136,
            "Calmar": 1.2649605579369076,
            "Sharpe": 0.905018960336107,
            "worst_day": -0.06821506023001589,
            "turnover": 68.51754385964914,
            "fee_drag": 0.06851754385964913,
            "funding_drag": -0.0018828308881578967,
            "missing_return_exposure": 0.4,
            "funding_coverage": 0.9907894736842104,
            "days": 912,
            "yearly": {
              "2022": 0.15491493298390036,
              "2023": 0.3309986951098316,
              "2024": 0.07877990794752843
            }
          },
          "OOS": {
            "CAGR": 0.15342574843900225,
            "MDD": 0.24554866498091765,
            "Calmar": 0.6248282736577918,
            "Sharpe": 0.6211612087263324,
            "worst_day": -0.061033979114891945,
            "turnover": 74.93261131167269,
            "fee_drag": 0.0749326113116727,
            "funding_drag": 0.003564061606498195,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902526,
            "days": 831,
            "yearly": {
              "2024": 0.36145419015561364,
              "2025": 0.20742885675798806,
              "2026": -0.15808548193010596
            }
          },
          "full": {
            "CAGR": 0.19001746954428733,
            "MDD": 0.2512973949146031,
            "Calmar": 0.7561457993182135,
            "Sharpe": 0.7571992487000301,
            "worst_day": -0.06821506023001589,
            "turnover": 71.5760183591509,
            "fee_drag": 0.0715760183591509,
            "funding_drag": 0.0007140524526678133,
            "missing_return_exposure": 0.4,
            "funding_coverage": 0.9900172117039586,
            "days": 1743,
            "yearly": {
              "2022": 0.15491493298390036,
              "2023": 0.3309986951098316,
              "2024": 0.4687094259308491,
              "2025": 0.20742885675798806,
              "2026": -0.15808548193010596
            }
          }
        }
      },
      {
        "config": {
          "signal": "resid_14",
          "k": 6,
          "r": 5,
          "liquidity": 0.2,
          "weighting": "equal"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.1265851668669269,
            "MDD": 0.22373379795261328,
            "Calmar": 0.5657847317897744,
            "Sharpe": 0.6260892790117144,
            "worst_day": -0.06014679437747905,
            "turnover": 65.30244883040936,
            "fee_drag": 0.06530244883040935,
            "funding_drag": 0.007492273188505118,
            "missing_return_exposure": 0.3333333333333333,
            "funding_coverage": 0.9912280701754386,
            "days": 912,
            "yearly": {
              "2022": 0.14110910897164985,
              "2023": 0.09435014085733462,
              "2024": 0.07858826805517394
            }
          },
          "OOS": {
            "CAGR": 0.272238862170771,
            "MDD": 0.22310572425592134,
            "Calmar": 1.2202235647638056,
            "Sharpe": 1.0120055104848322,
            "worst_day": -0.057844462200476454,
            "turnover": 70.42318491776976,
            "fee_drag": 0.07042318491776976,
            "funding_drag": 0.0021165622342559165,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902527,
            "days": 831,
            "yearly": {
              "2024": 0.37956627440998525,
              "2025": 0.4628162547542045,
              "2026": -0.14268503360081408
            }
          },
          "full": {
            "CAGR": 0.19382147074191658,
            "MDD": 0.24613362828807328,
            "Calmar": 0.7874644033405672,
            "Sharpe": 0.8232070016680777,
            "worst_day": -0.06014679437747905,
            "turnover": 67.74383247274814,
            "fee_drag": 0.06774383247274814,
            "funding_drag": 0.004929326657821763,
            "missing_return_exposure": 0.3333333333333333,
            "funding_coverage": 0.9902467010900746,
            "days": 1743,
            "yearly": {
              "2022": 0.14110910897164985,
              "2023": 0.09435014085733462,
              "2024": 0.4879839985831955,
              "2025": 0.4628162547542045,
              "2026": -0.14268503360081408
            }
          }
        }
      },
      {
        "config": {
          "signal": "resid_14",
          "k": 4,
          "r": 4,
          "liquidity": 0.2,
          "weighting": "equal"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.3163125019717965,
            "MDD": 0.1847536372674694,
            "Calmar": 1.7120772648923182,
            "Sharpe": 1.091062040164102,
            "worst_day": -0.06510076369615958,
            "turnover": 82.04495614035088,
            "fee_drag": 0.08204495614035089,
            "funding_drag": 0.009622448074287285,
            "missing_return_exposure": 0.125,
            "funding_coverage": 0.9910910087719298,
            "days": 912,
            "yearly": {
              "2022": 0.3159871546533808,
              "2023": 0.31318039239243745,
              "2024": 0.1498944297266498
            }
          },
          "OOS": {
            "CAGR": 0.009032368042550587,
            "MDD": 0.4163789606012245,
            "Calmar": 0.021692661967137886,
            "Sharpe": 0.1892788955746784,
            "worst_day": -0.060574267852283925,
            "turnover": 86.74789410348977,
            "fee_drag": 0.08674789410348978,
            "funding_drag": 0.0074246429978941045,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902527,
            "days": 831,
            "yearly": {
              "2024": 0.3271962629407137,
              "2025": -0.10691616951589655,
              "2026": -0.1388805316860815
            }
          },
          "full": {
            "CAGR": 0.15961738042570928,
            "MDD": 0.41637896060122437,
            "Calmar": 0.3833464116324035,
            "Sharpe": 0.634312493017859,
            "worst_day": -0.06510076369615958,
            "turnover": 84.28714859437751,
            "fee_drag": 0.08428714859437753,
            "funding_drag": 0.00857461329604131,
            "missing_return_exposure": 0.125,
            "funding_coverage": 0.9901749856569134,
            "days": 1743,
            "yearly": {
              "2022": 0.3159871546533808,
              "2023": 0.31318039239243745,
              "2024": 0.5261355899095517,
              "2025": -0.10691616951589655,
              "2026": -0.1388805316860815
            }
          }
        }
      },
      {
        "config": {
          "signal": "resid_14",
          "k": 4,
          "r": 6,
          "liquidity": 0.2,
          "weighting": "equal"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.18592319617294306,
            "MDD": 0.2094875365159069,
            "Calmar": 0.8875143565346449,
            "Sharpe": 0.7367277181956698,
            "worst_day": -0.08747418687076391,
            "turnover": 66.73656798245614,
            "fee_drag": 0.06673656798245614,
            "funding_drag": 0.008805556295687137,
            "missing_return_exposure": 0.25,
            "funding_coverage": 0.9920504385964912,
            "days": 912,
            "yearly": {
              "2022": 0.1251042041906163,
              "2023": 0.2554514586361478,
              "2024": 0.08404494579596489
            }
          },
          "OOS": {
            "CAGR": 0.08216220048880474,
            "MDD": 0.3570689375542624,
            "Calmar": 0.2301017866509849,
            "Sharpe": 0.4042014782109185,
            "worst_day": -0.05695938450776428,
            "turnover": 71.59446450060169,
            "fee_drag": 0.07159446450060168,
            "funding_drag": 0.0030166382521058964,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902527,
            "days": 831,
            "yearly": {
              "2024": 0.34759341405815647,
              "2025": 0.08093844116949156,
              "2026": -0.17829865584360505
            }
          },
          "full": {
            "CAGR": 0.13526804849177965,
            "MDD": 0.3570689375542615,
            "Calmar": 0.378828943840078,
            "Sharpe": 0.5672697801483295,
            "worst_day": -0.08747418687076391,
            "turnover": 69.05263912794034,
            "fee_drag": 0.06905263912794034,
            "funding_drag": 0.006045607417766305,
            "missing_return_exposure": 0.25,
            "funding_coverage": 0.9906769936890418,
            "days": 1743,
            "yearly": {
              "2022": 0.1251042041906163,
              "2023": 0.2554514586361478,
              "2024": 0.46085182949767334,
              "2025": 0.08093844116949156,
              "2026": -0.17829865584360505
            }
          }
        }
      }
    ],
    "fraction_beating_baseline": {
      "IS": 0.75,
      "OOS": 0.125
    },
    "comparison": "Calmar",
    "lookback_applicable": true
  },
  {
    "selected": {
      "signal": "resid_21",
      "k": 8,
      "r": 7,
      "liquidity": 0.2,
      "weighting": "equal"
    },
    "neighbors": [
      {
        "config": {
          "signal": "resid_21_horizon18",
          "k": 8,
          "r": 7,
          "liquidity": 0.2,
          "weighting": "equal"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.2941907555224055,
            "MDD": 0.12648754858658262,
            "Calmar": 2.325847554243867,
            "Sharpe": 1.3883677772280538,
            "worst_day": -0.0401412474176952,
            "turnover": 44.052709899749374,
            "fee_drag": 0.044052709899749375,
            "funding_drag": -0.004075944036849937,
            "missing_return_exposure": 0.25,
            "funding_coverage": 0.9929413377192983,
            "days": 912,
            "yearly": {
              "2022": 0.12428849860048508,
              "2023": 0.446677177659371,
              "2024": 0.1710971197329001
            }
          },
          "OOS": {
            "CAGR": -0.034202866510646746,
            "MDD": 0.32419123914229,
            "Calmar": -0.10550213078285824,
            "Sharpe": -0.033276325577542294,
            "worst_day": -0.04777118767984878,
            "turnover": 49.63297232250301,
            "fee_drag": 0.049632972322503015,
            "funding_drag": 0.0019477164259927807,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902527,
            "days": 831,
            "yearly": {
              "2024": 0.17794290644920774,
              "2025": -0.03867166356294938,
              "2026": -0.1841814339973492
            }
          },
          "full": {
            "CAGR": 0.125630003407331,
            "MDD": 0.32419123914229064,
            "Calmar": 0.38751819370476814,
            "Sharpe": 0.6546531042034598,
            "worst_day": -0.04777118767984878,
            "turnover": 46.71317924760265,
            "fee_drag": 0.04671317924760266,
            "funding_drag": -0.0012040783772846477,
            "missing_return_exposure": 0.25,
            "funding_coverage": 0.9911431440045898,
            "days": 1743,
            "yearly": {
              "2022": 0.12428849860048508,
              "2023": 0.446677177659371,
              "2024": 0.379485544952469,
              "2025": -0.03867166356294938,
              "2026": -0.1841814339973492
            }
          }
        }
      },
      {
        "config": {
          "signal": "resid_21_horizon24",
          "k": 8,
          "r": 7,
          "liquidity": 0.2,
          "weighting": "equal"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.057095314115227724,
            "MDD": 0.16171841757638472,
            "Calmar": 0.353053875810155,
            "Sharpe": 0.374173847484913,
            "worst_day": -0.044348438085790365,
            "turnover": 38.91417998120301,
            "fee_drag": 0.03891417998120301,
            "funding_drag": -0.005351205024279449,
            "missing_return_exposure": 0.1875,
            "funding_coverage": 0.9920504385964912,
            "days": 912,
            "yearly": {
              "2022": -0.08616687665560807,
              "2023": 0.24007928465089612,
              "2024": 0.013761952576329062
            }
          },
          "OOS": {
            "CAGR": -0.08585477714276113,
            "MDD": 0.44665064500330254,
            "Calmar": -0.19221908241535465,
            "Sharpe": -0.26883802258105843,
            "worst_day": -0.04904862651371744,
            "turnover": 42.989620938628164,
            "fee_drag": 0.04298962093862816,
            "funding_drag": 0.0014121206528279182,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902527,
            "days": 831,
            "yearly": {
              "2024": 0.3478443664074331,
              "2025": -0.13271824883230166,
              "2026": -0.3026627646405615
            }
          },
          "full": {
            "CAGR": -0.013650507252037647,
            "MDD": 0.44665064500330254,
            "Calmar": -0.030561933369505634,
            "Sharpe": 0.04583819487734144,
            "worst_day": -0.04904862651371744,
            "turnover": 40.85720432751414,
            "fee_drag": 0.04085720432751414,
            "funding_drag": -0.002126693470822063,
            "missing_return_exposure": 0.1875,
            "funding_coverage": 0.9906769936890418,
            "days": 1743,
            "yearly": {
              "2022": -0.08616687665560807,
              "2023": 0.24007928465089612,
              "2024": 0.36639333665820484,
              "2025": -0.13271824883230166,
              "2026": -0.3026627646405615
            }
          }
        }
      },
      {
        "config": {
          "signal": "resid_21",
          "k": 6,
          "r": 7,
          "liquidity": 0.2,
          "weighting": "equal"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.23972997978612365,
            "MDD": 0.16352951794895498,
            "Calmar": 1.4659737446358418,
            "Sharpe": 1.0177632476536784,
            "worst_day": -0.051050223695736086,
            "turnover": 46.29203216374269,
            "fee_drag": 0.04629203216374269,
            "funding_drag": -0.001444273716191521,
            "missing_return_exposure": 0.16666666666666666,
            "funding_coverage": 0.9923245614035088,
            "days": 912,
            "yearly": {
              "2022": 0.04167974589428591,
              "2023": 0.4632844552027213,
              "2024": 0.122346443852827
            }
          },
          "OOS": {
            "CAGR": -0.10645691384492695,
            "MDD": 0.4814183185679187,
            "Calmar": -0.22113183013393778,
            "Sharpe": -0.2851559932667447,
            "worst_day": -0.05165053284152987,
            "turnover": 51.24348174889691,
            "fee_drag": 0.05124348174889692,
            "funding_drag": 0.007048838492779784,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902527,
            "days": 831,
            "yearly": {
              "2024": 0.34159137106724935,
              "2025": -0.155579881583366,
              "2026": -0.31683560275869416
            }
          },
          "full": {
            "CAGR": 0.060536699407329975,
            "MDD": 0.4814183185679197,
            "Calmar": 0.12574656400157175,
            "Sharpe": 0.35814955676456667,
            "worst_day": -0.05165053284152987,
            "turnover": 48.65270606234462,
            "fee_drag": 0.048652706062344626,
            "funding_drag": 0.0026049381287052975,
            "missing_return_exposure": 0.16666666666666666,
            "funding_coverage": 0.9908204245553643,
            "days": 1743,
            "yearly": {
              "2022": 0.04167974589428591,
              "2023": 0.4632844552027213,
              "2024": 0.5057303044209664,
              "2025": -0.155579881583366,
              "2026": -0.31683560275869416
            }
          }
        }
      },
      {
        "config": {
          "signal": "resid_21",
          "k": 7,
          "r": 7,
          "liquidity": 0.2,
          "weighting": "equal"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.2277487565045766,
            "MDD": 0.12730159293131693,
            "Calmar": 1.7890487562669695,
            "Sharpe": 1.059006800595569,
            "worst_day": -0.04538093118897912,
            "turnover": 43.909774436090224,
            "fee_drag": 0.043909774436090225,
            "funding_drag": -0.001876613710056392,
            "missing_return_exposure": 0.21428571428571427,
            "funding_coverage": 0.9920895989974937,
            "days": 912,
            "yearly": {
              "2022": 0.05056470238072053,
              "2023": 0.36525894198892495,
              "2024": 0.164163167939138
            }
          },
          "OOS": {
            "CAGR": -0.12320768526179782,
            "MDD": 0.45562650158730167,
            "Calmar": -0.2704137815350283,
            "Sharpe": -0.4247742053234107,
            "worst_day": -0.049774977821031796,
            "turnover": 49.068248237923335,
            "fee_drag": 0.04906824823792333,
            "funding_drag": 0.007140333990888775,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902526,
            "days": 831,
            "yearly": {
              "2024": 0.2661705369299645,
              "2025": -0.13383730356595758,
              "2026": -0.32407172789982064
            }
          },
          "full": {
            "CAGR": 0.04568406373396794,
            "MDD": 0.45562650158730233,
            "Calmar": 0.10026647610447313,
            "Sharpe": 0.3095183547438381,
            "worst_day": -0.049774977821031796,
            "turnover": 46.369150069666425,
            "fee_drag": 0.04636915006966642,
            "funding_drag": 0.0024223441439226285,
            "missing_return_exposure": 0.21428571428571427,
            "funding_coverage": 0.9906974838128022,
            "days": 1743,
            "yearly": {
              "2022": 0.05056470238072053,
              "2023": 0.36525894198892495,
              "2024": 0.47402910342358595,
              "2025": -0.13383730356595758,
              "2026": -0.32407172789982064
            }
          }
        }
      },
      {
        "config": {
          "signal": "resid_21",
          "k": 9,
          "r": 7,
          "liquidity": 0.2,
          "weighting": "equal"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.2837921127604113,
            "MDD": 0.0983495052538863,
            "Calmar": 2.885546928048193,
            "Sharpe": 1.4238170722180086,
            "worst_day": -0.04201212037133051,
            "turnover": 38.28764619883041,
            "fee_drag": 0.03828764619883041,
            "funding_drag": -0.004728541807208996,
            "missing_return_exposure": 0.2777777777777778,
            "funding_coverage": 0.9928728070175439,
            "days": 912,
            "yearly": {
              "2022": 0.17066802317923213,
              "2023": 0.39452109330663854,
              "2024": 0.14348189203701778
            }
          },
          "OOS": {
            "CAGR": -0.10172559693557393,
            "MDD": 0.407679125755133,
            "Calmar": -0.24952368298757108,
            "Sharpe": -0.40736297023314433,
            "worst_day": -0.04375659838679957,
            "turnover": 44.94785399117529,
            "fee_drag": 0.04494785399117529,
            "funding_drag": 0.002395942672817221,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902527,
            "days": 831,
            "yearly": {
              "2024": 0.19176582184412938,
              "2025": -0.043365437722623246,
              "2026": -0.31294934570707744
            }
          },
          "full": {
            "CAGR": 0.08281784309364393,
            "MDD": 0.407679125755132,
            "Calmar": 0.2031446739889929,
            "Sharpe": 0.4997172981983706,
            "worst_day": -0.04375659838679957,
            "turnover": 41.46299483648881,
            "fee_drag": 0.04146299483648882,
            "funding_drag": -0.0013318426661293704,
            "missing_return_exposure": 0.2777777777777778,
            "funding_coverage": 0.9911072862880091,
            "days": 1743,
            "yearly": {
              "2022": 0.17066802317923213,
              "2023": 0.39452109330663854,
              "2024": 0.36276263682737975,
              "2025": -0.043365437722623246,
              "2026": -0.31294934570707744
            }
          }
        }
      },
      {
        "config": {
          "signal": "resid_21",
          "k": 10,
          "r": 7,
          "liquidity": 0.2,
          "weighting": "equal"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.24335465297446124,
            "MDD": 0.10149802391375151,
            "Calmar": 2.397629466966304,
            "Sharpe": 1.307624654027889,
            "worst_day": -0.04144506328437425,
            "turnover": 36.25986842105264,
            "fee_drag": 0.03625986842105264,
            "funding_drag": -0.004872735106124687,
            "missing_return_exposure": 0.25,
            "funding_coverage": 0.9932017543859651,
            "days": 912,
            "yearly": {
              "2022": 0.14771719784029536,
              "2023": 0.35807948608996276,
              "2024": 0.10559966668762155
            }
          },
          "OOS": {
            "CAGR": -0.07220581552841998,
            "MDD": 0.38418943732144617,
            "Calmar": -0.18794326057435656,
            "Sharpe": -0.28000947377060187,
            "worst_day": -0.042148967644698554,
            "turnover": 42.82490974729242,
            "fee_drag": 0.04282490974729243,
            "funding_drag": 0.0014247564169675097,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902529,
            "days": 831,
            "yearly": {
              "2024": 0.2368689023785191,
              "2025": -0.017202192121119175,
              "2026": -0.3064002762938398
            }
          },
          "full": {
            "CAGR": 0.08137820727467981,
            "MDD": 0.3841894373214475,
            "Calmar": 0.21181791941508135,
            "Sharpe": 0.5096611871900837,
            "worst_day": -0.042148967644698554,
            "turnover": 39.38984509466438,
            "fee_drag": 0.03938984509466438,
            "funding_drag": -0.0018703166002786663,
            "missing_return_exposure": 0.25,
            "funding_coverage": 0.9912794033275962,
            "days": 1743,
            "yearly": {
              "2022": 0.14771719784029536,
              "2023": 0.35807948608996276,
              "2024": 0.36748184620597213,
              "2025": -0.017202192121119175,
              "2026": -0.3064002762938398
            }
          }
        }
      },
      {
        "config": {
          "signal": "resid_21",
          "k": 8,
          "r": 6,
          "liquidity": 0.2,
          "weighting": "equal"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.1429390821098846,
            "MDD": 0.14528542329402183,
            "Calmar": 0.983850126661442,
            "Sharpe": 0.7797746537270043,
            "worst_day": -0.038186397191371846,
            "turnover": 43.04501488095238,
            "fee_drag": 0.04304501488095239,
            "funding_drag": 0.0034425924949091496,
            "missing_return_exposure": 0.125,
            "funding_coverage": 0.9916784147869674,
            "days": 912,
            "yearly": {
              "2022": -0.007773127845822625,
              "2023": 0.2987607778854571,
              "2024": 0.08352285271832494
            }
          },
          "OOS": {
            "CAGR": 0.1268002584083452,
            "MDD": 0.23725468610530553,
            "Calmar": 0.534447856393719,
            "Sharpe": 0.6219290892446454,
            "worst_day": -0.04658752456103754,
            "turnover": 49.083935018050546,
            "fee_drag": 0.04908393501805055,
            "funding_drag": 0.0017911351045427194,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902527,
            "days": 831,
            "yearly": {
              "2024": 0.29179183785570784,
              "2025": 0.3008963128521436,
              "2026": -0.2190821609299688
            }
          },
          "full": {
            "CAGR": 0.13521603868931686,
            "MDD": 0.23725468610530476,
            "Calmar": 0.5699193592715873,
            "Sharpe": 0.6940405164479184,
            "worst_day": -0.04658752456103754,
            "turnover": 45.92415580690108,
            "fee_drag": 0.045924155806901075,
            "funding_drag": 0.002655236733925499,
            "missing_return_exposure": 0.125,
            "funding_coverage": 0.9904823375133185,
            "days": 1743,
            "yearly": {
              "2022": -0.007773127845822625,
              "2023": 0.2987607778854571,
              "2024": 0.3996859772716652,
              "2025": 0.3008963128521436,
              "2026": -0.2190821609299688
            }
          }
        }
      },
      {
        "config": {
          "signal": "resid_21",
          "k": 8,
          "r": 8,
          "liquidity": 0.2,
          "weighting": "equal"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.19513416847033827,
            "MDD": 0.14710875636461795,
            "Calmar": 1.3264619543563159,
            "Sharpe": 0.9856114804676526,
            "worst_day": -0.04631971673700408,
            "turnover": 38.45678649749374,
            "fee_drag": 0.03845678649749375,
            "funding_drag": 0.0023305824243225245,
            "missing_return_exposure": 0.25,
            "funding_coverage": 0.9921287593984962,
            "days": 912,
            "yearly": {
              "2022": 0.041850742685925146,
              "2023": 0.23419887108791348,
              "2024": 0.21407343523460232
            }
          },
          "OOS": {
            "CAGR": 0.017346267273111282,
            "MDD": 0.3276990118357883,
            "Calmar": 0.052933535490194236,
            "Sharpe": 0.18979324288548874,
            "worst_day": -0.04691086013168633,
            "turnover": 43.64846570397112,
            "fee_drag": 0.04364846570397113,
            "funding_drag": 0.0017797554828519859,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902527,
            "days": 831,
            "yearly": {
              "2024": 0.38872521169625385,
              "2025": -0.033752971463694825,
              "2026": -0.22500337987268948
            }
          },
          "full": {
            "CAGR": 0.10679712946047326,
            "MDD": 0.327699011835789,
            "Calmar": 0.3259000656187198,
            "Sharpe": 0.5769043982559152,
            "worst_day": -0.04691086013168633,
            "turnover": 40.93199327923941,
            "fee_drag": 0.04093199327923941,
            "funding_drag": 0.00206796785842349,
            "missing_return_exposure": 0.25,
            "funding_coverage": 0.9907179739365625,
            "days": 1743,
            "yearly": {
              "2022": 0.041850742685925146,
              "2023": 0.23419887108791348,
              "2024": 0.6860143883609731,
              "2025": -0.033752971463694825,
              "2026": -0.22500337987268948
            }
          }
        }
      }
    ],
    "fraction_beating_baseline": {
      "IS": 0.875,
      "OOS": 0.0
    },
    "comparison": "Calmar",
    "lookback_applicable": true
  },
  {
    "selected": {
      "signal": "resid_21",
      "k": 10,
      "r": 7,
      "liquidity": 0.2,
      "weighting": "equal"
    },
    "neighbors": [
      {
        "config": {
          "signal": "resid_21_horizon18",
          "k": 10,
          "r": 7,
          "liquidity": 0.2,
          "weighting": "equal"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.2476717130806212,
            "MDD": 0.10300469602970952,
            "Calmar": 2.4044701127916106,
            "Sharpe": 1.3442754529883085,
            "worst_day": -0.034295142349546004,
            "turnover": 39.93045112781955,
            "fee_drag": 0.03993045112781955,
            "funding_drag": -0.004195633320018796,
            "missing_return_exposure": 0.25,
            "funding_coverage": 0.9922697368421053,
            "days": 912,
            "yearly": {
              "2022": 0.09687382771359077,
              "2023": 0.33257741584803635,
              "2024": 0.18924149847304106
            }
          },
          "OOS": {
            "CAGR": -0.06313028729936043,
            "MDD": 0.3247384893075944,
            "Calmar": -0.1944034642581681,
            "Sharpe": -0.2067150503518728,
            "worst_day": -0.05608658779893072,
            "turnover": 46.119133574007236,
            "fee_drag": 0.04611913357400723,
            "funding_drag": 0.0013096727075812273,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902529,
            "days": 831,
            "yearly": {
              "2024": 0.16619019862045858,
              "2025": -0.08610705552169107,
              "2026": -0.19117051942234586
            }
          },
          "full": {
            "CAGR": 0.08838059147265587,
            "MDD": 0.32473848930759286,
            "Calmar": 0.27215927394717176,
            "Sharpe": 0.5354372220304283,
            "worst_day": -0.05608658779893072,
            "turnover": 42.88099336119991,
            "fee_drag": 0.04288099336119991,
            "funding_drag": -0.0015709004979100074,
            "missing_return_exposure": 0.25,
            "funding_coverage": 0.9907917383821,
            "days": 1743,
            "yearly": {
              "2022": 0.09687382771359077,
              "2023": 0.33257741584803635,
              "2024": 0.38688177931196943,
              "2025": -0.08610705552169107,
              "2026": -0.19117051942234586
            }
          }
        }
      },
      {
        "config": {
          "signal": "resid_21_horizon24",
          "k": 10,
          "r": 7,
          "liquidity": 0.2,
          "weighting": "equal"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.11593944822856117,
            "MDD": 0.107707157154462,
            "Calmar": 1.0764321637632057,
            "Sharpe": 0.7072163848917298,
            "worst_day": -0.040260143579289864,
            "turnover": 34.521773182957396,
            "fee_drag": 0.0345217731829574,
            "funding_drag": 0.00170071764293546,
            "missing_return_exposure": 0.25,
            "funding_coverage": 0.99265350877193,
            "days": 912,
            "yearly": {
              "2022": 0.0021943200353908843,
              "2023": 0.23430112743855092,
              "2024": 0.06331820954068634
            }
          },
          "OOS": {
            "CAGR": -0.09505385113318565,
            "MDD": 0.43328343536085157,
            "Calmar": -0.21938030253573373,
            "Sharpe": -0.3824495648640792,
            "worst_day": -0.05044027005341101,
            "turnover": 40.54091456077016,
            "fee_drag": 0.04054091456077017,
            "funding_drag": 0.0008100867539109508,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902529,
            "days": 831,
            "yearly": {
              "2024": 0.24546818894119382,
              "2025": -0.12243786815189428,
              "2026": -0.2711604443945952
            }
          },
          "full": {
            "CAGR": 0.009826019636153704,
            "MDD": 0.4332834353608501,
            "Calmar": 0.02267804128715498,
            "Sharpe": 0.14673654199502797,
            "worst_day": -0.05044027005341101,
            "turnover": 37.3914843045652,
            "fee_drag": 0.0373914843045652,
            "funding_drag": 0.0012760967199409873,
            "missing_return_exposure": 0.25,
            "funding_coverage": 0.9909925415949513,
            "days": 1743,
            "yearly": {
              "2022": 0.0021943200353908843,
              "2023": 0.23430112743855092,
              "2024": 0.3243290047048293,
              "2025": -0.12243786815189428,
              "2026": -0.2711604443945952
            }
          }
        }
      },
      {
        "config": {
          "signal": "resid_21",
          "k": 8,
          "r": 7,
          "liquidity": 0.2,
          "weighting": "equal"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.2724718227087237,
            "MDD": 0.11038302319345772,
            "Calmar": 2.4684214549114905,
            "Sharpe": 1.2941964895564446,
            "worst_day": -0.04197983021258045,
            "turnover": 41.12253289473684,
            "fee_drag": 0.041122532894736843,
            "funding_drag": -0.002549129247434994,
            "missing_return_exposure": 0.1875,
            "funding_coverage": 0.9925986842105263,
            "days": 912,
            "yearly": {
              "2022": 0.16295016564229647,
              "2023": 0.3398546710997814,
              "2024": 0.1718129206412753
            }
          },
          "OOS": {
            "CAGR": -0.14681007951896874,
            "MDD": 0.464975160510152,
            "Calmar": -0.3157374672614654,
            "Sharpe": -0.5910762619217292,
            "worst_day": -0.047668086220372,
            "turnover": 46.88778580024068,
            "fee_drag": 0.04688778580024068,
            "funding_drag": 0.003891731791516246,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902527,
            "days": 831,
            "yearly": {
              "2024": 0.17798602486004933,
              "2025": -0.13533863713891792,
              "2026": -0.31604939127638987
            }
          },
          "full": {
            "CAGR": 0.05167303135659429,
            "MDD": 0.46497516051015164,
            "Calmar": 0.11113073502657811,
            "Sharpe": 0.3424463434207665,
            "worst_day": -0.047668086220372,
            "turnover": 43.87119908204246,
            "fee_drag": 0.04387119908204246,
            "funding_drag": 0.0005216427108945989,
            "missing_return_exposure": 0.1875,
            "funding_coverage": 0.9909638554216867,
            "days": 1743,
            "yearly": {
              "2022": 0.16295016564229647,
              "2023": 0.3398546710997814,
              "2024": 0.38037924426586023,
              "2025": -0.13533863713891792,
              "2026": -0.31604939127638987
            }
          }
        }
      },
      {
        "config": {
          "signal": "resid_21",
          "k": 9,
          "r": 7,
          "liquidity": 0.2,
          "weighting": "equal"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.2837921127604113,
            "MDD": 0.0983495052538863,
            "Calmar": 2.885546928048193,
            "Sharpe": 1.4238170722180086,
            "worst_day": -0.04201212037133051,
            "turnover": 38.28764619883041,
            "fee_drag": 0.03828764619883041,
            "funding_drag": -0.004728541807208996,
            "missing_return_exposure": 0.2777777777777778,
            "funding_coverage": 0.9928728070175439,
            "days": 912,
            "yearly": {
              "2022": 0.17066802317923213,
              "2023": 0.39452109330663854,
              "2024": 0.14348189203701778
            }
          },
          "OOS": {
            "CAGR": -0.10172559693557393,
            "MDD": 0.407679125755133,
            "Calmar": -0.24952368298757108,
            "Sharpe": -0.40736297023314433,
            "worst_day": -0.04375659838679957,
            "turnover": 44.94785399117529,
            "fee_drag": 0.04494785399117529,
            "funding_drag": 0.002395942672817221,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902527,
            "days": 831,
            "yearly": {
              "2024": 0.19176582184412938,
              "2025": -0.043365437722623246,
              "2026": -0.31294934570707744
            }
          },
          "full": {
            "CAGR": 0.08281784309364393,
            "MDD": 0.407679125755132,
            "Calmar": 0.2031446739889929,
            "Sharpe": 0.4997172981983706,
            "worst_day": -0.04375659838679957,
            "turnover": 41.46299483648881,
            "fee_drag": 0.04146299483648882,
            "funding_drag": -0.0013318426661293704,
            "missing_return_exposure": 0.2777777777777778,
            "funding_coverage": 0.9911072862880091,
            "days": 1743,
            "yearly": {
              "2022": 0.17066802317923213,
              "2023": 0.39452109330663854,
              "2024": 0.36276263682737975,
              "2025": -0.043365437722623246,
              "2026": -0.31294934570707744
            }
          }
        }
      },
      {
        "config": {
          "signal": "resid_21",
          "k": 11,
          "r": 7,
          "liquidity": 0.2,
          "weighting": "equal"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.23584958887705731,
            "MDD": 0.09938821176839086,
            "Calmar": 2.373013707366715,
            "Sharpe": 1.3215557402347191,
            "worst_day": -0.0385607319607002,
            "turnover": 34.78269537480064,
            "fee_drag": 0.03478269537480064,
            "funding_drag": -0.005243242905915356,
            "missing_return_exposure": 0.2727272727272727,
            "funding_coverage": 0.993072169059011,
            "days": 912,
            "yearly": {
              "2022": 0.1483399395520495,
              "2023": 0.37005389929104915,
              "2024": 0.07889688765489744
            }
          },
          "OOS": {
            "CAGR": -0.06594934856606416,
            "MDD": 0.3440871021923566,
            "Calmar": -0.19166469229990546,
            "Sharpe": -0.2693978394870126,
            "worst_day": -0.042988772272067655,
            "turnover": 41.28760529482551,
            "fee_drag": 0.041287605294825516,
            "funding_drag": 0.0020802632151843345,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902526,
            "days": 831,
            "yearly": {
              "2024": 0.2058624191193934,
              "2025": -0.015243242374803123,
              "2026": -0.2790332151041439
            }
          },
          "full": {
            "CAGR": 0.08141747722576387,
            "MDD": 0.3440871021923583,
            "Calmar": 0.23661880002769847,
            "Sharpe": 0.5257249831439532,
            "worst_day": -0.042988772272067655,
            "turnover": 37.88400354665414,
            "fee_drag": 0.03788400354665415,
            "funding_drag": -0.001751657371415159,
            "missing_return_exposure": 0.2727272727272727,
            "funding_coverage": 0.9912115996453345,
            "days": 1743,
            "yearly": {
              "2022": 0.1483399395520495,
              "2023": 0.37005389929104915,
              "2024": 0.30100121092791965,
              "2025": -0.015243242374803123,
              "2026": -0.2790332151041439
            }
          }
        }
      },
      {
        "config": {
          "signal": "resid_21",
          "k": 12,
          "r": 7,
          "liquidity": 0.2,
          "weighting": "equal"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.21682339393111238,
            "MDD": 0.0961620761038886,
            "Calmar": 2.2547703077548724,
            "Sharpe": 1.2844164490273442,
            "worst_day": -0.03538771646473937,
            "turnover": 33.6881562333865,
            "fee_drag": 0.0336881562333865,
            "funding_drag": 0.00028377490002230797,
            "missing_return_exposure": 0.2727272727272727,
            "funding_coverage": 0.993072169059011,
            "days": 912,
            "yearly": {
              "2022": 0.12245796917243457,
              "2023": 0.37370962413228126,
              "2024": 0.0589783902715908
            }
          },
          "OOS": {
            "CAGR": -0.04903619893125222,
            "MDD": 0.31913399585276503,
            "Calmar": -0.153653949652783,
            "Sharpe": -0.1928431849217814,
            "worst_day": -0.039550367335437375,
            "turnover": 39.494083433614115,
            "fee_drag": 0.03949408343361412,
            "funding_drag": 0.0016300006167268362,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902526,
            "days": 831,
            "yearly": {
              "2024": 0.1974563501169011,
              "2025": 0.0032554039636816245,
              "2026": -0.25764014594428974
            }
          },
          "full": {
            "CAGR": 0.0818909195817894,
            "MDD": 0.3191339958527657,
            "Calmar": 0.256603560404045,
            "Sharpe": 0.5465138247018884,
            "worst_day": -0.039550367335437375,
            "turnover": 36.456214468262665,
            "fee_drag": 0.036456214468262665,
            "funding_drag": 0.0009256071264029523,
            "missing_return_exposure": 0.2727272727272727,
            "funding_coverage": 0.9912115996453345,
            "days": 1743,
            "yearly": {
              "2022": 0.12245796917243457,
              "2023": 0.37370962413228126,
              "2024": 0.26808039806728967,
              "2025": 0.0032554039636816245,
              "2026": -0.25764014594428974
            }
          }
        }
      },
      {
        "config": {
          "signal": "resid_21",
          "k": 10,
          "r": 6,
          "liquidity": 0.2,
          "weighting": "equal"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.11537475276604292,
            "MDD": 0.15795226138051743,
            "Calmar": 0.7304406518631444,
            "Sharpe": 0.7060585280383468,
            "worst_day": -0.038239161759992424,
            "turnover": 38.59448099415205,
            "fee_drag": 0.03859448099415205,
            "funding_drag": 0.0023190944605002086,
            "missing_return_exposure": 0.2,
            "funding_coverage": 0.9916109718741299,
            "days": 912,
            "yearly": {
              "2022": 0.013228329855490273,
              "2023": 0.19853360339632076,
              "2024": 0.08175652941912981
            }
          },
          "OOS": {
            "CAGR": 0.055336678029500375,
            "MDD": 0.2634159531612317,
            "Calmar": 0.21007337393734044,
            "Sharpe": 0.3615216444538238,
            "worst_day": -0.04289133681301971,
            "turnover": 46.777978339350184,
            "fee_drag": 0.04677797833935019,
            "funding_drag": 0.001300769738267148,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902529,
            "days": 831,
            "yearly": {
              "2024": 0.21904025622804646,
              "2025": 0.22002568582518478,
              "2026": -0.2399054304668129
            }
          },
          "full": {
            "CAGR": 0.08633625080058338,
            "MDD": 0.2634159531612299,
            "Calmar": 0.327756347952621,
            "Sharpe": 0.525272365773565,
            "worst_day": -0.04289133681301971,
            "turnover": 42.496079556320524,
            "fee_drag": 0.042496079556320523,
            "funding_drag": 0.0018335936893150836,
            "missing_return_exposure": 0.2,
            "funding_coverage": 0.9904470489668427,
            "days": 1743,
            "yearly": {
              "2022": 0.013228329855490273,
              "2023": 0.19853360339632076,
              "2024": 0.3187047567994581,
              "2025": 0.22002568582518478,
              "2026": -0.2399054304668129
            }
          }
        }
      },
      {
        "config": {
          "signal": "resid_21",
          "k": 10,
          "r": 8,
          "liquidity": 0.2,
          "weighting": "equal"
        },
        "metrics": {
          "IS": {
            "CAGR": 0.15342957585073802,
            "MDD": 0.11268229705742272,
            "Calmar": 1.3616120709054285,
            "Sharpe": 0.8922761668776562,
            "worst_day": -0.03878708812482434,
            "turnover": 34.54464285714286,
            "fee_drag": 0.03454464285714286,
            "funding_drag": 0.001976329263001254,
            "missing_return_exposure": 0.2,
            "funding_coverage": 0.9918546365914788,
            "days": 912,
            "yearly": {
              "2022": 0.054416717447418606,
              "2023": 0.20696357703002333,
              "2024": 0.12249997884042152
            }
          },
          "OOS": {
            "CAGR": 0.037459674061702586,
            "MDD": 0.27162370882272846,
            "Calmar": 0.1379101781065442,
            "Sharpe": 0.2817379597644516,
            "worst_day": -0.047753194886271944,
            "turnover": 40.14560770156439,
            "fee_drag": 0.04014560770156439,
            "funding_drag": 8.322351383874834e-05,
            "missing_return_exposure": 0.0,
            "funding_coverage": 0.9891696750902529,
            "days": 831,
            "yearly": {
              "2024": 0.3407924946199301,
              "2025": 0.04778724750134655,
              "2026": -0.22602451387712397
            }
          },
          "full": {
            "CAGR": 0.0966056072882635,
            "MDD": 0.27162370882272757,
            "Calmar": 0.3556597018241591,
            "Sharpe": 0.5781772528839925,
            "worst_day": -0.047753194886271944,
            "turnover": 37.214982378493566,
            "fee_drag": 0.03721498237849357,
            "funding_drag": 0.0010737642156380635,
            "missing_return_exposure": 0.2,
            "funding_coverage": 0.9905745430702403,
            "days": 1743,
            "yearly": {
              "2022": 0.054416717447418606,
              "2023": 0.20696357703002333,
              "2024": 0.5050395468402704,
              "2025": 0.04778724750134655,
              "2026": -0.22602451387712397
            }
          }
        }
      }
    ],
    "fraction_beating_baseline": {
      "IS": 0.875,
      "OOS": 0.0
    },
    "comparison": "Calmar",
    "lookback_applicable": true
  }
]
```

## survivorship

```json
{
  "comparisons": {
    "all": {
      "symbols": [
        "BTC",
        "ETH",
        "BNB",
        "XRP",
        "SOL",
        "TRX",
        "DOGE",
        "ZEC",
        "LINK",
        "XMR",
        "ADA",
        "XLM",
        "BCH",
        "LTC",
        "HBAR",
        "AVAX",
        "SUI",
        "UNI",
        "NEAR",
        "TAO",
        "AAVE",
        "ONDO",
        "THETA",
        "DOT",
        "ENA",
        "WLD",
        "ICP",
        "ETC",
        "POL",
        "QNT",
        "ALGO",
        "ATOM",
        "RENDER",
        "JUP",
        "ARB",
        "FIL",
        "VET",
        "CAKE",
        "LDO",
        "CRV",
        "INJ",
        "OP",
        "APT",
        "IMX",
        "STX"
      ],
      "baseline": {
        "IS": {
          "CAGR": 0.13660407604998626,
          "MDD": 0.16831464470042334,
          "Calmar": 0.8115994677297541,
          "Sharpe": 0.6909801350002572,
          "worst_day": -0.061029440731136364,
          "turnover": 82.9954769736842,
          "fee_drag": 0.08299547697368422,
          "funding_drag": 0.006730461657529242,
          "missing_return_exposure": 0.375,
          "funding_coverage": 0.9851745248538013,
          "days": 912,
          "yearly": {
            "2022": -0.10226506198397234,
            "2023": 0.3034837016928802,
            "2024": 0.17677413243764661
          }
        },
        "OOS": {
          "CAGR": 0.25588525388916583,
          "MDD": 0.2136145222467204,
          "Calmar": 1.1978832300250803,
          "Sharpe": 1.0332196767000126,
          "worst_day": -0.08622482059474879,
          "turnover": 90.31663658243082,
          "fee_drag": 0.09031663658243082,
          "funding_drag": 0.002921650131618532,
          "missing_return_exposure": 0.0,
          "funding_coverage": 0.9891696750902527,
          "days": 831,
          "yearly": {
            "2024": 0.2802023551205901,
            "2025": 0.3419985039889901,
            "2026": -0.02220020250962107
          }
        },
        "full": {
          "CAGR": 0.19198976977656934,
          "MDD": 0.21361452224671995,
          "Calmar": 0.8987674047498769,
          "Sharpe": 0.8636554407044613,
          "worst_day": -0.08622482059474879,
          "turnover": 86.48594377510041,
          "fee_drag": 0.08648594377510041,
          "funding_drag": 0.004914556678738764,
          "missing_return_exposure": 0.375,
          "funding_coverage": 0.9870792694587875,
          "days": 1743,
          "yearly": {
            "2022": -0.10226506198397234,
            "2023": 0.3034837016928802,
            "2024": 0.5065090157916632,
            "2025": 0.3419985039889901,
            "2026": -0.02220020250962107
          }
        }
      },
      "selected": {
        "IS": {
          "CAGR": 0.48000927742366617,
          "MDD": 0.17094344435056164,
          "Calmar": 2.8080005012610423,
          "Sharpe": 1.4699486245500335,
          "worst_day": -0.07392182592936669,
          "turnover": 73.06231305738328,
          "fee_drag": 0.07306231305738328,
          "funding_drag": -0.0018931425866888071,
          "missing_return_exposure": 0.3571428571428571,
          "funding_coverage": 0.9917893692564745,
          "days": 912,
          "yearly": {
            "2022": 0.4441345782743231,
            "2023": 0.5697531819183004,
            "2024": 0.17486730083707558
          }
        },
        "OOS": {
          "CAGR": 0.11365149170344413,
          "MDD": 0.3850632395390079,
          "Calmar": 0.29515019880761934,
          "Sharpe": 0.4821055110711363,
          "worst_day": -0.06991072311910884,
          "turnover": 78.78372142533856,
          "fee_drag": 0.07878372142533854,
          "funding_drag": 0.006173709619246725,
          "missing_return_exposure": 0.0,
          "funding_coverage": 0.9891696750902527,
          "days": 831,
          "yearly": {
            "2024": 0.450569169270314,
            "2025": 0.14716028449025864,
            "2026": -0.23215746010988636
          }
        },
        "full": {
          "CAGR": 0.292340169060167,
          "MDD": 0.38506323953900834,
          "Calmar": 0.7592004092890094,
          "Sharpe": 0.9573376258152716,
          "worst_day": -0.07392182592936669,
          "turnover": 75.79007573883527,
          "fee_drag": 0.07579007573883527,
          "funding_drag": 0.001952843749015397,
          "missing_return_exposure": 0.3571428571428571,
          "funding_coverage": 0.9905403928639729,
          "days": 1743,
          "yearly": {
            "2022": 0.4441345782743231,
            "2023": 0.5697531819183004,
            "2024": 0.7042262845780938,
            "2025": 0.14716028449025864,
            "2026": -0.23215746010988636
          }
        }
      }
    },
    "listed_by_2022": {
      "symbols": [
        "BTC",
        "ETH",
        "BNB",
        "XRP",
        "SOL",
        "TRX",
        "DOGE",
        "ZEC",
        "LINK",
        "XMR",
        "ADA",
        "XLM",
        "BCH",
        "LTC",
        "HBAR",
        "AVAX",
        "UNI",
        "NEAR",
        "AAVE",
        "THETA",
        "DOT",
        "ICP",
        "ETC",
        "ALGO",
        "ATOM",
        "FIL",
        "VET",
        "CRV"
      ],
      "baseline": {
        "IS": {
          "CAGR": 0.11952814460233596,
          "MDD": 0.13732456823809092,
          "Calmar": 0.8704061198656031,
          "Sharpe": 0.6970899480943618,
          "worst_day": -0.04977469607562002,
          "turnover": 77.0422149122807,
          "fee_drag": 0.07704221491228071,
          "funding_drag": 0.006344244781843933,
          "missing_return_exposure": 0.375,
          "funding_coverage": 0.9849689327485381,
          "days": 912,
          "yearly": {
            "2022": -0.040962956640677395,
            "2023": 0.3186357422442321,
            "2024": 0.04847998226279282
          }
        },
        "OOS": {
          "CAGR": 0.16712223358067746,
          "MDD": 0.1596409441222918,
          "Calmar": 1.0468632248419596,
          "Sharpe": 0.8389685965953254,
          "worst_day": -0.07101651314251733,
          "turnover": 78.29271961492178,
          "fee_drag": 0.07829271961492178,
          "funding_drag": -0.0010929616990072197,
          "missing_return_exposure": 0.0,
          "funding_coverage": 0.9891696750902527,
          "days": 831,
          "yearly": {
            "2024": 0.20287355080189484,
            "2025": 0.34688237582505255,
            "2026": -0.1224841723686283
          }
        },
        "full": {
          "CAGR": 0.14197223555444727,
          "MDD": 0.15964094412229102,
          "Calmar": 0.8893221994834305,
          "Sharpe": 0.7677953379745347,
          "worst_day": -0.07101651314251733,
          "turnover": 77.63841078600115,
          "fee_drag": 0.07763841078600116,
          "funding_drag": 0.0027984509863262595,
          "missing_return_exposure": 0.375,
          "funding_coverage": 0.9869716963090458,
          "days": 1743,
          "yearly": {
            "2022": -0.040962956640677395,
            "2023": 0.3186357422442321,
            "2024": 0.2611888392091526,
            "2025": 0.34688237582505255,
            "2026": -0.1224841723686283
          }
        }
      },
      "selected": {
        "IS": {
          "CAGR": 0.23286588462136182,
          "MDD": 0.1690727927110831,
          "Calmar": 1.3773113987611854,
          "Sharpe": 0.9462102008671749,
          "worst_day": -0.08593498317183834,
          "turnover": 71.49362513856758,
          "fee_drag": 0.07149362513856758,
          "funding_drag": 0.0018233789364921103,
          "missing_return_exposure": 0.3571428571428571,
          "funding_coverage": 0.9917893692564745,
          "days": 912,
          "yearly": {
            "2022": 0.4073539903487533,
            "2023": 0.16205114094814155,
            "2024": 0.03165967479670462
          }
        },
        "OOS": {
          "CAGR": 0.35620896709297534,
          "MDD": 0.29334777827225067,
          "Calmar": 1.2142889548745257,
          "Sharpe": 1.107428933777611,
          "worst_day": -0.1390398731390291,
          "turnover": 71.25981319122114,
          "fee_drag": 0.07125981319122114,
          "funding_drag": -0.0015375613496361232,
          "missing_return_exposure": 0.0,
          "funding_coverage": 0.9891696750902527,
          "days": 831,
          "yearly": {
            "2024": 0.3470744191760615,
            "2025": 0.595955989108911,
            "2026": -0.06919838510759024
          }
        },
        "full": {
          "CAGR": 0.290205862125827,
          "MDD": 0.2933477782722509,
          "Calmar": 0.989289449659619,
          "Sharpe": 1.025833458862362,
          "worst_day": -0.1390398731390291,
          "turnover": 71.382151972621,
          "fee_drag": 0.071382151972621,
          "funding_drag": 0.00022100293088536156,
          "missing_return_exposure": 0.3571428571428571,
          "funding_coverage": 0.9905403928639729,
          "days": 1743,
          "yearly": {
            "2022": 0.4073539903487533,
            "2023": 0.16205114094814155,
            "2024": 0.3897223572141353,
            "2025": 0.595955989108911,
            "2026": -0.06919838510759024
          }
        }
      }
    },
    "drop_top5": {
      "symbols": [
        "AAVE",
        "ADA",
        "ALGO",
        "APT",
        "ARB",
        "ATOM",
        "AVAX",
        "BCH",
        "BNB",
        "CAKE",
        "CRV",
        "DOGE",
        "DOT",
        "ENA",
        "ETC",
        "ETH",
        "FIL",
        "HBAR",
        "ICP",
        "IMX",
        "JUP",
        "LDO",
        "LINK",
        "LTC",
        "NEAR",
        "ONDO",
        "OP",
        "POL",
        "QNT",
        "RENDER",
        "SOL",
        "STX",
        "SUI",
        "TAO",
        "THETA",
        "UNI",
        "VET",
        "WLD",
        "XLM",
        "XRP"
      ],
      "baseline": {
        "IS": {
          "CAGR": 0.17079383162142814,
          "MDD": 0.15909470892595734,
          "Calmar": 1.0735355862834859,
          "Sharpe": 0.8562265230244754,
          "worst_day": -0.05438682257994909,
          "turnover": 78.44298245614036,
          "fee_drag": 0.07844298245614036,
          "funding_drag": 0.009684963262518278,
          "missing_return_exposure": 0.375,
          "funding_coverage": 0.9839409722222223,
          "days": 912,
          "yearly": {
            "2022": -0.059545729988646046,
            "2023": 0.3447490090337728,
            "2024": 0.17254181608686192
          }
        },
        "OOS": {
          "CAGR": 0.1771907380262392,
          "MDD": 0.1641209680426594,
          "Calmar": 1.079634979853291,
          "Sharpe": 0.8609422089639996,
          "worst_day": -0.046764899655998504,
          "turnover": 88.34010228640193,
          "fee_drag": 0.08834010228640193,
          "funding_drag": 0.006669885533243081,
          "missing_return_exposure": 0.0,
          "funding_coverage": 0.9891696750902527,
          "days": 831,
          "yearly": {
            "2024": 0.23852807797083853,
            "2025": 0.10227946360803086,
            "2026": 0.06194076660402659
          }
        },
        "full": {
          "CAGR": 0.1738393001966161,
          "MDD": 0.16650792232627454,
          "Calmar": 1.0440302044966703,
          "Sharpe": 0.8586489354410332,
          "worst_day": -0.05438682257994909,
          "turnover": 83.16157487091222,
          "fee_drag": 0.08316157487091223,
          "funding_drag": 0.008247482142020464,
          "missing_return_exposure": 0.375,
          "funding_coverage": 0.9864338305603366,
          "days": 1743,
          "yearly": {
            "2022": -0.059545729988646046,
            "2023": 0.3447490090337728,
            "2024": 0.45222596181849917,
            "2025": 0.10227946360803086,
            "2026": 0.06194076660402659
          }
        }
      },
      "selected": {
        "IS": {
          "CAGR": 0.3757724612137383,
          "MDD": 0.1956025550167534,
          "Calmar": 1.9211020080057408,
          "Sharpe": 1.2411116471999761,
          "worst_day": -0.07513828421222757,
          "turnover": 71.3444735662434,
          "fee_drag": 0.0713444735662434,
          "funding_drag": 0.014029271203503356,
          "missing_return_exposure": 0.3402777777777778,
          "funding_coverage": 0.992328022550062,
          "days": 912,
          "yearly": {
            "2022": 0.43931137564954437,
            "2023": 0.31458428100480473,
            "2024": 0.17282589745360255
          }
        },
        "OOS": {
          "CAGR": 0.10663448649058704,
          "MDD": 0.26570749388582426,
          "Calmar": 0.4013228416373095,
          "Sharpe": 0.47279639122748235,
          "worst_day": -0.06212258680747673,
          "turnover": 76.38711841431872,
          "fee_drag": 0.07638711841431871,
          "funding_drag": 0.007343431115718841,
          "missing_return_exposure": 0.0,
          "funding_coverage": 0.9891696750902527,
          "days": 831,
          "yearly": {
            "2024": 0.2917112004336304,
            "2025": 0.041147324863672896,
            "2026": -0.06350105572361953
          }
        },
        "full": {
          "CAGR": 0.2401441662900594,
          "MDD": 0.2728647839266318,
          "Calmar": 0.8800848641377981,
          "Sharpe": 0.8526202543377739,
          "worst_day": -0.07513828421222757,
          "turnover": 73.7486261013843,
          "fee_drag": 0.0737486261013843,
          "funding_drag": 0.010841702005024339,
          "missing_return_exposure": 0.3402777777777778,
          "funding_coverage": 0.9908222355511512,
          "days": 1743,
          "yearly": {
            "2022": 0.43931137564954437,
            "2023": 0.31458428100480473,
            "2024": 0.5149523478994402,
            "2025": 0.041147324863672896,
            "2026": -0.06350105572361953
          }
        }
      }
    }
  },
  "dropped_top5": [
    "ZEC",
    "TRX",
    "INJ",
    "XMR",
    "BTC"
  ]
}
```

현재 고정된 45종목은 상장폐지·실패 종목이 누락된 생존자 집합일 수 있다. 과거 상장 조건은 미래 상장을 미리 거래하는 오류를 막지만 상장폐지 생존자 편향을 제거하지 못한다. 모멘텀 롱의 성과를 상향 편향시킬 가능성이 있고, 숏에서 실패 종목이 빠지는 효과는 반대 방향이므로 달러중립 전략의 순 편향 방향은 자료 없이 확정할 수 없다. 2022년 이전 상장 부분집합도 생존자 집합이다. 사후 최고 수익 5종목 제거는 미래 정보를 쓰는 스트레스이며 실행 가능한 선택 규칙이 아니다.

## failures

소스 누락은 metadata에 보고한다. 가격 결측 구간은 수익률 0으로 계산하고 관측 결측 시 비중을 청산한다. 청산된 종목은 다음 적격 리밸런스까지 제외하며, 남은 양측 비중 재정규화로 달러중립을 유지한다. 실제 상장폐지·거래정지 청산가격이 없으므로 이 처리는 손실을 과소평가할 수 있다. JSON missing_return_exposure로 영향 구간의 보유 노출 합계를 보고한다. 펀딩 누락=0은 carry와 비용 추정에 편향을 줄 수 있다. funding_coverage는 실제 펀딩 관측이 있는 일자의 보유 절대비중 평균이며 지급 이벤트 전체의 완전성을 보장하지 않는다.

## recommendation

(자동 생성 문구를 수정함) 결론: **단순 14일 수익률 랭크가 사실상 최선. 교체 근거 없음.**
- IS 최고 신호들(resid_14 K4, resid_21, revmom_*, sleeve 앙상블; IS Calmar 2.5~3.3)은 OOS에서 전부 붕괴(Calmar -0.5~0.3, MDD 38~65%). 5,953회 평가의 다중검정 과최적화.
- 3개 롤링 폴드: 훈련 Calmar 최고 구성을 고르면 3개 폴드 모두 기준 전략보다 나쁨(fold1 Calmar 0.15 vs 3.08, fold2 1.42 vs 1.87, fold3 -0.15 vs 1.32).
- IS와 OOS 모두 기준 Calmar 초과 + 양 구간 MDD<=25%인 구성은 5,904개 중 32개(0.5%). 모두 ret_14/resid_14/volmom_14/carry_neg_30 계열이고 거의 전부 R=3, 유동성 하위 20~33% 제외 또는 K=6~10. 즉 '14일/3일 리밸런스' 골격 위의 미세 개선(유동성 필터, 변동성 조정)일 뿐 새 알파가 아님.
- 단기 반전(1~3일), 저변동, 펀딩 carry_pos, 돌파/SMA 거리, taker imbalance: OOS 음수 또는 0 근처.
- 후보(소폭, 약한 증거): volmom_14 K10 R3 liq20% equal (IS 1.50/OOS 1.84, full MDD 15.8%), carry_neg(저펀딩 롱) 은 회전이 낮고(연 20~50) 비용 우위지만 fold1에서 CAGR 2%.
실제 운용 변경 승인 근거 아님.

## assumptions

close t 신호로 w[t]를 결정하고 일자 t+1 수익과 펀딩에는 w[t]를 적용한다. 당일 종가 리밸런스 비용은 당일 equity에 반영한다. 비용=편도 거래대금 0.05% 수수료+0.05% 슬리피지; 기준 재현만 0.04%. 단일 전략 롱·숏 각각 0.5, 표본 부족 시 K=min(요청 K, 적격 수/2 내림), 결측 강제 청산 시 생존 종목을 롱·숏 각각 0.5로 재정규화하며 한쪽이 비면 전체를 현금화한다. 이는 R일 일정 외 예외적 거래이고 비용에 포함한다. 일별 비중은 리밸런스 사이 고정하는 목표비중 근사이며 가격에 따른 실제 비중 drift·수량 고정·증거금·청산·시장충격은 모형에 없다. 회전율은 목표비중 변화의 절대합으로 반회전이 아니다. 수익률은 (1+가격수익−펀딩)×(1−비용×회전율)−1. Sharpe는 무위험수익 0, sqrt(365), CAGR은 일수/365, 낙폭은 초기 equity=1 포함. fee drag는 연환산 단순 비용합이며 총성과 차이와 일치할 필요가 없다. skip-N은 close[t-1]/close[t-N]−1. BTC beta는 60일 일수익 공분산/분산으로 산출하고 잔차 일수익을 N일 합산한다. breakout은 close/60일 최고 종가−1이다. 동일 점수는 유니버스 열 순서로 결정한다.

미래 변경 테스트: {"passed": true, "signals": 41, "weighting_methods": 3, "cutoff": "2023-06-01", "accounting": true, "loader": true}. 라이브러리 metrics와 NumPy grid metrics의 일치, 합성 전체 실행을 검증한다. 실행 시간 73.5초.
