# Adaptive selective M2 historical diagnostic

- Verdict: **REJECT_HISTORICAL_DIAGNOSTIC**
- Issued forecasts: 426337
- M2 target-first rate: 0.4941607226208375
- Wilson 95%: [0.4926600195114742, 0.495661530957481]
- Global non-overlap: 12639 events, M2=0.4939473059577498
- Coverage: 10.057471% (426337/4239008 feature-ready anchors)
- Mean net return per issued forecast: 10bp=-0.0009981376498881258, 30bp=-0.002998137649888126
- Expiry direction accuracy: 0.4865634462877958

## Preregistered gates

- FAIL — m2_at_least_80pct
- PASS — issued_n_at_least_200
- PASS — global_nonoverlap_n_at_least_200
- PASS — at_least_20_symbols
- PASS — coverage_at_least_10pct
- PASS — wilson_lower_above_momentum
- FAIL — positive_net_10bp
- FAIL — positive_net_30bp

## Baselines

- Same-event momentum: {'n': 426337, 'm2_hits': 201095, 'm2': 0.4716808534093921, 'wilson95': [0.4701826597082943, 0.4731795574384945], 'executed': 413090, 'entry_missing': 0, 'mean_net_10bp': -0.0009764243890749312, 'mean_net_30bp': -0.0029142810611442094, 'mean_net_10bp_executed': -0.0010077364370113993, 'mean_net_30bp_executed': -0.003007736437011399}
- Deterministic random: {'n': 426337, 'm2_hits': 206090, 'm2': 0.4833969371647312, 'wilson95': [0.481897056366666, 0.48489711715994555], 'executed': 426337, 'entry_missing': 0, 'mean_net_10bp': -0.0010090236471264411, 'mean_net_30bp': -0.003009023647126441, 'mean_net_10bp_executed': -0.0010090236471264411, 'mean_net_30bp_executed': -0.003009023647126441}
- No signal: {'n': 426337, 'm2_hits': 0, 'm2': 0.0, 'wilson95': [0.0, 9.010299851990988e-06], 'executed': 0, 'entry_missing': 0, 'mean_net_10bp': 0.0, 'mean_net_30bp': 0.0, 'mean_net_10bp_executed': None, 'mean_net_30bp_executed': None}

## Interpretation and limitations

- Historical interval was exposed during strategy selection; this is not sealed OOS or Core evidence.
- 10bp and 30bp are total round-trip fee proxies; measured spread/slippage is unavailable.
- No point-in-time universe or original source ZIP/vintage proof.
- A 92-day diagnostic cannot establish performance across market regimes.

This is a historical exposed diagnostic, not sealed OOS, live execution evidence, or a Core strategy.
