# US-23 - Leader = 126d return, dip = IBS<0.10 (US, Round 4 prereg)

## Signal (fixed defaults)
Score = close_t/close_{t-126}-1, top quartile. Trigger: IBS_t=(close-low)/(high-low) < 0.10.

## Execution
Buy close t; exit first close > SMA5 within 5 bars else close t+5. Long only.

## Common (Round 4 US hypotheses; written 2026-11-13 BEFORE any run of them)
- Origin: coordinator request after US-18 Stage 3: test whether the US-18 mechanism (dip inside a momentum leader) survives survivorship-robust designs. Ideas come from first principles and DEV data only (US-18 Stage 1/2 dev results); the holdout diagnostics of US-18 are NOT used.
- Universes (each is a separate trial): F14 = top-100 names by lib value20 on 2014-12-31, frozen; events from 2015-01-02. F18 = top-100 by value20 on 2018-12-31, frozen; events from 2019-01-02. Universe chosen with information known at the freeze date only, so later rallies do not select members. Residual bias: members are still CURRENT S&P 500 constituents (survivors); stated and discounted.
- Leader = top quartile (0.25) of the stated score among valid names of the frozen universe on day t (cross-sectional rank, not a level) unless stated. Entry: buy close t. Exit: first close above SMA5 within 5 bars, else close t+5 (as US-18). Costs: USCost (RT 0.403%), 2x and 3x reported, next-open-entry variant reported. Dev data only (to 2024-11-11); holdout locked. Halves = midpoint of each universe's event window (calendar from its start date).
- Stage 1 verdict: net mean>0, clustered t>=3, both halves>0. Additional reporting: block-clustered t, top-5-symbol share of P&L, years positive. Trials join the cumulative BH list (99 so far).
- A survivor enters Stage 2 only with: top-5 symbol share <= 40%, dev 2x-cost mean > 0. Stage 2 grid <=3 params x 3 values, plateau, walk-forward, BH q<0.10 over the cumulative list; Stage 3 only after that.
