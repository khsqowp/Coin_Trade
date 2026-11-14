"""Prediction schema and causal input validation."""
import math
import re
import pandas as pd
from .features import _digest

HORIZON = {"1m": 20, "5m": 100, "30m": 600, "60m": 1200}
FIELDS = {"symbol", "timeframe", "anchor_time", "created_at", "model", "prompt_version",
          "code_sha", "input_sha256", "direction", "confidence", "path", "target_low",
          "target_high", "invalidation", "side", "leverage_suggestion", "rationale"}


def validate_prediction(prediction, candles):
    """Validate fields and verify hash/side against completed anchor candles."""
    if set(prediction) != FIELDS:
        raise ValueError("prediction fields mismatch")
    tf = prediction["timeframe"]
    if tf not in HORIZON:
        raise ValueError("invalid timeframe")
    frame = candles.sort_values("t_open_ms").reset_index(drop=True)
    width = {"1m": 1, "5m": 5, "30m": 30, "60m": 60}[tf] * 60_000
    raw_anchor = prediction["anchor_time"]
    anchor = int(raw_anchor) if isinstance(raw_anchor, (int, float)) else int(pd.Timestamp(raw_anchor).timestamp() * 1000)
    frame = frame[frame.t_open_ms + width <= anchor].reset_index(drop=True)
    if frame.empty or int(frame.t_open_ms.iloc[-1]) + width != anchor:
        raise ValueError("anchor candle missing or incomplete")
    if prediction["input_sha256"] != _digest(frame):
        raise ValueError("input_sha256 mismatch")
    _validate_values(prediction)
    price = float(frame.c.iloc[-1])
    side, inv = prediction["side"], float(prediction["invalidation"])
    if side == "long" and inv >= price or side == "short" and inv <= price:
        raise ValueError("invalidation is not adverse to anchor price")
    return True


def _validate_values(p):
    """Check scalar enums, numeric ranges, timestamp and trajectory shape."""
    enums = (("direction", {"up", "down", "flat"}), ("side", {"long", "short", "none"}),
             ("model", {"claude", "codex"}))
    for key, allowed in enums:
        if not isinstance(p[key], str) or (p[key] not in allowed and
                not (key == "model" and p[key].startswith("baseline_"))):
            raise ValueError(f"invalid {key}")
    leverage = p["leverage_suggestion"]
    if isinstance(leverage, bool) or not isinstance(leverage, int) or not 1 <= leverage <= 125:
        raise ValueError("numeric range error")
    nums = [float(p[k]) for k in ("target_low", "target_high", "invalidation", "confidence")]
    if not all(math.isfinite(float(x)) for x in nums) or p["target_low"] > p["target_high"]:
        raise ValueError("invalid numeric values")
    if not 0 <= nums[3] <= 1 or not isinstance(p["symbol"], str) or not p["symbol"]:
        raise ValueError("invalid confidence or symbol")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", str(p["input_sha256"])):
        raise ValueError("invalid input hash")
    pd.Timestamp(p["created_at"])
    if not isinstance(p["rationale"], list) or not all(isinstance(x, str) for x in p["rationale"]):
        raise ValueError("rationale must be a string list")
    horizon = HORIZON[p["timeframe"]]
    if not isinstance(p["path"], list) or len(p["path"]) != 4:
        raise ValueError("path must contain four points")
    expected = [horizon * n // 4 for n in (1, 2, 3, 4)]
    if [x.get("minutes") for x in p["path"]] != expected:
        raise ValueError("path points do not match horizon")
    if not all(math.isfinite(float(x["price"])) for x in p["path"]):
        raise ValueError("invalid path price")
