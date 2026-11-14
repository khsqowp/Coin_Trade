"""Dense, deterministic feature signal probe restricted to dev symbols."""
import hashlib
import json
import math
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .collector import DB_PATH
from .features import FeatureStream, build_features
from .indicators import atr as wilder_atr
from .p3a import TIMEFRAMES, WIDTH, _PrefixDigester, _frame, _prefix
from .schema import HORIZON
from .splits import symbol_split
from .stats import wilson
from .store import connect_trials, record_trial

VERSION = "p4b-market-context-double-holdout-v4"
THRESHOLDS = (0.05, 0.10, 0.15, 0.20)
LABELS = {"down": 0, "up": 1}


def _fingerprint(db):
    dev = _dev_aggregates(db)
    db_path = db.execute("PRAGMA database_list").fetchone()[2]
    stat = Path(db_path).stat()
    source = json.dumps({"dev": dev, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}, separators=(",", ":"))
    return hashlib.sha256(f"{VERSION}:{source}".encode()).hexdigest(), dev


def _dev_aggregates(db):
    """Return only stable coverage metadata for dev symbols."""
    rows=[list(r) for r in db.execute("SELECT symbol,COUNT(*),MIN(t_open_ms),MAX(t_open_ms) FROM candles GROUP BY symbol ORDER BY symbol")]
    return [r for r in rows if symbol_split(r[0])=="dev"]


def _legacy_fingerprint(db):
    """Reconstruct the immediately preceding P4 cache key for safe reuse."""
    db_path=db.execute("PRAGMA database_list").fetchone()[2]; stat=Path(db_path).stat()
    source=json.dumps({"dev":_dev_aggregates(db),"size":stat.st_size,"mtime_ns":stat.st_mtime_ns},separators=(",",":"))
    return hashlib.sha256(f"p4-signal-ceiling-v5:{source}".encode()).hexdigest()


def _feature_row(x, nearest=None):
    """Flatten one causal feature snapshot into finite numeric columns."""
    p, atr = float(x["anchor_price"]), max(float(x["atr14"] or 0), 1e-12)
    i, out = x["indicators"], {}
    for k in ("rsi14", "adx14", "plus_di14", "minus_di14"):
        out[k] = float(i[k] or 0)
    out["di_diff"] = out["plus_di14"] - out["minus_di14"]
    out["atr_pct"] = atr / max(abs(p), 1e-12)
    for k in ("ema12", "ema26", "sma20", "vwap_utc_day"):
        out[f"dist_{k}_atr"] = (p - float(i[k] or p)) / atr
    for k in ("macd", "macd_signal", "macd_hist"):
        out[f"{k}_atr"] = float(i[k] or 0) / atr
    mid, upper, lower = (float(i[k] or p) for k in ("bollinger_mid", "bollinger_upper", "bollinger_lower"))
    out["bollinger_pct_b"] = (p - lower) / max(upper - lower, 1e-12)
    vp = i.get("volume_profile") or {}
    for k in ("poc", "vah", "val"):
        out[f"dist_{k}_atr"] = (p - float(vp.get(k) or p)) / atr
    levels = x.get("levels", {}).get("support_resistance", [])
    if nearest is None:
        below = [float(z["high"]) for z in levels if float(z["high"]) <= p]
        above = [float(z["low"]) for z in levels if float(z["low"]) >= p]
        distances = (p - max(below) if below else 0.0, min(above) - p if above else 0.0)
    else:
        distances = nearest
    out["support_dist_atr"] = distances[0] / atr
    out["resistance_dist_atr"] = distances[1] / atr
    st = x.get("structure") or {}
    for label in ("HH", "HL", "LH", "LL"):
        out[f"structure_{label}"] = float(st.get("label") == label)
    for event in ("BOS", "CHoCH"):
        out[f"event_{event}"] = float(st.get("event") == event)
    for k, v in (x.get("patterns") or {}).items():
        out[f"pattern_{k}"] = float(bool(v))
    for k, v in (x.get("levels", {}).get("fibonacci") or {}).items():
        if isinstance(v, (float, int)):
            out[f"fib_{k}_dist_atr"] = (p - float(v)) / atr
    fib = x.get("levels", {}).get("fibonacci") or {}
    out["fib_available"] = float(bool(fib))
    for key in ("0.236", "0.382", "0.5", "0.618", "0.786", "extension_1.272", "extension_1.618"):
        out.setdefault(f"fib_{key}_dist_atr", 0.0)
    swings = x.get("levels", {}).get("swing_counts", {})
    for k in ("high", "low"):
        out[f"swing_{k}_count"] = float(swings.get(k, 0))
    return {k: float(v) if math.isfinite(float(v)) else 0.0 for k, v in out.items()}


def _context_series(frame, stride=20):
    """Build sparse causal context snapshots at the regular probe grid."""
    close = frame.c.to_numpy(float); high = frame.h.to_numpy(float); low = frame.l.to_numpy(float)
    volume = frame.v.to_numpy(float); times = frame.t_open_ms.to_numpy(np.int64)
    prev = np.r_[close[0], close[:-1]]
    tr = np.maximum(high - low, np.maximum(abs(high - prev), abs(low - prev)))
    atr = wilder_atr(high,low,close)
    med_atr = _trailing_median(atr,100,5); med_vol = _trailing_median(volume,50,5)
    mad_vol = _trailing_median(abs(volume-med_vol),50)
    dates=times//86_400_000
    opens = frame.o.to_numpy(float)
    daily_open,previous_high,previous_low=_group_context(dates,opens,high,low)
    week_ids=dates-((dates+3)%7); weekly_open=_first_by_group(week_ids,opens)
    sample=np.arange(14,len(frame),stride,dtype=int)
    returns={lag: np.r_[np.zeros(min(lag,len(close))),
        (close[lag:]-close[:-lag])/np.maximum(atr[lag:],1e-12)] for lag in (1,5,20)}
    return {"times":times[sample],"close":close[sample],"atr":atr[sample],
            "ret_1":returns[1][sample],"ret_5":returns[5][sample],"ret_20":returns[20][sample],
            "atr_vs_100":(atr/np.maximum(med_atr,1e-12))[sample],
            "vol_z":((volume-med_vol)/np.maximum(1.4826*mad_vol,1e-12))[sample],
            "daily_open":daily_open[sample],"weekly_open":weekly_open[sample],
            "prev_high":previous_high[sample],"prev_low":previous_low[sample]}


def _trailing_median(values,window,min_periods=5):
    """Calculate a causal rolling median using a compiled trailing filter."""
    from scipy.ndimage import rank_filter
    values=np.asarray(values,dtype=float); origin=(window-1)//2
    clean=np.where(np.isfinite(values),values,np.inf)
    upper=rank_filter(clean,rank=window//2,size=window,mode="nearest",origin=origin)
    if window%2: result=upper
    else:
        lower=rank_filter(clean,rank=window//2-1,size=window,mode="nearest",origin=origin)
        result=(upper+lower)/2
    missing=np.flatnonzero(~np.isfinite(values)); limit=max(window-1,int(missing[-1])+window if len(missing) else 0)
    for i in range(min(len(values),limit)):
        start=max(0,i-window+1); valid=values[start:i+1]; valid=valid[np.isfinite(valid)]
        if len(valid)<min_periods: result[i]=np.nan
        elif i+1<window or not np.isfinite(values[start:i+1]).all(): result[i]=np.median(valid)
    return result


def _first_by_group(keys,values):
    """Broadcast the first value for each already ordered integer group."""
    starts=np.r_[True,keys[1:]!=keys[:-1]]
    return values[np.maximum.accumulate(np.where(starts,np.arange(len(keys)),0))]


def _group_context(days,opens,high,low):
    """Return daily opens and previous observed-day extrema without lookahead."""
    starts=np.r_[0,np.flatnonzero(days[1:]!=days[:-1])+1]
    daily_high=np.maximum.reduceat(high,starts); daily_low=np.minimum.reduceat(low,starts)
    previous_high=np.r_[np.nan,daily_high[:-1]]; previous_low=np.r_[np.nan,daily_low[:-1]]
    groups=np.cumsum(np.r_[0,(days[1:]!=days[:-1]).astype(int)])
    return opens[starts][groups],previous_high[groups],previous_low[groups]


def _market_stats(series,symbols,width):
    """Aggregate sampled dev returns once per timestamp for fast causal lookup."""
    groups={}
    for name in symbols:
        data=series.get(name)
        if data is None: continue
        for t,value in zip(data["times"],data["ret_5"]): groups.setdefault(int(t+width),[]).append(float(value))
    return {t:(float(np.mean(np.asarray(v)>0)),float(np.median(v))) for t,v in groups.items()}


def _context_at(symbol, pos, series, market_stats, width=60_000, stride=20):
    """Return strictly historical cross-sectional, calendar, and volatility features."""
    own = series[symbol]; own_idx=max(0,(pos-14)//stride); t=int(own["times"][own_idx]+width)
    c=float(own["close"][own_idx]); atr=max(float(own["atr"][own_idx]),1e-12); result={}
    def past_return(name, lag):
        data = series.get(name)
        if data is None: return 0.0
        idx = int(np.searchsorted(data["times"], t, side="left") - 1)
        if idx < 0: return 0.0
        return float(data[f"ret_{lag}"][idx])
    for asset in ("BTCUSDT", "ETHUSDT"):
        for lag in (1, 5, 20): result[f"{asset.lower()}_ret_{lag}_atr"] = past_return(asset, lag)
    own_ret=float(own["ret_5"][own_idx])
    breadth,median=market_stats.get(t,(.5,0.0))
    result["breadth_up_5"] = breadth
    result["market_median_ret_5_atr"] = median
    result["relative_strength_5_atr"] = own_ret-result["market_median_ret_5_atr"]
    stamp = pd.Timestamp(t, unit="ms", tz="UTC")
    result["utc_hour_sin"] = math.sin(2*math.pi*stamp.hour/24); result["utc_hour_cos"] = math.cos(2*math.pi*stamp.hour/24)
    result["utc_weekday_sin"] = math.sin(2*math.pi*stamp.day_of_week/7); result["utc_weekday_cos"] = math.cos(2*math.pi*stamp.day_of_week/7)
    result["atr_vs_100bar_median"] = float(own["atr_vs_100"][own_idx])
    result["volume_zscore_50"] = float(own["vol_z"][own_idx])
    result["dist_daily_open_atr"] = (c-own["daily_open"][own_idx])/atr
    result["dist_weekly_open_atr"] = (c-own["weekly_open"][own_idx])/atr
    result["dist_prev_day_high_atr"] = (c-own["prev_high"][own_idx])/atr if math.isfinite(own["prev_high"][own_idx]) else 0.0
    result["dist_prev_day_low_atr"] = (c-own["prev_low"][own_idx])/atr if math.isfinite(own["prev_low"][own_idx]) else 0.0
    return {k:float(v) if math.isfinite(float(v)) else 0.0 for k,v in result.items()}


def _feature_for_anchor(frame, pos, tf, digester, stream=None):
    """Build one snapshot from the strict prefix ending at its anchor candle."""
    prefix = frame.iloc[:pos + 1] if stream is not None else _prefix(frame, pos)
    return build_features(prefix, tf, _digest_override=digester.digest(prefix), _stream=stream, _index=pos)


def _make_dataset(db_path, cache_path, fingerprint):
    """Build all horizon-spaced dev anchors, targets, and causal feature rows."""
    cache = sqlite3.connect(cache_path)
    cache.execute("CREATE TABLE IF NOT EXISTS rows(fingerprint TEXT,tf TEXT,symbol TEXT,anchor INTEGER,label TEXT,ret_atr REAL,exp_label INTEGER,cont_label INTEGER,cont_eligible INTEGER,features TEXT,PRIMARY KEY(fingerprint,tf,symbol,anchor))")
    cache.execute("CREATE TABLE IF NOT EXISTS cells(fingerprint TEXT,tf TEXT,symbol TEXT,PRIMARY KEY(fingerprint,tf,symbol))")
    source = sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True)
    count = 0
    try:
        symbols = [r[0] for r in source.execute("SELECT DISTINCT symbol FROM candles ORDER BY symbol") if symbol_split(r[0]) == "dev"]
        legacy_fp=_legacy_fingerprint(source)
        legacy_path=_find_legacy_cache(Path(cache_path).parent,symbols,legacy_fp)
        legacy=sqlite3.connect(Path(legacy_path).resolve().as_uri()+"?mode=ro",uri=True) if legacy_path else None
        context_names = sorted(set(symbols + ["BTCUSDT", "ETHUSDT"]))
        for tf in TIMEFRAMES:
            complete=cache.execute("SELECT COUNT(*) FROM cells WHERE fingerprint=? AND tf=?",(fingerprint,tf)).fetchone()[0]
            if complete==len(symbols): continue
            stride = HORIZON[tf] // (WIDTH[tf] // 60_000)
            series = {}
            for name in context_names:
                context_frame = _frame(source, name, tf)
                if len(context_frame): series[name] = _context_series(context_frame, stride)
            market_stats=_market_stats(series,symbols,WIDTH[tf])
            for symbol in symbols:
                done = cache.execute("SELECT 1 FROM cells WHERE fingerprint=? AND tf=? AND symbol=?", (fingerprint, tf, symbol)).fetchone()
                if done: continue
                frame = _frame(source, symbol, tf)
                if legacy: count += _augment_cell(cache,legacy,legacy_fp,fingerprint,symbol,tf,frame,series,market_stats,symbols,stride)
                else: count += _build_cell(cache,fingerprint,symbol,tf,frame,series,market_stats,symbols)
        return cache.execute("SELECT COUNT(*) FROM rows WHERE fingerprint=?", (fingerprint,)).fetchone()[0]
    finally:
        if legacy: legacy.close()
        source.close(); cache.close()


def _find_legacy_cache(root,symbols,fingerprint):
    """Find the exact prior-P4 cache matching current source metadata."""
    expected=len(symbols)*len(TIMEFRAMES)
    for path in root.glob("features_*.sqlite"):
        if path.stat().st_size < 1_000_000: continue
        db=sqlite3.connect(path.resolve().as_uri()+"?mode=ro",uri=True)
        try:
            columns={r[1] for r in db.execute("PRAGMA table_info(rows)")}
            if columns!={"fingerprint","tf","symbol","anchor","label","ret_atr","features"}: continue
            row=db.execute("SELECT COUNT(*) FROM cells WHERE fingerprint=?",(fingerprint,)).fetchone()
            if row and row[0]==expected: return path
        finally: db.close()
    return None


def _augment_cell(cache,legacy,legacy_fp,fingerprint,symbol,tf,frame,series,market_stats,symbols,stride):
    """Add new causal market features and targets to cached P4 snapshots."""
    rows=legacy.execute("SELECT anchor,label,ret_atr,features FROM rows WHERE fingerprint=? AND tf=? AND symbol=? ORDER BY anchor",(legacy_fp,tf,symbol)).fetchall()
    if not rows: return _build_cell(cache,fingerprint,symbol,tf,frame,series,market_stats,symbols)
    anchors=frame.t_open_ms.to_numpy(np.int64)+WIDTH[tf]; closes=frame.c.to_numpy(float)
    atrs=wilder_atr(frame.h,frame.l,frame.c); pending=[]
    for anchor,label,ret_atr,encoded in rows:
        pos=int(np.searchsorted(anchors,int(anchor)))
        if pos>=len(frame) or anchors[pos]!=anchor or pos+stride>=len(frame): continue
        atr=max(float(atrs[pos]),1e-12); previous=closes[pos]-closes[max(0,pos-5)]; eligible=abs(previous)>atr
        features=json.loads(encoded); features.update(_context_at(symbol,pos,series,market_stats,WIDTH[tf],stride))
        pending.append((fingerprint,tf,symbol,int(anchor),label,float(ret_atr),int(abs(ret_atr)>math.sqrt(stride)),int(eligible and previous*(ret_atr*atr)>0),int(eligible),json.dumps(features,separators=(",",":"))))
        if len(pending)>=500: cache.executemany("INSERT OR REPLACE INTO rows VALUES(?,?,?,?,?,?,?,?,?,?)",pending); cache.commit(); pending.clear()
    if pending: cache.executemany("INSERT OR REPLACE INTO rows VALUES(?,?,?,?,?,?,?,?,?,?)",pending); cache.commit()
    cache.execute("INSERT OR REPLACE INTO cells VALUES(?,?,?)",(fingerprint,tf,symbol)); cache.commit()
    return len(rows)


def _build_cell(cache, fingerprint, symbol, tf, frame, series, market_stats, symbols):
    """Append a symbol/timeframe cell, including causal labels and context."""
    stride = HORIZON[tf] // (WIDTH[tf] // 60_000); first = 14
    if len(frame) <= first + stride: return 0
    digester = _PrefixDigester(frame); stream = FeatureStream(frame); pending = []; count = 0
    for pos in range(first, len(frame)-stride, stride):
        ft = _feature_for_anchor(frame, pos, tf, digester, stream)
        price = float(ft["anchor_price"]); atr = max(float(ft["atr14"] or 0),1e-12)
        move = float(frame.c.iloc[pos+stride])-price; scale = math.sqrt(stride)
        label = "flat" if abs(move)<=.25*atr*scale else "up" if move>0 else "down"
        previous = price-float(frame.c.iloc[max(0,pos-5)])
        eligible = abs(previous)>atr
        continuation = int(eligible and move*previous>0)
        features = _feature_row(ft,stream.nearest_levels(price))
        features.update(_context_at(symbol,pos,series,market_stats,WIDTH[tf],stride))
        pending.append((fingerprint,tf,symbol,int(frame.t_open_ms.iloc[pos]+WIDTH[tf]),label,move/atr,
                        int(abs(move)>atr*scale),continuation,int(eligible),json.dumps(features,separators=(",",":"))))
        if len(pending)>=500:
            cache.executemany("INSERT OR REPLACE INTO rows VALUES(?,?,?,?,?,?,?,?,?,?)",pending); cache.commit(); count+=len(pending); pending.clear()
    if pending:
        cache.executemany("INSERT OR REPLACE INTO rows VALUES(?,?,?,?,?,?,?,?,?,?)",pending); cache.commit(); count+=len(pending)
    cache.execute("INSERT OR IGNORE INTO cells VALUES(?,?,?)",(fingerprint,tf,symbol)); cache.commit()
    return count


def _wilson_acc(y, pred):
    hits = int(np.sum(np.asarray(y) == np.asarray(pred)))
    return {"n": len(y), "accuracy": hits / len(y) if len(y) else None, "wilson95": wilson(hits, len(y))}


def _metric_row(y, p):
    from sklearn.metrics import roc_auc_score
    pred = (p >= .5).astype(int)
    result = {"n": len(y), "accuracy": _wilson_acc(y, pred), "roc_auc": float(roc_auc_score(y, p)) if len(set(y)) > 1 else None,
              "always_up": _wilson_acc(y, np.ones(len(y), dtype=int)), "always_down": _wilson_acc(y, np.zeros(len(y), dtype=int))}
    result["calibration_deciles"] = _calibration(y, p)
    result["high_confidence"] = {str(t): _coverage(y, p, t) for t in THRESHOLDS}
    return result


def _calibration(y, p):
    bins = []
    for d in range(10):
        mask = (p >= d / 10) & (p < (d + 1) / 10 if d < 9 else p <= 1)
        if mask.any(): bins.append({"decile": d + 1, "n": int(mask.sum()), "mean_probability": float(p[mask].mean()), "realized_up": float(np.asarray(y)[mask].mean())})
    return bins


def _coverage(y, p, threshold):
    mask = np.abs(p - .5) > threshold
    result = _wilson_acc(np.asarray(y)[mask], (p[mask] >= .5).astype(int)) if mask.any() else {"n": 0, "accuracy": None, "wilson95": None}
    result["coverage"] = float(mask.mean()) if len(mask) else 0.0
    return result


def _fit_models(x_train, y_train, x_test, seed):
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    models = {"logistic_l2": make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(C=1.0, max_iter=1000, random_state=seed)),
              "hist_gradient_boosting": make_pipeline(SimpleImputer(strategy="median"), HistGradientBoostingClassifier(max_iter=60, learning_rate=.08, max_leaf_nodes=15, l2_regularization=1.0, random_state=seed))}
    return {name: (model.fit(x_train, y_train), model.predict_proba(x_test)[:, 1]) for name, model in models.items()}


def _rows(cache_path, fingerprint, tf, target="up_down"):
    """Load one timeframe's selected target and its finite numeric features."""
    db = sqlite3.connect(cache_path)
    try:
        cursor = db.execute("SELECT symbol,anchor,label,ret_atr,exp_label,cont_label,cont_eligible,features FROM rows WHERE fingerprint=? AND tf=? ORDER BY anchor,symbol", (fingerprint, tf))
        symbols, times, labels, vectors, keys = [], [], [], [], None
        while batch := cursor.fetchmany(5000):
            for symbol, anchor, label, _, expansion, continuation, eligible, encoded in batch:
                if target == "up_down":
                    if label not in LABELS: continue
                    y = LABELS[label]
                elif target == "expansion": y = int(expansion)
                else:
                    if not eligible: continue
                    y = int(continuation)
                feat = json.loads(encoded)
                if keys is None:
                    keys = sorted(feat)
                symbols.append(symbol); times.append(anchor); labels.append(y)
                vectors.append([feat.get(k, 0.0) for k in keys])
    finally: db.close()
    if not labels: return [], np.empty((0, 0)), np.array([], dtype=int)
    meta = (np.array(symbols), np.array(times, dtype=np.int64), [], keys)
    return meta, np.asarray(vectors, dtype=float), np.asarray(labels, dtype=int)


def _eval_split(meta, x, y, mode, seed, timeframe="1m", importance=False):
    symbols, times = meta[:2]
    cut = int(np.quantile(times, .70)); gap = int(meta[4]) * 60_000
    early, late = times < cut, times >= cut + gap
    if mode == "temporal": train, test = early, late
    else:
        uniques = sorted(set(symbols)); boundary = max(1, int(len(uniques)*.70)); held = set(uniques[boundary:])
        train = early & np.array([s not in held for s in symbols])
        test = late & np.array([s in held for s in symbols])
    if train.sum() == 0 or test.sum() == 0: return {"n_train": int(train.sum()), "n_test": int(test.sum()), "models": {}}
    fitted = _fit_models(x[train], y[train], x[test], seed)
    result = {"n_train": int(train.sum()), "n_test": int(test.sum()), "models": {}}
    for name, (model, prob) in fitted.items():
        stats = _metric_row(y[test], prob)
        stats["majority_baseline"] = _wilson_acc(y[test], np.full(int(test.sum()), int(np.mean(y[test]) >= .5)))
        rng = np.random.default_rng(seed)
        null_acc = {name: [] for name in fitted}; null_auc = {name: [] for name in fitted}
        for repetition in range(10):
            shuffled = rng.permutation(y[train])
            null = _fit_models(x[train], shuffled, x[test], seed + repetition + 1)
            for null_name, (_, pred_prob) in null.items():
                null_acc[null_name].append(float(np.mean((pred_prob >= .5) == y[test])))
                from sklearn.metrics import roc_auc_score
                null_auc[null_name].append(float(roc_auc_score(y[test], pred_prob)))
        stats["permutation_label_control"] = {"n_permutations": 10,
            "accuracy_min": min(null_acc[name]), "accuracy_median": float(np.median(null_acc[name])), "accuracy_max": max(null_acc[name]),
            "roc_auc_min": min(null_auc[name]), "roc_auc_median": float(np.median(null_auc[name])), "roc_auc_max": max(null_auc[name])}
        if importance and name == "hist_gradient_boosting":
            stats["permutation_importance_top10"] = _top_importance(model, x[test], y[test], meta[3], seed)
        result["models"][name] = stats
    result["test_label_balance"] = {str(k): float(np.mean(y[test] == k)) for k in sorted(set(y[test]))}
    return result


def _top_importance(model, x, y, keys, seed):
    """Compute deterministic held-out permutation importance on a bounded sample."""
    from sklearn.inspection import permutation_importance
    idx = np.arange(len(y))
    if len(idx) > 20_000: idx = np.random.default_rng(seed).choice(idx, 20_000, replace=False)
    result = permutation_importance(model, x[idx], y[idx], scoring="roc_auc", n_repeats=3, random_state=seed, n_jobs=1)
    order = np.argsort(result.importances_mean)[::-1][:10]
    return [{"feature": keys[i], "importance_mean": float(result.importances_mean[i]),
             "importance_std": float(result.importances_std[i])} for i in order]


def _markdown(report):
    lines = ["# Signal ceiling probe v2", "", f"Fingerprint: `{report['fingerprint']}`", "", "Numbers and permutation-label controls only; no verdict.", ""]
    for tf, targets in report["timeframes"].items():
        lines += [f"## {tf}", ""]
        for target, folds in targets.items():
            lines += [f"### {target}", "", "| Split | Model | n train/test | Test class balance | Accuracy [Wilson 95% CI] | AUC | Always up | Always down | Majority baseline | Null accuracy median [min,max] | Null AUC median [min,max] |", "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|"]
            for fold, result in folds.items():
                for name, m in result.get("models", {}).items():
                    ci=m["accuracy"]["wilson95"]; acc=m["accuracy"]["accuracy"]; null=m["permutation_label_control"]
                    base=m["majority_baseline"]["accuracy"]
                    balance=",".join(f"{k}:{v:.3f}" for k,v in result.get("test_label_balance",{}).items())
                    lines.append(f"| {fold} | {name} | {result['n_train']}/{result['n_test']} | {balance} | {acc:.4f} [{ci['low']:.4f},{ci['high']:.4f}] | {m['roc_auc']:.4f} | {m['always_up']['accuracy']:.4f} | {m['always_down']['accuracy']:.4f} | {base:.4f} | {null['accuracy_median']:.4f} [{null['accuracy_min']:.4f},{null['accuracy_max']:.4f}] | {null['roc_auc_median']:.4f} [{null['roc_auc_min']:.4f},{null['roc_auc_max']:.4f}] |")
            lines.append("")
            lines.extend(_detail_tables(folds, target == "up_down"))
            for fold, result in folds.items():
                for name, m in result.get("models", {}).items():
                    if "permutation_importance_top10" not in m: continue
                    lines += [f"Top HGB permutation importance, {fold}:", "", "| Feature | Mean AUC decrease | SD |", "|---|---:|---:|"]
                    lines.extend(f"| {q['feature']} | {q['importance_mean']:.6f} | {q['importance_std']:.6f} |" for q in m["permutation_importance_top10"])
                    lines.append("")
    return "\n".join(lines)


def _detail_tables(folds, calibration=False):
    """Render confidence coverage and optional calibration details."""
    lines=["High-confidence subsets (coverage / n / accuracy with Wilson 95% CI):", "",
           "| Split | Model | Threshold | Coverage | n | Accuracy [95% CI] |", "|---|---|---:|---:|---:|---:|"]
    for fold,result in folds.items():
        for name,m in result.get("models",{}).items():
            for threshold,subset in m["high_confidence"].items():
                ci=subset["wilson95"]; acc="n/a" if ci is None else f"{subset['accuracy']:.4f} [{ci['low']:.4f},{ci['high']:.4f}]"
                lines.append(f"| {fold} | {name} | {threshold} | {subset['coverage']:.4f} | {subset['n']} | {acc} |")
    if not calibration: return lines+[""]
    lines += ["", "Calibration deciles (mean probability / realized class-1 rate):", "",
              "| Split | Model | Decile | n | Mean probability | Realized up |", "|---|---|---:|---:|---:|---:|"]
    for fold,result in folds.items():
        for name,m in result.get("models",{}).items():
            for row in m["calibration_deciles"]:
                lines.append(f"| {fold} | {name} | {row['decile']} | {row['n']} | {row['mean_probability']:.4f} | {row['realized_up']:.4f} |")
    return lines+[""]


def run_probe(data_db=DB_PATH, output_dir=None, trials_db=None, seed=1):
    """Build cached dev data, evaluate v2 labels and write reports."""
    import sklearn  # fail before a costly full-span feature build if dependencies are absent
    started = time.monotonic(); root = Path(output_dir or Path(__file__).parent / "data" / "probe"); root.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(Path(data_db).resolve().as_uri() + "?mode=ro", uri=True)
    try: fingerprint, _ = _fingerprint(db)
    finally: db.close()
    cache = root / f"features_{fingerprint}.sqlite"
    n_rows = _make_dataset(data_db, cache, fingerprint)
    report = {"fingerprint": fingerprint, "dataset_rows": n_rows, "seed": seed, "timeframes": {}, "runtime_seconds": None}
    for tf in TIMEFRAMES:
        report["timeframes"][tf] = {}
        for target in ("up_down", "expansion", "continuation"):
            meta,x,y=_rows(cache,fingerprint,tf,target)
            if meta:
                meta=(*meta,HORIZON[tf]//(WIDTH[tf]//60_000))
                report["timeframes"][tf][target]={
                    "temporal":_eval_split(meta,x,y,"temporal",seed,tf),
                    "double_holdout":_eval_split(meta,x,y,"double_holdout",seed,tf,target=="up_down")}
            else:
                report["timeframes"][tf][target]={"temporal":{"n_train":0,"n_test":0,"models":{}},"double_holdout":{"n_train":0,"n_test":0,"models":{}}}
    report["runtime_seconds"] = time.monotonic() - started
    report["created_at"] = datetime.now(timezone.utc).isoformat()
    json_path, md_path = root / f"report_{fingerprint}.json", root / f"report_{fingerprint}.md"
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False)); md_path.write_text(_markdown(report) + "\n")
    trials = connect_trials(trials_db)
    try: record_trial(trials, report["created_at"], "probe", VERSION, VERSION, "dev", "signal ceiling probe v2 (market context, double holdout)", n_rows, fingerprint)
    finally: trials.close()
    return {"fingerprint": fingerprint, "dataset_rows": n_rows, "report_json": str(json_path), "report_md": str(md_path), "runtime_seconds": report["runtime_seconds"]}
