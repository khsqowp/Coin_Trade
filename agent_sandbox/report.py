"""Measured weekly reports, including unavailable-data caveats."""

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
from config import Config
from state import StateStore


def max_drawdown(curve: list[float]) -> float:
    peak = 0.0
    worst = 0.0
    for value in curve:
        peak = max(peak, value)
        if peak > 0:
            worst = max(worst, (peak - value) / peak * 100)
    return worst


def closed_trades(fills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group partial fills into flat-to-flat symbol lifecycles, net of both fees."""
    active: dict[str, dict[str, Any]] = {}
    trades = []
    for fill in sorted(fills, key=lambda r: r["ts"]):
        symbol = fill["symbol"]
        signed_qty = fill["qty"] * (1 if fill["side"] == "BUY" else -1)
        trade = active.setdefault(
            symbol,
            {
                "symbol": symbol,
                "qty": 0.0,
                "net_pnl": 0.0,
                "entry_decision_id": fill.get("decision_id"),
            },
        )
        trade["qty"] += signed_qty
        trade["net_pnl"] += fill.get("realized_pnl", 0) - fill.get("fee", 0)
        if abs(trade["qty"]) < 1e-9:
            trade["closed_at"] = fill["ts"]
            trades.append(trade)
            del active[symbol]
    return trades


def write_week_report(
    store: StateStore,
    config: Config,
    event: dict[str, Any],
    benchmarks: dict[str, Any] | None = None,
) -> Path:
    gid, start, end = event["generation"], event["week_start"], event["boundary"]

    def rows(name: str) -> list[dict[str, Any]]:
        return [
            r
            for r in store.records(name + ".jsonl")
            if r.get("generation") == gid and start <= r.get("ts", 0) < end
        ]

    fills = rows("fills")
    all_fills = [
        f
        for f in store.records("fills.jsonl")
        if f.get("generation") == gid and f.get("ts", 0) < end
    ]
    trades = [t for t in closed_trades(all_fills) if start <= t["closed_at"] < end]
    wins = sum(t["net_pnl"] > 0 for t in trades)
    decisions = [
        r
        for r in store.records("decisions.jsonl")
        if r.get("generation") == gid and r.get("ts", 0) < end
    ]
    scored = []
    for d in decisions:
        related = [
            t
            for t in trades
            if t.get("entry_decision_id") == d.get("decision_id")
            and d.get("decision_id") is not None
        ]
        score = sum(t["net_pnl"] for t in related)
        if related:
            rationale = "; ".join(
                a.get("rationale", "") for a in d.get("decision", {}).get("actions", [])
            )
            scored.append(
                (score, str(d.get("decision_id")), rationale.replace("\n", " "))
            )
    scored.sort(reverse=True)
    curve = (
        [config.start_equity]
        + [r["equity"] for r in sorted(rows("equity"), key=lambda r: r["ts"])]
        + [event["boundary_equity"]]
    )
    rejected = Counter(r.get("reason", "Unknown") for r in rows("rejections"))
    iso = datetime.fromtimestamp(start, timezone.utc).strftime("%G-W%V")
    path = store.dir / "reports" / f"gen_{gid}_week_{iso}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Generation {gid}, {iso}",
        "",
        f"Mode: {event['mode']}",
        f"Net virtual PnL: {event['week_pnl']:.4f} USDT",
        f"Target: {config.weekly_target:.4f} USDT; difference: {event['week_pnl'] - config.weekly_target:.4f} USDT",
        f"Result: {'survived' if event['survived'] else 'retired'}; partial week: {event['partial_week']}",
        f"Maximum sampled drawdown: {max_drawdown(curve):.4f}%",
        f"Closed trades: {len(trades)}; win rate (net of both fees): {wins / len(trades) * 100 if trades else 0:.2f}%",
        f"Fees: {sum(f.get('fee', 0) for f in fills):.6f} USDT",
        "",
        "## Benchmarks",
        json.dumps(
            benchmarks
            or {
                "BTC_buy_hold_pct": None,
                "random_trader": None,
                "reason": "Not fetched yet",
            },
            indent=2,
        ),
        "",
        "## Best 3 decisions (attributed realized net PnL)",
    ]
    lines += [
        f"- {ident}: {score:.4f} USDT. {rationale}"
        for score, ident, rationale in scored[:3]
    ] or ["- No attributable fills."]
    lines += ["", "## Worst 3 decisions (attributed realized net PnL)"]
    lines += [
        f"- {ident}: {score:.4f} USDT. {rationale}"
        for score, ident, rationale in sorted(scored)[:3]
    ] or ["- No attributable fills."]
    lines += ["", "## Rejections"] + (
        [f"- {reason}: {count}" for reason, count in sorted(rejected.items())]
        or ["- None."]
    )
    lines += [
        "",
        "Caveats: paper capital; testnet liquidity differs; sampled equity may be stale at the boundary; "
        "intrabar stops assume stop-first ties; no slippage or liquidation simulation; "
        "unclosed trade outcomes remain unrealized; benchmark symbol filters unavailable offline; results are not evidence of profitability.",
        f"Boundary equity observation epoch: {event.get('equity_observed_at')}",
    ]
    temp = path.with_suffix(".tmp")
    temp.write_text("\n".join(lines) + "\n")
    temp.replace(path)
    return path
