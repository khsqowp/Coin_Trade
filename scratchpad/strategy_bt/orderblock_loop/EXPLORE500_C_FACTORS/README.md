# EXPLORE500 lane C (factors) - README

> EXPLORATORY SCREEN ONLY - not part of the 13-round preregistered G-gate track, not added to TRAIN_TRIALS.csv, no promotion without separate formal preregistration + synthetic tests + resource-gated TRAIN run.

Files: IDEAS.csv (166 ideas), screen.py (harness; re-run writes all outputs), RESULTS.csv (per-idea metrics), RANKED_TOP20.md (top 20 and caveats).
CSV files start with a `#` label line; read with `pandas.read_csv(..., comment='#')`.

Reproduce: `/opt/anaconda3/bin/python3 screen.py` (about 15 seconds on the TRAIN cache).

Simplifications: 1h timeframe only; 31 symbols with TRAIN bars from the cache; greedy one-position-per-symbol; shared exit convention (see screen.py header).
