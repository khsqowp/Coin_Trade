"""Compact closed-candle data and measured virtual-account scoreboard."""

from datetime import datetime, timezone
from typing import Any
from config import Config
from ledger import Ledger
from indicators import summarize_candles
from http_client import BanError


def closed_candles(
    candles: list[list[Any]], now: float, interval: str
) -> list[list[Any]]:
    seconds = {"15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}[interval]
    return [
        c
        for c in candles
        if (float(c[6]) / 1000 if len(c) > 6 else float(c[0]) / 1000 + seconds) <= now
    ]


def compact(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 8)
    if isinstance(value, dict):
        return {k: compact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [compact(v) for v in value]
    return value


def build_bundle(
    exchange: Any, ledger: Ledger, config: Config, now: float
) -> dict[str, Any]:
    fetch_started = exchange.http.clock() if hasattr(exchange, "http") else now
    server = exchange.server_time() / 1000
    account = exchange.account()
    premium = {r["symbol"]: r for r in exchange.premium_index()}
    ledger.prices = {s: float(r["markPrice"]) for s, r in premium.items()}
    ledger.symbol_info = exchange.exchange_info()
    held = {p["symbol"] for p in ledger.positions}
    detailed = set(config.core_symbols) | held
    symbols = {}
    for symbol in dict.fromkeys(config.watchlist + sorted(held)):
        r = premium.get(symbol, {})
        candles = {}
        for interval in (
            ("15m", "1h", "4h", "1d") if symbol in detailed else ("1h", "4h")
        ):
            candles[interval] = summarize_candles(
                closed_candles(exchange.klines(symbol, interval, 250), now, interval)
            )
        entry: dict[str, Any] = {
            "mark_price": ledger.prices.get(symbol),
            "funding_rate": float(r.get("lastFundingRate", 0)),
            "candles": candles,
        }
        if symbol in detailed:
            try:
                entry["open_interest"] = exchange.open_interest(symbol)
            except BanError:
                raise
            except Exception:
                entry["open_interest"] = None
        symbols[symbol] = entry
    equity = ledger.equity()
    positions = []
    for p in ledger.positions:
        mark = ledger.prices.get(p["symbol"], p["entry"])
        positions.append(
            {
                **p,
                "unrealized_pnl": (mark - p["entry"])
                * p["qty"]
                * (1 if p["side"] == "long" else -1),
                "distance_to_stop_pct": (
                    abs(mark - p["stop"]) / mark * 100 if p.get("stop") else None
                ),
            }
        )
    c = ledger.current
    decisions = [
        r
        for r in ledger.store.records("decisions.jsonl")
        if r.get("generation") == c["generation"]
    ][-config.decisions_history_n :]
    fills = [
        r
        for r in ledger.store.records("fills.jsonl")
        if r.get("generation") == c["generation"]
    ]
    for d in decisions:
        d["fills"] = [
            f
            for f in fills
            if d.get("decision_id") is not None
            and d["decision_id"] in (f.get("decision_id"), f.get("entry_decision_id"))
        ]
    curve = [
        r["equity"]
        for r in ledger.store.records("equity.jsonl")
        if r.get("generation") == c["generation"]
    ]
    peak = max([config.start_equity, equity] + curve)
    mark_times = [float(r["time"]) / 1000 for r in premium.values() if r.get("time")]
    fetched = min([fetch_started] + mark_times)
    return compact(
        {
            "timestamp": datetime.fromtimestamp(now, timezone.utc).isoformat(),
            "fetched_at": fetched,
            "server_time_skew": server - now,
            "generation": c["generation"],
            "account": {
                "virtual_equity": equity,
                "raw_testnet_equity_info": account["equity"],
            },
            "positions": positions,
            "foreign_symbols": c.get("foreign_symbols", []),
            "symbols": symbols,
            "notes": ledger.store.notes(c["generation"]),
            "recent_decisions": decisions,
            "week_to_date_pnl": equity - c["week_start_equity"],
            "weekly_target": config.weekly_target,
            "hours_left_in_week": max(0, (c["week_start"] + 604800 - now) / 3600),
            "day_pnl": equity - c["day_start_equity"],
            "drawdown_pct": (peak - equity) / peak * 100 if peak > 0 else 0,
            "sit_out_until": c.get("sit_out_until"),
            "risk_limits": {
                k: getattr(config, k)
                for k in (
                    "max_leverage",
                    "max_positions",
                    "max_risk_per_trade_pct",
                    "max_gross_exposure_x",
                    "daily_loss_limit_pct",
                    "stale_data_seconds",
                )
            },
        }
    )
