"""Transparent accuracy, coverage, confidence and clustered summaries."""
import math
import pandas as pd
from .schema import HORIZON


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
    if "status" not in frame:
        return {"n": 0, "accuracy": None, "wilson95": wilson(0, 0), "coverage": 0.0}
    valid = frame[frame.status == "SCORED"]
    n, hits = len(valid), int(valid.m1_hit.sum()) if len(valid) else 0
    return {"n": n, "accuracy": hits / n if n else None, "wilson95": wilson(hits, n),
            "coverage": n / len(frame) if len(frame) else 0}


def _m2_summary(frame):
    """Summarize target-first outcomes over actionable, scored long/short signals."""
    if "status" not in frame:
        return {"n": 0, "target_first_count": 0, "target_first_rate": None,
                "wilson95": wilson(0, 0), "issued_predictions": 0,
                "actionable_issued": 0, "actionable_unscorable": 0,
                "coverage": 0.0, "actionable_signal_rate": 0.0, "exit_reasons": {}}
    issued = frame[frame.side.isin(["long", "short"])] if "side" in frame else frame.iloc[0:0]
    actionable = issued[issued.status == "SCORED"]
    n = len(actionable)
    hits = int(actionable.m2_hit.sum()) if n else 0
    reasons = actionable.m2_exit_reason.value_counts().to_dict() if n else {}
    return {"n": n, "target_first_count": hits,
            "target_first_rate": hits / n if n else None,
            "wilson95": wilson(hits, n),
            "issued_predictions": len(frame),
            "actionable_issued": len(issued),
            "actionable_unscorable": len(issued) - n,
            "coverage": n / len(issued) if len(issued) else 0.0,
            "actionable_signal_rate": len(issued) / len(frame) if len(frame) else 0.0,
            "exit_reasons": {str(key): int(value) for key, value in reasons.items()}}


def _nonoverlap_m2(frame):
    """Summarize M2 on a greedy, per-symbol non-overlapping forecast sample.

    Overlapping anchors at the same timestamp are resolved by retaining the
    longest declared horizon. Subsequent anchors for that symbol are retained
    only at or after the retained interval's end. This does not make signals
    across different symbols statistically independent; day clusters remain
    visible for that reason.
    """
    required = {"status", "side", "m2_hit", "symbol", "timeframe", "anchor_time"}
    empty = {"n": 0, "target_first_count": 0, "target_first_rate": None,
             "wilson95": wilson(0, 0), "actionable_issued": 0,
             "scorable_candidates": 0, "excluded_overlapping": 0,
             "coverage": 0.0, "per_symbol": {}, "anchor_day_clusters": {},
             "selection": "Per symbol; earliest anchor first; longest horizon wins same-time ties."}
    if not required.issubset(frame.columns):
        return empty

    issued = frame[frame.side.isin(["long", "short"])]
    candidates = issued[issued.status == "SCORED"].copy()
    candidates = candidates[candidates.timeframe.isin(HORIZON)]
    candidates = candidates[candidates.symbol.notna() & candidates.anchor_time.notna()]
    if candidates.empty:
        return {**empty, "actionable_issued": len(issued)}

    def to_ms(value):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return int(value)
        stamp = pd.Timestamp(value)
        stamp = stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")
        return int(stamp.timestamp() * 1000)

    try:
        candidates["_anchor_ms"] = candidates.anchor_time.map(to_ms)
    except (TypeError, ValueError, OverflowError):
        candidates = candidates.iloc[0:0].copy()
    candidates["_horizon_ms"] = candidates.timeframe.map(HORIZON).astype("int64") * 60_000
    # Stable sorting makes ties deterministic; longest horizon is selected first.
    candidates = candidates.sort_values(
        ["symbol", "_anchor_ms", "_horizon_ms", "timeframe"],
        ascending=[True, True, False, True], kind="mergesort")
    selected = []
    for _, group in candidates.groupby("symbol", sort=True):
        next_available = None
        for index, row in group.iterrows():
            anchor = int(row["_anchor_ms"])
            if next_available is None or anchor >= next_available:
                selected.append(index)
                next_available = anchor + int(row["_horizon_ms"])
    sample = candidates.loc[selected].copy() if selected else candidates.iloc[0:0].copy()
    n = len(sample)
    hits = int(sample.m2_hit.astype(bool).sum()) if n else 0
    by_symbol = {}
    for symbol, group in sample.groupby("symbol", sort=True):
        count = len(group)
        wins = int(group.m2_hit.astype(bool).sum())
        by_symbol[str(symbol)] = {"n": count, "target_first_count": wins,
                                  "target_first_rate": wins / count,
                                  "wilson95": wilson(wins, count)}
    day_clusters = {}
    if n:
        sample["_anchor_day"] = pd.to_datetime(sample["_anchor_ms"], unit="ms", utc=True).dt.date.astype(str)
        for day, group in sample.groupby("_anchor_day", sort=True):
            count = len(group)
            wins = int(group.m2_hit.astype(bool).sum())
            day_clusters[str(day)] = {"n": count, "target_first_count": wins,
                                      "target_first_rate": wins / count}
    return {"n": n, "target_first_count": hits,
            "target_first_rate": hits / n if n else None,
            "wilson95": wilson(hits, n), "actionable_issued": len(issued),
            "scorable_candidates": len(candidates),
            "excluded_overlapping": len(candidates) - n,
            "coverage": n / len(issued) if len(issued) else 0.0,
            "per_symbol": by_symbol, "anchor_day_clusters": day_clusters,
            "selection": "Per symbol; earliest anchor first; longest horizon wins same-time ties."}


def report(scores, thresholds=(.5, .6, .7, .8, .9)):
    """Build M1/M2, confidence, symbol/timeframe, day-cluster and baseline tables."""
    frame = pd.DataFrame(scores)
    result = {"overall": _summary(frame), "m2_overall": _m2_summary(frame),
              "m2_nonoverlap": _nonoverlap_m2(frame),
              "m2_per_symbol": {}, "m2_per_timeframe": {},
              "m4": {}, "per_symbol": {}, "per_timeframe": {},
              "clustered_by_anchor_day": {}, "baselines": {}}
    for threshold in thresholds:
        chosen = frame[frame.confidence >= threshold] if len(frame) else frame
        item = _summary(chosen)
        item["coverage"] = len(chosen) / len(frame) if len(frame) else 0
        result["m4"][str(threshold)] = item
    for key, target in (("symbol", "per_symbol"), ("timeframe", "per_timeframe")):
        if key in frame:
            result[target] = {str(name): _summary(group) for name, group in frame.groupby(key)}
    for key, target in (("symbol", "m2_per_symbol"), ("timeframe", "m2_per_timeframe")):
        if key in frame:
            result[target] = {str(name): _m2_summary(group) for name, group in frame.groupby(key)}
    if "anchor_time" in frame:
        frame["anchor_day"] = pd.to_datetime(frame.anchor_time, utc=True).dt.date.astype(str)
        result["clustered_by_anchor_day"] = {day: _summary(group) for day, group in frame.groupby("anchor_day")}
    if "model" in frame:
        result["baselines"] = {str(name): _summary(group) for name, group in frame.groupby("model")
                               if str(name).startswith("baseline_")}
    result["effective_sample_warning"] = "Same-time anchors across symbols are correlated; day clusters are shown separately."
    return result
