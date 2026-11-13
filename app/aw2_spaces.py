"""Round-2 bounded configuration spaces and deterministic sampling."""
from __future__ import annotations
import hashlib, itertools, json, random
from app.aw_universe import STOCK_SECTOR

CADENCE = (21, 42, 63, 126)
ETF_CADENCE = (5, 10, 21, 42, 63)

def space(market: str, family: str) -> dict:
    kr = market == "KR"
    idx = "069500" if kr else "SPY"
    bill = "153130" if kr else "SHY"
    sectors = [x for x in ("091160","091170","091180","117700","117680","117460","102970","140700","140710","244580","305720","139260","139230","143860","157490","228790","449450") if kr] if kr else ["XLK","XLF","XLE","XLV","XLI","XLY","XLP","XLU","XLB","XLRE","XLC","MTUM","USMV","QUAL","VLUE","VNQ","XBI","ITA","KRE","XHB","XME","SMH","SOXX","IBB"]
    if family == "F1":
        index_choices=["069500","229200","102110"] if kr else ["SPY","QQQ","IWM"]
        bond_choices=["153130","114260","148070"] if kr else ["BIL","SHY","IEF","TIP"]
        hedges=["132030","261240"] if kr else ["GLD","DBC","UUP"]
        baskets=[]
        for ni in (1,2):
            for ix in itertools.combinations(index_choices,ni):
                for nb in (1,2):
                    for bd in itertools.combinations(bond_choices,nb):
                        for nh in (0,1):
                            for hg in itertools.combinations(hedges,nh):
                                baskets.append([*ix,*bd,*hg])
        return {"basket": baskets, "weighting": ["fixed","inverse_vol","risk_parity"], "weights": [[.6,.4],[.5,.3,.2],[.4,.3,.2,.1],[.3,.25,.2,.15,.1]], "cadence": list(ETF_CADENCE), "vol_window": [20,63,126], "band": [0,.2]}
    if family in ("F2","F11"):
        assets = (["069500","229200","360750","133690","132030","261240","148070","153130"] if family == "F11" else [idx]+sectors)
        return {"lookback": [21,63,126,189,252], "lookbacks": [[63,126],[63,126,252]], "k": [1,2,3,4,5], "absolute_floor": [0,"bill_return"], "trend": [0,100,150,200], "cadence": list(ETF_CADENCE), "assets": [assets], "universe_mode":["index_only","index_sector","index_sector_theme"]}
    if family == "F3":
        return {"trends": [[20,50],[50,100,200],[100,150,200],[50,100,150,200]], "moms": [[],[21],[63],[126],[63,126],[63,126,252]], "min_exposure": [0,.2,.4], "max_exposure": [.8,1.], "rebalance_threshold": [.05,.1,.2,.34], "cadence": list(ETF_CADENCE)}
    if family in ("F4","F13","F5","F10","F6"):
        values = {"lookback":[63,126,189,252],"skip_recent":[False,True],"k":[3,5,8,10,15],"cadence":list(CADENCE if not kr else ETF_CADENCE),"buffer":[1,1.5,2,3],"weighting":["equal","inverse_vol"],"max_weight":[None,.15,.10],"remainder_to":["short","index"],"sector_limit":[0,2,3],"crash_window":[0,10,14,20],"crash_cut":[-.07,-.10,-.12],"crash_release":[0,-.03],"trend_filter":[0,200,"universe200"],"signal":["return","return_vol","high52","rank_average"]}
        if family == "F5": values.update({"sector_count":[2,3,4,5],"per_sector":[1,2,3],"sector_lookback":[63,126,252],"lookback":[63,126,252]})
        if family == "F6": values.update({"core":[.3,.5,.7],"satellite":["F2","F4","F5"],"sector_count":[2,3,4,5],"per_sector":[1,2,3],"sector_lookback":[63,126,252]})
        if family == "F10": values.update({"trends":[[50,100,200],[100,150,200]],"moms":[[21,63],[63,126],[126,252]],"min_exposure":[0,.2,.4],"max_exposure":[.8,1.]})
        return values
    if family == "F7":
        return {"trend_mode":["sma100","sma150","sma200","mom126"],"defensive_mode":["defensive_sector","lowvol_etf","lowvol_stock","bill_mix"],"confirm_days":[1,5,10],"defensive_symbols":[sectors],"lookback":[63,126,252],"cadence":list(CADENCE),"k":[1,3,5]}
    if family == "F8":
        return {"rsi":[2,3,4],"threshold":[5,10,15,20],"trend_filter":[0,100,200],"exit_mode":["sma5","rsi50","rsi70","days5","days10"],"stop":[0,.05,.07,.10],"slots":[2,4,6],"cadence":[1],"slot_weight":[.1,.15,.2],"target_scope":["index","index_sector"]}
    if family == "F12":
        return {"target_vol":[.08,.10,.12,.15,.20],"vol_window":[20,63],"cap":[1.],"threshold":[.1,.2],"cadence":list(ETF_CADENCE)}
    return {}

def _config_id(market, family, params):
    raw=json.dumps(params,sort_keys=True,separators=(",",":"),ensure_ascii=True)
    return hashlib.sha256(f"2|{market}|{family}|{raw}".encode()).hexdigest()[:20]

def sample(market: str, family: str, n: int, seed: int = 20261113) -> list[dict]:
    """Uniform random configurations; finite spaces are enumerated before cycling."""
    spec=space(market,family); keys=list(spec)
    if not keys: return []
    rng=random.Random(seed + sum(map(ord,market+family)))
    out=[]; seen=set()
    for _ in range(n*20):
        p={k:rng.choice(spec[k]) for k in keys}
        if family in ("F4","F5","F6","F10","F13"):
            k=int(p.get("k",5)); cap=p.get("max_weight") or 1/k
            p["max_weight"]=float(cap)
            p["remainder_to"]=p.get("remainder_to","short")
            p["absolute_floor"]=0
            p["trend"]=int(p.get("trend_filter",0)) if isinstance(p.get("trend_filter",0),int) else 0
            if family in ("F4","F13","F10") and p["crash_window"]==0: p["crash_cut"]=-.10; p["crash_release"]=0
        if family in ("F2","F11"):
            p["k"]=int(p["k"])
            lookbacks=p.pop("lookbacks")
            p["multi_lookbacks"]=lookbacks if rng.random()<.5 else []
        if family=="F1":
            # The per-key random draw above already chose one basket and one
            # weight vector. A second draw would collapse each list to a scalar.
            p["invested"]=1.
            if p["weighting"]=="risk_parity": p["weighting"]="inverse_vol"
        if family=="F7": p["defensive_symbols"]=p["defensive_symbols"][0]
        if family=="F5": p["sector_count"]=p["sector_count"]; p["k"]=p["per_sector"]*p["sector_count"]
        if family=="F6": p["core"]=p["core"]
        if family=="F8": p["trend"]=int(p["trend_filter"]); p["stop"]=p["stop"]
        cid=_config_id(market,family,p)
        if cid not in seen: seen.add(cid); p["_config_id"]=cid; out.append(p)
        if len(out)>=n: break
    return out

def refine(market: str, family: str, leaders: list[dict], n: int = 60) -> list[dict]:
    spec=space(market,family); out=[]; seen=set()
    for base in leaders[:10]:
        clean={k:v for k,v in base.items() if k!="_config_id"}
        for key, choices in spec.items():
            for value in choices:
                if clean.get(key)==value: continue
                p=dict(clean); p[key]=value
                if family in ("F4","F5","F6","F10","F13") and key=="k": p["max_weight"]=float(p.get("max_weight") or 1/int(value))
                cid=_config_id(market,family,p)
                if cid not in seen: seen.add(cid); p["_config_id"]=cid; out.append(p)
                if len(out)>=n:return out
    return out
