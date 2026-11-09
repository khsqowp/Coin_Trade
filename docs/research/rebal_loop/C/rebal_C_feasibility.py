"""Pre-outcome feasibility audit for the hourly cadence study; read-only and offline."""
from __future__ import annotations
import os
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[5]
R2C = ROOT / "trading/docs/research/lev_loop/R2C"
OLD_NAME = "rs_final_panel.npz"
PIT_NAME = "pit_panel.npz"

def safe_env_file_status(name: str, filename: str) -> dict[str, object]:
    value = os.environ.get(name, "")
    return {"configured": bool(value), "file_present": bool(value) and (Path(value) / filename).is_file()}

def panel_status(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {"present": False}
    with np.load(path, allow_pickle=True) as z:
        return {"present": True, "keys": sorted(z.files), "H_shape": list(z["H"].shape),
                "L_shape": list(z["L"].shape), "C_shape": list(z["C"].shape),
                "FD_shape": list(z["FD"].shape), "names_count": len(z["names"]),
                "days_count": len(z["days"]), "hourly_bars_per_day_axis": z["C"].shape[1]}

def main() -> None:
    print("FEASIBILITY AUDIT — no strategy outputs calculated")
    old = safe_env_file_status("RS_FINAL_SCRATCH", OLD_NAME)
    pit = safe_env_file_status("RS_FINAL_SCRATCH", PIT_NAME)
    print("OLD configured:", old["configured"], "panel present:", old["file_present"])
    print("OLD-PIT configured:", pit["configured"], "panel present:", pit["file_present"])
    print("NEW panel:", panel_status(R2C / "data/new_panel_2020_2021.npz"))
    print("R2C hourly panel builder source: daily x 24 array layout; see r2c_build_panel.py")
    print("R2C runner cadence source: int rebal compared with day index i-last_reb; see rs_lev_r2c_engine.py")
    print("Parity status: NOT RUN; required OLD panel absent or unavailable")
    print("Decision: hourly 1..72h backtest is not identified by the legacy engine without a new hourly clock implementation and OLD baseline parity")

if __name__ == "__main__":
    main()
