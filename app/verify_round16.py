"""Independent Round16 causality, old-engine parity, exit and correction checks."""

import copy
import importlib.util
import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
from app import crypto_round16_liquidation_research as r
from app.liquidation_proximity_signal_core import find_signals, TIER_SETS
from app.technical_portfolio_engine import (
    prepare,
    simulate_portfolio,
    simulate_research_portfolio,
)
from app.crypto_round11_research import build as build11, configs as configs11
from app.crypto_round8_research import core


def old_module(path: str, target: Path):
    """Load HEAD engine source into an isolated temporary module."""
    target.write_text(
        subprocess.check_output(["git", "show", "HEAD:" + path], text=True)
    )
    spec = importlib.util.spec_from_file_location(target.stem, target)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def synthetic() -> None:
    dates = pd.date_range("2020-01-01", periods=6, tz="UTC")
    f = pd.DataFrame(
        dict(
            Open=100.0,
            High=110.0,
            Low=90.0,
            Close=100.0,
            SIGNAL=False,
            VOL_RATIO=1.0,
            ATR14=1.0,
            STOP_LEVEL=0.0,
        ),
        index=dates,
    )
    f.loc[dates[0], "SIGNAL"] = True
    # Exit signal at close day2 cannot sell at open day2; sell day3 gap80.
    f.loc[dates[3], "Open"] = 80.0
    signals = np.zeros((6, 1))
    signals[2, 0] = 1
    for fn in (simulate_portfolio, simulate_research_portfolio):
        m = fn({"X": f}, top_k=1, exit_signals=signals, return_trace=True)
        assert m["records"][0]["entry"] == 1 and m["records"][0]["exit"] == 3
        np.testing.assert_allclose(m["final"], 0.8 * (1 - 0.0004) ** 2, atol=1e-12)
        assert m["records"][0]["pnl"] < 0
        # Price move later today cannot affect open entry weight.
        changed = f.copy()
        changed.loc[dates[1], "Close"] = 500.0
        n = fn({"X": changed}, top_k=1, exit_signals=signals, return_trace=True)
        assert n["allocations"] == m["allocations"]
    # Simple repeated trailing extrema yield density >=2; expired anchors disappear.
    raw = f.drop(columns=["SIGNAL", "VOL_RATIO", "ATR14", "STOP_LEVEL"]).copy()
    raw["High"], raw["Low"] = 100.0, 100.0
    q = find_signals(raw, 7, TIER_SETS[1])
    assert q.DOWN_DENSITY.max() >= 2
    assert q.DOWN_DISTANCE.dropna().ge(0).all()
    assert q.UP_DISTANCE.dropna().ge(0).all()
    grid = r.plans()
    assert len(grid) == 397
    # Full BH can accept tied p-values even if the first rank threshold fails.
    rows: list[dict] = []
    for i in range(10):
        rows.append(
            dict(
                dominates=True,
                robustness=dict(
                    votes=[True] * 4,
                    monte_carlo=dict(
                        tests={
                            k: dict(p=0.004 if i < 5 else 1.0)
                            for k in ("cagr", "sharpe")
                        }
                    ),
                ),
            )
        )
    out = dict(grid=list(range(10)), experiments=rows)
    r.corrections(out)
    assert rows[0]["correction"]["cagr"]["bh_q"] == 0.008
    assert rows[0]["verdict"] == "복귀조건 A 후보"
    rows[0]["robustness"]["votes"][0] = False
    r.corrections(out)
    assert rows[0]["verdict"] == "기각"
    print(
        "PASS synthetic next-open exit/gap/fees/negative exit/BH step-up/AND",
        flush=True,
    )


def saved_arithmetic(frames: dict, out: dict) -> dict:
    """Reconstruct NAV from stored fills plus source prices, then verify all gates."""
    assert out["grid"] == r.plans()
    assert [x["config"] for x in out["experiments"]] == out["grid"]
    snapshot = copy.deepcopy(
        [(x["correction"], x["verdict"]) for x in out["experiments"]]
    )
    r.corrections(out)
    assert snapshot == [(x["correction"], x["verdict"]) for x in out["experiments"]]
    dates = sorted(set().union(*(f.loc[r.START :].index for f in frames.values())))
    close = {s: f.Close.reindex(dates).ffill().to_numpy() for s, f in frames.items()}
    years = (dates[-1] - dates[0]).days / 365.25
    count = 0
    for row in out["experiments"]:
        m, b = row["metrics"], out["baseline"]
        assert row["dominates"] == (
            m["cagr"] > b["cagr"] and m["mdd"] < b["mdd"] and m["sharpe"] > b["sharpe"]
        )
        if "paired_control" in row:
            pair = row["paired_control"]
            assert all(
                pair["delta"][k] == m[k] - pair["metrics"][k] for k in pair["delta"]
            )
        if "robustness" not in row:
            assert not row["dominates"]
            continue
        rob = row["robustness"]
        assert tuple((p["start"], p["end"]) for p in rob["periods"]) == r.ALPHA_PERIODS
        for period in rob["periods"]:
            btc = r.btc_period(frames["BTC"], period["start"], period["end"])
            assert btc["cagr"] == period["btc_cagr"]
            assert period["alpha"] == period["metrics"]["cagr"] - btc["cagr"]
        records = rob["records"]
        assert len(records) == m["trades"]
        net = sum(x["pnl"] for x in records)
        np.testing.assert_allclose(net, m["final"] - 1, atol=1e-8)
        top10 = (
            sum(
                x["pnl"]
                for x in sorted(records, key=lambda x: (-x["pnl"], x["id"]))[:10]
            )
            / net
            * 100
        )
        grouped: dict[str, float] = {}
        for trade in records:
            grouped[trade["symbol"]] = grouped.get(trade["symbol"], 0.0) + trade["pnl"]
        top5 = (
            sum(sorted(grouped.values(), reverse=True)[:5])
            / sum(grouped.values())
            * 100
        )
        np.testing.assert_allclose(
            top10, rob["concentration"]["10"]["net_pct"], atol=1e-10
        )
        np.testing.assert_allclose(top5, rob["symbols"]["net_pct"], atol=1e-10)
        trials = rob["monte_carlo"]["trials"]
        assert len(trials) == 500 and [t["seed"] for t in trials] == list(
            range(1600000, 1600500)
        )
        for k, test in rob["monte_carlo"]["tests"].items():
            n = sum(t[k] >= m[k] for t in trials)
            assert test["p"] == (n + 1) / 501 and test["exceedances"] == n
        nav = np.ones(len(dates))
        for trade in records:
            e, x = trade["entry"], trade["exit"]
            assert trade["entry_date"] == str(dates[e]) and trade["exit_date"] == str(
                dates[x]
            )
            nav[e:x] += trade["qty"] * close[trade["symbol"]][e:x] - trade["cost"]
            nav[x:] += trade["pnl"]
        daily = pd.Series(nav).pct_change().dropna()
        np.testing.assert_allclose(
            [
                ((nav[-1] ** (1 / years)) - 1) * 100,
                ((np.maximum.accumulate(nav) - nav) / np.maximum.accumulate(nav)).max()
                * 100,
                daily.mean() / daily.std() * np.sqrt(365),
                nav[-1],
            ],
            [m[k] for k in ("cagr", "mdd", "sharpe", "final")],
            atol=1e-8,
            rtol=1e-10,
        )
        boot = r.bootstrap(nav.tolist(), years)
        np.testing.assert_allclose(
            boot["samples"], rob["bootstrap"]["samples"], atol=1e-8, rtol=1e-10
        )
        np.testing.assert_allclose(
            boot["ci95"], rob["bootstrap"]["ci95"], atol=1e-8, rtol=1e-10
        )
        votes = [
            sum(p["alpha"] > 0 for p in rob["periods"]) >= 7,
            top10 <= 103 and top5 <= 88,
            all(t["p"] < 0.05 for t in rob["monte_carlo"]["tests"].values()),
            boot["ci95"][0] > 0,
        ]
        assert votes == rob["votes"]
        count += 1
    result = dict(
        saved_results_arithmetic=True,
        nav_and_bootstrap_reconstructed=count,
        exact_configs=len(out["experiments"]),
    )
    print("PASS saved arithmetic", json.dumps(result), flush=True)
    return result


def run() -> dict:
    synthetic()
    frames, _, _ = r.load_data()
    cutoff = pd.Timestamp("2024-06-30", tz="UTC")
    count = 0
    for tiers in TIER_SETS:
        for window in (7, 14, 30):
            for symbol, f in frames.items():
                whole = find_signals(f, window, tiers)
                prefix = find_signals(f.loc[:cutoff], window, tiers)
                pd.testing.assert_frame_equal(whole.loc[:cutoff], prefix)
                # Future mutation verifies actual suffix isolation for all symbols.
                changed = f.copy()
                changed.loc[
                    changed.index > cutoff, ["Open", "High", "Low", "Close"]
                ] *= 3.0
                changed.loc[changed.index > cutoff, "Volume"] *= 7.0
                future = find_signals(changed, window, tiers)
                pd.testing.assert_frame_equal(whole.loc[:cutoff], future.loc[:cutoff])
                count += 1
            print(
                "PASS proxy",
                tiers,
                window,
                "45 symbols prefix/future mutation",
                flush=True,
            )
    bank, _ = r.donors(frames)
    with tempfile.TemporaryDirectory() as directory:
        old_technical = old_module(
            "app/technical_portfolio_engine.py", Path(directory) / "old_technical.py"
        )
        old_research = old_module(
            "app/round11_portfolio.py", Path(directory) / "old_research.py"
        )
        for family, (p, kw) in bank.items():
            before = old_technical.simulate_portfolio(p, return_trace=True, **kw)
            after = simulate_portfolio(p, return_trace=True, **kw)
            assert r.summary(before) == r.summary(after)
            assert (
                before["trace"] == after["trace"]
                and before["allocations"] == after["allocations"]
            )
            assert len(after["records"]) == after["trades"]
            np.testing.assert_allclose(
                sum(x["pnl"] for x in after["records"]), after["final"] - 1, atol=1e-8
            )
        cores = {n: core(n, frames) for n in ("volume", "heikin_ashi", "frvp")}
        for config in [c for group in configs11().values() for c in group]:
            p, data, kw, _ = build11(config, frames, cores)
            before = old_research.simulate(p, prepared=data, return_trace=True, **kw)
            after = simulate_research_portfolio(
                p, prepared=data, return_trace=True, **kw
            )
            assert before == after
        print("PASS HEAD engine parity: 10 C donors + all Round11 configs", flush=True)
    result = dict(
        proxy_prefix_future_checks=count,
        technical_controls=10,
        round11_configs=sum(len(group) for group in configs11().values()),
        synthetic=True,
        old_engine_parity=True,
    )
    if r.PATH.exists():
        out = json.loads(r.PATH.read_text())
        if len(out["experiments"]) == len(out["grid"]):
            result.update(saved_arithmetic(frames, out))
    print("VERIFICATION", json.dumps(result), flush=True)
    return result


if __name__ == "__main__":
    run()
