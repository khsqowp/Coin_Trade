"""Apply the original Round4 robustness criteria to saved equity transfers."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/research/equity_transfer_2026-10/full_runs/round4_robustness_transfer.json"
OUT = ROOT / "docs/research/equity_transfer_2026-10/full_runs/round4_diagnostic_summary.json"


def analyze():
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    out = {"source": SOURCE.name, "method": "Round4 source instability thresholds applied to the fixed Heikin-Ashi dd=25% BTC-proxy winner on each equity cost case.", "markets": {}}
    for market, payload in data["markets"].items():
        results = {}
        for cost in sorted({r["cost_case"] for r in payload["full_winners"]}):
            main = next(r for r in payload["full_winners"]
                        if r["winner_index"] == 3 and r["cost_case"] == cost)
            periods = [r for r in payload["independent_periods"]
                       if r["winner_index"] == 3 and r["cost_case"] == cost]
            sensitivities = [r for r in payload["sensitivity"] if r["cost_case"] == cost]
            jumps = []
            for left, right in zip(sensitivities, sensitivities[1:]):
                delta = {key: abs(right["metrics"][key] - left["metrics"][key])
                         for key in ("cagr", "mdd", "sharpe")}
                jumps.append({"left": left["threshold"], "right": right["threshold"],
                              "delta": delta,
                              "unstable": bool(delta["cagr"] > 30 or delta["mdd"] > 10 or delta["sharpe"] > .30)})
            flags = {
                "periods": any(r["metrics"]["sharpe"] < .5 or r["metrics"]["cagr"] < 0 for r in periods),
                "top10_trade_concentration": (main["concentration"]["10"]["net_pct"] is not None and
                                               main["concentration"]["10"]["net_pct"] >= 50),
                "threshold_sensitivity": any(r["unstable"] for r in jumps),
                "stop_resume_flapping": main["breaker_flapping"]["within"]["5"]["pct"] >= 30,
                "top5_symbol_concentration": (main["symbol_audit"]["top5_net_pct"] is not None and
                                               main["symbol_audit"]["top5_net_pct"] >= 50),
            }
            count = sum(flags.values())
            results[cost] = {
                "main_policy": main["config"], "full_metrics": main["metrics"],
                "period_count": len(periods),
                "bad_periods": [{"start": p["period_start"], "end": p["period_end"],
                                 "cagr": p["metrics"]["cagr"], "sharpe": p["metrics"]["sharpe"]}
                                for p in periods if p["metrics"]["sharpe"] < .5 or p["metrics"]["cagr"] < 0],
                "top10_trade_net_pnl_pct": main["concentration"]["10"]["net_pct"],
                "top5_symbol_net_pnl_pct": main["symbol_audit"]["top5_net_pct"],
                "resumes_followed_by_pause_within_5d_pct": main["breaker_flapping"]["within"]["5"]["pct"],
                "sensitivity_jumps": jumps, "flags": flags, "instability_count": count,
                "verdict": "기각" if count >= 2 else "승격" if count == 0 else "조건부 보류",
            }
        out["markets"][market] = results
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False))
    return out


if __name__ == "__main__":
    analyze()
