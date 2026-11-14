"""Deterministic allocator: regime-agent weights -> target exposure per (strategy, symbol). NO LLM, no orders.

Rules (all deterministic):
  * Only strategies REGISTERED in the pool (ablation ok, lookahead ok) and not UNVERIFIABLE receive exposure; unverified ones
    (liq_cluster, kr_surge_chase) get 0 here and are listed under `forward_only` (paper observation).
  * family weight (from the Regime agent, renormalised over families that have eligible strategies is NOT done: weight of a
    family without eligible strategy stays in cash - conservative) is split equally among the family's eligible strategies.
  * exposure budget per symbol = risk_multiplier (<=1, agent can only reduce) x profile.max_position_pct (Risk Engine limit).
  * FINAL authority is the Risk Engine config: allocations are clamped to cfg.max_position_pct, non-whitelisted symbols dropped,
    and the clamp can never be raised by agent input. The agent cannot change cfg."""
from .risk import PROFILES, RiskConfig


def allocate(regime_out, registry, profile="crypto_fast", cfg=None, symbols=None):
    cfg = cfg or PROFILES[profile]
    rm = min(1.0, max(0.0, float(regime_out.get("risk_multiplier", 0.0))))
    weights = regime_out.get("strategy_weights", {})
    elig, fwd = {}, []
    for e in registry:
        if e.get("profile_group") not in (None, profile):
            continue
        if symbols and e["symbol"] not in symbols:
            continue
        if e.get("unverifiable"):
            fwd.append({"strategy": e["strategy"], "symbol": e["symbol"], "tf": e["tf"], "reason": "unverifiable"})
        elif e.get("registered"):
            elig.setdefault(e["family"], []).append(e)
    rows = []
    for fam, es in elig.items():
        fw = float(weights.get(fam, 0.0))
        for e in es:
            rows.append({"strategy": e["strategy"], "symbol": e["symbol"], "tf": e["tf"], "family": fam,
                         "weight": round(fw / len(es), 5)})
    budget = rm * cfg.max_position_pct
    by_sym = {}
    for r in rows:
        r["alloc_pct_equity_if_signal"] = round(r["weight"] * budget, 6)
        by_sym.setdefault(r["symbol"], []).append(r)
    final, notes = [], []
    for sym, rs in by_sym.items():
        if sym not in cfg.whitelist:
            notes.append("%s dropped: not in Risk Engine whitelist" % sym)
            continue
        total = sum(r["alloc_pct_equity_if_signal"] for r in rs)
        scale = 1.0 if total <= cfg.max_position_pct else cfg.max_position_pct / total    # Risk Engine cap has priority
        for r in rs:
            r["alloc_pct_equity_if_signal"] = round(r["alloc_pct_equity_if_signal"] * scale, 6)
            final.append(r)
    assert all(r["alloc_pct_equity_if_signal"] <= cfg.max_position_pct + 1e-12 for r in final)
    cash_w = round(1.0 - sum(weights.get(f, 0.0) for f in elig), 4)
    return {"profile": profile, "risk_multiplier": rm, "symbol_budget_pct": round(budget, 6),
            "risk_engine_max_position_pct": cfg.max_position_pct, "allocations": final, "forward_only": fwd,
            "unallocated_weight": cash_w, "notes": notes}
