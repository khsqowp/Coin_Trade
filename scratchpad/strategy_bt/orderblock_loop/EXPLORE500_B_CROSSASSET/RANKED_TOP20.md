# RANKED TOP 20 — Lane B (crypto cross-asset / cross-sectional / calendar / regime)

> **EXPLORATORY SCREEN ONLY — not part of the 13-round preregistered G-gate track, not added to TRAIN_TRIALS.csv, no promotion without separate formal preregistration + synthetic tests + resource-gated TRAIN run.**

Caveats: exploratory screen only. No look-ahead-bias audit beyond causal construction, no multiple-testing correction (about 150 ideas scored, so expect false positives), no walk-forward, TRAIN window only, 1h bars, 30 usable perps (POLUSDT and TONUSDT have no TRAIN bars; TIAUSDT and SEIUSDT dropped for <2000 TRAIN bars). Long-only alt-vs-BTC ideas carry raw alt beta during the in-sample trend and are not beta-neutralized. Not G-eligible. Not added to any real ledger. Ranking is by composite_score, which is a rough_sharpe shrunk by trade count and halved when the first- and second-half TRAIN Sharpe disagree.

Scored ideas: 139 of 150 screenable proposed; 17 data-blocked (listed, not scored). Zero-trade ideas (gate never fires in TRAIN, e.g. overlay O2a): 2. Spearman(prior_rank, empirical rank) over scored ideas = 0.04 (positive rho means the qualitative prior ranks the scored set in the same order, not that the prior is good).

Shared conventions: entry = next 1h open, exit = close after H bars, 12bp per active rebalance/trade, one position per symbol for event ideas.

| # | idea | composite | n | win% | PF | exp bp | rough Sharpe | H1 / H2 Sharpe | why |
|---|---|---|---|---|---|---|---|---|---|
| 1 | XB117 Alt/BTC ratio breakout (336h), 72h hold | +2.699 | 1530 | 50.0 | 1.59 | +218.4 | +2.70 | +3.49 / +1.87 | Enter next bar when alt/BTC log ratio makes a new 336-bar high (vs prior bars); long alt; hold 72h. (same sign in both TRAIN halves.) |
| 2 | XB116 Alt/BTC ratio breakout (336h), 24h hold | +2.333 | 2395 | 50.9 | 1.56 | +125.8 | +2.33 | +2.90 / +2.01 | Enter next bar when alt/BTC log ratio makes a new 336-bar high (vs prior bars); long alt; hold 24h. (same sign in both TRAIN halves.) |
| 3 | XB115 Alt/BTC ratio breakout (168h), 72h hold | +2.234 | 2406 | 49.0 | 1.38 | +136.2 | +2.23 | +3.25 / +1.07 | Enter next bar when alt/BTC log ratio makes a new 168-bar high (vs prior bars); long alt; hold 72h. (same sign in both TRAIN halves.) |
| 4 | XB114 Alt/BTC ratio breakout (168h), 24h hold | +1.921 | 3731 | 49.1 | 1.34 | +76.6 | +1.92 | +2.77 / +0.84 | Enter next bar when alt/BTC log ratio makes a new 168-bar high (vs prior bars); long alt; hold 24h. (same sign in both TRAIN halves.) |
| 5 | XB078 Overlay [O1] on RESMOM 168h/24h | +1.569 | 691 | 52.0 | 1.43 | +25.2 | +1.57 | +2.25 / +0.58 | Base RESMOM 168h/24h basket, traded only when BTC above its 720-bar SMA; flat otherwise. (same sign in both TRAIN halves.) |
| 6 | XB054 Overlay [O1] on CSMOM 168h/24h | +1.399 | 699 | 51.1 | 1.37 | +22.3 | +1.40 | +2.02 / +0.45 | Base CSMOM 168h/24h basket, traded only when BTC above its 720-bar SMA; flat otherwise. (same sign in both TRAIN halves.) |
| 7 | XB144 Per-symbol funding overheat long (< -5bp/8h), 24h hold | +1.275 | 649 | 54.4 | 1.54 | +130.3 | +1.28 | +1.37 / +1.18 | At each settlement where funding < -5bp per 8h, long the perp at next open; hold 24h. (same sign in both TRAIN halves.) |
| 8 | XB057 Overlay [O3a] on CSMOM 168h/24h | +1.207 | 703 | 50.8 | 1.32 | +16.2 | +1.21 | +1.98 / +0.09 | Base CSMOM 168h/24h basket, traded only when BTC 168-bar realized vol at or below its trailing-2160-bar median; flat otherwise. (same sign in both TRAIN halves.) |
| 9 | XB081 Overlay [O3a] on RESMOM 168h/24h | +1.182 | 700 | 50.1 | 1.32 | +16.3 | +1.18 | +2.00 / +0.03 | Base RESMOM 168h/24h basket, traded only when BTC 168-bar realized vol at or below its trailing-2160-bar median; flat otherwise. (same sign in both TRAIN halves.) |
| 10 | XB063 Overlay [O3a] on CSMOM 336h/168h | +1.143 | 94 | 62.8 | 2.87 | +177.1 | +1.67 | +2.02 / +1.25 | Base CSMOM 336h/168h basket, traded only when BTC 168-bar realized vol at or below its trailing-2160-bar median; flat otherwise. (same sign in both TRAIN halves.) |
| 11 | XB040 CS beta-residual momentum vs BTC 336h, 168h hold | +1.066 | 192 | 55.7 | 1.60 | +82.2 | +1.09 | +1.25 / +0.96 | Rank by residual 336-bar log return = alt return - beta_720 x BTC return; long top 5 residual, short bottom 5, equal weight; hold 168h. (same sign in both TRAIN halves.) |
| 12 | XB008 CS momentum 336h lookback, 168h hold | +1.026 | 192 | 56.2 | 1.57 | +82.8 | +1.05 | +1.04 / +1.21 | Each 168h rebalance, rank the 35 perps by 336-bar log return; long top-5, short bottom-5, equal weight, dollar-neutral. (same sign in both TRAIN halves.) |
| 13 | XB059 Overlay [O4] on CSMOM 168h/24h | +1.022 | 318 | 51.9 | 1.38 | +16.8 | +1.02 | +1.57 / +0.30 | Base CSMOM 168h/24h basket, traded only when breadth (share of perps above 100-bar SMA) between 0.3 and 0.7; flat otherwise. (same sign in both TRAIN halves.) |
| 14 | XB133 Weekend long Fri 20:00 UTC -> Sun 20:00 UTC | +0.820 | 4339 | 52.3 | 1.32 | +59.0 | +0.83 | +1.30 / +0.24 | Long each perp at Fri 20:00 UTC; exit after 48 bars. (same sign in both TRAIN halves.) |
| 15 | XB130 Weekday long Fri 00:00 UTC, 24h hold | +0.814 | 4333 | 51.6 | 1.29 | +53.6 | +0.82 | +1.08 / +0.52 | Long each perp at the 00:00 UTC bar on Fri; exit after 24 bars. (same sign in both TRAIN halves.) |
| 16 | XB064 Overlay [O3b] on CSMOM 336h/168h | +0.812 | 150 | 56.0 | 1.60 | +83.4 | +0.94 | +1.10 / +0.78 | Base CSMOM 336h/168h basket, traded only when BTC 168-bar realized vol at or below its trailing-2160-bar 80th pct; flat otherwise. (same sign in both TRAIN halves.) |
| 17 | XB092 Overlay [O2b] on FUND rev/24h | +0.771 | 95 | 57.9 | 2.14 | +76.8 | +1.12 | +1.56 / +1.05 | Base FUND rev/24h basket, traded only when market avg 168-bar corr to EW basket < 0.7; flat otherwise. (same sign in both TRAIN halves.) |
| 18 | XB010 CS momentum 720h lookback, 168h hold | +0.759 | 190 | 56.3 | 1.36 | +51.8 | +0.78 | +0.82 / +0.78 | Each 168h rebalance, rank the 35 perps by 720-bar log return; long top-5, short bottom-5, equal weight, dollar-neutral. (same sign in both TRAIN halves.) |
| 19 | XB038 CS beta-residual momentum vs BTC 168h, 168h hold | +0.669 | 192 | 54.2 | 1.34 | +50.3 | +0.68 | +0.64 / +0.83 | Rank by residual 168-bar log return = alt return - beta_720 x BTC return; long top 5 residual, short bottom 5, equal weight; hold 168h. (same sign in both TRAIN halves.) |
| 20 | XB060 Overlay [O1] on CSMOM 336h/168h | +0.656 | 100 | 61.0 | 1.76 | +112.6 | +0.93 | +1.08 / +0.87 | Base CSMOM 336h/168h basket, traded only when BTC above its 720-bar SMA; flat otherwise. (same sign in both TRAIN halves.) |

Top 10 summary (composite score, one-line mechanism):
1. XB117 Alt/BTC ratio breakout (336h), 72h hold — composite +2.699; Enter next bar when alt/BTC log ratio makes a new 336-bar high (vs prior bars); long alt; hold 72h.
2. XB116 Alt/BTC ratio breakout (336h), 24h hold — composite +2.333; Enter next bar when alt/BTC log ratio makes a new 336-bar high (vs prior bars); long alt; hold 24h.
3. XB115 Alt/BTC ratio breakout (168h), 72h hold — composite +2.234; Enter next bar when alt/BTC log ratio makes a new 168-bar high (vs prior bars); long alt; hold 72h.
4. XB114 Alt/BTC ratio breakout (168h), 24h hold — composite +1.921; Enter next bar when alt/BTC log ratio makes a new 168-bar high (vs prior bars); long alt; hold 24h.
5. XB078 Overlay [O1] on RESMOM 168h/24h — composite +1.569; Base RESMOM 168h/24h basket, traded only when BTC above its 720-bar SMA; flat otherwise.
6. XB054 Overlay [O1] on CSMOM 168h/24h — composite +1.399; Base CSMOM 168h/24h basket, traded only when BTC above its 720-bar SMA; flat otherwise.
7. XB144 Per-symbol funding overheat long (< -5bp/8h), 24h hold — composite +1.275; At each settlement where funding < -5bp per 8h, long the perp at next open; hold 24h.
8. XB057 Overlay [O3a] on CSMOM 168h/24h — composite +1.207; Base CSMOM 168h/24h basket, traded only when BTC 168-bar realized vol at or below its trailing-2160-bar median; flat otherwise.
9. XB081 Overlay [O3a] on RESMOM 168h/24h — composite +1.182; Base RESMOM 168h/24h basket, traded only when BTC 168-bar realized vol at or below its trailing-2160-bar median; flat otherwise.
10. XB063 Overlay [O3a] on CSMOM 336h/168h — composite +1.143; Base CSMOM 336h/168h basket, traded only when BTC 168-bar realized vol at or below its trailing-2160-bar median; flat otherwise.
