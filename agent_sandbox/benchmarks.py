"""Offline baselines with chronological data and deterministic random seeds."""

from typing import Any
import random
import statistics
from config import Config
from indicators import atr
from risk import RiskEngine


def btc_buy_hold(candles: list[list[Any]], t0: float, t1: float) -> float | None:
    rows = sorted(
        [c for c in candles if t0 <= float(c[0]) / 1000 < t1], key=lambda c: c[0]
    )
    if not rows or float(rows[0][1]) <= 0:
        return None
    return (float(rows[-1][4]) / float(rows[0][1]) - 1) * 100


def _percentile(values: list[float], p: float) -> float:
    index = (len(values) - 1) * p
    lo = int(index)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (index - lo)


def random_trader(
    candles_by_symbol: dict[str, list[list[Any]]],
    t0: float,
    t1: float,
    config: Config,
    seed: int = 0,
    runs: int | None = None,
) -> dict[str, Any]:
    count = config.random_benchmark_runs if runs is None else runs
    if count <= 0:
        raise ValueError("runs must be positive")
    data = {
        s: sorted(rows, key=lambda c: c[0])
        for s, rows in candles_by_symbol.items()
        if s in config.watchlist
    }
    by_hour: dict[float, dict[str, list[Any]]] = {}
    for symbol, rows in data.items():
        for c in rows:
            ts = float(c[0]) / 1000
            if t0 <= ts < t1 and ts + 3600 <= t1:
                by_hour.setdefault(ts, {})[symbol] = c
    if not by_hour:
        return {
            "mean": None,
            "median": None,
            "p10": None,
            "p90": None,
            "share_ge_target": None,
            "runs": 0,
            "unit": "USDT PnL",
            "reason": "No complete hourly candles",
        }
    outcomes = []
    for run in range(count):
        rng = random.Random(seed + run)
        cash = config.start_equity
        positions: dict[str, dict[str, Any]] = {}
        prices: dict[str, float] = {}
        day_start = cash
        day = None
        sit_out = False
        engine = RiskEngine(config)
        for ts, bars in sorted(by_hour.items()):
            utc_day = int(ts // 86400)
            prices.update({s: float(c[1]) for s, c in bars.items()})

            def equity() -> float:
                return cash + sum(
                    (prices[p["symbol"]] - p["entry"])
                    * p["qty"]
                    * (1 if p["side"] == "long" else -1)
                    for p in positions.values()
                )

            def close(symbol: str, price: float) -> None:
                nonlocal cash
                p = positions.pop(symbol)
                cash += (price - p["entry"]) * p["qty"] * (
                    1 if p["side"] == "long" else -1
                ) - p["qty"] * price * config.taker_fee_rate

            if day != utc_day:
                day, day_start, sit_out = utc_day, equity(), False
            for s, p in list(positions.items()):
                if s not in bars:
                    continue
                c = bars[s]
                high, low = float(c[2]), float(c[3])
                stop_hit = (
                    low <= p["stop"] if p["side"] == "long" else high >= p["stop"]
                )
                tp_hit = high >= p["tp"] if p["side"] == "long" else low <= p["tp"]
                if stop_hit or tp_hit:
                    close(s, p["stop"] if stop_hit else p["tp"])
            prices.update({s: float(c[4]) for s, c in bars.items()})
            if engine.daily_loss_breached(equity(), day_start):
                for s in list(positions):
                    close(s, prices[s])
                sit_out = True
            free = sorted(s for s in bars if s not in positions)
            if (
                not sit_out
                and free
                and len(positions) < config.max_positions
                and rng.random() < 0.1
            ):
                symbol = rng.choice(free)
                history = [c for c in data[symbol] if float(c[0]) / 1000 <= ts]
                av = atr(history)
                if av is None or av <= 0:
                    continue
                side = rng.choice(["long", "short"])
                price = prices[symbol]
                sign = 1 if side == "long" else -1
                a = {
                    "type": "open",
                    "symbol": symbol,
                    "side": side,
                    "size_pct_equity": 10,
                    "leverage": 3,
                    "stop_loss": price - sign * 2 * av,
                    "take_profit": price + sign * 3 * av,
                    "rationale": "Random baseline",
                }
                ctx = {
                    "equity": equity(),
                    "positions": list(positions.values()),
                    "prices": prices,
                    "allowed_symbols": config.watchlist,
                    "symbol_info": {},
                    "data_age_seconds": 0,
                    "sit_out_until": None,
                }
                if engine.evaluate([a], ctx)[0][1]:
                    notional = equity() * 0.1 * 3
                    qty = notional / price
                    cash -= notional * config.taker_fee_rate
                    positions[symbol] = {
                        "symbol": symbol,
                        "side": side,
                        "qty": qty,
                        "entry": price,
                        "stop": a["stop_loss"],
                        "tp": a["take_profit"],
                        "notional": notional,
                    }
        for s in list(positions):
            close(s, prices[s])
        outcomes.append(cash - config.start_equity)
    ordered = sorted(outcomes)
    return {
        "mean": statistics.mean(outcomes),
        "median": statistics.median(outcomes),
        "p10": _percentile(ordered, 0.1),
        "p90": _percentile(ordered, 0.9),
        "share_ge_target": sum(v >= config.weekly_target for v in outcomes) / count,
        "runs": count,
        "unit": "USDT PnL",
        "samples": outcomes,
    }
