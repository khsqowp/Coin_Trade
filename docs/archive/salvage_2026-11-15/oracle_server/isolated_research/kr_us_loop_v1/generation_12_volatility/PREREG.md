# Generation 12 — downside-semivariance exposure control (US SPY)

Status: **PENDING ROOT REVIEW — NO MARKET PERFORMANCE VALUES HAVE BEEN READ OR COMPUTED.**

Registered: 2026-11-06 (Asia/Seoul). This is one fixed, exploratory portfolio risk-control hypothesis. It is not a new return-predictive signal, a deployable strategy, or evidence that no other strategy can work.

## Why this candidate is distinct, and what it is not

Generation 01 already tested total-realized-volatility targeting (`MOM12_1_VOL10_OVERLAY`) on the 12-1 momentum basket. The feasibility inventory also proposes, but does not report as run, a Rogers–Satchell OHLC range-volatility overlay. This candidate instead tests a downside-only risk forecast as a continuous, long-only exposure control on a fixed SPY buy-and-hold base. It is not a new stock-ranking rule, a trend filter, a range-volatility estimator, or a parameter sweep. It remains correlated with the existing volatility-managed portfolio family; the distinction is the downside semivariance forecast and the fixed broad-market base, not independent evidence.

## Frozen hypothesis

Reducing SPY exposure when trailing downside semivariance rises may lower realized drawdown and improve risk-adjusted return after turnover costs, relative to unscaled SPY buy-and-hold. The rule is not expected to guarantee higher CAGR, and only this exact definition may be tested in this attempt.

## Market, instrument, and data boundary

- **Market/instrument:** United States, SPY only, long-only, cash is the only alternative holding. No leverage, shorting, other ETF, constituent selection, or external macro series.
- **KR:** no KR run is authorized in this candidate. The local KODEX 200 benchmark is absent and the available KR equal-weight mirror is not an authoritative market index or a reconciled PIT/delisting universe. Substituting that proxy would change the tested question. A KR analogue remains blocked until an independently validated, point-in-time market total-return benchmark and matching execution calendar are supplied.
- **Input:** only `trading/docs/research/kr_us_loop_v1/data_mirror/us_daily/SPY.parquet`; no server/live source, internet pull, or other local price file.
- Require a unique, strictly ascending date index; required `open`, `close`, and `adjclose` values finite and positive; raw OHLC integrity if high/low are present and used by the shared loader; adjusted close finite and positive; and derived adjusted open finite and positive. Do not silently sort, forward-fill, interpolate, or delete invalid observations. Any failure blocks the attempt before performance calculation.
- Adjusted open is `raw_open * adjclose / raw_close`. The downside forecast uses adjusted-close simple returns. Vendor adjustment, split/dividend history, exchange-calendar completeness, and actual executable auction prices are not independently verified. The local Yahoo-derived mirror is an exploratory snapshot, not a pristine or authoritative dataset.

## Signal and exposure calculation

At each observed session close `t`, compute adjusted-close simple returns `r_j = AdjClose[j] / AdjClose[j-1] - 1` for the **63 immediately preceding completed close-to-close intervals**, `j = t-62 ... t`. The current close-to-close return ending at `t` is known at that close and is included. The forecast is unavailable until all 63 returns are finite; no shorter warm-up or missing-value repair is allowed.

Define downside RMS volatility as:

`downside_rms_63(t) = sqrt((1/63) * sum(min(r_j, 0)^2))`

and annualize it as `sigma_down(t) = sqrt(252) * downside_rms_63(t)`. This is a zero-threshold downside root-mean-square, not demeaned semideviation and not total standard deviation. If it is zero or invalid, the attempt fails closed rather than dividing by zero or silently assigning full exposure.

The target SPY weight decided at close `t` is:

`w_target(t) = min(1.0, 0.10 / sigma_down(t))`

with lower bound zero (the formula is strictly positive for valid finite inputs). The target is entered/rebalanced at the **next observed open**. The 10% annualized downside-risk target is fixed, has no leverage, and will not be optimized or compared with alternate targets. Until the first valid forecast, the portfolio remains cash. At each subsequent open, use the forecast from the preceding close; no same-close fill is assumed.

## Portfolio accounting and costs

- Construct adjusted-open-to-adjusted-open simple returns on consecutive observed dates. A position held at open `i` earns the interval through open `i+1`; the target computed at the close before open `i+1` is not applied until that next open, so it cannot capture the preceding overnight move retroactively.
- At each rebalance open, first mark the prior position through the preceding open-to-open return. Compute its drifted risky weight as `w_old*(1+r_asset)/(1+w_old*r_asset)`; reject non-finite or non-positive wealth factors. Then trade to the frozen target. Charge 10 basis points per unit of absolute traded notional (`0.001 * abs(target - drifted_weight)`) multiplicatively to wealth at that open. Cash earns zero. No tax, borrowing, market-impact model, cash yield, or intraday stop is assumed.
- At the first eligible target open, charge the same 10 bp per unit of entry notional. At the final observed open, do not enter a new terminal target; first earn the prior open-to-open interval, then liquidate the carried position and charge 10 bp per unit of remaining risky notional. The benchmark enters SPY at the first common eligible open, holds 100%, and pays 10 bp entry and terminal exit charges on the same curve dates.
- Primary comparator: net SPY buy-and-hold on exactly the strategy's eligible curve intervals. Report net CAGR and annualized Sharpe (252); also report within-window maximum drawdown, average exposure, exposure changes, total traded notional, completed holding intervals, and cost drag. Descriptive windows are full eligible sample, 2001-01-02 through 2016-12-30, and 2017-01-03 through the last eligible date. Window drawdowns restart at each window boundary for description only; the portfolio itself is continuous.
- No rebasing at the descriptive partitions, no OOS label, no DSR/PSR/BH significance assertion, and no claim of investment suitability. Historical partitions and this mirror have already been inspected in related research; global cumulative trial count and vendor provenance remain unresolved.

## Decision rule and one-attempt budget

Exactly one frozen rule and one execution attempt are allowed. If net Sharpe and maximum drawdown do not both improve against matched SPY buy-and-hold in **each** displayed window, reject this fixed downside-risk-control candidate for the stated risk-management hypothesis. CAGR is reported without requiring it to beat SPY because the candidate intentionally permits cash exposure to reduce downside risk. A positive result only retains this candidate as an exploratory lead for a separately preregistered, validated-data and prospective-holdout study; it does not establish a durable edge. No threshold/lookback variants, subperiod selection, or rerun after seeing performance are allowed. Input, integrity, implementation, or serialization failures are `FAILED` attempts, not performance rejections; their artifacts must remain recorded and the same attempt must not be silently rerun.

## Pre-performance verification plan (must pass before root authorizes one run)

1. Unit tests on synthetic data for the 63-return warm-up boundary; exact downside-RMS math including zero returns and positive-only windows; exposure cap at 100%; no leverage; invalid/zero forecast rejection; and missing/duplicate/unsorted dates fail-closed.
2. Causality test: perturb all prices strictly after cutoff `t`; all forecasts and targets through close `t` must remain unchanged. Assert that a close-`t` target first affects the next observed open and never receives the prior interval's return.
3. Accounting tests: hand-calculated two-interval example for open-to-open return, drifted exposure, buys/sells turnover, multiplicative cost, initial entry, final liquidation, and matched benchmark dates. Assert finite wealth and consistent curve/manifest lengths.
4. Independent review must verify the implementation, hash-pinned input, trade clock, costs, metric windows, and no accidental parameter variants. The test runner must write durable `STARTED` before the performance data are loaded for calculation and `FAILED` on every exception; only root GO may change this status to run-authorized.

## Freeze and attempt handling

The candidate is preregistered by this document, but execution remains blocked until root review. Before any authorized run, record SHA-256 hashes for this document, runner, tests, data file, and relevant loader/helpers in a write-once freeze/manifest; independently verify every digest. A rule or accounting change requires a dated addendum and a new attempt ID; this attempt's source and ledger entries must remain intact. No market performance values have been calculated as part of preparing this preregistration.
