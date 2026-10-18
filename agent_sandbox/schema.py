"""Strict all-or-nothing decisions and tolerant outer JSON extraction."""

from typing import Any
import json
import math
import re


def number(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def validate_decision(obj: Any) -> tuple[bool, list[str], dict[str, Any]]:
    errors: list[str] = []
    empty = {"actions": [], "notes": ""}
    if not isinstance(obj, dict):
        return False, ["Decision must be an object"], empty
    if set(obj) - {"actions", "notes", "summary"}:
        errors.append("Unknown decision keys")
    for key, limit in [("notes", 4000), ("summary", 500)]:
        if key == "summary" and key not in obj:
            continue
        if not isinstance(obj.get(key), str) or len(obj[key]) > limit:
            errors.append(f"{key} must be a string of at most {limit} characters")
    actions = obj.get("actions")
    if not isinstance(actions, list) or len(actions) > 10:
        errors.append("actions must be a list of at most 10 actions")
        actions = []
    for i, a in enumerate(actions):
        prefix = f"Action {i}: "
        if not isinstance(a, dict):
            errors.append(prefix + "must be an object")
            continue
        kind = a.get("type")
        required = {"type", "symbol", "rationale"}
        allowed = required.copy()
        if kind == "open":
            required |= {"side", "size_pct_equity", "leverage", "stop_loss"}
            allowed = required | {"take_profit"}
        elif kind == "modify":
            allowed |= {"stop_loss", "take_profit"}
            if not ({"stop_loss", "take_profit"} & set(a)):
                errors.append(prefix + "modify requires a stop_loss or take_profit")
        elif kind != "close":
            errors.append(prefix + "unknown action type")
        if required - set(a):
            errors.append(
                prefix
                + "missing required keys: "
                + ", ".join(sorted(required - set(a)))
            )
        if set(a) - allowed:
            errors.append(prefix + "unknown keys")
        if not isinstance(a.get("symbol"), str) or not re.fullmatch(
            r"[A-Z0-9]{2,30}", a.get("symbol", "")
        ):
            errors.append(prefix + "invalid symbol")
        if not isinstance(a.get("rationale"), str) or len(a["rationale"]) > 1000:
            errors.append(
                prefix + "rationale must be a string of at most 1000 characters"
            )
        for k in ("stop_loss", "take_profit", "size_pct_equity"):
            if k in a and (not number(a[k]) or a[k] <= 0):
                errors.append(prefix + k + " must be a finite positive number")
        if kind == "open":
            if a.get("side") not in ("long", "short"):
                errors.append(prefix + "invalid side")
            if type(a.get("leverage")) is not int or a["leverage"] < 1:
                errors.append(prefix + "leverage must be a positive integer")
            if number(a.get("size_pct_equity")) and a["size_pct_equity"] > 100:
                errors.append(prefix + "size_pct_equity exceeds 100")
    return not errors, errors, empty if errors else obj.copy()


def extract_json(text: str) -> dict[str, Any] | None:
    text = re.sub(r"```(?:json)?\s*|```", "", text.strip(), flags=re.I)
    decoder = json.JSONDecoder()
    candidates: list[dict[str, Any]] = []
    i = 0
    while i < len(text):
        if text[i] not in "{[":
            i += 1
            continue
        try:
            value, end = decoder.raw_decode(text, i)
        except ValueError:
            # A broken outer object must not expose its nested action as a decision.
            return None
        if isinstance(value, dict):
            candidates.append(value)
        elif isinstance(value, list):
            return None
        i = end
    if not candidates or any(c != candidates[0] for c in candidates[1:]):
        return None
    return candidates[0]
