"""Validate the immutable Y calendar, prior rejection and all five gate arithmetic."""

import json
import numpy as np
from app.crypto_round14_research import PATH, ROOT
from app.round_period_standard import ALPHA_PERIODS, assert_standard, alpha_pass
from app.crypto_round4_robustness import concentration
from app.crypto_round6_research import symbols


def run() -> None:
    out = json.loads(PATH.read_text())
    assert (
        tuple(map(tuple, out["periods"])) == ALPHA_PERIODS
        and len(set(ALPHA_PERIODS)) == 8
    )
    assert_standard(out["round13_reassessment"]["periods"])
    assert not alpha_pass(out["round13_reassessment"]["periods"])
    assert out["round13_reassessment"]["verdict"] == "기각"
    historical = json.loads((ROOT / "docs/round4-results-2026-10-07.json").read_text())[
        "periods"
    ]
    try:
        assert_standard([dict(start=a, end=b, alpha=1) for a, b in historical])
    except ValueError:
        pass
    else:
        raise AssertionError("definition X must be rejected")
    seen = {
        json.dumps(r["config"], sort_keys=True)
        for n in [12, 13]
        for r in json.loads(
            (ROOT / f"docs/round{n}-results-2026-10-07.json").read_text()
        )["experiments"]
    }
    for row in out["experiments"]:
        key = json.dumps(row["config"], sort_keys=True)
        assert key not in seen
        seen.add(key)
        assert all(row["causal_checks"].values())
        m, b = row["metrics"], out["baseline"]
        assert np.isfinite(list(m.values())).all()
        assert row["dominates"] == (
            m["cagr"] > b["cagr"] and m["mdd"] < b["mdd"] and m["sharpe"] > b["sharpe"]
        )
        if not row["dominates"]:
            continue
        r = row["robustness"]
        assert_standard(r["periods"])
        for p in r["periods"]:
            np.testing.assert_allclose(
                p["alpha"], p["metrics"]["cagr"] - p["btc_cagr"], rtol=0, atol=1e-10
            )
        conc = concentration(r["records"])
        sy = symbols(r["records"])
        for count, values in conc.items():
            for field, value in values.items():
                np.testing.assert_allclose(
                    value, r["concentration"][count][field], rtol=0, atol=1e-10
                )
        assert json.loads(json.dumps(sy["top5"])) == r["symbols"]["top5"]
        np.testing.assert_allclose(
            sy["net_pct"], r["symbols"]["net_pct"], rtol=0, atol=1e-10
        )
        assert abs(sum(t["pnl"] for t in r["records"]) - (m["final"] - 1)) < 1e-8
        trials = r["monte_carlo"]["trials"]
        assert len(trials) >= 300
        assert len({t["seed"] for t in trials}) == len(trials)
        for k in ["cagr", "sharpe"]:
            assert r["monte_carlo"]["tests"][k]["p"] == (
                1 + sum(t[k] >= m[k] for t in trials)
            ) / (1 + len(trials))
        boot = r["bootstrap"]
        assert boot["block_size"] == 20 and boot["iterations"] >= 1000
        np.testing.assert_allclose(
            np.percentile(boot["samples"], [2.5, 97.5]), boot["ci95"]
        )
        rates = (
            [r["breaker_5day_pct"]] if r["breaker_5day_pct"] is not None else []
        ) + ([r["thrashing"]["within"]["5"]["pct"]] if r["thrashing"] else [])
        expected = [
            alpha_pass(r["periods"]),
            conc["10"]["net_pct"] <= 103 and sy["net_pct"] <= 88,
            all(t["p"] < 0.05 for t in r["monte_carlo"]["tests"].values()),
            boot["ci95"][0] > 0,
            all(x <= 50 for x in rates),
        ]
        assert r["votes"] == expected and r["verdict"] == (
            "통과" if all(expected) else "기각"
        )
    if out["status"] == "복귀조건 A 달성":
        assert any(
            all(r.get("robustness", {}).get("votes", [False]))
            for r in out["experiments"]
        )
    import sys

    if "--replay" in sys.argv:
        from app import crypto_round12_research as old
        from app.crypto_round13_extension import build, audit
        from app.technical_portfolio_engine import simulate_portfolio
        from app.crypto_round6_research import btc_period

        frames, manifest, skipped = old.load_data()
        assert manifest == out["manifest"] and not skipped
        old.build = build
        for i, row in enumerate(out["experiments"], 1):
            p, kw, state = build(frames, row["config"])
            full = simulate_portfolio(p, return_trace=True, **kw)
            for k, v in old.summary(full).items():
                np.testing.assert_allclose(v, row["metrics"][k], rtol=0, atol=1e-10)
            assert all(audit(frames, row["config"], full).values())
            print(
                f"REPLAY {i}/{len(out['experiments'])} full45 causal and metrics",
                flush=True,
            )
            if row["config"] != out.get("winner_config"):
                continue
            r = row["robustness"]
            for saved in r["periods"]:
                start, end = saved["start"], saved["end"]
                sub = {
                    s: f.loc[start:end] for s, f in p.items() if len(f.loc[start:end])
                }
                actual = old.summary(simulate_portfolio(sub, **kw))
                for k, v in actual.items():
                    np.testing.assert_allclose(
                        v, saved["metrics"][k], rtol=0, atol=1e-10
                    )
                benchmark = btc_period(frames["BTC"], start, end)["cagr"]
                np.testing.assert_allclose(
                    benchmark, saved["btc_cagr"], rtol=0, atol=1e-10
                )
            boot = r["bootstrap"]
            ordered = sorted(
                r["records"], key=lambda t: (t["entry"], t["exit"], t["id"])
            )
            returns = np.array([t["proceeds"] / t["cost"] - 1 for t in ordered])
            assert [t["id"] for t in ordered] == boot["ordered_ids"]
            np.testing.assert_allclose(returns, boot["returns"], atol=1e-14)
            rng = np.random.default_rng(boot["seed"])
            samples = []
            for saved_starts in boot["block_starts"]:
                starts = rng.integers(
                    0, len(returns) - 19, size=int(np.ceil(len(returns) / 20))
                )
                assert starts.tolist() == saved_starts
                indices = (starts[:, None] + np.arange(20)).ravel()[: len(returns)]
                sample = returns[indices]
                samples.append(sample.mean() / sample.std(ddof=1) * boot["annualizer"])
            np.testing.assert_allclose(samples, boot["samples"], rtol=0, atol=1e-10)
            # Replay independent engine draws at start/middle/end of the MC bank.
            from app.technical_portfolio_engine import prepare
            from app.crypto_round7_research import random_data

            data = prepare(p)
            for trial in [r["monte_carlo"]["trials"][i] for i in [0, 149, 299]]:
                random = random_data(
                    data, trial["seed"], r["monte_carlo"]["probability"]
                )
                actual = old.summary(simulate_portfolio(p, prepared=random, **kw))
                for k, v in actual.items():
                    np.testing.assert_allclose(v, trial[k], rtol=0, atol=1e-10)
            from app.crypto_round10_research import transition_stats

            assert transition_stats(state, data[0]) == r["thrashing"]
            print(
                "PASS winner eight Y windows, three MC engine draws, 1000 bootstrap sequences, transitions independently replayed",
                flush=True,
            )
    print(
        f"PASS Round14 {len(out['experiments'])} novel combinations; immutable Y only; X rejected; causal audits; independent five gate arithmetic"
    )


if __name__ == "__main__":
    run()
