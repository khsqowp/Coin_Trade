"""Five unchanged gates with one immutable definition Y calendar."""

import numpy as np
from app.round_period_standard import ALPHA_PERIODS, PERIOD_STANDARD, alpha_pass
from app.technical_portfolio_engine import prepare, simulate_portfolio
from app.crypto_round4_robustness import ledger_run, concentration
from app.crypto_round6_research import btc_period, symbols
from app.crypto_round7_research import summary, random_data, block_bootstrap
from app.crypto_round10_research import transition_stats


def robustness(p: dict, kw: dict, state: object, full: dict) -> dict:
    periods = [dict(start=a, end=b) for a, b in ALPHA_PERIODS]
    rows = {}
    for start, end in ALPHA_PERIODS:
        sub = {s: f.loc[start:end] for s, f in p.items() if len(f.loc[start:end])}
        m = simulate_portfolio(sub, **kw)
        b = btc_period(p["BTC"], start, end)["cagr"]
        rows[(start, end)] = dict(
            start=start, end=end, metrics=summary(m), btc_cagr=b, alpha=m["cagr"] - b
        )
    m, records, _, _, _ = ledger_run(p, kw)
    for k in summary(m):
        assert abs(m[k] - full[k]) < 1e-8
    conc, sy = concentration(records), symbols(records)
    data = prepare(p)
    eligible = np.isfinite(data[2]["Open"][:-1]) & np.isfinite(data[2]["Open"][1:])
    probability = len(records) / eligible.sum()
    trials = []
    for seed in range(1200000, 1200300):
        trials.append(
            dict(
                seed=seed,
                **summary(
                    simulate_portfolio(
                        p, prepared=random_data(data, seed, probability), **kw
                    )
                )
            )
        )
    tests = {
        k: dict(p=float((1 + sum(t[k] >= full[k] for t in trials)) / 301))
        for k in ["cagr", "sharpe"]
    }
    boot = block_bootstrap(records, full)
    current = [rows[(r["start"], r["end"])] for r in periods]
    if kw.get("dd_trigger"):
        # Identical Round4 breaker definition: resume-to-next-pause in 5 days.
        log = full["breaker_log"]
        resumes = [e for e in log if e["kind"] == "resume"]
        near = 0
        for e in resumes:
            nxt = next(
                (x for x in log if x["index"] > e["index"] and x["kind"] == "pause"),
                None,
            )
            near += bool(nxt and nxt["index"] - e["index"] <= 5)
        breaker_pct = 100 * near / len(resumes) if resumes else 0.0
    else:
        breaker_pct = None
    transitions = transition_stats(state, data[0]) if state is not None else None
    rates = ([breaker_pct] if breaker_pct is not None else []) + (
        [transitions["within"]["5"]["pct"]] if transitions else []
    )
    votes = [
        alpha_pass(current),
        conc["10"]["net_pct"] <= 103 and sy["net_pct"] <= 88,
        all(t["p"] < 0.05 for t in tests.values()),
        boot["ci95"][0] > 0,
        all(x <= 50 for x in rates),
    ]
    return dict(
        periods=current,
        period_criterion=PERIOD_STANDARD,
        concentration=conc,
        symbols=sy,
        monte_carlo=dict(probability=probability, trials=trials, tests=tests),
        bootstrap=boot,
        thrashing=transitions,
        breaker_5day_pct=breaker_pct,
        votes=[bool(x) for x in votes],
        verdict="통과" if all(votes) else "기각",
        records=records,
    )
