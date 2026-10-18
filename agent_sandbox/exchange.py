"""Binance USDS-M testnet adapter; no third-party exchange SDK."""

from decimal import Decimal, ROUND_DOWN, ROUND_UP
from typing import Any
import uuid
from http_client import ThrottledHttp, ExchangeError
from safety import SafetyError


def round_step(value: float, step: str | float, up: bool = False) -> str:
    unit = Decimal(str(step))
    if unit <= 0:
        raise ValueError("Step must be positive")
    rounded = (Decimal(str(value)) / unit).to_integral_value(
        rounding=ROUND_UP if up else ROUND_DOWN
    ) * unit
    return format(rounded, "f")


class TestnetExchange:
    __test__ = False

    def __init__(self, http: ThrottledHttp, dry_run: bool = True):
        self.http, self.dry_run = http, dry_run

    def server_time(self) -> int:
        return int(self.http.get("/fapi/v1/time")["serverTime"])

    def exchange_info(self) -> dict[str, dict[str, Any]]:
        result = {}
        for s in self.http.get("/fapi/v1/exchangeInfo")["symbols"]:
            f = {x["filterType"]: x for x in s["filters"]}
            lot = f.get("MARKET_LOT_SIZE", f["LOT_SIZE"])
            if float(lot["stepSize"]) == 0:
                lot = f["LOT_SIZE"]
            result[s["symbol"]] = {
                "tickSize": f["PRICE_FILTER"]["tickSize"],
                "stepSize": lot["stepSize"],
                "minQty": float(lot["minQty"]),
                "minNotional": float(f.get("MIN_NOTIONAL", {}).get("notional", 0)),
                "status": s.get("status", "TRADING"),
            }
        return result

    def klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 250,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> list[list[Any]]:
        params: dict[str, Any] = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        }
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        return self.http.get("/fapi/v1/klines", params)

    def premium_index(self) -> list[dict[str, Any]]:
        return self.http.get("/fapi/v1/premiumIndex")

    def open_interest(self, symbol: str) -> float:
        return float(
            self.http.get("/fapi/v1/openInterest", {"symbol": symbol})["openInterest"]
        )

    def account(self) -> dict[str, Any]:
        a = self.http.get("/fapi/v2/account", signed=True)
        return {
            "equity": float(a["totalWalletBalance"])
            + float(a["totalUnrealizedProfit"]),
            "positions": a.get("positions", []),
        }

    def position_risk(self) -> list[dict[str, Any]]:
        return self.http.get("/fapi/v2/positionRisk", signed=True)

    def position_mode(self) -> bool:
        value = self.http.get("/fapi/v1/positionSide/dual", signed=True)[
            "dualSidePosition"
        ]
        if value not in (False, "false"):
            raise SafetyError("Hedge mode is refused; one-way mode is required")
        return False

    def user_trades(
        self, symbol: str, start_time: int, from_id: int | None = None
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"symbol": symbol, "limit": 1000}
        params["fromId" if from_id is not None else "startTime"] = (
            from_id if from_id is not None else start_time
        )
        if from_id is None:
            params["endTime"] = start_time + 7 * 86400000 - 1
        return self.http.get("/fapi/v1/userTrades", params, signed=True)

    def order(self, symbol: str, order_id: int) -> dict[str, Any]:
        return self.http.get(
            "/fapi/v1/order", {"symbol": symbol, "orderId": order_id}, signed=True
        )

    def order_by_client(self, symbol: str, client_order_id: str) -> dict[str, Any]:
        return self.http.get(
            "/fapi/v1/order",
            {"symbol": symbol, "origClientOrderId": client_order_id},
            signed=True,
        )

    def open_orders(self, symbol: str | None = None) -> list[dict[str, Any]]:
        return self.http.get(
            "/fapi/v1/openOrders", {"symbol": symbol} if symbol else {}, signed=True
        )

    def _writable(self) -> None:
        if self.dry_run:
            raise SafetyError("Exchange mutations are disabled in dry-run")

    def set_leverage(self, symbol: str, leverage: int) -> dict[str, Any]:
        self._writable()
        return self.http.post(
            "/fapi/v1/leverage", {"symbol": symbol, "leverage": leverage}, signed=True
        )

    def new_order(
        self,
        symbol: str,
        side: str,
        quantity: float | str,
        order_type: str = "MARKET",
        stop_price: float | str | None = None,
        reduce_only: bool = False,
        client_order_id: str | None = None,
    ) -> dict[str, Any]:
        self._writable()
        if order_type not in ("MARKET", "STOP_MARKET", "TAKE_PROFIT_MARKET"):
            raise SafetyError("Unsupported order type")
        cid = client_order_id or "ags_" + uuid.uuid4().hex[:24]
        if not cid.startswith("ags_"):
            raise SafetyError("Agent clientOrderId must start with ags_")
        p: dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
            "newClientOrderId": cid,
            "newOrderRespType": "RESULT",
        }
        if reduce_only or order_type != "MARKET":
            p["reduceOnly"] = "true"
        if order_type != "MARKET":
            if stop_price is None:
                raise SafetyError("Trigger price is required")
            p.update(stopPrice=stop_price, workingType="MARK_PRICE")
        try:
            # Never blindly retry an order after an ambiguous acknowledgement.
            return self.http.post("/fapi/v1/order", p, signed=True, retry=False)
        except ExchangeError as exc:
            if exc.code == "NETWORK" or (exc.status is not None and exc.status >= 500):
                try:
                    return self.order_by_client(symbol, cid)
                except ExchangeError:
                    raise exc from None
            raise

    def cancel_order(self, symbol: str, order_id: int) -> dict[str, Any]:
        self._writable()
        return self.http.delete(
            "/fapi/v1/order", {"symbol": symbol, "orderId": order_id}, signed=True
        )

    def cancel_all(
        self, symbol: str, owned_order_ids: set[int] | None = None
    ) -> list[dict[str, Any]]:
        self._writable()
        if owned_order_ids is None:
            raise SafetyError(
                "Cancellation requires explicitly registered owned order IDs"
            )
        return [
            self.cancel_order(symbol, o["orderId"])
            for o in self.open_orders(symbol)
            if o.get("clientOrderId", "").startswith("ags_")
            and int(o["orderId"]) in owned_order_ids
        ]
