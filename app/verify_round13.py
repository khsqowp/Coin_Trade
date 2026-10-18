"""Artifact checks and causal synthetic entry tests; no external data fetching."""

import json
import sys
import numpy as np
import pandas as pd
from app.crypto_technical_ict_research import ROOT
from app.round13_signals import FAMILIES, find_signals

EXTRA_FAMILIES = []
from app.technical_portfolio_engine import simulate_portfolio


def cost_checks():
    from app.round13_costs import simulate_cost_portfolio

    dates = pd.date_range("2020-01-01", periods=80, tz="UTC")
    close = 100 * np.exp(np.linspace(0, 0.2, 80) + 0.03 * np.sin(np.arange(80)))
    f = pd.DataFrame(
        dict(
            Open=close,
            High=close * 1.02,
            Low=close * 0.98,
            Close=close,
            SIGNAL=np.arange(80) % 7 == 0,
            VOL_RATIO=2.0,
            ATR14=1.0,
            STOP_LEVEL=0.0,
        ),
        index=dates,
    )
    book = {"A": f, "B": f.copy()}
    for kwargs in [
        {},
        {"sizing": "inverse_vol", "target_vol": 0.8, "weight_cap": 0.25},
        {"entry_scale": dict.fromkeys(dates, 0.6)},
        {"btc_ok": dict.fromkeys(dates, True), "hold_days": 30},
    ]:
        a = simulate_portfolio(book, return_trace=True, **kwargs)
        b = simulate_cost_portfolio(book, return_trace=True, **kwargs)
        assert a == b
    from app.round13_adaptive import CompletedTradeScale, posterior_scale
    from app.crypto_round4_robustness import ledger_run

    for mode in ["win", "payoff"]:
        scale = CompletedTradeScale(mode, 40)
        kwargs = dict(entry_scale=scale, hold_days=3, top_k=2)
        actual, records, _, _, _ = ledger_run(book, kwargs)
        history = list(scale.history)
        for observation in history:
            completed = [
                t
                for t in records
                if pd.Timestamp(t["exit_date"]) <= pd.Timestamp(observation["date"])
            ]
            returns = [
                t["return_pct"] / 100
                for t in sorted(completed, key=lambda t: (t["exit"], t["id"]))
            ]
            assert observation["completed"] == len(returns)
            np.testing.assert_allclose(
                observation["scale"],
                posterior_scale(returns, mode, 40),
                rtol=0,
                atol=1e-12,
            )
        assert len(records) > 5
        replay = simulate_portfolio(book, return_trace=True, **kwargs)
        assert replay == actual  # same mutable policy resets for every engine call
        zero = simulate_cost_portfolio(book, return_trace=True, **kwargs)
        assert zero == actual
        prefix = {k: f.iloc[:55] for k, f in book.items()}
        short = simulate_portfolio(prefix, return_trace=True, **kwargs)
        assert short["trace"][:-1] == actual["trace"][:54]
    print(
        "PASS online scale actual-ledger completed-count/posterior arithmetic, repeated-run reset, cost-zero parity, execution prefix"
    )
    days = pd.date_range("2020-01-01", periods=3, tz="UTC")
    single = pd.DataFrame(
        dict(
            Open=[100.0, 100.0, 110.0],
            High=[100.0, 100.0, 110.0],
            Low=[100.0, 100.0, 110.0],
            Close=[100.0, 100.0, 110.0],
            SIGNAL=[True, False, False],
            VOL_RATIO=1.0,
            ATR14=0.0,
            STOP_LEVEL=0.0,
        ),
        index=days,
    )
    slip, funding, fee = 0.001, 0.1095, 0.0004
    result = simulate_cost_portfolio(
        {"X": single}, top_k=1, hold_days=1, slippage=slip, funding_annual=funding
    )
    qty = (1 - fee) / (100 * (1 + slip))
    expected = qty * 110 * (1 - slip) * (1 - fee) - qty * 100 * funding / 365 * (
        2 / 3 + 1
    )
    np.testing.assert_allclose(result["final"], expected, rtol=0, atol=1e-12)
    print(
        "PASS cost adapter 4 complete traces and independent two-day funding/slippage arithmetic"
    )


def run():
    cost_checks()
    path = ROOT / "docs/round13-results-2026-10-07.json"
    out = json.loads(path.read_text())
    previous = json.loads((ROOT / "docs/round12-results-2026-10-07.json").read_text())
    previous_keys = {
        json.dumps(r["config"], sort_keys=True) for r in previous["experiments"]
    }
    seen = set()
    for row in out["experiments"]:
        key = json.dumps(row["config"], sort_keys=True)
        assert key not in previous_keys
        assert key not in seen
        seen.add(key)
        assert all(row["causal_checks"].values())
        m, b = row["metrics"], out["baseline"]
        assert row["dominates"] == (
            m["cagr"] > b["cagr"] and m["mdd"] < b["mdd"] and m["sharpe"] > b["sharpe"]
        )
        assert np.isfinite(list(m.values())).all()
        if row["dominates"]:
            r = row["robustness"]
            assert len(r["votes"]) == 5 and len(r["monte_carlo"]["trials"]) >= 300
            assert (
                r["bootstrap"]["iterations"] >= 1000
                and r["bootstrap"]["block_size"] == 20
            )
            assert r["verdict"] == ("통과" if all(r["votes"]) else "기각")
            assert abs(sum(t["pnl"] for t in r["records"]) - (m["final"] - 1)) < 1e-8
            from app.crypto_round4_robustness import concentration
            from app.crypto_round6_research import symbols

            actual_conc = concentration(r["records"])
            for count, values in actual_conc.items():
                for field, value in values.items():
                    np.testing.assert_allclose(
                        value, r["concentration"][count][field], rtol=0, atol=1e-10
                    )
            actual_symbols = symbols(r["records"])
            assert actual_symbols["top5"] == r["symbols"]["top5"]
            np.testing.assert_allclose(
                actual_symbols["net_pct"], r["symbols"]["net_pct"], rtol=0, atol=1e-10
            )
            assert [x["symbol"] for x in actual_symbols["rows"]] == [
                x["symbol"] for x in r["symbols"]["rows"]
            ]
            np.testing.assert_allclose(
                [x["pnl"] for x in actual_symbols["rows"]],
                [x["pnl"] for x in r["symbols"]["rows"]],
                rtol=0,
                atol=1e-10,
            )
            for metric in ["cagr", "sharpe"]:
                trials = r["monte_carlo"]["trials"]
                pvalue = (1 + sum(t[metric] >= m[metric] for t in trials)) / (
                    len(trials) + 1
                )
                assert pvalue == r["monte_carlo"]["tests"][metric]["p"]
            np.testing.assert_allclose(
                np.percentile(r["bootstrap"]["samples"], [2.5, 97.5]),
                r["bootstrap"]["ci95"],
            )
            rates = [r["breaker_5day_pct"]] if r["breaker_5day_pct"] is not None else []
            if r["thrashing"] is not None:
                rates.append(r["thrashing"]["within"]["5"]["pct"])
            expected = [
                sum(x["alpha"] > 0 for x in r["legacy_periods"]) >= 7,
                r["concentration"]["10"]["net_pct"] <= 103
                and r["symbols"]["net_pct"] <= 88,
                all(t["p"] < 0.05 for t in r["monte_carlo"]["tests"].values()),
                r["bootstrap"]["ci95"][0] > 0,
                all(v <= 50 for v in rates),
            ]
            assert expected == r["votes"]
            if "round12_extra_gate" in r:
                extra = list(expected)
                extra[0] = extra[0] and sum(x["alpha"] > 0 for x in r["periods"]) >= 7
                assert extra == r["round12_extra_gate"]["votes"]
                assert r["round12_extra_gate"]["verdict"] == (
                    "통과" if all(extra) else "기각"
                )
                assert r["round9_supplemental_positive"] == sum(
                    x["alpha"] > 0 for x in r["periods"]
                )
            boundary4 = json.loads(
                (ROOT / "docs/round4-results-2026-10-07.json").read_text()
            )["periods"]
            boundary6 = json.loads(
                (ROOT / "docs/round6-results-2026-10-07.json").read_text()
            )["periods"]
            assert boundary4 == boundary6
            assert [[x["start"], x["end"]] for x in r["legacy_periods"]] == boundary4
    rng = np.random.default_rng(120012)
    close = 100 * np.exp(np.cumsum(rng.normal(0.001, 0.025, 600)))
    frame = pd.DataFrame(
        dict(
            Open=close * 0.999,
            High=close * 1.03,
            Low=close * 0.97,
            Close=close,
            Volume=rng.uniform(100, 1000, 600),
        ),
        index=pd.date_range("2020-01-01", periods=600, tz="UTC"),
    )
    for name in FAMILIES + EXTRA_FAMILIES:
        a = find_signals(frame, name)
        b = find_signals(frame.iloc[:400], name)
        for field in ["SIGNAL", "VOL_RATIO", "ATR14", "STOP_LEVEL"]:
            np.testing.assert_allclose(a[field].iloc[:400], b[field], equal_nan=True)
        result = simulate_portfolio({"test": a}, return_trace=True)
        assert all(
            pd.Timestamp(x["known_through"]) < pd.Timestamp(x["date"])
            for x in result["allocations"]
        )
    assert len(out["manifest"]) == 45
    if "--replay" in sys.argv:
        from app.crypto_technical_ict_research import load_data
        from app.crypto_round13_extension import build, audit
        from app import crypto_round12_research as old

        old.build = build
        from app.crypto_bucket_ensemble_research import volume_prep
        from app.crypto_round7_research import summary

        frames, manifest, skipped = load_data()
        assert not skipped and manifest == out["manifest"]
        assert summary(simulate_portfolio(volume_prep(frames))) == out["baseline"]
        for i, row in enumerate(out["experiments"], 1):
            p, kw, _ = build(frames, row["config"])
            m = simulate_portfolio(p, return_trace=True, **kw)
            for k, v in summary(m).items():
                np.testing.assert_allclose(v, row["metrics"][k], rtol=0, atol=1e-10)
            assert all(audit(frames, row["config"], m).values())
            print(
                f'REPLAY {i}/{len(out["experiments"])} metrics + full45-universe prefix audit passed',
                flush=True,
            )
    print(
        f"PASS Round13 {len(seen)} unique experiments; {len(FAMILIES+EXTRA_FAMILIES)} synthetic prefix tests; artifacts, 5 gates, entry chronology"
    )


if __name__ == "__main__":
    run()
