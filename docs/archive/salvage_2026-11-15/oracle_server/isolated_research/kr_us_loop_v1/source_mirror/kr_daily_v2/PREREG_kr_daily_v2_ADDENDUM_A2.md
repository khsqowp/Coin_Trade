# Addendum A2 to PREREG_kr_daily_v2 (instrument segmentation). Written 2026-11-04 ~08:50 KST, BEFORE any v2 strategy run.
Trigger: a universe-list check found 102 codes appearing more than once in the KIND lists.
* 90 are market transfers (KOSDAQ->KOSPI or KONEX->KOSDAQ): the same company and code, listed as "delisted" from the old market and "listed" on the new market on the same date (e.g. Celltrion 2018-02-09, Kakao 2017-07-10, Hana Tour 2011-11-01).
* Others transferred and were later truly delisted.
* 3 were truly delisted and re-listed years later under the same code (101970, 036220, 198940).

The original fetch used the KIND listing date as the lower bound. For transfers that is the TRANSFER date, so the pre-transfer history of exactly these (typically successful) companies would have been dropped. That is a hindsight bias.

Rule (fetch_v2.segments):
1. A transfer pair becomes ONE instrument fetched over the full window (2011-05..END, or to its terminal delisting date).
2. A terminal delisting followed by a later re-listing under the same code becomes TWO instruments: <code>_old (to the delisting date) and <code> (from the re-listing date). No position can be carried through the gap.
3. Delisted entries whose reason is a transfer are not terminal delistings.

Result: 3,240 instruments (2,588 currently listed, 652 terminally delisted since 2011-06; SPACs excluded).
The fetch was stopped and restarted; 3 already-fetched files of affected codes were deleted and refetched.
The random fetch order (seed 20261104) is now over the sorted segment keys. The deadline rule is unchanged.
