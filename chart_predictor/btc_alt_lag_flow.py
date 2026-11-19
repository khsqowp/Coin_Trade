"""Preregistered BTC impulse / altcoin lag signal research (no order interface)."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd


SYMBOLS = ("BTCUSDT", "ETHUSDT", "BNBUSDT", "DOGEUSDT", "SOLUSDT", "XRPUSDT")
ALT_SYMBOLS = SYMBOLS[1:]
MINUTE_MS = 60_000
FEE_PER_SIDE = 0.0005
BASE_SLIPPAGE_PER_SIDE = 0.0004
STRESS_SLIPPAGE_PER_SIDE = 0.0008
TARGET_PCT = 0.006
STOP_PCT = 0.003
MAX_HOLD_MINUTES = 15
ENTRY_DELAY_MINUTES = 1
BTC_IMPULSE_PCT = 0.003
BTC_IMBALANCE_MIN = 0.15
ALT_IMBALANCE_MIN = 0.10
LAG_MIN = 0.001


def build_symbol_features(minute: pd.DataFrame) -> pd.DataFrame:
    """Aggregate only complete UTC bars and compute causal 5m/30m/4h fields."""
    required = {"open_ms", "open", "high", "low", "close", "quote_volume", "taker_buy_quote"}
    missing = required - set(minute.columns)
    if missing:
        raise ValueError(f"missing candle columns: {sorted(missing)}")
    frame = minute.sort_values("open_ms").copy()
    if frame.open_ms.duplicated().any() or (frame.open_ms % MINUTE_MS != 0).any():
        raise ValueError("duplicate or off-grid 1m open timestamp")
    if frame[["open", "high", "low", "close", "quote_volume", "taker_buy_quote"]].isna().any().any():
        raise ValueError("null candle field")
    if ((frame.high < frame[["open", "low", "close"]].max(axis=1)) |
            (frame.low > frame[["open", "high", "close"]].min(axis=1)) |
            (frame.quote_volume < 0) | (frame.taker_buy_quote < 0) |
            (frame.taker_buy_quote > frame.quote_volume + 1e-8)).any():
        raise ValueError("invalid OHLC or taker volume")

    indexed = frame.set_index(pd.to_datetime(frame.open_ms, unit="ms", utc=True))
    five = indexed.resample("5min", origin="epoch", closed="left", label="right").agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"),
        close=("close", "last"), quote_volume=("quote_volume", "sum"),
        taker_buy_quote=("taker_buy_quote", "sum"), count=("open", "count"),
    )
    five["complete_5m"] = five["count"].eq(5)
    five["imbalance_5m"] = 2 * five.taker_buy_quote / five.quote_volume.replace(0, np.nan) - 1
    prev_complete = five.complete_5m.shift(1, fill_value=False)
    five["ret_5m"] = five.close.pct_change().where(five.complete_5m & prev_complete)
    seven_complete = five.complete_5m.astype(int).rolling(7, min_periods=7).sum().eq(7)
    five["ret_30m"] = (five.close / five.close.shift(6) - 1).where(seven_complete)

    four = indexed.resample("4h", origin="epoch", closed="left", label="right").agg(
        close=("close", "last"), count=("open", "count"),
    )
    four["complete_4h"] = four["count"].eq(240)
    valid_close = four.close.where(four.complete_4h)
    four["ema20_4h"] = valid_close.ewm(span=20, adjust=False, min_periods=20).mean()
    four["ema50_4h"] = valid_close.ewm(span=50, adjust=False, min_periods=50).mean()
    four["warm_4h"] = four.complete_4h.astype(int).rolling(50, min_periods=50).sum().eq(50)
    five = pd.merge_asof(
        five.sort_index().reset_index(names="close_time"),
        four[["close", "ema20_4h", "ema50_4h", "warm_4h"]].sort_index()
            .reset_index(names="macro_time"),
        left_on="close_time", right_on="macro_time", direction="backward",
    ).drop(columns=["macro_time"])
    five["close_ms"] = five.close_time.astype("int64") // 1_000_000
    return five.set_index("close_ms", drop=True).sort_index()


def rank_lagged_alts(direction: int, btc_ret_30m: float, alts: list[dict]) -> list[dict]:
    """Return flow-confirmed alts ranked by directional BTC-relative lag."""
    if direction not in (-1, 1):
        raise ValueError("direction must be -1 or +1")
    eligible = []
    for row in alts:
        ret = row.get("ret_30m")
        imbalance = row.get("imbalance_5m")
        if ret is None or imbalance is None or not math.isfinite(ret) or not math.isfinite(imbalance):
            continue
        score = direction * (btc_ret_30m - ret)
        if direction * imbalance >= ALT_IMBALANCE_MIN and score >= LAG_MIN:
            eligible.append({**row, "lag_score": score})
    return sorted(eligible, key=lambda row: (-row["lag_score"], row["symbol"]))


def resolve_bracket(direction: int, entry_price: float, bars: pd.DataFrame) -> dict:
    """Resolve TP/SL/time barrier from the entry-minute path, conservatively."""
    if direction not in (-1, 1) or not math.isfinite(entry_price) or entry_price <= 0:
        raise ValueError("invalid direction or entry price")
    if bars.empty:
        return {"label": "unscorable", "exit_price": None, "exit_ms": None}
    rows = bars.sort_values("open_ms").to_dict("records")
    if len(rows) > MAX_HOLD_MINUTES:
        rows = rows[:MAX_HOLD_MINUTES]
    stop = entry_price * (1 - direction * STOP_PCT)
    target = entry_price * (1 + direction * TARGET_PCT)
    first_ms = int(rows[0]["open_ms"])
    for i, bar in enumerate(rows):
        stamp = int(bar["open_ms"])
        if stamp != first_ms + i * MINUTE_MS:
            return {"label": "unscorable", "exit_price": None, "exit_ms": None}
        op, hi, lo, close = (float(bar[k]) for k in ("open", "high", "low", "close"))
        if not all(math.isfinite(x) and x > 0 for x in (op, hi, lo, close)) or hi < max(op, lo, close) or lo > min(op, hi, close):
            return {"label": "unscorable", "exit_price": None, "exit_ms": None}
        if direction == 1:
            if op <= stop:
                return {"label": "stop", "exit_price": op, "exit_ms": stamp + MINUTE_MS}
            if op >= target:
                return {"label": "target", "exit_price": target, "exit_ms": stamp + MINUTE_MS}
            hit_stop, hit_target = lo <= stop, hi >= target
        else:
            if op >= stop:
                return {"label": "stop", "exit_price": op, "exit_ms": stamp + MINUTE_MS}
            if op <= target:
                return {"label": "target", "exit_price": target, "exit_ms": stamp + MINUTE_MS}
            hit_stop, hit_target = hi >= stop, lo <= target
        if hit_stop:
            return {"label": "stop", "exit_price": stop, "exit_ms": stamp + MINUTE_MS}
        if hit_target:
            return {"label": "target", "exit_price": target, "exit_ms": stamp + MINUTE_MS}
    if len(rows) < MAX_HOLD_MINUTES:
        return {"label": "unscorable", "exit_price": None, "exit_ms": None}
    bar = rows[-1]
    return {"label": "timeout", "exit_price": float(bar["close"]), "exit_ms": int(bar["open_ms"]) + MINUTE_MS}


def build_events(features: dict[str, pd.DataFrame], start_ms: int, end_ms: int) -> tuple[list[dict], int]:
    """Build paired lagger/leader signals from completed BTC 5m bars."""
    btc = features["BTCUSDT"]
    events, eligible_anchors = [], 0
    for stamp, b in btc.iterrows():
        stamp = int(stamp)
        if stamp < start_ms or stamp >= end_ms:
            continue
        if not bool(b.complete_5m) or not bool(b.warm_4h):
            continue
        if not all(math.isfinite(float(b[name])) for name in
                   ("ret_5m", "imbalance_5m", "ret_30m", "close_y", "ema20_4h", "ema50_4h")):
            continue
        direction = 1 if float(b.ret_5m) >= BTC_IMPULSE_PCT else -1 if float(b.ret_5m) <= -BTC_IMPULSE_PCT else 0
        if not direction or direction * float(b.imbalance_5m) < BTC_IMBALANCE_MIN:
            continue
        trend_ok = (float(b.close_y) > float(b.ema20_4h) > float(b.ema50_4h)) if direction == 1 else (
            float(b.close_y) < float(b.ema20_4h) < float(b.ema50_4h))
        if not trend_ok or not math.isfinite(float(b.ret_30m)):
            continue
        eligible_anchors += 1
        alt_rows = []
        for symbol in ALT_SYMBOLS:
            frame = features[symbol]
            if stamp not in frame.index:
                continue
            a = frame.loc[stamp]
            alt_rows.append({"symbol": symbol, "ret_30m": float(a.ret_30m),
                             "imbalance_5m": float(a.imbalance_5m)})
        ranked = rank_lagged_alts(direction, float(b.ret_30m), alt_rows)
        if not ranked:
            continue
        candidate = ranked[0]
        leader = min(ranked, key=lambda row: (row["lag_score"], row["symbol"]))
        for kind, row in (("lag", candidate), ("leader", leader)):
            events.append({"kind": kind, "symbol": row["symbol"], "signal_ms": stamp,
                           "entry_ms": stamp + ENTRY_DELAY_MINUTES * MINUTE_MS,
                           "direction": direction, "lag_score": row["lag_score"],
                           "btc_ret_5m": float(b.ret_5m), "btc_ret_30m": float(b.ret_30m),
                           "btc_imbalance_5m": float(b.imbalance_5m),
                           "alt_imbalance_5m": row["imbalance_5m"]})
    return events, eligible_anchors


def _minute_rows(db: sqlite3.Connection, symbol: str, end_ms: int) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT open_ms,open,high,low,close,quote_volume,taker_buy_quote FROM candles "
        "WHERE symbol=? AND open_ms<? ORDER BY open_ms", db,
        params=(symbol, end_ms + MAX_HOLD_MINUTES * MINUTE_MS),
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def attach_outcomes(events: list[dict], minutes: dict[str, pd.DataFrame]) -> list[dict]:
    """Resolve every issued event on exact future 1m bars; never shift missing entries."""
    arrays = {s: (f.open_ms.to_numpy(dtype=np.int64), f) for s, f in minutes.items()}
    out = []
    for event in events:
        timestamps, frame = arrays[event["symbol"]]
        i = int(np.searchsorted(timestamps, event["entry_ms"], side="left"))
        if i >= len(timestamps) or int(timestamps[i]) != event["entry_ms"]:
            out.append({**event, "label": "unscorable", "entry_price": None,
                        "exit_price": None, "exit_ms": None, "gross_return": None})
            continue
        bars = frame.iloc[i:i + MAX_HOLD_MINUTES]
        entry_price = float(bars.iloc[0].open)
        if entry_price <= 0:
            result = {"label": "unscorable", "exit_price": None, "exit_ms": None}
        else:
            result = resolve_bracket(event["direction"], entry_price, bars)
        gross = (event["direction"] * (result["exit_price"] / entry_price - 1)
                 if result["exit_price"] is not None else None)
        expiry_close = float(bars.iloc[-1].close) if len(bars) == MAX_HOLD_MINUTES else None
        m1 = (event["direction"] * (expiry_close / entry_price - 1)
              if expiry_close is not None else None)
        used_count = (max(1, int((result["exit_ms"] - event["entry_ms"]) // MINUTE_MS))
                      if result["exit_ms"] is not None else 0)
        used = bars.iloc[:used_count]
        if used.empty or result["label"] == "unscorable":
            min_mark = None
        elif event["direction"] == 1:
            min_mark = float((used.low / entry_price - 1).min())
        else:
            min_mark = float((1 - used.high / entry_price).min())
        out.append({**event, "label": result["label"], "entry_price": entry_price,
                    "exit_price": result["exit_price"], "exit_ms": result["exit_ms"],
                    "gross_return": gross, "min_mark_return": min_mark,
                    "m1_direction_correct": bool(m1 is not None and m1 > 0) if m1 is not None else None})
    return out


def wilson(successes: int, total: int, z: float = 1.959963984540054) -> list[float] | None:
    if total <= 0:
        return None
    p = successes / total
    den = 1 + z * z / total
    center = (p + z * z / (2 * total)) / den
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / den
    return [center - half, center + half]


def summarize(trades: list[dict], slippage: float) -> dict:
    issued = [t for t in trades if t["label"] != "unscorable"]
    hits = sum(t["label"] == "target" for t in issued)
    cost_side = FEE_PER_SIDE + slippage
    returns = [t["gross_return"] - cost_side * (1 + t["exit_price"] / t["entry_price"]) for t in issued]
    m1 = [t["m1_direction_correct"] for t in issued if t["m1_direction_correct"] is not None]
    return {"issued": len(trades), "scorable": len(issued), "unscorable": len(trades) - len(issued),
            "m2_target_first": hits / len(issued) if issued else None,
            "m2_wilson_95": wilson(hits, len(issued)), "mean_net_return": float(np.mean(returns)) if returns else None,
            "positive_net_rate": sum(x > 0 for x in returns) / len(returns) if returns else None,
            "m1_expiry_direction_accuracy": float(np.mean(m1)) if m1 else None,
            "labels": {name: sum(t["label"] == name for t in trades) for name in ("target", "stop", "timeout", "unscorable")}}


def compounded_portfolio(trades: list[dict], slippage: float) -> dict:
    """Single-position, 1x, chronological compounding; rejected overlaps remain scored separately."""
    ordered = sorted((t for t in trades if t["label"] != "unscorable"), key=lambda t: (t["entry_ms"], t["symbol"]))
    nav, peak, max_closed_dd, max_intratrade_dd, last_exit = 1.0, 1.0, 0.0, 0.0, -1
    accepted = []
    side_cost = FEE_PER_SIDE + slippage
    for trade in ordered:
        if trade["entry_ms"] < last_exit:
            continue
        net = trade["gross_return"] - side_cost * (1 + trade["exit_price"] / trade["entry_price"])
        min_mark = trade.get("min_mark_return")
        if min_mark is not None:
            marked_nav = nav * max(0.0, 1 + min_mark - 2 * side_cost)
            max_intratrade_dd = max(max_intratrade_dd, 1 - marked_nav / peak)
        nav *= max(0.0, 1 + net)
        peak = max(peak, nav)
        max_closed_dd = max(max_closed_dd, 1 - nav / peak)
        accepted.append({**trade, "net_return": net, "nav_after": nav})
        last_exit = trade["exit_ms"]
    years = ((max((x["exit_ms"] for x in accepted), default=0) - min((x["entry_ms"] for x in accepted), default=0))
             / (365.2425 * 24 * 60 * MINUTE_MS))
    cagr = nav ** (1 / years) - 1 if years > 0 and nav > 0 else None
    return {"trades": len(accepted), "final_nav": nav, "total_return": nav - 1,
            "cagr": cagr, "closed_trade_mdd": max_closed_dd,
            "intratrade_marked_mdd": max_intratrade_dd, "accepted": accepted}


def load_and_run(db_path: str, start_ms: int, end_ms: int) -> dict:
    path = Path(db_path).resolve()
    source_sha256 = _sha256(path)
    print("source_sha256 computed; opening SQLite read-only", file=sys.stderr, flush=True)
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        check = db.execute("PRAGMA integrity_check").fetchone()[0]
        if check != "ok":
            raise ValueError(f"source integrity check failed: {check}")
        schema = {r[1] for r in db.execute("PRAGMA table_info(candles)")}
        expected = {"symbol", "open_ms", "open", "high", "low", "close", "quote_volume", "taker_buy_quote"}
        if not expected.issubset(schema):
            raise ValueError(f"source missing columns: {sorted(expected - schema)}")
        features, minutes = {}, {}
        for symbol in SYMBOLS:
            print(f"loading and building causal features: {symbol}", file=sys.stderr, flush=True)
            frame = _minute_rows(db, symbol, end_ms)
            if frame.empty:
                raise ValueError(f"no rows for {symbol}")
            minutes[symbol] = frame[["open_ms", "open", "high", "low", "close"]].copy()
            features[symbol] = build_symbol_features(frame)
        print("building fixed candidate and matched leader events", file=sys.stderr, flush=True)
        events, eligible_anchors = build_events(features, start_ms, end_ms)
        print(f"resolving {len(events)} paired signals on 1m paths", file=sys.stderr, flush=True)
        outcomes = attach_outcomes(events, minutes)
        results = {}
        for kind in ("lag", "leader"):
            chosen = [t for t in outcomes if t["kind"] == kind]
            base = summarize(chosen, BASE_SLIPPAGE_PER_SIDE)
            stress = summarize(chosen, STRESS_SLIPPAGE_PER_SIDE)
            base_portfolio = compounded_portfolio(chosen, BASE_SLIPPAGE_PER_SIDE)
            stress_portfolio = compounded_portfolio(chosen, STRESS_SLIPPAGE_PER_SIDE)
            nonoverlap = base_portfolio.pop("accepted")
            stress_portfolio.pop("accepted")
            base["portfolio"] = base_portfolio
            stress["portfolio"] = stress_portfolio
            n_hit = sum(t["label"] == "target" for t in nonoverlap)
            base["nonoverlap"] = {"n": len(nonoverlap), "m2": n_hit / len(nonoverlap) if nonoverlap else None,
                                  "wilson_95": wilson(n_hit, len(nonoverlap))}
            by_symbol = {}
            for symbol in ALT_SYMBOLS:
                subset = [t for t in chosen if t["symbol"] == symbol]
                by_symbol[symbol] = summarize(subset, BASE_SLIPPAGE_PER_SIDE)
            by_direction = {}
            for direction, label in ((1, "long"), (-1, "short")):
                by_direction[label] = summarize([t for t in chosen if t["direction"] == direction], BASE_SLIPPAGE_PER_SIDE)
            by_year = {}
            for year in sorted({pd.Timestamp(t["signal_ms"], unit="ms", tz="UTC").year for t in nonoverlap}):
                subset = [t for t in nonoverlap if pd.Timestamp(t["signal_ms"], unit="ms", tz="UTC").year == year]
                base_cost_side = FEE_PER_SIDE + BASE_SLIPPAGE_PER_SIDE
                stress_cost_side = FEE_PER_SIDE + STRESS_SLIPPAGE_PER_SIDE
                by_year[str(year)] = {"n": len(subset), "m2": sum(t["label"] == "target" for t in subset) / len(subset),
                                      "base_net_nav": math.prod(1 + t["gross_return"] - base_cost_side * (1 + t["exit_price"] / t["entry_price"]) for t in subset),
                                      "stress_net_nav": math.prod(1 + t["gross_return"] - stress_cost_side * (1 + t["exit_price"] / t["entry_price"]) for t in subset)}
            results[kind] = {"base": base, "stress": stress, "by_symbol_base": by_symbol,
                             "by_direction_base": by_direction, "by_year_nonoverlap": by_year}
        btc_rows = db.execute(
            "SELECT open,close FROM candles WHERE symbol='BTCUSDT' AND open_ms=?", (start_ms,)
        ).fetchone()
        btc_end = db.execute(
            "SELECT close FROM candles WHERE symbol='BTCUSDT' AND open_ms<? ORDER BY open_ms DESC LIMIT 1", (end_ms,)
        ).fetchone()
        if btc_rows and btc_end and btc_rows[0] > 0:
            btc_ratio = float(btc_end[0]) / float(btc_rows[0])
            benchmarks = {"cash_nav": 1.0,
                          "btc_buy_hold_nav_base": 1 + (btc_ratio - 1) - (FEE_PER_SIDE + BASE_SLIPPAGE_PER_SIDE) * (1 + btc_ratio),
                          "btc_buy_hold_nav_stress": 1 + (btc_ratio - 1) - (FEE_PER_SIDE + STRESS_SLIPPAGE_PER_SIDE) * (1 + btc_ratio),
                          "btc_gross_return": btc_ratio - 1}
        else:
            benchmarks = {"cash_nav": 1.0, "btc_buy_hold_nav_base": None,
                          "btc_buy_hold_nav_stress": None, "btc_gross_return": None}
        return {"source": path.name, "source_sha256": source_sha256,
                "integrity_check": check, "symbols": list(SYMBOLS),
                "start_ms": start_ms, "end_ms_exclusive": end_ms,
                "valid_btc_shock_anchors": eligible_anchors, "signal_coverage": len(events) / (2 * eligible_anchors) if eligible_anchors else None,
                "trial_count_candidates": 1, "benchmarks": benchmarks, "results": results}
    finally:
        db.close()


def _parse_utc(value: str) -> int:
    stamp = pd.Timestamp(value, tz="UTC")
    return int(stamp.value // 1_000_000)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--start", default="2020-04-01 00:00")
    parser.add_argument("--end", default="2024-01-01 00:00")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = load_and_run(args.db, _parse_utc(args.start), _parse_utc(args.end))
    result["code_sha256"] = _sha256(Path(__file__).resolve())
    result["source_attribution"] = "Binance Vision USDⓈ-M Futures historical klines"
    result["derived_data_license"] = "CC BY-NC-SA 4.0 (with attribution), per Binance Vision Dataset Terms v1.0"
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
