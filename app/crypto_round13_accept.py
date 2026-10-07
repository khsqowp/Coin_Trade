"""Resolve explicit Round4/6 boundary mismatch without changing thresholds."""

import json
import numpy as np
from app import crypto_round12_research as old
from app import crypto_round13_research as r13
from app.crypto_round13_extension import build, audit
from app.round13_costs import simulate_cost_portfolio
from app.technical_portfolio_engine import simulate_portfolio


def run():
    out = json.loads(r13.PATH.read_text())
    for row in out["experiments"]:
        if row["dominates"]:
            r13.required_gates(row["robustness"])
    winners = [
        r
        for r in out["experiments"]
        if r.get("robustness", {}).get("verdict") == "통과"
    ]
    assert len(winners) == 1
    winner = winners[0]
    frames, manifest, skipped = old.load_data()
    assert not skipped and manifest == out["manifest"]
    old.build = build
    p, kw, _ = build(frames, winner["config"])
    full = simulate_portfolio(p, return_trace=True, **kw)
    assert old.summary(full) == winner["metrics"]
    assert all(audit(frames, winner["config"], full).values())
    zero = simulate_cost_portfolio(p, return_trace=True, **kw)
    assert zero == full
    winner["cost_zero_full_trace_parity"] = True
    winner["costs"] = [
        dict(
            funding_annual=0.1095,
            slippage=slip,
            metrics=old.summary(
                simulate_cost_portfolio(p, funding_annual=0.1095, slippage=slip, **kw)
            ),
        )
        for slip in [0.0005, 0.001]
    ]
    # Independently replay precisely the requested calendar and both alpha sides.
    round4 = json.loads((r13.ROOT / "docs/round4-results-2026-10-07.json").read_text())[
        "periods"
    ]
    round6 = json.loads((r13.ROOT / "docs/round6-results-2026-10-07.json").read_text())[
        "periods"
    ]
    assert round4 == round6
    actual = []
    for start, end in round4:
        sub = {s: f.loc[start:end] for s, f in p.items() if len(f.loc[start:end])}
        m = old.summary(simulate_portfolio(sub, **kw))
        btc = frames["BTC"].loc[start:end]
        b = ((btc.Close.iloc[-1] / btc.Open.iloc[0]) * 0.9996**2) ** (
            365.25 / (btc.index[-1] - btc.index[0]).days
        ) * 100 - 100
        actual.append(
            dict(start=start, end=end, metrics=m, btc_cagr=b, alpha=m["cagr"] - b)
        )
    saved = winner["robustness"]["legacy_periods"]
    for a, b in zip(actual, saved):
        assert (a["start"], a["end"]) == (b["start"], b["end"])
        for k in ["btc_cagr", "alpha"]:
            np.testing.assert_allclose(a[k], b[k], rtol=0, atol=1e-10)
        for k in a["metrics"]:
            np.testing.assert_allclose(
                a["metrics"][k], b["metrics"][k], rtol=0, atol=1e-10
            )
    assert sum(x["alpha"] > 0 for x in actual) == 7
    out["status"] = "복귀조건 A 달성"
    out["winner_config"] = winner["config"]
    out["required_periods"] = round4
    out["gate_correction"] = (
        "Round12 함수의 요청외 Round9 추가필수조건을 참고검증으로 분리; Round4/6 사용자지정경계·모든수치임계값 유지"
    )
    out["stopped_final_batch"] = dict(
        completed=5,
        unrecorded_partial="obv_breakout online_sizing=payoff online_window=80; MC 중 사용자지정경계 승자확인으로 interrupt",
        reason="복귀조건 A 확인 후 추가탐색 중단",
    )
    r13.save(out)
    print(
        "PASS specified Round4/6 7/8 independently replayed, future audit and cost-zero full trace parity"
    )
    print(
        json.dumps(
            dict(
                config=winner["config"],
                metrics=winner["metrics"],
                votes=winner["robustness"]["votes"],
                costs=winner["costs"],
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    run()
