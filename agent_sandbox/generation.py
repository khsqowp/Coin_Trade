"""UTC weekly evaluations and daily loss shutdown, under the caller's lock."""

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
import shutil
from config import Config
from state import StateStore
from ledger import Ledger
from executor import flatten
from risk import RiskEngine
from safety import SafetyError

WEEK = 7 * 86400


def week_bounds(ts: float) -> tuple[float, float]:
    dt = datetime.fromtimestamp(ts, timezone.utc)
    monday = (dt - timedelta(days=dt.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return monday.timestamp(), monday.timestamp() + WEEK


def evaluate_week(week_pnl: float, target: float) -> bool:
    return week_pnl >= target


def _fresh(generation: int, now: float, config: Config) -> dict[str, Any]:
    start, _ = week_bounds(now)
    return {
        "generation": generation,
        "start_ts": now,
        "start_virtual_equity": config.start_equity,
        "week_start": start,
        "week_start_equity": config.start_equity,
        "day": datetime.fromtimestamp(now, timezone.utc).date().isoformat(),
        "day_start_equity": config.start_equity,
        "sit_out_until": None,
        "positions": [],
        "realized_pnl": 0.0,
        "fees": 0.0,
        "paper_cumulative": 0.0,
        "foreign_symbols": [],
        "seen_fills": [],
    }


def initialize(
    store: StateStore, config: Config, now: float, dry_run: bool | None = None
) -> None:
    if store.read("current.json") is None:
        store.write("current.json", _fresh(1, now, config))
        store.write("generations.json", [])
        store.write_notes(1, "")
    for name in ("ticks", "decisions", "orders", "fills", "equity", "rejections"):
        (store.dir / (name + ".jsonl")).touch(exist_ok=True)
    if not (store.dir / "generations.json").exists():
        store.write("generations.json", [])
    if dry_run is not None:
        current = store.read("current.json")
        mode = "dry-run" if dry_run else "testnet orders"
        previous = current.get("execution_mode")
        if previous is not None and previous != mode:
            raise SafetyError(
                "Execution mode cannot change in an existing state directory; use separate state directories"
            )
        if previous is None and current["positions"]:
            raise SafetyError(
                "Positions in state without a recorded mode require manual reconciliation"
            )
        current["execution_mode"] = mode
        store.write("current.json", current)


def equity_at(
    store: StateStore, generation: int, boundary: float, fallback: float
) -> tuple[float, float | None]:
    records = [
        r
        for r in store.records("equity.jsonl")
        if r.get("generation") == generation and r["ts"] <= boundary
    ]
    if not records:
        return fallback, None
    last = max(records, key=lambda r: r["ts"])
    return float(last["equity"]), float(last["ts"])


def ensure_week_closed(
    store: StateStore,
    exchange_or_none: Any,
    config: Config,
    now: float,
    dry_run: bool = True,
) -> list[dict[str, Any]]:
    initialize(store, config, now)
    events = []
    while True:
        current = store.read("current.json")
        boundary = current["week_start"] + WEEK
        if boundary > now:
            break
        gid = current["generation"]
        eq, observed = equity_at(store, gid, boundary, current["week_start_equity"])
        pnl = eq - current["week_start_equity"]
        survive = evaluate_week(pnl, config.weekly_target)
        event = {
            "generation": gid,
            "week_start": current["week_start"],
            "boundary": boundary,
            "week_pnl": pnl,
            "boundary_equity": eq,
            "equity_observed_at": observed,
            "partial_week": current["start_ts"] > current["week_start"],
            "survived": survive,
            "mode": "dry-run" if dry_run else "testnet orders",
        }
        ledger = Ledger(store, config)
        ledger.now = now
        if exchange_or_none is not None:
            ledger.prices = {
                v["symbol"]: float(v["markPrice"])
                for v in exchange_or_none.premium_index()
            }
            ledger.symbol_info = exchange_or_none.exchange_info()
            if not dry_run:
                ledger.sync_fills(
                    exchange_or_none, list({p["symbol"] for p in ledger.positions}), now
                )
                ledger.reconcile(exchange_or_none.position_risk())
        if not survive:
            if ledger.positions and not ledger.prices:
                if dry_run:
                    # Offline callers must supply marks for actual open positions.
                    raise RuntimeError("Retirement needs mark prices for flattening")
                raise RuntimeError("Retirement needs an exchange")
            flatten(exchange_or_none, ledger, config, dry_run, "Weekly retirement")
            archive = store.dir / "archive" / f"gen_{gid}"
            archive.mkdir(parents=True, exist_ok=True)
            archived = StateStore(archive)
            archived.write("current.json", ledger.current)
            for name in (
                "ticks",
                "decisions",
                "orders",
                "fills",
                "equity",
                "rejections",
            ):
                rows = [
                    r
                    for r in store.records(name + ".jsonl")
                    if r.get("generation") == gid
                ]
                # Rebuild atomically so an interrupted retirement is safely repeatable.
                target = archive / (name + ".jsonl")
                temp = target.with_suffix(".tmp")
                import json

                temp.write_text(
                    "".join(json.dumps(r, allow_nan=False) + "\n" for r in rows)
                )
                temp.replace(target)
            if not (archive / "notes.md").exists():
                (archive / "notes.md").write_text(store.notes(gid))
            event["flatten_equity"] = ledger.equity()
            new = _fresh(gid + 1, boundary, config)
            new["foreign_symbols"] = ledger.current.get("foreign_symbols", [])
            new["execution_mode"] = current.get("execution_mode")
        else:
            new = ledger.current
            new.update(week_start=boundary, week_start_equity=eq)
        history = store.read("generations.json", [])
        key = (gid, current["week_start"])
        history = [e for e in history if (e["generation"], e["week_start"]) != key] + [
            event
        ]
        store.write("generations.json", history)
        from report import write_week_report

        report = write_week_report(store, config, event)
        if not survive:
            shutil.copyfile(
                report, store.dir / "archive" / f"gen_{gid}" / "final_report.md"
            )
        if not survive:
            store.write_notes(gid, "")
            store.write_notes(gid + 1, "")
        store.write("current.json", new)
        events.append(event)
    return events


def enforce_daily(
    ledger: Ledger, exchange: Any, config: Config, now: float, dry_run: bool
) -> bool:
    dt = datetime.fromtimestamp(now, timezone.utc)
    day = dt.date().isoformat()
    eq = ledger.equity()
    c = ledger.current
    if c.get("day") != day:
        c.update(day=day, day_start_equity=eq, sit_out_until=None)
    if c.get("sit_out_until") and c["sit_out_until"] <= now:
        c["sit_out_until"] = None
    breached = RiskEngine(config).daily_loss_breached(eq, c["day_start_equity"])
    if breached:
        flatten(exchange, ledger, config, dry_run, "Daily loss limit")
        c["sit_out_until"] = (
            dt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() + 86400
        )
    ledger.save()
    return breached or bool(c.get("sit_out_until"))
