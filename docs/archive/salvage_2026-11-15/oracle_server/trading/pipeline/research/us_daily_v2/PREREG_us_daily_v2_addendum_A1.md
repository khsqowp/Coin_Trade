# Addendum A1 to PREREG_us_daily_v2 (written after the coverage stage, BEFORE any v2 strategy run)
1. IS start: the pre-registered coverage rule found no year >= 85% before 2017 (yearly PIT coverage 2000: 47%, 2008: 61%, 2016: 77%;
   OOS years 79% .. 98%). Per the pre-registered fallback, IS = 2008-01-02 .. 2016-12-30. The IS therefore carries a large survivorship gap
   (only 61-77% of member-days have vendor data); the random-portfolio null and the EW_UNIV benchmark share that gap.
2. Ticker re-use exclusions (vendor longName audit of spells that ended before 2015 and overlap vendor data): CCU (Clear Channel vs
   Cervecerias Unidas), CPWR (Compuware vs Ocean Thermal), CSR (1996-2000 member vs Centerspace/IRET history), EP (El Paso vs Empire Petroleum),
   KG (King Pharmaceuticals vs Kestrel), SII (Smith International vs Sprott), SNT (Sonat vs Senstar), SUN (Sunoco Inc vs Sunoco LP).
   Non-EQUITY vendor instruments (29 tickers now used by ETFs/funds, e.g. FB, SDS, VO) were already excluded by the pre-registered rule.
   Same-lineage tickers are kept (e.g. CAR = Cendant -> Avis Budget, VIAV = JDSU, EHC = HealthSouth, ITT). Spells ending 2015 or later were not
   audited by name (residual risk).
3. Nothing else changes. The prereg timestamp says 2026-11-03 23:05:55 UTC; the "2026-11-04" in its header is the KST date (UTC+9).
