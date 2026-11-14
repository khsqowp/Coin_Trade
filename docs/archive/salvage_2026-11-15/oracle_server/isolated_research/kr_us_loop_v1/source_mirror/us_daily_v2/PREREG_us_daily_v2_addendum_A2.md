# Addendum A2 to PREREG_us_daily_v2 (written AFTER the IS stage had been run once and its numbers seen; BEFORE any OOS number was read)
Data errors found by the universe-wide data-quality pass (moves > 40% on eligible days, dollar-volume screen, adjustment-factor jumps):
1. Ticker re-use in RECENT spells (not covered by addendum A1's pre-2015 audit): PARA (Paramount's 2022-2025 spell carries "Parabolic Technologies",
   an OTC microcap, median $0.13M/day) and BBT (BB&T's 2001-2019 spell carries "Beacon Financial", median $1.1M/day). Both excluded.
   Screen: median close x volume over eligible days < $5M; the other flagged names (AIT, NC, TKR, WEN, WOR, 1999-2008) match the member company
   by name and are kept.
2. Double-counted corporate-action adjustments (e.g. DHR 2016-07-05 Fortive spin-off: split-adjusted close continuous, adjclose +61%):
   mechanical repair - when the vendor adjustment factor jumps > 15% in a day, the adjclose return exceeds 15% in size and the close return is
   below 10% in size, the factor jump is neutralised (all earlier adjclose values rescaled). Legitimate spin-off-as-dividend adjustments
   (close drops, adjclose smooth, e.g. MO 2008 PMI) are untouched by construction.
3. COMMITMENT: the run on the corrected data is the PRIMARY result, whatever it selects. The uncorrected run (archived unread in
   uncorrected_run/, its OOS files were produced but not opened) is reported afterwards only as a disclosure of the effect of the fixes.
   Strategy rules, periods, costs, gates are unchanged.
