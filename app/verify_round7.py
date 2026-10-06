"""Independent Round 7 artifact arithmetic and execution spot checks."""

import json
import numpy as np
import pandas as pd
from app.crypto_round7_research import PATH, ROOT, random_data, summary
from app.crypto_bucket_ensemble_research import CHAMPION_PATH, volume_prep
from app.crypto_technical_ict_research import load_data
from app.technical_portfolio_engine import prepare, simulate_portfolio


def run() -> None:
    d = json.loads(PATH.read_text())
    source = json.loads(CHAMPION_PATH.read_text())["champion"]
    frames, manifest, _ = load_data()
    assert manifest == d["manifest"]
    p = volume_prep(frames)
    data = prepare(p)
    assert summary(simulate_portfolio(p)) == d["baseline"]
    assert len(source["trades"]) == 468 and d["ledger_exact_match"]
    mc = d["monte_carlo"]
    trials = mc["trials"]
    assert len(trials) == len({t["seed"] for t in trials}) == 500
    for k in ["cagr", "sharpe"]:
        x = np.array([t[k] for t in trials])
        t = mc["tests"][k]
        assert t["percentile"] == 100 * np.mean(x < d["baseline"][k])
        assert t["p"] == (1 + np.sum(x >= d["baseline"][k])) / 501
        assert t["q95"] == np.percentile(x, 95)
    for row in [trials[0], trials[249], trials[-1]]:
        result = simulate_portfolio(
            {},
            prepared=random_data(data, row["seed"], mc["probability"]),
            return_trace=True,
        )
        assert summary(result) == {k: row[k] for k in d["baseline"]}
        assert all(
            pd.Timestamp(e["known_through"]) < pd.Timestamp(e["date"])
            for e in result["allocations"]
        )
        assert max(t["positions"] for t in result["trace"]) <= 8
    years = sorted({pd.Timestamp(t["exit_date"]).year for t in source["trades"]})
    assert years == d["leave_one_out"]["years"]
    for row in d["leave_one_out"]["rows"]:
        if row["kind"] == "symbol":
            reduced = {s: df for s, df in p.items() if s != row["excluded"]}
            assert len(reduced) == 44
        else:
            reduced = {s: df.copy() for s, df in p.items()}
            # Independently form blocked signal dates from next global execution day.
            blocked = [
                a for a, b in zip(data[0], data[0][1:]) if b.year == row["excluded"]
            ]
            for df in reduced.values():
                df.loc[df.index.isin(blocked), "SIGNAL"] = False
        m = simulate_portfolio(reduced)
        assert summary(m) == {k: row[k] for k in d["baseline"]}
        assert row["pass"] == (
            m["cagr"] >= d["baseline"]["cagr"] / 2
            and m["sharpe"] >= d["baseline"]["sharpe"] / 2
        )
    b = d["bootstrap"]
    records = sorted(source["trades"], key=lambda t: (t["entry"], t["exit"], t["id"]))
    assert b["ordered_ids"] == [t["id"] for t in records]
    returns = np.array([t["pnl"] / t["cost"] for t in records])
    np.testing.assert_allclose(returns, b["returns"], atol=1e-14)
    samples = []
    for starts in b["block_starts"]:
        assert len(starts) == 24 and min(starts) >= 0 and max(starts) <= 448
        indices = np.concatenate([np.arange(start, start + 20) for start in starts])[
            :468
        ]
        x = returns[indices]
        samples.append(
            x.mean() / x.std(ddof=1) * np.sqrt(468 / source["full"]["years"])
        )
    assert len(samples) == 1000
    np.testing.assert_allclose(samples, b["samples"], atol=1e-13)
    np.testing.assert_allclose(
        np.percentile(samples, [2.5, 97.5]), b["ci95"], atol=1e-13
    )
    votes = [
        all(t["significant"] and t["p"] < 0.05 for t in mc["tests"].values()),
        all(r["pass"] for r in d["leave_one_out"]["rows"]),
        b["ci95"][0] > 0,
    ]
    assert votes == d["votes"]
    doc = (ROOT / "docs/전략-백테스트-종합.md").read_text()
    assert doc.count("## 19.") == doc.count("## 20.") == 1
    assert doc.index("## 19.") < doc.index("## 결론") < doc.index("## 20.")
    section = doc.split("## 19.")[1].split("## 결론")[0]
    assert f'**{d["verdict"]}**' in section
    for n in range(1, 5):
        assert f"### 19-{n}." in section
    for row in d["leave_one_out"]["rows"]:
        assert (
            f"{row['cagr']:+.2f}% | {row['mdd']:.2f}% | {row['sharpe']:.3f}" in section
        )
    for n in range(1, 7):
        log = (ROOT / f"docs/round7-round{n}-regression-2026-10-07.txt").read_text()
        assert "PASS:" in log and "Traceback" not in log
    print(
        "PASS: exact baseline/468 source trades; 500 unique seeds and 3 full engine spot checks; causal timestamps/slot bounds; all 5 symbol and annual leave-outs independently rerun; 1000 block sequences independently reconstructed; percentile/p-value/votes; section19/20 placement and tables; Round1-6 regressions"
    )


if __name__ == "__main__":
    run()
