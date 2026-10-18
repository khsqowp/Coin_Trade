"""Fixed champion only: offline random controls, leave-one-out and block bootstrap."""

import json
import numpy as np
import pandas as pd
from app.crypto_bucket_ensemble_research import ROOT, CHAMPION_PATH, volume_prep
from app.crypto_round4_robustness import ledger_run
from app.crypto_technical_ict_research import load_data
from app.technical_portfolio_engine import prepare, simulate_portfolio

PATH = ROOT / "docs/round7-results-2026-10-07.json"


def random_data(data: tuple, seed: int, probability: float) -> tuple:
    """Row-major independent draws; extending calendar preserves every prior draw.

    No real SIGNAL or VOL_RATIO is consulted. Previous bar existence plus
    current open controls availability in the common engine, not future listing.
    """
    dates, keys, arrays = data
    rng = np.random.default_rng(seed)
    draws = rng.random((len(dates), len(keys), 2))
    a = dict(arrays)
    a["SIGNAL"] = (draws[:, :, 0] < probability) & np.isfinite(arrays["Open"])
    a["VOL_RATIO"] = draws[:, :, 1]
    return dates, keys, a


def summary(result: dict) -> dict:
    return {
        k: float(result[k]) if k != "trades" else int(result[k])
        for k in ["cagr", "mdd", "sharpe", "trades", "final"]
    }


def monte_carlo(data: tuple, probability: float, base: dict) -> tuple:
    eligible = np.isfinite(data[2]["Open"][:-1]) & np.isfinite(data[2]["Open"][1:])
    trials = []
    for seed in range(700000, 700500):
        result = simulate_portfolio({}, prepared=random_data(data, seed, probability))
        trials.append(dict(seed=seed, **summary(result)))
        if len(trials) % 50 == 0:
            print("MONTE CARLO", len(trials), flush=True)
    mc = dict(
        probability=float(probability),
        eligible_symbol_days=int(eligible.sum()),
        trials=trials,
        tests={},
    )
    for k in ["cagr", "sharpe"]:
        values = np.array([t[k] for t in trials])
        q95 = float(np.percentile(values, 95))
        mc["tests"][k] = dict(
            percentile=float(100 * np.mean(values < base[k])),
            p=float((1 + np.sum(values >= base[k])) / 501),
            q95=q95,
            significant=bool(base[k] > q95),
            quantiles=np.percentile(values, [0, 2.5, 50, 95, 97.5, 100]).tolist(),
        )
    mc["significant"] = all(
        t["significant"] and t["p"] < 0.05 for t in mc["tests"].values()
    )
    return mc, trials


def leave_one_out(
    prepped: dict, data: tuple, prior: dict, records: list, base: dict
) -> tuple:
    years = sorted({pd.Timestamp(t["exit_date"]).year for t in records})
    loo = []
    assert prior["champion"]["symbols"]["top5"] == ["ZEC", "ARB", "VET", "XLM", "WLD"]
    for symbol in prior["champion"]["symbols"]["top5"]:
        m = simulate_portfolio({s: df for s, df in prepped.items() if s != symbol})
        loo.append(dict(kind="symbol", excluded=symbol, **summary(m)))
    for year in years:
        # Engine reads SIGNAL at i-1; mask by execution year at i, not signal year.
        a = dict(data[2])
        a["SIGNAL"] = a["SIGNAL"].copy()
        for i in range(1, len(data[0])):
            if data[0][i].year == year:
                a["SIGNAL"][i - 1, :] = False
        r = simulate_portfolio({}, prepared=(data[0], data[1], a), return_trace=True)
        assert all(pd.Timestamp(e["date"]).year != year for e in r["allocations"])
        loo.append(dict(kind="year", excluded=year, **summary(r)))
    for row in loo:
        row["retained_cagr"] = row["cagr"] / base["cagr"]
        row["retained_sharpe"] = row["sharpe"] / base["sharpe"]
        row["pass"] = bool(
            row["retained_cagr"] >= 0.5 and row["retained_sharpe"] >= 0.5
        )
    return years, loo


def block_bootstrap(records: list, base: dict) -> dict:
    ordered = sorted(records, key=lambda t: (t["entry"], t["exit"], t["id"]))
    returns = np.array([t["return_pct"] / 100 for t in ordered])
    np.testing.assert_allclose(
        returns, [t["proceeds"] / t["cost"] - 1 for t in ordered], atol=1e-14
    )
    annualizer = np.sqrt(len(records) / base["years"])

    def trade_sharpe(x: np.ndarray) -> float:
        return float(x.mean() / x.std(ddof=1) * annualizer)

    rng = np.random.default_rng(710000)
    samples, starts_all = [], []
    for _ in range(1000):
        starts = rng.integers(
            0, len(records) - 20 + 1, size=int(np.ceil(len(records) / 20))
        )
        indices = (starts[:, None] + np.arange(20)).ravel()[: len(records)]
        starts_all.append(starts.tolist())
        samples.append(trade_sharpe(returns[indices]))
    ci = np.percentile(samples, [2.5, 97.5]).tolist()
    bootstrap = dict(
        block_size=20,
        seed=710000,
        iterations=1000,
        ordered_ids=[t["id"] for t in ordered],
        returns=returns.tolist(),
        annualizer=float(annualizer),
        original_trade_sharpe=trade_sharpe(returns),
        samples=samples,
        block_starts=starts_all,
        ci95=ci,
        significant=ci[0] > 0,
    )
    return bootstrap


def causal_checks(data: tuple, probability: float) -> None:
    dates = data[0]
    # Real prefix and future-price mutation checks using identical random stream.
    for end in [1200, 1900]:
        rd = random_data(data, 700000, probability)
        full = simulate_portfolio({}, prepared=rd, return_trace=True)
        short_data = (dates[:end], data[1], {k: v[:end] for k, v in data[2].items()})
        short_rd = random_data(short_data, 700000, probability)
        for k in ["SIGNAL", "VOL_RATIO"]:
            np.testing.assert_array_equal(rd[2][k][:end], short_rd[2][k])
        short = simulate_portfolio({}, prepared=short_rd, return_trace=True)
        assert full["trace"][: end - 1] == short["trace"][:-1]
        assert short["allocations"] == [
            e for e in full["allocations"] if e["date"] <= str(dates[end - 1])
        ]
        changed = {k: v.copy() for k, v in data[2].items()}
        for k in ["Open", "High", "Low", "Close"]:
            changed[k][end:] *= 10
        altered = simulate_portfolio(
            {},
            prepared=random_data((dates, data[1], changed), 700000, probability),
            return_trace=True,
        )
        assert altered["trace"][:end] == full["trace"][:end]


def run() -> None:
    prior = json.loads(CHAMPION_PATH.read_text())
    frames, manifest, _ = load_data()
    assert manifest == prior["manifest"] and len(frames) == 45
    prepped = volume_prep(frames)
    base, records, _, dates, curve = ledger_run(prepped, {})
    assert records == prior["champion"]["trades"] and len(records) == 468
    np.testing.assert_allclose(
        curve, [p["equity"] for p in prior["champion"]["daily_equity"]], atol=1e-10
    )
    for k in ["cagr", "mdd", "sharpe", "trades", "final"]:
        np.testing.assert_allclose(base[k], prior["champion"]["full"][k], atol=1e-10)
    data = prepare(prepped)
    eligible = np.isfinite(data[2]["Open"][:-1]) & np.isfinite(data[2]["Open"][1:])
    # Candidate frequency uses counts only, never control performance.
    probability = len(records) / eligible.sum()
    mc, trials = monte_carlo(data, probability, base)
    years, loo = leave_one_out(prepped, data, prior, records, base)
    bootstrap = block_bootstrap(records, base)
    causal_checks(data, probability)
    votes = [mc["significant"], all(r["pass"] for r in loo), bootstrap["significant"]]
    output = dict(
        manifest=manifest,
        baseline=summary(base),
        ledger_exact_match=True,
        monte_carlo=mc,
        leave_one_out=dict(years=years, rows=loo, significant=votes[1]),
        bootstrap=bootstrap,
        votes=votes,
        verdict=(
            "통계적 근거 있는 신호" if sum(votes) >= 2 else "유의미한 엣지 확인 못함"
        ),
        causal_checks=4,
    )
    assert all(
        np.isfinite([t[k] for k in ["cagr", "mdd", "sharpe", "final"]]).all()
        and 0 <= t["mdd"] <= 100
        for t in trials + loo
    )
    assert 0.75 * 468 <= np.mean([t["trades"] for t in trials]) <= 1.25 * 468
    PATH.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False, default=str)
    )
    print(
        "RESULT",
        output["verdict"],
        votes,
        mc["tests"],
        loo,
        bootstrap["ci95"],
        flush=True,
    )


if __name__ == "__main__":
    run()
