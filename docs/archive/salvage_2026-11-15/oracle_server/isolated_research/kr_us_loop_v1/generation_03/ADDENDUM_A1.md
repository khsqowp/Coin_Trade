# Generation 03 Addendum A1 — data gate and execution clarifications

Recorded before market-data execution after independent code review and raw-price audit.

- **KR stop:** The run must scan raw traded OHLC rows and fail all five KR candidate attempts before calling the shared KR loader. The reason is a reproduced defect in the inferred split-repair path; a raw audit passing alone would not certify the repair routine. This snapshot's scan found 28 invalid traded-OHLC rows across 3,236 files. All five KR failures are recorded separately in the run ledger.
- **FRAMA invalid feature:** An unavailable alpha/rank at a month-end exits the candidate on the next executable rebalance; no prior rank is fabricated. Recursive filter may carry its previous numerical value during warm-up, but it is not eligible for a new/continued position on an unavailable feature decision.
- **Ichimoku exit:** The frozen hold condition requires price above the cloud top and Tenkan above Kijun; failure of either condition exits at that monthly decision.
- **Missing bar execution:** Gen03 rejects a candidate attempt if a held name has an invalid OHLC mark or if an intended new entry lacks valid next-session open and close. It does not use the inherited simulator behavior that can leave a missing held bar at a flat mark.
- Synthetic checks and independent code review were completed after applying these clarifications. Market-data execution followed only after review clearance.
