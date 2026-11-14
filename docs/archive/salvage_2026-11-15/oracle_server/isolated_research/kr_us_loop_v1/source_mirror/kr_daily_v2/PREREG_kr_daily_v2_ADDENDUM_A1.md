# Addendum A1 to PREREG_kr_daily_v2 (data repair rule). Written 2026-11-04 ~08:55 KST, BEFORE any v2 strategy run.
Trigger: data QC (qc2.py) on the first 54 fetched files found 5 names with close-to-close moves far beyond the KRX daily limit (+552%, +121%, -96%, -90%, -88%).
QC only, no strategy was computed. Inspection showed all 5 are delisted names in their final 정리매매 (delisting liquidation) sessions, which have no price limit, after halts.
KIS shows halts as zero-volume rows at a flat price.

Rule (applied in bt2.load_panel to every name):
1. Moves are measured between consecutive rows with volume > 0 (halt rows are skipped).
2. A move with abs(C_t / C_prev_traded - 1) > L(t) is beyond the daily limit. L = 15.5% for dates before 2015-06-15, 30.5% from then on.
   - If t is within the last 15 rows of a name whose data ends before END, the move is a delisting/liquidation move. It is KEPT unchanged, because it is a real loss or gain for a holder.
   - Otherwise it is treated as an unadjusted corporate action (capital reduction, rights issue, re-basing after a halt). All open/high/low/close on rows before t are multiplied by C_t / C_prev_traded, and volume on those rows is divided by the same factor (traded value unchanged), so the return on day t becomes 0.
   The error from this repair is bounded by the true limit move (about 30%) on that day. Its sign is unknown.
3. The number of repaired events, the names involved, and the distribution of repair factors are reported.
Sensitivity (selection = 0): the IS pick run on unrepaired data.
