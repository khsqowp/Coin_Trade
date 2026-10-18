"""Sequential admission checks against virtual capital and owned positions."""

from copy import deepcopy
from typing import Any
from config import Config
from schema import number


class RiskEngine:
    def __init__(self, config: Config):
        self.config = config

    def daily_loss_breached(self, equity_now: float, equity_day_start: float) -> bool:
        return equity_day_start > 0 and equity_now <= equity_day_start * (
            1 - self.config.daily_loss_limit_pct / 100
        )

    def evaluate(
        self, actions: list[dict[str, Any]], ctx: dict[str, Any]
    ) -> list[tuple[dict[str, Any], bool, str]]:
        positions = {p["symbol"]: deepcopy(p) for p in ctx.get("positions", [])}
        results = []
        cfg = self.config
        equity = ctx["equity"]
        for a in actions:
            s, kind = a["symbol"], a["type"]
            reason = ""
            p = positions.get(s)
            price = ctx.get("prices", {}).get(s)
            info = ctx.get("symbol_info", {}).get(s, {})
            if s in ctx.get("foreign_symbols", []):
                reason = "Symbol has foreign account activity; trading is isolated"
            elif kind == "close":
                if not p:
                    reason = "No own open position to close"
            elif s not in ctx["allowed_symbols"]:
                reason = "Symbol is not allowed"
            elif ctx.get("data_age_seconds", 0) > cfg.stale_data_seconds:
                reason = "Market data is stale"
            elif not number(price) or price <= 0:
                reason = "No valid mark price"
            elif equity <= 0:
                reason = "Virtual equity is not positive"
            elif kind == "open":
                if ctx.get("sit_out_until"):
                    reason = "Daily loss sit-out is active"
                elif (
                    type(a.get("leverage")) is not int
                    or not 1 <= a["leverage"] <= cfg.max_leverage
                ):
                    reason = "Leverage exceeds limit or is invalid"
                elif p:
                    reason = "One position per symbol; use modify"
                elif len(positions) >= cfg.max_positions:
                    reason = "Maximum concurrent positions reached"
                elif (
                    not number(a.get("size_pct_equity"))
                    or not 0 < a["size_pct_equity"] <= 100
                ):
                    reason = "Invalid margin allocation"
            elif kind == "modify" and not p:
                reason = "No own open position to modify"
            elif kind not in ("modify", "open"):
                reason = "Unknown action type"
            if not reason and kind in ("open", "modify"):
                if kind == "open":
                    side = a["side"]
                else:
                    assert p is not None
                    side = p["side"]
                stop = a.get("stop_loss", p.get("stop") if p else None)
                tp = a.get("take_profit", p.get("tp") if p else None)
                if not number(stop) or stop <= 0:
                    reason = "Stop-loss is mandatory and must be positive"
                elif (side == "long" and stop >= price) or (
                    side == "short" and stop <= price
                ):
                    reason = "Stop-loss is on the wrong side of mark price"
                elif tp is not None and (
                    not number(tp)
                    or tp <= 0
                    or (side == "long" and tp <= price)
                    or (side == "short" and tp >= price)
                ):
                    reason = "Take-profit is on the wrong side of mark price"
                else:
                    if kind == "open":
                        notional = a["size_pct_equity"] / 100 * equity * a["leverage"]
                    else:
                        assert p is not None
                        notional = p["qty"] * price
                    risk = abs(price - stop) / price * notional
                    if risk > equity * cfg.max_risk_per_trade_pct / 100 + 1e-9:
                        reason = "Per-trade risk exceeds limit"
                    elif (
                        kind == "open"
                        and sum(
                            x["qty"] * ctx["prices"].get(x["symbol"], x["entry"])
                            for x in positions.values()
                        )
                        + notional
                        > equity * cfg.max_gross_exposure_x + 1e-9
                    ):
                        reason = "Gross exposure exceeds limit"
                    elif kind == "open" and notional < float(
                        info.get("minNotional", 0)
                    ):
                        reason = "Notional is below symbol minimum"
                    elif kind == "open" and notional / price < float(
                        info.get("minQty", 0)
                    ):
                        reason = "Quantity is below symbol minimum"
            if not reason:
                if kind == "close":
                    del positions[s]
                elif kind == "open":
                    positions[s] = {
                        "symbol": s,
                        "side": side,
                        "qty": notional / price,
                        "entry": price,
                        "stop": stop,
                        "tp": tp,
                        "notional": notional,
                    }
                else:
                    positions[s].update(stop=stop, tp=tp)
            results.append((a, not bool(reason), reason or "Accepted"))
        return results


def daily_loss_breached(
    equity_now: float, equity_day_start: float, config: Config | None = None
) -> bool:
    return RiskEngine(config or Config()).daily_loss_breached(
        equity_now, equity_day_start
    )
