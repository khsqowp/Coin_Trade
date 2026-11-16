# Decision — R025

**NO PASS.** The exhaustive search within the four frozen Round 5 candidate rules produced 135 cells. No cell reached 80% target-first accuracy. This is exploratory evidence on previously exposed development data, not validation.

The best eligible-by-count mean return was `bb_squeeze_breakout + orb_funding_session`, 240m: 898 events, 14.70% target-first, +0.3792% mean net notional return per event, +0.0691 mean net R. The highest raw mean return overall was `bb_squeeze_breakout + vwap_band_fade`, 240m, but only 19 events; it is not eligible even as a stable exploratory candidate. Neither result meets the user's 80% signal-accuracy goal, the M4 20-symbol gate, or a fresh independent-data gate.

No KR/US price-based trials were added: the authorized data and point-in-time universe gates remain unmet. Existing KR/US results and trial counts are summarized in the R025 report, with historical best numbers clearly separated from valid candidates.
