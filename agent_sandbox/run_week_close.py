"""Close passed weeks and enrich their reports with offline-testable baselines."""

from pathlib import Path
from typing import Any
import shutil
from config import load_config
from state import StateStore
from generation import initialize, ensure_week_closed
from run_tick import parser, parse_now, project_file, setup, prepare_ledger
from safety import SafetyError
from http_client import BanError
from benchmarks import btc_buy_hold, random_trader
from report import write_week_report


def main(argv: list[str] | None = None) -> int:
    args = parser(weekly=True).parse_args(argv)
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
            store.append(
                "equity.jsonl",
                {
                    "generation": ledger.current["generation"],
                    "ts": now,
                    "equity": ledger.equity(),
                    "stage": "week_close",
                },
            )
            ensure_week_closed(store, exchange, cfg, now, args.dry_run)
            history = store.read("generations.json", [])
            count = 0
            for event in history:
                if event.get("benchmarks_complete"):
                    continue
                start, end = event["week_start"], event["boundary"]
                # Include ATR warm-up history; ten watchlist requests plus other metadata.
                candles = {
                    s: exchange.klines(
                        s,
                        "1h",
                        250,
                        int((start - 30 * 3600) * 1000),
                        int(end * 1000) - 1,
                    )
                    for s in cfg.watchlist
                }
                benchmark: dict[str, Any] = {
                    "BTC_buy_hold_pct": btc_buy_hold(
                        candles.get("BTCUSDT", []), start, end
                    ),
                    "random_trader": random_trader(candles, start, end, cfg, seed=0),
                }
                benchmark["random_trader"].pop("samples", None)
                report = write_week_report(store, cfg, event, benchmark)
                if not event["survived"]:
                    shutil.copyfile(
                        report,
                        store.dir
                        / "archive"
                        / f"gen_{event['generation']}"
                        / "final_report.md",
                    )
                event["benchmarks_complete"] = True
                event["benchmarks"] = benchmark
                store.write("generations.json", history)
                count += 1
            print(f"weekly evaluations={len(history)} reports enriched={count}")
        return 0
    except SafetyError as exc:
        print(str(exc))
        return 2
    except BanError as exc:
        print(str(exc))
        return 3
    except (ValueError, OSError, RuntimeError, KeyError):
        print("Week close failed; state retained for a later retry.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
