"""One serialized tick. Defaults to paper fills, never to real orders."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import argparse
import json
import os
import time
from config import Config, load_config
from safety import (
    TESTNET_HOST,
    SafetyError,
    assert_testnet_url,
    load_testnet_keys,
    load_env_file,
    redact,
)
from http_client import ThrottledHttp, Signer, BanError
from exchange import TestnetExchange
from state import StateStore
from ledger import Ledger
from generation import initialize, ensure_week_closed, enforce_daily
from bundle import build_bundle, closed_candles
from agent import run_agent, render_prompt
from schema import extract_json, validate_decision
from risk import RiskEngine
from executor import (
    execute,
    recover_pending_orders,
    recover_openings,
    cleanup_closed_positions,
    resolve_flat_openings,
)


class FixtureExchange:
    """Explicit offline adapter. It never creates an HTTP client."""

    def __init__(self, data: dict[str, Any], now: float):
        self.data, self.now = data, now

    def server_time(self) -> int:
        return int(self.data.get("server_time", self.now * 1000))

    def account(self) -> dict[str, Any]:
        return self.data.get("account", {"equity": 1000, "positions": []})

    def premium_index(self) -> list[dict[str, Any]]:
        return self.data["premium_index"]

    def exchange_info(self) -> dict[str, Any]:
        return self.data["symbol_info"]

    def klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 250,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> list[list[Any]]:
        rows = self.data.get("candles", {}).get(symbol, {}).get(interval, [])
        rows = [
            c
            for c in rows
            if (start_time is None or c[0] >= start_time)
            and (end_time is None or c[0] <= end_time)
        ]
        return rows[-limit:]

    def open_interest(self, symbol: str) -> float:
        return float(self.data.get("open_interest", {}).get(symbol, 0))

    def position_mode(self) -> bool:
        if self.data.get("dualSidePosition", False):
            raise SafetyError("Hedge mode is refused")
        return False


def parser(weekly: bool = False) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Paper-money futures testnet harness")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", dest="dry_run", action="store_true", default=True)
    mode.add_argument("--testnet-orders", dest="dry_run", action="store_false")
    p.add_argument("--config")
    p.add_argument("--env-file")
    p.add_argument("--now", help="Timezone-aware ISO timestamp")
    p.add_argument("--offline-fixture")
    if not weekly:
        p.add_argument("--fake-llm")
    return p


def parse_now(value: str | None) -> float:
    if value is None:
        return time.time()
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise SafetyError("--now must include a timezone")
    return dt.timestamp()


def project_file(path: str) -> Path:
    p = Path(path).resolve()
    if not p.is_relative_to(Path(__file__).resolve().parent):
        raise SafetyError("Input files must be inside the project directory")
    return p


def setup(args: argparse.Namespace, cfg: Config, now: float) -> Any:
    assert_testnet_url(f"https://{TESTNET_HOST}")
    if args.offline_fixture:
        if not args.dry_run:
            raise SafetyError("Offline fixtures require dry-run")
        return FixtureExchange(
            json.loads(project_file(args.offline_fixture).read_text()), now
        )
    if args.env_file:
        load_env_file(project_file(args.env_file), os.environ)
    key, secret = load_testnet_keys()
    return TestnetExchange(ThrottledHttp(cfg, Signer(key, secret)), args.dry_run)


def prepare_ledger(
    store: StateStore, cfg: Config, exchange: Any, now: float, dry_run: bool
) -> Ledger:
    ledger = Ledger(store, cfg)
    ledger.now = now
    ledger.prices = {
        r["symbol"]: float(r["markPrice"]) for r in exchange.premium_index()
    }
    ledger.symbol_info = exchange.exchange_info()
    if dry_run:
        candles = {}
        last = ledger.current.get("last_tick", ledger.current["start_ts"])
        for p in list(ledger.positions):
            rows = []
            cursor = int(last * 1000)
            while cursor < int(now * 1000):
                page = exchange.klines(
                    p["symbol"], "15m", 1500, cursor, int(now * 1000) - 1
                )
                if not page:
                    break
                rows.extend(page)
                next_cursor = int(page[-1][0]) + 900000
                if next_cursor <= cursor:
                    break
                cursor = next_cursor
                if len(page) < 1500:
                    break
            candles[p["symbol"]] = rows
        ledger.simulate_triggers(candles, now)
    else:
        recover_pending_orders(exchange, ledger)
        symbols = list(set(cfg.watchlist) | {p["symbol"] for p in ledger.positions})
        ledger.sync_fills(exchange, symbols, now)
        cleanup_closed_positions(exchange, ledger)
        resolve_flat_openings(exchange, ledger)
        ledger.reconcile(exchange.position_risk())
        recover_openings(exchange, ledger)
    return ledger


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        cfg = load_config(project_file(args.config) if args.config else None)
        now = parse_now(args.now)
        store = StateStore(cfg.state_dir)
        with store.lock():
            initialize(store, cfg, now, args.dry_run)
            exchange = setup(args, cfg, now)
            if hasattr(exchange, "http"):
                exchange.http.check_ban()
            exchange.position_mode()
            initialize(store, cfg, now)
            ledger = prepare_ledger(store, cfg, exchange, now, args.dry_run)
            # Record current valuation before closing weeks; only <= boundary samples are used.
            store.append(
                "equity.jsonl",
                {
                    "generation": ledger.current["generation"],
                    "ts": now,
                    "equity": ledger.equity(),
                    "stage": "before",
                },
            )
            ensure_week_closed(store, exchange, cfg, now, args.dry_run)
            ledger = prepare_ledger(store, cfg, exchange, now, args.dry_run)
            skip = enforce_daily(ledger, exchange, cfg, now, args.dry_run)
            bundle = build_bundle(exchange, ledger, cfg, now)
            decision_id = f"{ledger.current['generation']}:{now}:{len(store.records('decisions.jsonl'))}"
            errors: list[str] = []
            decision: dict[str, Any] = {
                "actions": [],
                "notes": store.notes(ledger.current["generation"]),
            }
            raw = ""
            if not skip:
                if args.fake_llm:
                    raw = project_file(args.fake_llm).read_text()
                else:
                    # Credential text is removed even if accidentally supplied through notes.
                    secrets = [
                        os.environ.get(n, "")
                        for n in (
                            "BINANCE_FUTURE_TESTNET_API_KEY",
                            "BINANCE_FUTURE_TESTNET_SECRET_KEY",
                        )
                    ]
                    result = run_agent(redact(render_prompt(bundle, cfg), secrets), cfg)
                    raw = result.text if result.ok else ""
                    if not result.ok:
                        errors.append(result.error)
                secrets = [
                    os.environ.get(n, "")
                    for n in (
                        "BINANCE_FUTURE_TESTNET_API_KEY",
                        "BINANCE_FUTURE_TESTNET_SECRET_KEY",
                    )
                ]
                raw = redact(raw, secrets)
                ok, validation_errors, normalized = validate_decision(extract_json(raw))
                errors.extend(validation_errors)
                if ok:
                    decision = normalized
                    store.write_notes(ledger.current["generation"], decision["notes"])
            fetched = bundle["fetched_at"]
            current_clock = exchange.http.clock() if hasattr(exchange, "http") else now
            age = max(0, current_clock - fetched, abs(bundle["server_time_skew"]))
            ctx = {
                "equity": ledger.equity(),
                "positions": ledger.positions,
                "prices": ledger.prices,
                "allowed_symbols": [
                    s
                    for s in cfg.watchlist
                    if ledger.symbol_info.get(s, {}).get("status", "TRADING")
                    == "TRADING"
                ],
                "symbol_info": ledger.symbol_info,
                "data_age_seconds": age,
                "sit_out_until": ledger.current.get("sit_out_until"),
                "foreign_symbols": ledger.current.get("foreign_symbols", []),
            }
            reviewed = RiskEngine(cfg).evaluate(decision["actions"], ctx)
            accepted = []
            for action, ok, reason in reviewed:
                if ok:
                    accepted.append(dict(action, decision_id=decision_id))
                else:
                    store.append(
                        "rejections.jsonl",
                        {
                            "generation": ledger.current["generation"],
                            "ts": now,
                            "action": action,
                            "reason": reason,
                        },
                    )
            outcomes = execute(accepted, exchange, ledger, cfg, args.dry_run)
            store.append(
                "decisions.jsonl",
                {
                    "generation": ledger.current["generation"],
                    "ts": now,
                    "decision_id": decision_id,
                    "decision": decision,
                    "errors": errors,
                    "outcomes": outcomes,
                    "skipped": skip,
                },
            )
            for error in errors:
                store.append(
                    "rejections.jsonl",
                    {
                        "generation": ledger.current["generation"],
                        "ts": now,
                        "reason": error,
                    },
                )
            eq = ledger.equity()
            store.append(
                "ticks.jsonl",
                {
                    "generation": ledger.current["generation"],
                    "ts": now,
                    "virtual_equity": eq,
                    "mode": "dry-run" if args.dry_run else "testnet orders",
                },
            )
            store.append(
                "equity.jsonl",
                {
                    "generation": ledger.current["generation"],
                    "ts": now,
                    "equity": eq,
                    "stage": "after",
                },
            )
            ledger.current["last_tick"] = now
            ledger.current["paper_cumulative"] = eq - cfg.start_equity
            ledger.save()
            print(
                f"generation={ledger.current['generation']} mode={'dry-run' if args.dry_run else 'testnet-orders'} equity={eq:.4f} accepted={len(accepted)} rejected={len(reviewed)-len(accepted)} skipped={skip}"
            )
        return 0
    except SafetyError as exc:
        print(str(exc))
        return 2
    except BanError as exc:
        print(str(exc))
        return 3
    except (ValueError, OSError, RuntimeError, KeyError):
        print(
            "Tick failed; state retained. Check configuration, fixture, and owned orders."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
