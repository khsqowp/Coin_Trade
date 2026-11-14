"""Transparent accuracy, coverage, confidence and clustered summaries."""
import math
import pandas as pd


def wilson(successes, total, z=1.959963984540054):
    """Return Wilson score interval for a binomial proportion."""
    if total <= 0:
        return {"low": None, "high": None}
    p = successes / total
    den = 1 + z * z / total
    center = (p + z * z / (2 * total)) / den
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / den
    return {"low": center - half, "high": center + half}


def _summary(frame):
    """Summarize valid M1 outcomes with Wilson uncertainty."""
    valid = frame[frame.status == "SCORED"]
    n, hits = len(valid), int(valid.m1_hit.sum()) if len(valid) else 0
    return {"n": n, "accuracy": hits / n if n else None, "wilson95": wilson(hits, n),
            "coverage": n / len(frame) if len(frame) else 0}


def report(scores, thresholds=(.5, .6, .7, .8, .9)):
    """Build overall, M4, symbol/timeframe, day-cluster and baseline tables."""
    frame = pd.DataFrame(scores)
    result = {"overall": _summary(frame), "m4": {}, "per_symbol": {}, "per_timeframe": {},
              "clustered_by_anchor_day": {}, "baselines": {}}
    for threshold in thresholds:
        chosen = frame[frame.confidence >= threshold] if len(frame) else frame
        item = _summary(chosen)
        item["coverage"] = len(chosen) / len(frame) if len(frame) else 0
        result["m4"][str(threshold)] = item
    for key, target in (("symbol", "per_symbol"), ("timeframe", "per_timeframe")):
        if key in frame:
            result[target] = {str(name): _summary(group) for name, group in frame.groupby(key)}
    if "anchor_time" in frame:
        frame["anchor_day"] = pd.to_datetime(frame.anchor_time, utc=True).dt.date.astype(str)
        result["clustered_by_anchor_day"] = {day: _summary(group) for day, group in frame.groupby("anchor_day")}
    if "model" in frame:
        result["baselines"] = {str(name): _summary(group) for name, group in frame.groupby("model")
                               if str(name).startswith("baseline_")}
    result["effective_sample_warning"] = "Same-time anchors across symbols are correlated; day clusters are shown separately."
    return result
