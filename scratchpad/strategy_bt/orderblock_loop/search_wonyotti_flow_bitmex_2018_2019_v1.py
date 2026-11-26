"""Exploratory, preregistered Wonyotti flow test on BitMEX XBTUSD bars."""
from __future__ import annotations

import csv
import fcntl
import hashlib
import io
import json
import math
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = Path("/Users/user/CODE/Coin_Trade")
EXPECTED_DATA = REPO / "trading_data"
PREREG = HERE / "PREREG_WONYOTTI_FLOW_BITMEX_2018_2019_V1.md"
LEDGER = HERE / "TRAIN_TRIALS.csv"
START = datetime(2018, 3, 5, tzinfo=timezone.utc)
TEST_START = datetime(2019, 1, 1, tzinfo=timezone.utc)
END = datetime(2019, 6, 5, tzinfo=timezone.utc)
WINDOWS = (1, 4, 8)
THRESHOLDS = (0.00, 0.10, 0.25)
FUNDING_HOURS = (4, 12, 20)
FEE_RATE = 0.0010
SLIPPAGE = 0.0002
POSITION_ALLOCATION = 0.10
LEDGER_FIELDS = (
    "trial_id", "round", "market_group", "utc_timestamp", "definition",
    "parameter_grid_hash", "code_sha256", "train_period", "metric", "rank", "notes",
)


def data_root() -> Path:
    value = os.environ.get("TRADING_DATA_DIR")
    if value != str(EXPECTED_DATA):
        raise RuntimeError("TRADING_DATA_DIR must equal the canonical Coin_Trade data path")
    root = Path(value).resolve()
    if root != EXPECTED_DATA.resolve() or not root.is_dir():
        raise RuntimeError("canonical Coin_Trade data directory is unavailable")
    return root


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_bars(root: Path) -> tuple[dict[datetime, dict[str, float]], list[Path], set[datetime]]:
    folder = root / "external/crypto/wonyotti_bitmex/market/1h"
    expected_starts = [START + timedelta(days=7 * i) for i in range(66)]
    paths = [folder / f"XBTUSD-{stamp:%Y-%m-%d}-1h.json" for stamp in expected_starts]
    if any(not path.is_file() for path in paths):
        missing = [path.name for path in paths if not path.is_file()]
        raise FileNotFoundError(f"preregistered BitMEX weekly bars missing: {missing[:3]}")
    bars: dict[datetime, dict[str, float]] = {}
    invalid_hours: set[datetime] = set()
    for expected_start, path in zip(expected_starts, paths):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("timeframe") != "1h" or int(doc.get("openTimestamp", -1)) != int(expected_start.timestamp()):
            raise ValueError(f"bar file identity mismatch: {path.name}")
        arrays = {key: doc.get(key) for key in ("open", "high", "low", "close")}
        remaining_hours = int((END - expected_start).total_seconds() // 3600)
        expected_length = min(168, remaining_hours)
        if expected_length <= 0 or any(not isinstance(values, list) or len(values) != expected_length for values in arrays.values()):
            raise ValueError(f"weekly file length does not match preregistered coverage: {path.name}")
        for i in range(expected_length):
            stamp = expected_start + timedelta(hours=i)
            values = {key: float(arrays[key][i]) for key in arrays}
            if not all(math.isfinite(value) and value > 0 for value in values.values()):
                raise ValueError(f"non-finite or non-positive OHLC: {path.name} index={i}")
            if stamp in bars or stamp in invalid_hours:
                raise ValueError(f"duplicate market hour: {stamp.isoformat()}")
            if values["low"] > min(values["open"], values["close"]) or values["high"] < max(values["open"], values["close"]) or values["low"] > values["high"]:
                invalid_hours.add(stamp)
                continue
            bars[stamp] = values
    expected_count = int((END - START).total_seconds() // 3600)
    covered = set(bars) | invalid_hours
    if len(covered) != expected_count or any(START + timedelta(hours=i) not in covered for i in range(expected_count)):
        raise ValueError(f"market-hour continuity failure: valid={len(bars)}, invalid={len(invalid_hours)}, expected={expected_count}")
    return bars, paths, invalid_hours


def load_events(root: Path) -> tuple[dict[datetime, int], list[Path]]:
    folder = root / "external/crypto/wonyotti_bitmex/raw"
    paths = [
        folder / "aoa-execution-2018-03-01-2018-12-31.csv",
        folder / "aoa-execution-2019-01-01-2020-12-31.csv",
    ]
    flow: dict[datetime, int] = defaultdict(int)
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(f"preregistered execution file missing: {path.name}")
        with path.open(newline="", encoding="utf-8-sig") as stream:
            for row in csv.DictReader(stream):
                if row.get("exectype") != "Trade" or row.get("symbol") != "XBTUSD":
                    continue
                stamp = datetime.strptime(row["transacttime"], "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=timezone.utc)
                if START <= stamp < END:
                    side = 1 if row.get("side") == "Buy" else -1 if row.get("side") == "Sell" else 0
                    if side == 0:
                        raise ValueError("unexpected XBTUSD trade side")
                    flow[stamp.replace(minute=0, second=0, microsecond=0)] += side * int(float(row["lastqty"]))
    return dict(flow), paths


def signals_for_hour(flow: dict[datetime, int], signal_hour: datetime, window: int) -> tuple[int, int]:
    net = gross = 0
    for offset in range(window):
        qty = flow.get(signal_hour - timedelta(hours=offset), 0)
        net += qty
        gross += abs(qty)
    return net, gross


def funding_avoid(entry_hour: datetime) -> bool:
    return any(
        entry_hour.date() == (entry_hour.replace(hour=funding_hour) + timedelta(hours=delta)).date()
        and entry_hour.hour == (funding_hour + delta) % 24
        for funding_hour in FUNDING_HOURS
        for delta in (-1, 0, 1)
    )


def inverse_return(side: int, entry: float, exit_price: float, fee_rate: float, slippage: float) -> dict:
    adjusted_entry = entry * (1 + slippage if side > 0 else 1 - slippage)
    adjusted_exit = exit_price * (1 - slippage if side > 0 else 1 + slippage)
    gross = 1 - adjusted_entry / adjusted_exit if side > 0 else adjusted_entry / adjusted_exit - 1
    fees = fee_rate * (1 + adjusted_entry / adjusted_exit)
    net = gross - fees
    return {"gross_return": gross, "fee_return": fees, "net_return": net,
            "account_return": POSITION_ALLOCATION * max(net, -1.0),
            "direction_correct": (exit_price > entry if side > 0 else exit_price < entry)}


def build_trades(flow: dict[datetime, int], bars: dict, window: int, threshold: float,
                 start: datetime, end: datetime, fee_rate: float = FEE_RATE,
                 slippage: float = SLIPPAGE) -> tuple[list[dict], dict]:
    trades = []
    stats = {"eligible_signal_hours": 0, "no_flow": 0, "threshold_filtered": 0,
             "funding_window_skips": 0, "missing_entry_bars": 0,
             "invalid_price_window": 0}
    for signal_hour in sorted(bars):
        if not start <= signal_hour < end:
            continue
        stats["eligible_signal_hours"] += 1
        if any(signal_hour - timedelta(hours=offset) not in bars for offset in range(window)):
            stats["invalid_price_window"] += 1
            continue
        net, gross_flow = signals_for_hour(flow, signal_hour, window)
        if gross_flow == 0:
            stats["no_flow"] += 1
            continue
        imbalance = net / gross_flow
        if net == 0 or abs(imbalance) < threshold:
            stats["threshold_filtered"] += 1
            continue
        entry_hour = signal_hour + timedelta(hours=1)
        if funding_avoid(entry_hour):
            stats["funding_window_skips"] += 1
            continue
        market_bar = bars.get(entry_hour)
        if market_bar is None:
            stats["missing_entry_bars"] += 1
            continue
        side = 1 if net > 0 else -1
        pnl = inverse_return(side, market_bar["open"], market_bar["close"], fee_rate, slippage)
        trades.append({
            "signal_hour": signal_hour.isoformat(), "entry_hour": entry_hour.isoformat(),
            "side": side, "window_hours": window, "imbalance": imbalance,
            "signed_contracts": net, "gross_contracts": gross_flow,
            "entry": market_bar["open"], "exit": market_bar["close"], **pnl,
        })
    return trades, stats


def wilson(successes: int, total: int) -> tuple[float | None, float | None]:
    if total == 0:
        return None, None
    z = 1.959963984540054
    p = successes / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    radius = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return center - radius, center + radius


def metrics(trades: list[dict]) -> dict:
    n = len(trades)
    if not n:
        return {"n": 0, "direction_accuracy": None, "wilson95": [None, None],
                "net_ev_bp": None, "profit_factor": None, "equity_return_10pct_alloc_pct": None,
                "mdd_pct": None, "net_positive_rate": None}
    hits = sum(row["direction_correct"] for row in trades)
    wins = sum(max(row["net_return"], 0) for row in trades)
    losses = -sum(min(row["net_return"], 0) for row in trades)
    equity = peak = 1.0
    mdd = 0.0
    for row in trades:
        equity *= max(1e-12, 1 + row["account_return"])
        peak = max(peak, equity)
        mdd = max(mdd, (peak - equity) / peak)
    lo, hi = wilson(hits, n)
    return {"n": n, "direction_accuracy": hits / n, "wilson95": [lo, hi],
            "net_ev_bp": sum(row["net_return"] for row in trades) / n * 10000,
            "profit_factor": wins / losses if losses else None,
            "equity_return_10pct_alloc_pct": (equity - 1) * 100, "mdd_pct": mdd * 100,
            "net_positive_rate": sum(row["net_return"] > 0 for row in trades) / n}


def digest_inputs(paths: list[Path], root: Path) -> dict:
    return {str(path.relative_to(root)): sha256(path) for path in sorted(paths)}


def config_id(window: int, threshold: float) -> str:
    return f"WONYOTTI-FLOW-BITMEX-2018-2019-V1-W{window}-T{threshold:.2f}"


def prereg_hash() -> str:
    return sha256(PREREG)


def append_ledger(rows: list[dict], expected_before: int) -> int:
    csv.field_size_limit(20_000_000)
    with LEDGER.open("r+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        raw = stream.read()
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
        if tuple(reader.fieldnames or ()) != LEDGER_FIELDS:
            raise ValueError("TRAIN_TRIALS.csv schema mismatch")
        existing = list(reader)
        if len(existing) != expected_before:
            raise RuntimeError(f"ledger changed during run: before={expected_before}, now={len(existing)}; reconcile, do not retry")
        existing_ids = {row["trial_id"] for row in existing}
        if any(row["trial_id"] in existing_ids for row in rows):
            raise RuntimeError("trial ID already exists; reconcile before any append")
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=LEDGER_FIELDS, lineterminator="\n")
        writer.writerows(rows)
        payload = buffer.getvalue().encode("utf-8")
        stream.seek(0, os.SEEK_END)
        written = stream.write(payload)
        if written != len(payload):
            raise RuntimeError("short append; reconcile ledger; do not retry")
        stream.flush()
        os.fsync(stream.fileno())
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        return len(existing) + len(rows)


def trial_row(trial_id: str, definition: dict, metric: dict, rank: int,
              prereg_sha: str, code_sha: str, denominator: int, kind: str) -> dict:
    grid_sha = hashlib.sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest()
    return {
        "trial_id": trial_id, "round": "WONYOTTI-R2", "market_group": "crypto_single_asset_exploratory",
        "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "definition": json.dumps(definition, sort_keys=True, separators=(",", ":")),
        "parameter_grid_hash": grid_sha, "code_sha256": code_sha,
        "train_period": "2018-03-05/2019-01-01", "metric": json.dumps(metric, sort_keys=True, separators=(",", ":")),
        "rank": str(rank), "notes": f"{kind}; prereg_sha256={prereg_sha}; pre-run ledger rows={denominator}; exploratory only; not OB/G approval",
    }


def run() -> dict:
    root = data_root()
    prereg_sha = prereg_hash()
    before_bytes = LEDGER.stat().st_size
    csv.field_size_limit(20_000_000)
    with LEDGER.open(newline="", encoding="utf-8-sig") as stream:
        ledger_snapshot = list(csv.DictReader(stream))
    if len(ledger_snapshot) != 4204:
        raise RuntimeError(f"preregistered ledger baseline changed: expected 4204 rows, got {len(ledger_snapshot)}")
    if any(row.get("trial_id", "").startswith("WONYOTTI-FLOW-BITMEX-2018-2019-V1") for row in ledger_snapshot):
        raise RuntimeError("this experiment already has ledger rows; reconcile before running")
    bars, bar_paths, invalid_market_hours = load_bars(root)
    flow, event_paths = load_events(root)
    train_results = []
    train_trade_rows = {}
    train_stats = {}
    for window in WINDOWS:
        for threshold in THRESHOLDS:
            trades, stats = build_trades(flow, bars, window, threshold, START, TEST_START)
            train_results.append({"window": window, "threshold": threshold, "metrics": metrics(trades), "stats": stats})
            train_trade_rows[(window, threshold)] = trades
            train_stats[(window, threshold)] = stats
    winner = max(train_results, key=lambda row: (
        row["metrics"]["net_ev_bp"] if row["metrics"]["net_ev_bp"] is not None else -math.inf,
        row["metrics"]["n"], -row["window"], -row["threshold"],
    ))
    window, threshold = winner["window"], winner["threshold"]
    test, test_stats = build_trades(flow, bars, window, threshold, TEST_START, END)
    test_2x, _ = build_trades(flow, bars, window, threshold, TEST_START, END,
                              fee_rate=FEE_RATE * 2, slippage=SLIPPAGE * 2)
    input_hashes = digest_inputs(bar_paths + event_paths, root)
    data_fingerprint = hashlib.sha256(json.dumps(input_hashes, sort_keys=True).encode()).hexdigest()
    code_paths = [Path(__file__), Path(__file__).with_name("test_search_wonyotti_flow_bitmex_2018_2019_v1.py"), PREREG]
    code_sha = hashlib.sha256("".join(sha256(path) for path in code_paths).encode()).hexdigest()
    trial_rows = []
    for rank, result in enumerate(sorted(train_results, key=lambda row: (
            row["metrics"]["net_ev_bp"] if row["metrics"]["net_ev_bp"] is not None else -math.inf,
            row["metrics"]["n"], -row["window"], -row["threshold"]), reverse=True), start=1):
        config = {"window_hours": result["window"], "min_abs_imbalance": result["threshold"],
                  "side": "signed_net_contracts", "execution": "next_hour_open_to_close",
                  "instrument": "BitMEX_XBTUSD_inverse", "position_allocation": POSITION_ALLOCATION,
                  "costs": {"fee_per_side": FEE_RATE, "slippage_per_side": SLIPPAGE}}
        trial_rows.append(trial_row(config_id(result["window"], result["threshold"]), config,
                                    result["metrics"], rank, prereg_sha, code_sha, len(ledger_snapshot), "TRAIN grid"))
    selected_config = {"window_hours": window, "min_abs_imbalance": threshold,
                       "side": "signed_net_contracts", "execution": "next_hour_open_to_close",
                       "instrument": "BitMEX_XBTUSD_inverse", "position_allocation": POSITION_ALLOCATION,
                       "costs": {"fee_per_side": FEE_RATE, "slippage_per_side": SLIPPAGE}}
    trial_rows.append(trial_row(config_id(window, threshold) + "-OOS", selected_config,
                                {"test": metrics(test), "test_2x_cost": metrics(test_2x), "stats": test_stats},
                                1, prereg_sha, code_sha, len(ledger_snapshot), "single selected OOS"))
    if LEDGER.stat().st_size != before_bytes:
        raise RuntimeError("ledger metadata changed during run; preserve process state and reconcile before append")
    summary = {
        "experiment": "WONYOTTI-FLOW-BITMEX-2018-2019-V1", "classification": "exploratory_single_asset_not_G_candidate",
        "prereg_sha256": prereg_sha, "code_sha256": code_sha, "data_fingerprint_sha256": data_fingerprint,
        "ledger_rows_before": len(ledger_snapshot), "trials_to_append": len(trial_rows),
        "ledger_rows_expected_after": len(ledger_snapshot) + len(trial_rows),
        "market_bar_count": len(bars), "invalid_ohlc_bar_count": len(invalid_market_hours),
        "invalid_ohlc_hours_utc": sorted(stamp.isoformat() for stamp in invalid_market_hours),
        "market_first_utc": min(bars).isoformat(), "market_last_utc": max(bars).isoformat(),
        "flow_hours": len(flow), "input_sha256": input_hashes, "train_grid": train_results,
        "selected": {"window_hours": window, "min_abs_imbalance": threshold},
        "oos_test": metrics(test), "oos_test_2x_cost": metrics(test_2x), "oos_stats": test_stats,
        "candidate_filter": {"min_test_trades": 200, "wilson_lower_gt": 0.50,
                              "net_ev_bp_gt": 0, "profit_factor_gt": 1,
                              "two_x_cost_ev_bp_gt": 0},
        "not_g_approved": True,
    }
    out = root / "cache/wonyotti_bitmex_2018_2019_v1"
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    with (out / "selected_oos_trades.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(test[0]) if test else ["no_trades"])
        writer.writeheader()
        writer.writerows(test)
    if LEDGER.stat().st_size != before_bytes:
        raise RuntimeError("ledger changed before append; preserve outputs and reconcile; do not retry")
    final_rows = append_ledger(trial_rows, len(ledger_snapshot))
    summary["ledger_rows_after"] = final_rows
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True, allow_nan=False))
