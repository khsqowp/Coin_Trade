"""Protect positions first; never send exchange mutations in paper mode."""

from typing import Any
from config import Config
from exchange import round_step
from ledger import Ledger
from http_client import BanError, ExchangeError
import uuid
from risk import RiskEngine


def _register(ledger: Ledger, intent: dict[str, Any], response: dict[str, Any]) -> None:
    """Commit acknowledged metadata before removing a durable submission intent."""
    symbol = intent["symbol"]
    existing = {
        (r.get("symbol"), r.get("orderId"))
        for r in ledger.store.records("orders.jsonl")
    }
    if (symbol, response["orderId"]) not in existing:
        safe = {
            k: response[k]
            for k in ("orderId", "status", "executedQty", "avgPrice")
            if k in response
        }
        ledger.store.append(
            "orders.jsonl",
            {
                **safe,
                **intent,
                "clientOrderId": intent["clientOrderId"],
                "generation": ledger.current["generation"],
                "ts": ledger.now,
            },
        )
    opening = ledger.current.get("opening_intents", {}).get(symbol)
    if intent["type"] == "MARKET" and not intent["reduceOnly"] and opening:
        opening["market_order_id"] = response["orderId"]
        opening["executed_qty"] = float(response.get("executedQty", 0))
        opening["status"] = response.get("status", "")
    if intent["type"] == "MARKET" and intent["reduceOnly"] and opening:
        opening["emergency_close"] = True
    if intent["type"] in ("STOP_MARKET", "TAKE_PROFIT_MARKET"):
        protection = ledger.current.setdefault("protections", {}).setdefault(symbol, {})
        if intent["type"] == "STOP_MARKET":
            protection.update(
                stop_order_id=response["orderId"], stop=float(intent["stopPrice"])
            )
            if opening:
                opening["stop_order_id"] = response["orderId"]
        else:
            protection.update(
                tp_order_id=response["orderId"], tp=float(intent["stopPrice"])
            )
    ledger.current.setdefault("pending_orders", {}).pop(intent["clientOrderId"], None)
    ledger.save()


def _submit(
    exchange: Any,
    ledger: Ledger,
    action: dict[str, Any],
    side: str,
    quantity: float,
    order_type: str = "MARKET",
    trigger: float | None = None,
    reduce: bool = False,
) -> dict[str, Any]:
    symbol = action["symbol"]
    info = ledger.symbol_info[symbol]
    cid = "ags_" + uuid.uuid4().hex[:24]
    intent = {
        "symbol": symbol,
        "side": side,
        "quantity": round_step(quantity, info["stepSize"]),
        "type": order_type,
        "stopPrice": (
            round_step(trigger, info["tickSize"]) if trigger is not None else None
        ),
        "reduceOnly": reduce,
        "clientOrderId": cid,
        "stop": action.get("stop_loss"),
        "tp": action.get("take_profit"),
        "rationale": action.get("rationale", ""),
        "decision_id": action.get("decision_id"),
    }
    if order_type == "MARKET" and not reduce:
        ledger.current.setdefault("opening_intents", {})[symbol] = {
            "action": action,
            "quantity": quantity,
            "entry_client_id": cid,
        }
    ledger.current.setdefault("pending_orders", {})[cid] = intent
    ledger.save()
    try:
        response = exchange.new_order(
            symbol,
            side,
            intent["quantity"],
            order_type=order_type,
            stop_price=intent["stopPrice"],
            reduce_only=reduce,
            client_order_id=cid,
        )
    except ExchangeError as exc:
        if exc.status is not None and 400 <= exc.status < 500:
            ledger.current["pending_orders"].pop(cid, None)
            if order_type == "MARKET" and not reduce:
                ledger.current["opening_intents"].pop(symbol, None)
            ledger.save()
        raise
    _register(ledger, intent, response)
    return response


def recover_pending_orders(exchange: Any, ledger: Ledger) -> None:
    """Query durable client IDs; never resubmit an uncertain entry."""
    for cid, intent in list(ledger.current.get("pending_orders", {}).items()):
        try:
            response = exchange.order_by_client(intent["symbol"], cid)
        except BanError:
            raise
        except Exception:
            raise RuntimeError(
                "Unresolved order submission; trading remains blocked"
            ) from None
        _register(ledger, intent, response)


def cleanup_closed_positions(exchange: Any, ledger: Ledger) -> None:
    """Cancel sibling protections before a symbol can begin a new lifecycle."""
    for symbol in list(ledger.current.get("cleanup_symbols", [])):
        if ledger.position(symbol):
            raise RuntimeError(
                "Lifecycle cleanup cannot cancel protections on a reopened position"
            )
        owned = {
            int(r["orderId"])
            for r in ledger.store.records("orders.jsonl")
            if r.get("generation") == ledger.current["generation"]
            and r.get("symbol") == symbol
            and "orderId" in r
        }
        for canceled in exchange.cancel_all(symbol, owned_order_ids=owned):
            ledger.store.append(
                "orders.jsonl",
                {
                    "generation": ledger.current["generation"],
                    "ts": ledger.now,
                    "symbol": symbol,
                    "canceled_order_id": canceled["orderId"],
                },
            )
        ledger.current.get("protections", {}).pop(symbol, None)
        ledger.current.get("opening_intents", {}).pop(symbol, None)
        ledger.current["cleanup_symbols"].remove(symbol)
        ledger.save()


def resolve_flat_openings(exchange: Any, ledger: Ledger) -> None:
    for symbol, opening in list(ledger.current.get("opening_intents", {}).items()):
        if ledger.position(symbol) is not None:
            continue
        response = exchange.order_by_client(symbol, opening["entry_client_id"])
        status = response.get("status", "")
        if status in ("CANCELED", "EXPIRED", "REJECTED") and not float(
            response.get("executedQty", 0)
        ):
            ledger.current["opening_intents"].pop(symbol)
            ledger.current.get("protections", {}).pop(symbol, None)
            ledger.save()
        else:
            raise RuntimeError("Opening fills are pending; wait before reconciliation")


def recover_openings(exchange: Any, ledger: Ledger) -> None:
    for symbol, opening in list(ledger.current.get("opening_intents", {}).items()):
        if symbol in ledger.current.get("foreign_symbols", []):
            raise RuntimeError("Unresolved opening overlaps foreign activity")
        p = ledger.position(symbol)
        if opening.get("emergency_close") and not p:
            del ledger.current["opening_intents"][symbol]
            ledger.save()
            continue
        if p is None:
            if opening.get("status") in (
                "CANCELED",
                "EXPIRED",
                "REJECTED",
            ) and not opening.get("executed_qty"):
                del ledger.current["opening_intents"][symbol]
                ledger.save()
                continue
            raise RuntimeError(
                "Opening fills are not yet confirmed; trading remains blocked"
            )
        a = opening["action"]
        side = "SELL" if p["side"] == "long" else "BUY"
        if not opening.get("stop_order_id"):
            try:
                _submit(
                    exchange,
                    ledger,
                    a,
                    side,
                    p["qty"],
                    "STOP_MARKET",
                    a["stop_loss"],
                    True,
                )
            except Exception:
                ledger.store.append(
                    "rejections.jsonl",
                    {
                        "generation": ledger.current["generation"],
                        "ts": ledger.now,
                        "symbol": symbol,
                        "level": "CRITICAL",
                        "reason": "Recovered entry stop failed; emergency close attempted",
                    },
                )
                _submit(exchange, ledger, a, side, p["qty"], reduce=True)
                raise RuntimeError(
                    "Recovered opening needs confirmed emergency flatten"
                ) from None
        p.update(ledger.current.get("protections", {}).get(symbol, {}))
        del ledger.current["opening_intents"][symbol]
        ledger.save()
    for p in ledger.positions:
        p.update(ledger.current.get("protections", {}).get(p["symbol"], {}))
    ledger.save()


def _cancel(exchange: Any, ledger: Ledger, symbol: str, order_id: int) -> None:
    exchange.cancel_order(symbol, order_id)
    ledger.store.append(
        "orders.jsonl",
        {
            "generation": ledger.current["generation"],
            "ts": ledger.now,
            "symbol": symbol,
            "canceled_order_id": order_id,
        },
    )


def execute(
    accepted_actions: list[dict[str, Any]],
    exchange: Any,
    ledger: Ledger,
    config: Config,
    dry_run: bool,
) -> list[dict[str, Any]]:
    results = []
    for original in accepted_actions:
        if not dry_run:
            cleanup_closed_positions(exchange, ledger)
        a = dict(original)
        symbol, kind = a["symbol"], a["type"]
        if symbol in ledger.current.get("foreign_symbols", []):
            results.append({"symbol": symbol, "status": "blocked_foreign"})
            continue
        p = ledger.position(symbol)
        price = ledger.prices[symbol]
        info = ledger.symbol_info.get(
            symbol, {"stepSize": "0.00000001", "tickSize": "0.00000001"}
        )
        if kind == "open":
            qty = float(
                round_step(
                    a["size_pct_equity"]
                    / 100
                    * ledger.equity()
                    * a["leverage"]
                    / price,
                    info["stepSize"],
                )
            )
            stop = float(
                round_step(a["stop_loss"], info["tickSize"], up=a["side"] == "short")
            )
            tp = (
                float(
                    round_step(
                        a["take_profit"], info["tickSize"], up=a["side"] == "long"
                    )
                )
                if "take_profit" in a
                else None
            )
            # Rounding towards the mark can invalidate a trigger; fail closed.
            if (
                qty <= 0
                or qty < float(info.get("minQty", 0))
                or qty * price < float(info.get("minNotional", 0))
                or (a["side"] == "long" and stop >= price)
                or (a["side"] == "short" and stop <= price)
            ):
                ledger.store.append(
                    "rejections.jsonl",
                    {
                        "ts": ledger.now,
                        "generation": ledger.current["generation"],
                        "reason": "Rounded order violates symbol filters",
                        "action": a,
                    },
                )
                results.append({"symbol": symbol, "status": "rounding_rejected"})
                continue
            a.update(quantity=qty, stop_loss=stop)
            if tp is not None:
                a["take_profit"] = tp
        # Revalidate using actual capital and rounded prices, not admission-time estimates.
        checked = dict(a)
        if kind == "open":
            checked["size_pct_equity"] = (
                qty * price / a["leverage"] / ledger.equity() * 100
            )
        elif kind == "modify" and p:
            checked["stop_loss"] = float(
                round_step(
                    a.get("stop_loss", p["stop"]),
                    info["tickSize"],
                    up=p["side"] == "short",
                )
            )
            if "take_profit" in a:
                checked["take_profit"] = float(
                    round_step(
                        a["take_profit"], info["tickSize"], up=p["side"] == "long"
                    )
                )
            a.update(
                {k: checked[k] for k in ("stop_loss", "take_profit") if k in checked}
            )
        ctx = {
            "equity": ledger.equity(),
            "positions": ledger.positions,
            "prices": ledger.prices,
            "allowed_symbols": config.watchlist,
            "symbol_info": ledger.symbol_info,
            "foreign_symbols": ledger.current.get("foreign_symbols", []),
            "data_age_seconds": 0,
            "sit_out_until": ledger.current.get("sit_out_until"),
        }
        _, admitted, rejection = RiskEngine(config).evaluate([checked], ctx)[0]
        if not admitted:
            ledger.store.append(
                "rejections.jsonl",
                {
                    "ts": ledger.now,
                    "generation": ledger.current["generation"],
                    "reason": rejection,
                    "action": a,
                },
            )
            results.append({"symbol": symbol, "status": "risk_rejected"})
            continue
        if dry_run:
            if kind == "open":
                ledger.simulate_open(a, price, ledger.now)
            elif kind == "close":
                ledger.simulate_close(symbol, price, ledger.now)
            elif p:
                p.update(
                    stop=a.get("stop_loss", p["stop"]),
                    tp=a.get("take_profit", p.get("tp")),
                )
                ledger.save()
            ledger.store.append(
                "orders.jsonl",
                {
                    "generation": ledger.current["generation"],
                    "ts": ledger.now,
                    "simulated": True,
                    "action": a,
                },
            )
            results.append({"symbol": symbol, "status": "simulated"})
            continue

        def order(
            side: str,
            quantity: float,
            order_type: str = "MARKET",
            trigger: float | None = None,
            reduce: bool = False,
        ) -> dict[str, Any]:
            return _submit(
                exchange, ledger, a, side, quantity, order_type, trigger, reduce
            )

        try:
            if kind == "open":
                exchange.set_leverage(symbol, a["leverage"])
                entry_side = "BUY" if a["side"] == "long" else "SELL"
                close_side = "SELL" if a["side"] == "long" else "BUY"
                market = order(entry_side, qty)
                # Protect requested quantity even when acknowledgement is delayed. Reduce-only prevents reversal.
                filled_qty = qty
                try:
                    protective = order(
                        close_side, filled_qty, "STOP_MARKET", stop, True
                    )
                except Exception:
                    ledger.store.append(
                        "rejections.jsonl",
                        {
                            "generation": ledger.current["generation"],
                            "ts": ledger.now,
                            "symbol": symbol,
                            "level": "CRITICAL",
                            "reason": "Stop placement failed; emergency close attempted",
                        },
                    )
                    order(close_side, filled_qty, reduce=True)
                    ledger.sync_fills(exchange, [symbol], ledger.now)
                    raise RuntimeError(
                        "Stop placement failed; emergency close submitted"
                    ) from None
                ledger.sync_fills(exchange, [symbol], ledger.now)
                p = ledger.position(symbol)
                if p:
                    p.update(stop=stop, tp=tp, stop_order_id=protective["orderId"])
                if tp is not None:
                    profit = order(
                        close_side, filled_qty, "TAKE_PROFIT_MARKET", tp, True
                    )
                    if p:
                        p["tp_order_id"] = profit["orderId"]
                # Keep an opening journal until fills and mandatory protection are confirmed.
                if p:
                    ledger.current.get("opening_intents", {}).pop(symbol, None)
            elif kind == "close" and p:
                owned = {
                    int(r["orderId"])
                    for r in ledger.store.records("orders.jsonl")
                    if r.get("generation") == ledger.current["generation"]
                    and r.get("symbol") == symbol
                    and "orderId" in r
                }
                for canceled in exchange.cancel_all(symbol, owned_order_ids=owned):
                    ledger.store.append(
                        "orders.jsonl",
                        {
                            "generation": ledger.current["generation"],
                            "ts": ledger.now,
                            "symbol": symbol,
                            "canceled_order_id": canceled["orderId"],
                        },
                    )
                order("SELL" if p["side"] == "long" else "BUY", p["qty"], reduce=True)
                ledger.sync_fills(exchange, [symbol], ledger.now)
                cleanup_closed_positions(exchange, ledger)
            elif kind == "modify" and p:
                side = "SELL" if p["side"] == "long" else "BUY"
                # A new stop always exists before any previous protection is removed.
                stop = float(
                    round_step(
                        a.get("stop_loss", p["stop"]),
                        info["tickSize"],
                        up=p["side"] == "short",
                    )
                )
                new_stop = order(side, p["qty"], "STOP_MARKET", stop, True)
                old_stop = p.get("stop_order_id")
                p.update(stop=stop, stop_order_id=new_stop["orderId"])
                ledger.save()
                if old_stop:
                    _cancel(exchange, ledger, symbol, old_stop)
                if "take_profit" in a:
                    new_tp = order(
                        side, p["qty"], "TAKE_PROFIT_MARKET", a["take_profit"], True
                    )
                    old_tp = p.get("tp_order_id")
                    p.update(tp=a["take_profit"], tp_order_id=new_tp["orderId"])
                    ledger.save()
                    if old_tp:
                        _cancel(exchange, ledger, symbol, old_tp)
            ledger.save()
            results.append({"symbol": symbol, "status": "executed"})
        except BanError:
            raise
        except Exception:
            # Never serialize a transport/runner exception that could contain credentials.
            ledger.save()
            ledger.store.append(
                "rejections.jsonl",
                {
                    "generation": ledger.current["generation"],
                    "ts": ledger.now,
                    "symbol": symbol,
                    "reason": "Execution failed; inspect owned orders",
                    "level": "ERROR",
                },
            )
            results.append({"symbol": symbol, "status": "failed"})
            break
    return results


def flatten(
    exchange: Any, ledger: Ledger, config: Config, dry_run: bool, reason: str
) -> None:
    if not dry_run:
        cleanup_closed_positions(exchange, ledger)
    actions = [
        {"type": "close", "symbol": p["symbol"], "rationale": reason}
        for p in list(ledger.positions)
    ]
    outcomes = execute(actions, exchange, ledger, config, dry_run)
    if (
        any(r["status"] not in ("executed", "simulated") for r in outcomes)
        or ledger.positions
    ):
        raise RuntimeError("Flatten incomplete; generation cannot advance")
