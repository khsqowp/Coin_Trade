"""Read-only shadow forecasts and walk-forward scoring for paper strategies."""
from __future__ import annotations

import json
import logging
import os
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol


HORIZONS = (1, 5)
MAX_PENDING = 10_000
MAX_SCORES = 10_000
logger = logging.getLogger("shadow_predictor.core")


class Forecaster(Protocol):
    def forecast(self, symbol: str, bars: list[dict[str, Any]], horizon: int) -> list[float]: ...


class KronosForecaster:
    """Lazy-load Kronos-mini; expects official shiyu-coder/Kronos sources on sys.path."""

    def __init__(self, model_id: str, tokenizer_id: str, context_length: int = 300):
        import torch
        import pandas as pd
        from model import Kronos, KronosPredictor, KronosTokenizer

        self.pd = pd
        self.torch = torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tokenizer = KronosTokenizer.from_pretrained(tokenizer_id)
        self.model = Kronos.from_pretrained(model_id)
        self.tokenizer.eval()
        self.model.eval()
        self.predictor = KronosPredictor(self.model, self.tokenizer, device=device, max_context=context_length)

    def forecast(self, symbol: str, bars: list[dict[str, Any]], horizon: int) -> list[float]:
        pd = self.pd
        frame = pd.DataFrame(bars)[["open", "high", "low", "close", "volume"]].astype(float)
        timestamps = pd.to_datetime([int(bar["minute"]) * 60_000 for bar in bars], unit="ms", utc=True)
        x_timestamp = pd.Series(timestamps)
        last = timestamps[-1]
        y_timestamp = pd.Series([last + pd.Timedelta(minutes=i) for i in range(1, horizon + 1)])
        with self.torch.no_grad():
            predicted = self.predictor.predict(
                df=frame.reset_index(drop=True),
                x_timestamp=x_timestamp.reset_index(drop=True),
                y_timestamp=y_timestamp.reset_index(drop=True),
                pred_len=horizon,
                T=1.0,
                top_k=1,
                top_p=1.0,
                verbose=False,
                sample_count=1,
            )
        closes = [float(value) for value in predicted["close"].tolist()]
        if len(closes) != horizon or any(not (value > 0) for value in closes):
            raise ValueError(f"invalid Kronos close forecast for {symbol}")
        return closes


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("state root must be a JSON object")
    return value


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _append_completed(output: dict[str, Any], bars_by_symbol: dict[str, list[dict[str, Any]]]) -> None:
    pending = output.setdefault("pending", [])
    scores = output.setdefault("scores", [])
    expired = output.setdefault("expired", [])
    for symbol, bars in bars_by_symbol.items():
        actuals = {int(bar["minute"]): float(bar["close"]) for bar in bars}
        earliest_minute = min(actuals) if actuals else None
        remaining = []
        for item in pending:
            if item["symbol"] != symbol:
                remaining.append(item)
                continue
            target_minute = int(item["target_minute"])
            if target_minute not in actuals:
                if earliest_minute is not None and target_minute < earliest_minute:
                    expired.append({
                        "symbol": symbol,
                        "horizon": int(item["horizon"]),
                        "origin_minute": int(item["origin_minute"]),
                        "target_minute": target_minute,
                        "predicted_close": float(item["predicted_close"]),
                        "base_close": float(item["base_close"]),
                        "status": "expired",
                    })
                else:
                    remaining.append(item)
                continue
            actual = actuals[target_minute]
            predicted = float(item["predicted_close"])
            base = float(item["base_close"])
            origin = float(item["origin_close"])
            scores.append({
                "symbol": symbol,
                "horizon": int(item["horizon"]),
                "origin_minute": int(item["origin_minute"]),
                "target_minute": int(item["target_minute"]),
                "predicted_close": predicted,
                "actual_close": actual,
                "baseline_close": base,
                "absolute_error_pct": abs(predicted / actual - 1) * 100,
                "baseline_absolute_error_pct": abs(base / actual - 1) * 100,
                "direction_hit": (predicted - origin) * (actual - origin) >= 0,
            })
        pending[:] = remaining
    del scores[:-MAX_SCORES]
    del expired[:-MAX_SCORES]
    del pending[:-MAX_PENDING]


def score_summary(scores: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for score in scores:
        grouped[f"{score['symbol']}:{score['horizon']}m"].append(score)
        grouped[f"ALL:{score['horizon']}m"].append(score)
    result = {}
    for key, rows in grouped.items():
        count = len(rows)
        result[key] = {
            "samples": count,
            "mae_pct": sum(row["absolute_error_pct"] for row in rows) / count,
            "random_walk_mae_pct": sum(row["baseline_absolute_error_pct"] for row in rows) / count,
            "direction_accuracy_pct": sum(bool(row["direction_hit"]) for row in rows) / count * 100,
        }
    return result


def _strategy_view(state: dict[str, Any], forecasts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for strategy_id, item in state.get("summary", {}).items():
        positions = item.get("open_positions", {})
        conflicts = []
        for symbol, position in positions.items():
            forecast = forecasts.get(symbol)
            if not forecast:
                continue
            side = position.get("side")
            predicted_side = "long" if forecast["predicted_return_5m_pct"] > 0 else "short"
            if side in ("long", "short") and side != predicted_side:
                conflicts.append({"symbol": symbol, "position_side": side, "forecast_side": predicted_side})
        result[strategy_id] = {
            "name": item.get("name"),
            "equity": item.get("equity"),
            "total_pnl": item.get("total_pnl"),
            "trades": item.get("trades"),
            "open_positions": positions,
            "forecast_conflicts_review_only": conflicts,
        }
    return result


def process_snapshot(state: dict[str, Any], output: dict[str, Any], forecaster: Forecaster) -> bool:
    bars_by_symbol = state.get("bars")
    if not isinstance(bars_by_symbol, dict):
        raise ValueError("input state has no bars object")
    _append_completed(output, bars_by_symbol)
    forecasts = output.setdefault("latest_forecasts", {})
    processed = output.setdefault("last_processed_minute", {})
    has_new_forecasts = False
    for symbol, bars in bars_by_symbol.items():
        try:
            if len(bars) < 30:
                continue
            minute = int(bars[-1]["minute"])
            if processed.get(symbol) == minute:
                continue
            closes = forecaster.forecast(symbol, bars[-300:], max(HORIZONS))
            origin_close = float(bars[-1]["close"])
            forecast = {
                "origin_minute": minute,
                "origin_close": origin_close,
                "predicted_close_1m": closes[0],
                "predicted_close_5m": closes[-1],
                "predicted_return_1m_pct": (closes[0] / origin_close - 1) * 100,
                "predicted_return_5m_pct": (closes[-1] / origin_close - 1) * 100,
            }
            new_forecasts = [{
                "symbol": symbol,
                "origin_minute": minute,
                "target_minute": minute + horizon,
                "horizon": horizon,
                "origin_close": origin_close,
                "predicted_close": close,
                "base_close": origin_close,
            } for horizon, close in ((1, closes[0]), (5, closes[-1]))]
        except Exception:
            logger.warning("Forecast failed for symbol %s", symbol, exc_info=True)
            continue
        output.setdefault("pending", []).extend(new_forecasts)
        forecasts[symbol] = forecast
        processed[symbol] = minute
        has_new_forecasts = True
    output["coverage"] = {
        "scored": len(output.get("scores", [])),
        "expired": len(output.get("expired", [])),
        "pending": len(output.get("pending", [])),
    }
    if not has_new_forecasts and output.get("source_updated_at") == state.get("updated_at"):
        return False
    output["strategy_snapshot"] = _strategy_view(state, forecasts)
    output["source_updated_at"] = state.get("updated_at")
    output["updated_at"] = datetime.now(timezone.utc).isoformat()
    output["model"] = {"name": "Kronos-mini", "horizons_minutes": list(HORIZONS)}
    output["guardrails"] = {
        "mode": "shadow_only",
        "orders_enabled": False,
        "exchange_access": False,
        "source_state_read_only": True,
        "strategy_changes": False,
        "interpretation": "Forecast conflicts are review-only hypotheses; no adjustment is applied.",
    }
    output["metrics"] = score_summary(output.get("scores", []))
    return True
