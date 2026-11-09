"""R2-B step 1: pre-registered stress-day selection (no network). Reads panel npz only."""
import json, os, numpy as np, pandas as pd
SCR = os.environ["RS_FINAL_SCRATCH"]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "research", "lev_loop", "R2B", "data", "days.json")
Z = np.load(os.path.join(SCR, "rs_final_panel.npz"), allow_pickle=True)
DAYS = pd.DatetimeIndex(Z["days"], tz="UTC"); C = Z["C"]
ND = C.shape[0]
flat = C.reshape(ND * 24, -1)
prev = np.vstack([np.full((1, flat.shape[1]), np.nan), flat[:-1]])
r = (flat / prev - 1).reshape(ND, 24, -1)
with np.errstate(all="ignore"):
    med = np.nanmedian(r, axis=2)           # ND x 24
score = np.nanmax(np.abs(med), axis=1)
start = int(DAYS.searchsorted(pd.Timestamp("2022-01-01", tz="UTC")))
fixed = ["2025-10-10", "2024-12-09", "2025-05-10", "2024-08-05"]
chosen = [pd.Timestamp(d, tz="UTC") for d in fixed]
order = np.argsort(-np.nan_to_num(score[start:], nan=-1)) + start
extra = []
for i in order:
    d = DAYS[i]
    if all(abs((d - c).days) > 1 for c in chosen):
        chosen.append(d); extra.append(str(d.date()))
    if len(extra) == 2: break
print("top 12 days by score:")
for i in order[:12]: print(DAYS[i].date(), round(float(score[i]), 4))
for f in fixed:
    i = int(DAYS.searchsorted(pd.Timestamp(f, tz="UTC"))); print("fixed", f, "score", round(float(score[i]), 4) if i < ND else None)
res = dict(fixed=fixed, extra=extra, days=[str(c.date()) for c in chosen])
json.dump(res, open(OUT, "w"), indent=1); print(res)
