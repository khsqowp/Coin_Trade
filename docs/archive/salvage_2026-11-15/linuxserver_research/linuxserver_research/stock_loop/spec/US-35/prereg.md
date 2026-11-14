# US-35 - Membership-date (point-in-time) universe re-judgement (US, Round 7; ONE extra round authorised by coordinator for this purpose only)
Written 2026-11-13 BEFORE any US-35 run.

## Data
- Raw: Wikipedia 'List of S&P 500 companies', fetched once from the box 2026-11-13T16:30:42+09:00, saved at results/us35_raw/sp500_wikipedia.html (+ retrieved_at.txt). The 'Date added' column of the constituents table is used (all 503 rows have a date). The 'Selected changes' table was not parseable from the fetched html (only 2 tables), so removals are not available.
- Symbols matched to the harness price cache after replacing '.' by '-' ; unmatched names (present in one source only) are excluded from the primary run and their count is reported.
- Membership M[t,j] = (date_t >= Date added_j). Universe MEM = point-in-time top-100 by lib value20 among names with M true at t (lagged not needed: signals at close t use value20 incl. t, entries at close t).
- RESIDUAL BIAS (cannot be fixed here): the cache holds only CURRENT constituents; companies removed/delisted/acquired earlier are absent, so every result is still biased toward survivors (crashed-and-removed names missing). 'Date added' removes only the index-inclusion lookahead (names are tradable only after they entered the index). Dates may also reflect the original index entry for re-added names.

## Hypotheses (all pre-declared specs, NO new parameters; each is one trial)
On universe MEM (dev only, to 2024-11-11, calendar-midpoint halves):
 a. US-35-18c : RSI(2)<5 AND 126-day return in top quartile of the universe; buy close t; exit first close > SMA5 within 5 bars else t+5 (the US-18-T100 candidate cell).
 b. US-35-h5 / h10 / h20 : same selection, fixed holds 5 / 10 / 20 bars (US-32 style).
 c. US-35-24 : 126d top quartile AND 3-day drop <= -5% (US-24), SMA5/5d exit.
 d. US-35-25 : 126d top quartile AND close <= 0.96 x SMA10 (US-25), SMA5/5d exit.
 e. US-35-34 : every 20th bar buy all 126d top-quartile names, hold 20 bars (US-34, no dip).
Additionally US-35-18c on the frozen universes F14 and F18 (the US-18 candidate cell with SMA5 exit was not run there before) => 2 trials. Total 9 new trials (cumulative 149 with the earlier 140).
The F14/F18 results of US-24, US-25, US-32 (h5/10/20) and US-34 already exist (rounds 4-6) and are reused for the gate (not re-run).

## Decision rules (fixed now)
- Stage 1 on MEM: net mean>0, clustered t>=3, both halves >0. 
- Strict gate (as US-33): the same specification must have net mean>0, t>=2 and dev 2x-cost mean>0 on MEM, F14 and F18 (all three), and top-5 symbol share <= 40% on MEM.
- Only specs that clear Stage 1 on MEM AND the strict gate go to Stage 2 (<=3 params x 3 values, plateau, walk-forward, BH q<0.10 over the cumulative list) and then to a NEW Stage 3 holdout look (new unlock logged; BH over all holdout looks; holdout looks so far: 3, all US-18-T100).
- Item 4: US-35-18c on MEM is the dev-only re-judgement of the holdout-passed US-18-T100 candidate. If its dev net mean is ~0 (|t|<1 or 2x<0 and mean<0.15%) US-18 will be recorded as a survivorship artifact. No holdout data is used to decide anything in this round.
