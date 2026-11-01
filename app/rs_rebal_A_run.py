"""Offline V0 parity gate for the hourly rebalancing research engine.

Uses only rs_final_panel.npz and local .rs_cache data; never imports exchange clients.
The sweep is intentionally blocked until every parity comparison passes.
"""
import numpy as np

from app.rs_final_data import load_panel
from app.rs_final_engine import Sim
from app.rs_rebal_A_engine import run as run_hourly


def main():
    panel = load_panel()
    sim = Sim(panel)
    nd = sim.nd
    try:
        from app.rs_risk_load import load
        from app.rs_risk_engine import build_panel

        ohlc, funding = load()
        raw = build_panel(
            {k: v for k, v in ohlc.items() if k in sim.names},
            {k: v for k, v in funding.items() if k in sim.names},
        )
        raw_names = {name: i for i, name in enumerate(raw["names"])}
        hourly_funding = np.zeros_like(sim.C)
        for j, name in enumerate(sim.names):
            if name in raw_names:
                hourly_funding[:, :, j] = (
                    sim.C[:, :, j] * raw["F"][:, :, raw_names[name]]
                )
        daily_sum = hourly_funding.sum(axis=1)
        mask = np.isfinite(daily_sum) & np.isfinite(sim.FD)
        funding_error = float(np.max(np.abs(daily_sum[mask] - sim.FD[mask])))
    except Exception as exc:
        raise RuntimeError("Local hourly funding reconstruction failed") from exc

    print("panel", nd, len(sim.names), sim.days[0], sim.days[-1])
    print("funding_reconstruction_max_abs_daily_FD_diff", funding_error)
    if funding_error > 1e-10:
        raise RuntimeError("Hourly funding does not reconcile to daily FD")

    score = np.repeat(sim.signal((14,), False)[:, None, :], 24, axis=1)
    score = score.reshape(nd * 24, -1)
    crash = np.repeat(sim.crash[:, None], 24, axis=1).ravel()
    windows = {
        "FULL": (sim.d_start("2022-01-01"), nd),
        "IS": (sim.d_start("2022-01-01"), sim.d_start("2024-07-01")),
        "OOS": (sim.d_start("2024-07-01"), min(nd, sim.d_start("2026-10-10"))),
    }
    passed = True
    for window, (d0, d1) in windows.items():
        for phase in range(3):
            ref = sim.run(
                rebal=3, lev=4, deploy=0.95, K=8, kill=0.35, cool=14,
                cost=0.001, fund=1, resize=0, crash_flat=True,
                phase=phase, d0=d0, d1=d1,
            )
            eqh, _, _ = run_hourly(
                sim.H, sim.L, sim.C, hourly_funding, score, crash,
                d0, d1, 72, 23 + 24 * phase, 0.001, 0, 0,
            )
            a = ref["eq"].iloc[d0:d1].to_numpy()
            b = eqh[d0 * 24 + 23:d1 * 24:24]
            a = a[np.isfinite(a)]
            b = b[np.isfinite(b)]
            length = min(len(a), len(b))
            a, b = a[-length:], b[-length:]
            abs_diff = float(np.max(np.abs(a - b))) if length else float("nan")
            rel_diff = float(
                np.max(np.abs(a - b) / np.maximum(np.abs(a), 1e-12))
            ) if length else float("nan")
            exact = bool(np.array_equal(a, b))
            passed &= (rel_diff < 1e-9)
            print(
                window, "phase", phase, "n", length,
                "max_abs", abs_diff, "max_rel", rel_diff,
                "sim_final", float(a[-1]), "hourly_final", float(b[-1]),
                "bit_exact", exact,
            )
    for period, legacy_days in ((24, 1), (48, 2)):
        d0, d1 = windows["FULL"]
        ref = sim.run(rebal=legacy_days, lev=4, deploy=0.95, K=8, kill=0.35,
                      cool=14, cost=0.001, fund=1, resize=0, crash_flat=True,
                      phase=0, d0=d0, d1=d1)
        eqh, _, _ = run_hourly(sim.H, sim.L, sim.C, hourly_funding, score, crash,
                               d0, d1, period, 23, 0.001, 0, 0)
        a = ref["eq"].iloc[d0:d1].to_numpy()
        b = eqh[d0 * 24 + 23:d1 * 24:24]
        mask = np.isfinite(a) & np.isfinite(b)
        ad = float(np.max(np.abs(a[mask] - b[mask])))
        rd = float(np.max(np.abs(a[mask] - b[mask]) / np.maximum(np.abs(a[mask]), 1e-12)))
        passed &= rd < 1e-9
        print("GENERALITY", period, "h", "max_abs", ad, "max_rel", rd,
              "bit_exact", bool(np.array_equal(a[mask], b[mask])))
    if not passed:
        raise SystemExit("V0 parity failed; do not run the performance sweep")
    print("V0 parity passed; the preregistered sweep may proceed")


if __name__ == "__main__":
    main()
