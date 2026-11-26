"""Pre-registered test of hourly Wonyotti XBTUSD signed fills."""

from __future__ import annotations

import csv
import hashlib
import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq


REPO = Path("/Users/user/CODE/Coin_Trade")
EXPECTED_DATA = REPO / "trading_data"
START = pd.Timestamp("2020-01-01T00:00:00Z")
END = pd.Timestamp("2022-01-01T00:00:00Z")
TEST_START = pd.Timestamp("2021-03-14T14:24:00Z")
ROUND_TRIP_COST = 0.0012


def data_root() -> Path:
    value = os.environ.get("TRADING_DATA_DIR")
    if value != str(EXPECTED_DATA):
        raise RuntimeError("TRADING_DATA_DIR must equal the canonical Coin_Trade data path")
    return EXPECTED_DATA


def signed_hour_flow(events: list[tuple[pd.Timestamp, int]]) -> dict[pd.Timestamp, int]:
    flow: dict[pd.Timestamp, int] = defaultdict(int)
    for timestamp, signed_contracts in events:
        hour = timestamp.floor("h")
        if START <= hour < END:
            flow[hour] += signed_contracts
    return dict(flow)


def aggregate_hourly_bars(minutes: pd.DataFrame) -> dict[pd.Timestamp, dict[str, float]]:
    df = minutes.copy()
    df["time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df = df[(df["time"] >= START) & (df["time"] < END)].sort_values("time")
    if df["time"].duplicated().any():
        raise ValueError("duplicate one-minute open timestamps")
    df["hour"] = df["time"].dt.floor("h")
    result = {}
    for hour, group in df.groupby("hour", sort=True):
        expected = pd.date_range(hour, periods=60, freq="min")
        if len(group) != 60 or not group["time"].reset_index(drop=True).equals(
            pd.Series(expected, name="time")
        ):
            continue
        result[hour] = {
            "open": float(group.iloc[0]["open"]),
            "high": float(group["high"].max()),
            "low": float(group["low"].min()),
            "close": float(group.iloc[-1]["close"]),
        }
    return result


def wilson(successes: int, total: int) -> tuple[float, float]:
    if total == 0:
        return float("nan"), float("nan")
    z = 1.959963984540054
    p = successes / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    radius = z * ((p * (1 - p) / total + z * z / (4 * total * total)) ** 0.5) / denom
    return center - radius, center + radius


def metrics(trades: list[dict]) -> dict:
    if not trades:
        return {"n": 0}
    returns = [row["net_return"] for row in trades]
    direction_hits = sum(row["direction_correct"] for row in trades)
    profit_wins = sum(value > 0 for value in returns)
    positive = sum(value for value in returns if value > 0)
    negative = -sum(value for value in returns if value < 0)
    lo, hi = wilson(direction_hits, len(returns))
    equity = peak = 1.0
    mdd = 0.0
    for value in returns:
        equity *= 1 + value
        peak = max(peak, equity)
        mdd = max(mdd, (peak - equity) / peak)
    return {
        "n": len(returns),
        "direction_accuracy": direction_hits / len(returns),
        "wilson95": [lo, hi],
        "net_win_rate": profit_wins / len(returns),
        "net_ev_bp": sum(returns) / len(returns) * 10000,
        "profit_factor": positive / negative if negative else float("inf"),
        "cumulative_1x_pct": (equity - 1) * 100,
        "max_drawdown_pct": mdd * 100,
        "total_net_return_pct": (sum(returns)) * 100,
        "funding_events_charged": sum(row["funding_events"] for row in trades),
    }


def read_events(root: Path) -> list[tuple[pd.Timestamp, int]]:
    raw = root / "external/crypto/wonyotti_bitmex/raw"
    paths = [raw / "aoa-execution-2019-01-01-2020-12-31.csv", raw / "aoa-execution-2021-01-01-2021-06-30.csv", raw / "aoa-execution-2021-07-01-2021-12-31.csv"]
    events = []
    for path in paths:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                if row.get("exectype") != "Trade" or row.get("symbol") != "XBTUSD":
                    continue
                stamp = datetime.strptime(row["transacttime"], "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=timezone.utc)
                timestamp = pd.Timestamp(stamp)
                if START <= timestamp < END:
                    sign = 1 if row["side"] == "Buy" else -1
                    events.append((timestamp, sign * int(float(row["lastqty"]))))
    return events


def load_market_data(root: Path) -> tuple[pd.DataFrame, dict[pd.Timestamp, float], dict[str, str], dict[str, int]]:
    base = root / "external/crypto/binance"
    minute_frames = []
    funding: dict[pd.Timestamp, float] = {}
    hashes: dict[str, str] = {}
    counts: dict[str, int] = {}
    months = pd.period_range("2020-01", "2021-12", freq="M")
    for month in months:
        name = str(month)
        price_path = base / f"um_klines_1m/BTCUSDT/{name}.parquet"
        funding_path = base / f"um_fundingRate/BTCUSDT/{name}.parquet"
        if not price_path.is_file() or not funding_path.is_file():
            raise FileNotFoundError(f"missing pre-registered month {name}")
        frame = pd.read_parquet(price_path, columns=["open_time", "open", "high", "low", "close"])
        expected = int((month.end_time.normalize() - month.start_time.normalize()).days + 1) * 1440
        if len(frame) != expected or frame["open_time"].nunique() != expected:
            raise ValueError(f"incomplete or duplicated minute bars in {name}: {len(frame)}/{expected}")
        expected_first = int(month.start_time.timestamp() * 1000)
        expected_last = expected_first + (expected - 1) * 60_000
        if frame["open_time"].min() != expected_first or frame["open_time"].max() != expected_last:
            raise ValueError(f"wrong first minute timestamp in {name}")
        if frame["high"].lt(frame[["open", "close"]].max(axis=1)).any() or frame["low"].gt(frame[["open", "close"]].min(axis=1)).any():
            raise ValueError(f"invalid OHLC range in {name}")
        minute_frames.append(frame)
        fp = pq.ParquetFile(funding_path)
        rate_frame = pd.read_parquet(funding_path, columns=["calc_time", "last_funding_rate"])
        if len(rate_frame) != fp.metadata.num_rows:
            raise ValueError(f"funding row-count mismatch in {name}")
        funding_times = pd.to_datetime(rate_frame["calc_time"], unit="ms", utc=True)
        expected_funding = pd.date_range(month.start_time, month.end_time.normalize() + pd.Timedelta(hours=16), freq="8h")
        actual_schedule = funding_times.dt.floor("h").dt.strftime("%Y-%m-%dT%H").tolist()
        expected_schedule = expected_funding.strftime("%Y-%m-%dT%H").tolist()
        if actual_schedule != expected_schedule:
            raise ValueError(f"incomplete or unexpected funding schedule in {name}")
        for row in rate_frame.itertuples(index=False):
            funding[pd.to_datetime(row.calc_time, unit="ms", utc=True)] = float(row.last_funding_rate)
        for path in (price_path, funding_path):
            hashes[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
        counts[name] = len(frame)
    return pd.concat(minute_frames, ignore_index=True), funding, hashes, counts


def build_trades(flow: dict[pd.Timestamp, int], bars: dict, funding: dict, cost_multiplier: float = 1.0) -> list[dict]:
    trades = []
    for signal_hour, signed_qty in sorted(flow.items()):
        if signed_qty == 0:
            continue
        entry_hour = signal_hour + pd.Timedelta(hours=1)
        bar = bars.get(entry_hour)
        if bar is None or bar["open"] <= 0:
            continue
        side = 1 if signed_qty > 0 else -1
        gross = side * (bar["close"] / bar["open"] - 1)
        fee_and_slippage = ROUND_TRIP_COST * cost_multiplier
        start_ms = entry_hour.value // 1_000_000
        end_ms = (entry_hour + pd.Timedelta(minutes=59)).value // 1_000_000
        f_events = [rate for stamp, rate in funding.items() if start_ms < stamp.value // 1_000_000 <= end_ms]
        funding_return = sum(-side * rate for rate in f_events)
        net = gross - fee_and_slippage + funding_return
        trades.append({
            "signal_hour": signal_hour.isoformat(),
            "entry_hour": entry_hour.isoformat(),
            "side": side,
            "signed_contracts": signed_qty,
            "entry": bar["open"],
            "exit": bar["close"],
            "gross_return": gross,
            "net_return": net,
            "funding_return": funding_return,
            "direction_correct": gross > 0,
            "funding_events": len(f_events),
        })
    return trades


def run() -> dict:
    root = data_root()
    minute_frames, funding, input_hashes, month_counts = load_market_data(root)
    bars = aggregate_hourly_bars(minute_frames)
    flow = signed_hour_flow(read_events(root))
    trades = build_trades(flow, bars, funding)
    trades_2x = build_trades(flow, bars, funding, cost_multiplier=2.0)
    active_flow = {hour: qty for hour, qty in flow.items() if qty != 0}
    no_following_bar = sum(hour + pd.Timedelta(hours=1) not in bars for hour in active_flow)
    train = [row for row in trades if pd.Timestamp(row["signal_hour"]) < TEST_START]
    test = [row for row in trades if pd.Timestamp(row["signal_hour"]) >= TEST_START]
    reversed_test = [
        dict(
            row,
            net_return=-row["gross_return"] - ROUND_TRIP_COST - row["funding_return"],
            direction_correct=row["gross_return"] < 0,
        )
        for row in test
    ]
    event_root = root / "external/crypto/wonyotti_bitmex/raw"
    event_paths = [
        event_root / "aoa-execution-2019-01-01-2020-12-31.csv",
        event_root / "aoa-execution-2021-01-01-2021-06-30.csv",
        event_root / "aoa-execution-2021-07-01-2021-12-31.csv",
    ]
    input_hashes.update({str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in event_paths})
    input_hashes["external/crypto/wonyotti_bitmex/aoa_public_2021-12-31_with_letter.zip.part"] = hashlib.sha256(
        (root / "external/crypto/wonyotti_bitmex/aoa_public_2021-12-31_with_letter.zip.part").read_bytes()
    ).hexdigest()
    prereg = REPO / "scratchpad/strategy_bt/orderblock_loop/PREREG_WONYOTTI_FLOW_BINANCE_1H_V1.md"
    script = Path(__file__)
    result = {
        "experiment": "WONYOTTI-FLOW-BINANCE-1H-V1",
        "test_start_utc": TEST_START.isoformat(),
        "prereg_sha256": hashlib.sha256(prereg.read_bytes()).hexdigest(),
        "script_sha256": hashlib.sha256(script.read_bytes()).hexdigest(),
        "data_month_rows": month_counts,
        "minute_rows": int(len(minute_frames)),
        "complete_hour_bars": len(bars),
        "flow_hours": len(flow),
        "zero_net_flow_hours": len(flow) - len(active_flow),
        "nonzero_flow_hours": len(active_flow),
        "nonzero_flow_without_following_bar": no_following_bar,
        "trade_count": len(trades),
        "train": metrics(train),
        "test": metrics(test),
        "test_2x_cost": metrics([row for row in trades_2x if pd.Timestamp(row["signal_hour"]) >= TEST_START]),
        "test_sign_reversed": metrics(reversed_test),
        "test_by_year": {str(year): metrics([r for r in test if r["signal_hour"].startswith(str(year))]) for year in (2021,)},
        "input_sha256": input_hashes,
    }
    out = root / "cache/wonyotti_flow_v1/run_20261125_final"
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    with (out / "trades.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(trades[0]) if trades else [])
        if trades:
            writer.writeheader()
            writer.writerows(trades)
    return result


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
