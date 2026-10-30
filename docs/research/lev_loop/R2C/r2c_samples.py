"""R2C sample loaders (OLD survivor panel, NEW pre-2022 PIT, OLD-PIT 2022-2026 PIT)."""
import os, sys
sys.path.insert(0, "/Users/user/Desktop/CODE/Ochestration/trading")
import numpy as np, pandas as pd
from app import rs_lev_r2c_data as D, rs_lev_r2c_lib as LIB
HERE = os.path.dirname(os.path.abspath(__file__))
SCR = os.environ["RS_FINAL_SCRATCH"]

def _panel_from_npz(z, a=None, b=None, cols=None):
    days = pd.DatetimeIndex(z["days"], tz="UTC")
    a = 0 if a is None else a; b = len(days) if b is None else b
    cols = list(range(len(z["names"]))) if cols is None else cols
    return dict(names=[str(x) for x in z["names"][cols]], days=days[a:b], H=np.ascontiguousarray(z["H"][a:b][:, :, cols]),
                L=np.ascontiguousarray(z["L"][a:b][:, :, cols]), C=np.ascontiguousarray(z["C"][a:b][:, :, cols]),
                FD=np.ascontiguousarray(z["FD"][a:b][:, cols]), member=np.ascontiguousarray(z["member"][a:b][:, cols]))

def old():
    return LIB.Sample("OLD", D.load_old(), "2022-01-01", None)

def new():
    z = np.load(os.path.join(HERE, "data/new_panel_2020_2021.npz"), allow_pickle=True)
    return LIB.Sample("NEW", _panel_from_npz(z), "2020-03-01", None)

def old_pit():
    z = np.load(os.path.join(SCR, "pit_panel.npz"), allow_pickle=True)
    days = pd.DatetimeIndex(z["days"], tz="UTC")
    a = int(days.searchsorted(pd.Timestamp("2021-12-01", tz="UTC"))); b = int(days.searchsorted(pd.Timestamp("2026-10-01", tz="UTC")))
    s22 = int(days.searchsorted(pd.Timestamp("2022-01-01", tz="UTC")))
    cols = [j for j in range(len(z["names"])) if z["member"][s22:b, j].any()]
    return LIB.Sample("OLDPIT", _panel_from_npz(z, a, b, cols), "2022-01-01", None)
