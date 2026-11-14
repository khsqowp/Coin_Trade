import json
import numpy as np
import pandas as pd
import pytest
from chart_predictor import cli
from chart_predictor import indicators as I
from chart_predictor.collector import collect_symbol, connect
from chart_predictor.features import build_features
from chart_predictor.resample import resample_frame
from chart_predictor.universe import select_universe


def candles(n=100):
    x = np.arange(n, dtype=float)
    close = 100 + np.sin(x / 4) * 3 + x * .1
    return pd.DataFrame({"t_open_ms": 1_700_000_000_000 + x.astype(int) * 60_000,
        "o": close - .2, "h": close + 1, "l": close - 1, "c": close,
        "v": x + 1, "quote_v": (x + 1) * close, "trades": x.astype(int) + 1})


def test_universe_crypto_filters_and_volume_order():
    info = {"symbols": [
        {"symbol":"BTCUSDT","contractType":"PERPETUAL","quoteAsset":"USDT","status":"TRADING","underlyingType":"COIN"},
        {"symbol":"NVDAUSDT","contractType":"PERPETUAL","quoteAsset":"USDT","status":"TRADING","underlyingType":"EQUITY"},
        {"symbol":"ETHUSDT","contractType":"PERPETUAL","quoteAsset":"USDT","status":"TRADING","underlyingType":"COIN"}]}
    selected = select_universe(info, [{"symbol":"BTCUSDT","quoteVolume":"10"},
        {"symbol":"NVDAUSDT","quoteVolume":"100"},{"symbol":"ETHUSDT","quoteVolume":"20"}], 1)
    assert selected == [{"symbol":"ETHUSDT", "quoteVolume":20.0}]


class Response:
    def __init__(self, status, rows=(), headers=None):
        self.status_code, self.rows, self.headers = status, rows, headers or {}
    def raise_for_status(self):
        if self.status_code >= 400: raise RuntimeError("http error")
    def json(self): return self.rows


class Session:
    def __init__(self, pages): self.pages, self.calls = list(pages), []
    def get(self, url, params, timeout):
        self.calls.append(params)
        return self.pages.pop(0)


def kline(t, close_t): return [t,"1","2",".5","1.5","4",close_t,"6",7,"0","0","0"]


def _stable(value):
    if isinstance(value, np.ndarray): return _stable(value.tolist())
    if isinstance(value, np.generic): return _stable(value.item())
    if isinstance(value, dict): return {key:_stable(item) for key,item in value.items()}
    if isinstance(value, (tuple, list)): return [_stable(item) for item in value]
    if isinstance(value, float) and np.isnan(value): return "NaN"
    return value


def _bytes(value):
    return json.dumps(_stable(value), sort_keys=True, separators=(",", ":")).encode()


def _slice_output(value, stop):
    if isinstance(value, np.ndarray): return value[:stop]
    if isinstance(value, dict): return {key:_slice_output(item,stop) for key,item in value.items()}
    if isinstance(value, tuple): return tuple(_slice_output(item,stop) for item in value)
    if isinstance(value, list): return value[:stop]
    return value


def _assert_array_prefix(function, values, k):
    full, prefix = function(values), function(values[:k])
    if isinstance(full, tuple):
        for series, short in zip(full, prefix): np.testing.assert_equal(series[k-1], short[-1])
    else:
        np.testing.assert_equal(full[k-1], prefix[-1])


def _zone_oracle(swing_high, swing_low):
    prices = sorted(np.r_[swing_high[np.isfinite(swing_high)],
                          swing_low[np.isfinite(swing_low)]].tolist())
    groups = []
    for price in prices:
        if groups and abs(price-np.mean(groups[-1]))/max(abs(price),1e-12) <= .005:
            groups[-1].append(price)
        else: groups.append([price])
    return [{"low":min(g),"high":max(g),"touches":len(g)} for g in groups]


def _line_oracle(sh, sl):
    result = {}
    for name, values in (("resistance",sh),("support",sl)):
        points=[(i,float(x)) for i,x in enumerate(values) if np.isfinite(x)][-3:]
        result[name]=[{"start_index":points[0][0],"end_index":p[0],"start_price":points[0][1],"end_price":p[1]} for p in points[1:]]
    result["channel_candidates"]=[]
    if result["support"] and result["resistance"]:
        result["channel_candidates"]=[{"support":result["support"][-1],"resistance":result["resistance"][-1]}]
    return result


def _fib_oracle(sh, sl):
    pivots=sorted([(i,float(v),"high") for i,v in enumerate(sh) if np.isfinite(v)]+
                  [(i,float(v),"low") for i,v in enumerate(sl) if np.isfinite(v)])
    if len(pivots)<2 or pivots[-1][2]==pivots[-2][2]: return {}
    a,b=pivots[-2][1],pivots[-1][1]; move=b-a
    return {str(r):float(b-move*r) for r in (.236,.382,.5,.618,.786)} | {
        "extension_1.272":float(a+move*1.272),"extension_1.618":float(a+move*1.618)}


def _profile_oracle(close, volume, bins=24):
    hist,edges=np.histogram(close,bins=bins,weights=volume); centers=(edges[:-1]+edges[1:])/2
    poc=int(np.argmax(hist)); left=right=poc; target=hist.sum()*.70; total=hist[poc]
    while total<target and (left>0 or right<len(hist)-1):
        take_left=left>0 and (right==len(hist)-1 or hist[left-1]>=hist[right+1])
        if take_left: left-=1; total+=hist[left]
        else: right+=1; total+=hist[right]
    return {"poc":float(centers[poc]),"vah":float(edges[right+1]),"val":float(edges[left])}


def test_collector_resumes_skips_partial_and_handles_429(tmp_path):
    db = connect(tmp_path / "c.sqlite")
    start = 1_700_000_000_000 // 60_000 * 60_000
    db.execute("INSERT INTO candles VALUES(?,?,?,?,?,?,?,?,?)", ("BTCUSDT", start,1,2,.5,1.5,4,6,7)); db.commit()
    now = int(pd.Timestamp.now(tz="UTC").timestamp() * 1000)
    pages = [Response(429, headers={"Retry-After":"3"}),
             Response(200, [kline(start+60_000, now-1), kline(start+120_000, now+60_000)])]
    session, sleeps = Session(pages), []
    count = collect_symbol("BTCUSDT", start, start+120_000, db=db, session=session, sleep=sleeps.append)
    assert sleeps == [3.0] and count == 1
    assert db.execute("SELECT COUNT(*) FROM candles").fetchone()[0] == 2
    assert collect_symbol("BTCUSDT", start, start+120_000, db=db, session=Session([Response(200, [])]), sleep=sleeps.append) == 0
    assert db.execute("SELECT COUNT(*) FROM candles").fetchone()[0] == 2
    db.close()


def test_collector_slows_when_weight_header_is_high():
    start = 1_700_000_000_000
    now = int(pd.Timestamp.now(tz="UTC").timestamp() * 1000)
    session = Session([Response(200, [kline(start, now-1)],
                                {"X-MBX-USED-WEIGHT-1M":"920"})])
    sleeps = []
    from chart_predictor.collector import _request
    _request(session, {"symbol":"BTCUSDT","interval":"1m"}, sleeps.append)
    assert sleeps == [10]


def test_resample_only_complete_closed_utc_buckets():
    base = 1_700_000_040_000 // 300_000 * 300_000
    frame = pd.DataFrame({"t_open_ms": [base+i*60_000 for i in (0,1,2,4)],
        "o":[1,2,3,4],"h":[2,3,4,5],"l":[0,1,2,3],"c":[1,2,3,4],
        "v":[1]*4,"quote_v":[2]*4,"trades":[1]*4})
    out = resample_frame(frame, "5m")
    assert out.empty
    frame = pd.concat([frame, pd.DataFrame([{"t_open_ms":base+3*60_000,"o":3,"h":4,"l":2,"c":3,"v":1,"quote_v":2,"trades":1}])])
    out = resample_frame(frame, "5m", now_ms=base+5*60_000-1)
    assert out.empty
    out = resample_frame(frame, "5m", now_ms=base+5*60_000)
    assert len(out) == 1 and out.iloc[0].h == 5 and out.iloc[0].v == 5


def test_all_indicator_outputs_are_prefix_invariant():
    df = candles(); o,h,l,c,v = (df[k].to_numpy() for k in ("o","h","l","c","v")); t=df.t_open_ms
    for k in (30,50,75,99):
        cut=lambda values: values[:k]
        arrays=[(lambda x:I.sma(x,10),c),(lambda x:I.ema(x,12),c),(lambda x:I.macd(x),c),
            (lambda x:I.rsi(x),c),(lambda x:I.atr(h[:len(x)],l[:len(x)],x),c),
            (lambda x:I.bollinger(x),c)]
        for function, values in arrays: _assert_array_prefix(function,values,k)
        # Multi-input arrays are checked against the full result at the same confirmation index.
        for function, inputs in ((lambda a,b:I.adx_di(a,b,c[:len(a)]),(h,l)),
            (lambda a,b,d,e:I.vwap(a,b,c[:len(a)],d,t[:len(a)]),(h,l,v,t)),
            (lambda a,b:I.confirmed_swings(a,b),(h,l))):
            full= function(*inputs); short=function(*(cut(item) for item in inputs))
            if isinstance(full,tuple):
                for series,prefix in zip(full,short): np.testing.assert_equal(series[k-1],prefix[-1])
            else: np.testing.assert_equal(full[k-1],short[-1])
        patterns=I.candle_patterns(o,h,l,c); prefix=I.candle_patterns(o[:k],h[:k],l[:k],c[:k])
        assert _bytes({name:values[k-1] for name,values in patterns.items()}) == _bytes(
            {name:values[-1] for name,values in prefix.items()})
        structure=I.market_structure(h,l); short=I.market_structure(h[:k],l[:k])
        assert _bytes({"label":structure["labels"][k-1],"event":structure["events"][k-1],
            "high":structure["swing_high"][k-1],"low":structure["swing_low"][k-1]}) == _bytes(
            {"label":short["labels"][-1],"event":short["events"][-1],
             "high":short["swing_high"][-1],"low":short["swing_low"][-1]})
        assert _bytes(I.volume_profile(h[:k],l[:k],c[:k],v[:k])) == _bytes(_profile_oracle(c[:k],v[:k]))
        sh,sl=I.confirmed_swings(h,l); sh,sl=sh[:k],sl[:k]
        assert _bytes(I.support_resistance(h[:k],l[:k])) == _bytes(_zone_oracle(sh,sl))
        assert _bytes(I.trendline_candidates(h[:k],l[:k])) == _bytes(_line_oracle(sh,sl))
        assert _bytes(I.fibonacci_levels(h[:k],l[:k])) == _bytes(_fib_oracle(sh,sl))
        # Mutating every row after the anchor must preserve every prefix payload byte-for-byte.
        changed=df.copy(); changed.loc[k:, ["o","h","l","c","v"]] *= -17
        changed_prefix=changed.iloc[:k]
        for function, before, after in ((I.support_resistance, I.support_resistance(h[:k],l[:k]),
                I.support_resistance(changed_prefix.h,changed_prefix.l)),
            (I.trendline_candidates,I.trendline_candidates(h[:k],l[:k]),
                I.trendline_candidates(changed_prefix.h,changed_prefix.l)),
            (I.fibonacci_levels,I.fibonacci_levels(h[:k],l[:k]),
                I.fibonacci_levels(changed_prefix.h,changed_prefix.l))):
            assert _bytes(before)==_bytes(after)
        assert _bytes(I.volume_profile(h[:k],l[:k],c[:k],v[:k])) == _bytes(
            I.volume_profile(changed_prefix.h,changed_prefix.l,changed_prefix.c,changed_prefix.v))
        temporal=[(lambda z:I.sma(z,10),[c]),(lambda z:I.ema(z,12),[c]),
            (lambda z:I.macd(z),[c]),(lambda z:I.rsi(z),[c]),
            (lambda a,b,z:I.atr(a,b,z),[h,l,c]),(lambda a,b,z:I.adx_di(a,b,z),[h,l,c]),
            (lambda z:I.bollinger(z),[c]),(lambda a,b,z,w,t:I.vwap(a,b,z,w,t),[h,l,c,v,t]),
            (lambda a,b:I.confirmed_swings(a,b),[h,l]),
            (lambda a,b:I.market_structure(a,b),[h,l]),
            (lambda a,b,z,w:I.candle_patterns(a,b,z,w),[o,h,l,c])]
        changed_values={"o":changed.o.to_numpy(),"h":changed.h.to_numpy(),
                        "l":changed.l.to_numpy(),"c":changed.c.to_numpy(),
                        "v":changed.v.to_numpy(),"t":t.to_numpy()}
        for function, source in temporal:
            before=_slice_output(function(*source),k)
            keymap={id(o):"o",id(h):"h",id(l):"l",id(c):"c",id(v):"v",id(t):"t"}
            after_args=[changed_values[keymap[id(values)]] for values in source]
            assert _bytes(before)==_bytes(_slice_output(function(*after_args),k))


def test_lookahead_detection_rejects_next_bar_peeking(monkeypatch):
    values=candles(20).c.to_numpy()
    def next_bar_peeking(series): return np.r_[series[1:],series[-1]]
    monkeypatch.setattr(I,"ema",next_bar_peeking)
    with pytest.raises(AssertionError):
        _assert_array_prefix(I.ema,values,10)


def test_features_future_mutation_does_not_change_anchor_output():
    df=candles()
    for k in (30, 50, 70, 90):
        baseline=build_features(df.iloc[:k],"1m")
        changed=df.copy(); changed.loc[k:, ["o","h","l","c","v"]] *= 1000
        assert baseline == build_features(changed.iloc[:k],"1m")
        assert baseline == build_features(df.iloc[:k].copy(),"1m")
    assert len(baseline["input_sha256"]) == 64
    assert "anchor_time" in baseline and "atr14" in baseline
