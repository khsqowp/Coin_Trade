# R023 decision — reject; exploratory only

The BTC-shock/altcoin-laggard filter did not establish improvement over its matched breakout baseline and is not an 80% signal.

- Candidate: 393 trades, target-first 118/393 = **30.03%**, event-cluster bootstrap 95% interval **24.22–35.96%**, mean net return **−0.453R** (event-bootstrap 95% interval **−0.640 to −0.265R**).
- Baseline without the lag filter: 1,530 trades, target-first 446/1,530 = **29.15%**, mean net return **−0.438R**.
- Paired event-bootstrap candidate-minus-baseline difference: target-first **+0.9 percentage points**, 95% interval **−4.02 to +5.63 points**; mean net-R difference interval **−0.169 to +0.133R**. Neither supports a reliable improvement.
- The filter kept **25.69%** of baseline trades. All five candidate altcoin sleeves had negative mean net R. Stop-first dominated timeout.

The result does not satisfy the user's 80% goal. It also cannot be called a confirmatory preregistered test: the frozen rule was written down only after the pilot executed. The 2020–2023 development interval was already exposed, the universe contains only six current survivor contracts, and no separate validation or sealed sample was used. The costs are assumed and the observed funding cashflow was zero for these short holding intervals.

This is a useful rejection because the cross-asset laggard mechanism is materially different from R021's funding-extreme re-entry and the P5–P9 setup families. It is not evidence that other cross-asset predictors cannot work. Preserve the null result, do not tune this same exposed sample, and keep the overall research goal active.
