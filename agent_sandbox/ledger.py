"""Owned fills and virtual capital, independent of raw exchange equity."""

from typing import Any
from config import Config
from state import StateStore


class Ledger:
    def __init__(self, store: StateStore, config: Config):
        self.store, self.config = store, config
        self.current = store.read("current.json", {})
        self.prices: dict[str, float] = {}
        self.symbol_info: dict[str, dict[str, Any]] = {}
        self.now: float = 0
        self.flush_pending_fills()

    @property
    def positions(self) -> list[dict[str, Any]]:
        return self.current.setdefault("positions", [])

    def save(self) -> None:
        self.store.write("current.json", self.current)

    def position(self, symbol: str) -> dict[str, Any] | None:
        return next((p for p in self.positions if p["symbol"] == symbol), None)

    def equity(self, prices: dict[str, float] | None = None) -> float:
        prices = prices if prices is not None else self.prices
        unrealized = sum(
            (prices.get(p["symbol"], p["entry"]) - p["entry"])
            * p["qty"]
            * (1 if p["side"] == "long" else -1)
            for p in self.positions
        )
        return (
            self.current.get("start_virtual_equity", self.config.start_equity)
            + self.current.get("realized_pnl", 0)
            - self.current.get("fees", 0)
            + unrealized
        )

    def apply_fill(
        self,
        symbol: str,
        side: str,
        qty: float,
        price: float,
        fee: float,
        ts: float,
        fill_id: str,
        **metadata: Any,
    ) -> bool:
        original_qty = qty
        seen = self.current.setdefault("seen_fills", [])
        if fill_id in seen:
            return False
        p = self.position(symbol)
        realized = 0.0
        direction = "long" if side == "BUY" else "short"
        if p and p["side"] != direction:
            metadata.setdefault("entry_decision_id", p.get("decision_id"))
            metadata.setdefault("decision_id", p.get("decision_id"))
            metadata["exit"] = True
            closed = min(qty, p["qty"])
            realized = (
                (price - p["entry"]) * closed * (1 if p["side"] == "long" else -1)
            )
            p["qty"] -= closed
            qty -= closed
            p["notional"] = p["qty"] * p["entry"]
            if p["qty"] <= 1e-12:
                self.positions.remove(p)
                if fill_id.startswith("live:"):
                    cleanup = self.current.setdefault("cleanup_symbols", [])
                    if symbol not in cleanup:
                        cleanup.append(symbol)
                p = None
        if qty > 1e-12:
            if p:
                p["entry"] = (p["entry"] * p["qty"] + price * qty) / (p["qty"] + qty)
                p["qty"] += qty
            else:
                p = {
                    "symbol": symbol,
                    "side": direction,
                    "qty": qty,
                    "entry": price,
                    "stop": metadata.get("stop"),
                    "tp": metadata.get("tp"),
                    "opened_at": ts,
                    "decision_id": metadata.get("decision_id"),
                    "stop_order_id": None,
                    "tp_order_id": None,
                }
                self.positions.append(p)
            p["notional"] = p["qty"] * p["entry"]
        self.current["realized_pnl"] = self.current.get("realized_pnl", 0) + realized
        self.current["fees"] = self.current.get("fees", 0) + fee
        seen.append(fill_id)
        event = {
            "generation": self.current["generation"],
            "ts": ts,
            "symbol": symbol,
            "side": side,
            "price": price,
            "fee": fee,
            "realized_pnl": realized,
            "fill_id": fill_id,
            "qty": original_qty,
            **metadata,
        }
        self.current.setdefault("pending_fills", []).append(event)
        self.save()
        self.flush_pending_fills()
        return True

    def flush_pending_fills(self) -> None:
        pending = self.current.get("pending_fills", [])
        if not pending:
            return
        logged = {r["fill_id"] for r in self.store.records("fills.jsonl")}
        for event in pending:
            if event["fill_id"] not in logged:
                self.store.append("fills.jsonl", event)
                logged.add(event["fill_id"])
        self.current["pending_fills"] = []
        self.save()

    def simulate_open(self, action: dict[str, Any], price: float, ts: float) -> None:
        qty = action.get(
            "quantity",
            action["size_pct_equity"]
            / 100
            * self.equity()
            * action["leverage"]
            / price,
        )
        self.apply_fill(
            action["symbol"],
            "BUY" if action["side"] == "long" else "SELL",
            qty,
            price,
            qty * price * self.config.taker_fee_rate,
            ts,
            self._sim_id(),
            stop=action["stop_loss"],
            tp=action.get("take_profit"),
            rationale=action["rationale"],
            decision_id=action.get("decision_id"),
            exit=False,
        )

    def _sim_id(self) -> str:
        self.current["sim_sequence"] = self.current.get("sim_sequence", 0) + 1
        return f"sim:{self.current['generation']}:{self.current['sim_sequence']}"

    def simulate_close(
        self, symbol: str, price: float, ts: float, reason: str = "close"
    ) -> None:
        p = self.position(symbol)
        if not p:
            return
        self.apply_fill(
            symbol,
            "SELL" if p["side"] == "long" else "BUY",
            p["qty"],
            price,
            p["qty"] * price * self.config.taker_fee_rate,
            ts,
            self._sim_id(),
            exit=True,
            reason=reason,
        )

    def simulate_triggers(
        self, candles: dict[str, list[list[Any]]], now: float
    ) -> None:
        last = self.current.get("last_tick", self.current.get("start_ts", now))
        for p in list(self.positions):
            for c in sorted(candles.get(p["symbol"], []), key=lambda c: c[0]):
                opened, closed = float(c[0]) / 1000, (
                    float(c[6]) / 1000 if len(c) > 6 else float(c[0]) / 1000 + 900
                )
                # Use only completed candles wholly after the position existed.
                if closed <= last or closed > now or opened < p.get("opened_at", last):
                    continue
                high, low = float(c[2]), float(c[3])
                stop, tp = p.get("stop"), p.get("tp")
                stop_hit = stop is not None and (
                    low <= stop if p["side"] == "long" else high >= stop
                )
                tp_hit = tp is not None and (
                    high >= tp if p["side"] == "long" else low <= tp
                )
                if stop_hit or tp_hit:
                    fill_price = stop if stop_hit else tp
                    assert fill_price is not None
                    self.simulate_close(
                        p["symbol"],
                        fill_price,
                        closed,
                        "stop" if stop_hit else "take_profit",
                    )
                    break

    def sync_fills(self, exchange: Any, symbols: list[str], now: float) -> None:
        orders = {
            (r["symbol"], str(r["orderId"])): r
            for r in self.store.records("orders.jsonl")
            if r.get("generation") == self.current["generation"]
            and "orderId" in r
            and "symbol" in r
        }
        cursors = self.current.setdefault("trade_cursors", {})
        for symbol in symbols:
            cursor = cursors.get(symbol, {})
            from_id = cursor.get("from_id")
            start = cursor.get("start_ms", int(self.current["start_ts"] * 1000))
            while True:
                trades = exchange.user_trades(symbol, start, from_id)
                for t in sorted(trades, key=lambda t: (t["time"], t["id"])):
                    key = (symbol, str(t["orderId"]))
                    order = orders.get(key)
                    # Unregistered orders (even another bot's ags_ orders) are foreign.
                    if not order or not order.get("clientOrderId", "").startswith(
                        "ags_"
                    ):
                        continue
                    if t.get("commissionAsset", "USDT") != "USDT":
                        raise RuntimeError("Non-USDT fee cannot be valued honestly")
                    self.apply_fill(
                        symbol,
                        t["side"],
                        float(t["qty"]),
                        float(t["price"]),
                        float(t["commission"]),
                        float(t["time"]) / 1000,
                        f"live:{symbol}:{t['id']}",
                        stop=order.get("stop"),
                        tp=order.get("tp"),
                        rationale=order.get("rationale", ""),
                        decision_id=order.get("decision_id"),
                        exit=order.get("reduceOnly", False) in (True, "true"),
                    )
                if trades:
                    from_id = max(int(t["id"]) for t in trades) + 1
                    cursors[symbol] = {"from_id": from_id, "start_ms": start}
                    self.save()
                if (
                    not trades
                    and from_id is None
                    and start + 7 * 86400000 < int(now * 1000)
                ):
                    start += 7 * 86400000
                    cursors[symbol] = {"start_ms": start}
                    self.save()
                    continue
                if not trades and from_id is None:
                    cursors[symbol] = {"start_ms": max(start, int(now * 1000) - 60000)}
                    self.save()
                if len(trades) < 1000:
                    break

    def reconcile(self, exchange_positions: list[dict[str, Any]]) -> list[str]:
        amounts = {
            p["symbol"]: float(p.get("positionAmt", 0)) for p in exchange_positions
        }
        foreign = set(self.current.get("foreign_symbols", []))
        for symbol in set(amounts) | {p["symbol"] for p in self.positions}:
            own = self.position(symbol)
            expected = own["qty"] * (1 if own["side"] == "long" else -1) if own else 0
            actual = amounts.get(symbol, 0)
            entry_differs = False
            if own and abs(actual) > 1e-12:
                raw = next(x for x in exchange_positions if x["symbol"] == symbol)
                raw_entry = float(raw.get("entryPrice", own["entry"]))
                entry_differs = abs(raw_entry - own["entry"]) > max(
                    1e-6, own["entry"] * 1e-6
                )
            if (
                abs(expected - actual) > max(1e-9, abs(expected) * 1e-6)
                or entry_differs
            ):
                if symbol not in foreign:
                    self.store.append(
                        "rejections.jsonl",
                        {
                            "generation": self.current["generation"],
                            "ts": self.now,
                            "symbol": symbol,
                            "reason": "Foreign/manual position mismatch",
                            "level": "WARNING",
                        },
                    )
                foreign.add(symbol)
        self.current["foreign_symbols"] = sorted(foreign)
        self.save()
        return sorted(foreign)
