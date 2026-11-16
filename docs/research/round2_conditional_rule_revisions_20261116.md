# Round 2 — one-time revisions of conditionally retained rules

Date: 2026-11-16 (Asia/Seoul)
Status: rule definitions only. No strategy backtest, market-data read, vendor contact, purchase, or account action occurred. These revisions use the single bounded correction allowed by the Round 1 red-team. They do not pass market-data gates or imply approval to test.

## Final disposition context

Red-team allowed one correction for 14 candidates: KR-01/02/04/05/06/07/10 and US-04/05/06/07/08/09. Chief scope review removes US-10 because options are outside the user-fixed stock/ETF universe. Thus 13 retained conditional candidates are specified below. The other 17 candidates remain rejected and are not revived.

## Korea stocks and ETFs

### KR-01 — point-in-time quarterly EPS surprise

- **Single correction:** restrict the ambiguous EPS-or-operating-income condition to consolidated basic EPS for the same fiscal quarter. Define surprise as `reported EPS / point-in-time consensus median - 1 >= 10%`.
- Consensus is the median of at least three individual EPS estimates available no later than 18:00 KST on the trading day before the disclosure. Event key: permanent issuer ID + fiscal period end + consolidation status. A correction is a new information version at its own public timestamp; it never rewrites the original signal. Exclude missing fields, fewer than three estimates, or consensus <= 0.
- Keep the registered entry/exit thresholds: after-close disclosures enter at the next session close; intraday disclosures enter at the next session close; 10-session expiry, +15% target, and -8% close stop. One event per issuer/fiscal quarter.
- **Data gate remains closed:** point-in-time analyst consensus vintages and delisted/merged security outcomes are not established.

### KR-02 — KOSPI 200 official additions

- **Single correction:** freeze event identity/versioning as `index + first official notice timestamp (KST) + stated effective date + security permanent ID`; only explicitly named additions qualify. Corrections/withdrawals are separate versions timestamped when published. A withdrawal cancels an unfilled signal; it does not delete a fill already recorded.
- Enter at the next session close after the original public notice; exit on the fifth session after the effective date or 20 sessions after notice, whichever comes first, with the registered -8% stop. Exclude events without the official original notice, effective date, or correction history.
- **Data gate remains closed:** PIT KOSPI 200 constituent notices and historic price/inactive-name coverage are unverified.

### KR-04 — foreign on-exchange cash net buying with price confirmation

- **Single correction:** define flow as exchange-reported foreign-investor on-exchange cash-equity net-buy quantity multiplied by that day's close. Explicitly exclude off-exchange/block transactions, lending, short-sale volumes, and other investor categories. Use each field only after its actual public availability timestamp.
- Trigger when the sum of the latest five available trading sessions' flow notionals is at least 1% of the preceding 20 sessions' aggregate traded value and the same five-session adjusted-close return is positive. Event key: permanent security ID + signal-confirmation date. Missing publication time/flow/price or any missing session in either window means no signal; do not fill missing values with zero.
- Preserve registered next-session-close entry, five-session holding, exit if the flow turns negative, and -7% stop.
- **Data gate remains closed:** source field semantics, availability vintages, and PIT inactive securities are not proven.

### KR-05 — closing-auction program imbalance

- **Single correction:** define the same-day ranking population as all KOSPI/KOSDAQ common stocks that were listed and tradable that day and have both closing-auction value and program net-buy notional. Trigger for program net-buy in the cross-sectional top 1% and closing-auction value >=2 times that security's median closing-auction value over its preceding 20 valid sessions. Event key: permanent security ID + signal date; use the signal only after the official publication timestamp.
- Enter only at the next session's opening-auction executable fill price; if auction execution data or an executable fill is absent, record no fill. Exit at that session's close under the registered rule; apply the registered -1.5% stop from entry/open as defined in the original candidate.
- **Not executable with current evidence:** no historical auction/NBBO/fill archive is established. The rule remains a proposal behind a closed data gate.

### KR-06 — post-unlock supply absorption

- **Single correction:** use actual first tradable date of released shareholder shares, not the contractual scheduled date. Reference price is the split-adjusted close of the preceding valid session; unlock ratio denominator is the latest publicly available free-float shares immediately before release.
- Require each of the first two valid post-release sessions to close at or above the reference close, and their combined traded value to be >=3 times the median daily traded value of the 20 valid sessions before release. Enter at the third valid session close. Event key: permanent security ID + actual release date + released shareholder/quantity filing ID. Missing release date/amount/float/reference or either confirmation session excludes the event; no zero-fill or calendar-day interpolation.
- Preserve registered 10-session expiry, +12% target and -7% stop.
- **Data gate remains closed:** actual unlock dates/quantities, historic float and complete delisted IPO panel are not verified.

### KR-07 — regular cash-dividend surprise

- **Single correction:** define expected DPS as the median of at least three point-in-time analyst estimates for the same common-share class and fiscal year, available by 18:00 KST on the trading day before the declaration. Use regular cash DPS only; exclude special/stock dividends, currency mismatches, or estimates <=0. Surprise is `declared regular cash DPS / expected DPS - 1`.
- Preserve both original thresholds: the declared regular DPS must also be >=20% above the prior-year regular DPS, and surprise must rank in the sector's top decile among eligible disclosures on the same signal date. Use the sector classification available on the signal date. Event key: permanent security ID + fiscal year + dividend type. Corrections apply only from their public timestamps and never rewrite prior signals.
- Enter at the first close after the announcement becomes public; hold 20 sessions or exit at registered -8% close stop. Total return must include the distribution and applicable tax treatment.
- **Data gate remains closed:** timestamped historical dividend consensus, historical sector classifications, distributions and full inactive-security returns are not established.

### KR-10 — structured shareholder-meeting agenda

- **Single correction:** classify only the original shareholder-meeting notice's structured agenda fields/codes for an outside-director election or shareholder proposal; exclude free-text interpretation and all later voting outcomes from entry features. Event key: permanent security ID + meeting date + original filing receipt number. Store the original and every correction with DART public timestamp (KST); a correction changes only information available after its own publication.
- Enter at the first regular-session close after the original notice is public; exit three sessions after the meeting or 15 sessions after filing, whichever comes first, with the registered -8% stop. Missing structured agenda code, filing identity, publication time, or price excludes the event.
- **Data gate remains closed:** complete historical structured agenda/vintage and delisted outcome panel are unverified.

## US stocks and ETFs

The listed times below mean the first regular-session open after the information's actual public timestamp, not a synthetic same-close fill. All ATR values and trailing extrema must be computed only from bars available at that decision time. Each event keeps its source filing/publication version.

### US-04 — new Schedule 13D activist filing, excluding 13G

- **Single correction:** only a new initial Schedule 13D with reported beneficial ownership >=5% qualifies; exclude all Schedule 13G filings. Key one event per issuer + reporting-person group + initial filing; amendments do not make a new signal and cannot rewrite the initial snapshot.
- Enter at first regular-session open after the filing timestamp. Exit at 40 sessions, the first open after a public settlement/board-change event, or the registered 2 ATR stop measured from the post-filing low, whichever occurs first. Missing filing timestamp, ownership percentage, group/issuer map, or price excludes the event.
- **Data gate remains closed:** complete historical filings/amendments, point-in-time issuer mapping and inactive-security outcomes are not validated.

### US-05 — reported executed buyback progress

- **Single correction:** for each issuer/plan, use only the cumulative shares actually purchased since the plan's reported start, as known in that filing, divided by the shares authorized by that plan. Signal only if the cumulative numerator has increased from the prior public filing and is >=30% of the plan denominator. Filing publication time, plan identity, period and correction version are frozen as-of each filing; later amendments do not rewrite earlier entries.
- Enter at first regular-session open after the qualifying filing. Exit after 40 sessions, the first open after public plan cancellation/end, or a 2 ATR trailing stop from the post-entry high, whichever occurs first. Exclude missing/ambiguous plan denominator, cumulative period or public timestamp.
- **Data gate remains closed:** historical as-filed executed repurchase quantities and correction history are not established.

### US-06 — unlevered US stock/sector ETF net creations

- **Single correction:** freeze the universe to non-leveraged, non-inverse US equity broad-market and sector ETFs; retain PIT listing/liquidation membership. Daily net creation notional is `(shares_outstanding_t - shares_outstanding_t-1) * NAV_t`; the five-session sum divided by the mean AUM of the preceding 20 sessions is the flow ratio. Require this ratio >=2% and the underlying index's same five-session return >=0.
- Entry occurs at the first open after both inputs were publicly available. Exit at 20 sessions, the first open after the trailing five-session net-creation/AUM ratio reaches <=-1%, or a 2 ATR trailing stop from the post-entry high, whichever first. Missing dates/fields mean no signal, never zero flow. ETF holdings/underlying overlap is tracked; correlated or duplicate exposures do not count as independent events.
- **Data gate remains closed:** daily as-of shares outstanding, NAV/AUM, underlying index mapping, ETF liquidation history and distribution-adjusted returns are not established.

### US-07 — regular cash-dividend initiation/increase

- **Single correction:** include only a newly declared regular cash dividend or a regular cash DPS increase >=20% versus the prior regular cash payment per share. Compare amounts in the same currency and split-adjusted share basis; exclude special and stock dividends from the trigger. Event key: permanent security ID + declaration date + regular-dividend type. Corrections apply from the corrected filing's public timestamp only.
- Enter at first regular-session open after declaration. Exit after 60 sessions, the first open after a public cut/cancellation, or the registered 2 ATR trailing stop, whichever comes first. Include cash distributions during holding in total return; exclude missing declaration time, split/currency basis, or regular/special classification.
- **Data gate remains closed:** full vintage dividend announcements, distributions, delisted outcomes and total-return treatment are not proven.

### US-08 — IPO lock-up short after confirmed actual release

- **Single correction:** do not signal from a contractual calendar alone. Require a publicly confirmed actual release date/quantity >=10% of the then-public float. On the first full session after confirmed tradability, require close < open and volume >=1.5 times the median volume of the prior 20 valid sessions; enter short at the next session open only if borrowable quantity, borrow fee and recall conditions are confirmed before entry.
- Cover after 10 sessions or at entry +2 ATR adverse price move, whichever first; a gap through the stop fills at the next open. Missing actual release, float, price, volume or borrow evidence means no trade, not an assumed borrow. Record borrow fee and recall/forced-cover outcome.
- **Data gate remains closed:** actual release, historical float and security-level borrow availability/fees/recalls are not available in the verified sources.

### US-09 — official index-change event, direction-specific

- **Single correction:** official additions form the long cohort; official deletions form a separate short cohort only when PIT borrow availability is documented. Never convert an unborrowable deletion into a long trade. Event key is permanent security ID + index + effective date; notice revisions are versions available only from their release timestamps. Skip if the five sessions before entry show >10% return.
- Enter at first open after the official notice; exit at the index effective-date regular-session close. No notice/effective timestamp or price means no event. Cluster repeated changes by issuer and index; do not count amended duplicate notices as independent events.
- **Data gate remains closed:** complete historical index notice/membership, PIT borrow and delisted returns are not established.

## Gate after revision

- These are one-time **definition corrections**, not data-eligible tests. No threshold has been tuned to results and no return/accuracy number was generated.
- 13 candidates now have rule-level definitions; all 13 still need a separate source-rights/PIT/cost/benchmark/holdout gate. KR-05, KR-07, US-06, US-08 and US-09 have especially direct field-level blockers in the current source audit.
- Before any performance test, a red-team must review the corrected text once and compare each mechanism with the full catalog. Any remaining contradiction, ambiguous field, or scope issue rejects that rule; do not grant a second revision.
- A corrected candidate's first development trial, if later eligible, is not an OOS test and cannot be used to claim the final 80% or equity thresholds.
