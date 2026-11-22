"""AW-2 candidate weight generators. Signals use information available at close t."""
from __future__ import annotations

import numpy as np
import pandas as pd
from app.aw_universe import STOCK_SECTOR


def weights(panel, family: str, params: dict, offset: int = 0) -> pd.DataFrame:
    d, syms, c = panel.dates, panel.symbols, panel.c
    # Work in one dense array: no daily DataFrame .loc/.iloc writes.  All rolling
    # indicators are materialized once before the state loop.
    out = np.zeros((len(d), len(syms)), dtype=np.float64)
    pos = {s: i for i, s in enumerate(syms)}
    w = pd.DataFrame(out, index=d, columns=syms)
    idx = "069500" if panel.market == "KR" else "SPY"
    if idx not in syms: return w
    roles = panel.roles
    def role(r): return [s for s in syms if roles[s] == r]
    sectors, defenses, stocks = role("sector"), role("defensive"), role("stock")
    indices = role("index")
    lb = int(params.get("lookback", 126)); cadence = int(params.get("cadence", 21))
    mom = c.pct_change(lb, fill_method=None)
    if params.get("multi_lookbacks"):
        mom=pd.concat([c.pct_change(int(n),fill_method=None) for n in params["multi_lookbacks"]],axis=1,keys=range(len(params["multi_lookbacks"]))).groupby(level=1,axis=1).mean()
        mom=mom.reindex(columns=syms)
    if params.get("skip_recent"):
        mom = c.shift(21).pct_change(lb, fill_method=None)
    short = next((s for s in defenses if "단기채권" in panel.names[s] or s in ("BIL", "SHY")), defenses[0] if defenses else None)
    trend_param=int(params.get("trend",200)); sma = c.rolling(trend_param if trend_param>0 else 200, min_periods=trend_param if trend_param>0 else 200).mean()
    invvol_n = int(params.get("vol_window", 63))
    vol = c.pct_change(fill_method=None).rolling(invvol_n, min_periods=max(20, invvol_n//2)).std()*np.sqrt(252)
    trend_windows={int(n) for n in params.get("trends",[]) if int(n)>0}|{trend_param if trend_param>0 else 200}
    trends = {n: c[idx].rolling(n, min_periods=n).mean().to_numpy() for n in trend_windows}
    asset_trend_windows={trend_param} if family in ("F2","F11","F8") and trend_param>0 else set()
    asset_trends={n:c.rolling(n,min_periods=n).mean() for n in asset_trend_windows}
    f7_trends={n:c[idx].rolling(n,min_periods=n).mean().to_numpy() for n in (100,150,200)} if family=="F7" else {}
    high52=c.rolling(252,min_periods=126).max() if family in ("F4","F5","F6","F10","F13") else None
    close_idx = c[idx].to_numpy(dtype=float)
    index_sma = trends[trend_param if trend_param>0 else 200]
    momentum_values = mom.to_numpy(dtype=float)
    vol_values = vol.to_numpy(dtype=float)
    stock_elig_values = panel.stock_eligible.reindex(index=d, columns=stocks, fill_value=False).to_numpy(dtype=bool) if stocks else np.empty((len(d), 0), bool)
    sector_mom = c.pct_change(int(params.get("sector_lookback",lb)),fill_method=None) if family in ("F5","F6") else mom
    stock_universe_mean=c[stocks].mean(axis=1) if stocks else pd.Series(np.nan,index=d)
    stock_universe_sma=stock_universe_mean.rolling(200,min_periods=200).mean()
    held = []
    crash_active = False
    weak_state=False;weak_count=0;strong_count=0
    f1_hold=np.zeros(len(syms),dtype=float)
    mr_held: dict[str, tuple[float, int]] = {}
    f8_names = indices if params.get("target_scope")=="index" else indices + sectors
    if family == "F8":
        rn=int(params["rsi"]); delta=c[f8_names].diff(); up=delta.clip(lower=0).rolling(rn,min_periods=rn).mean(); down=-delta.clip(upper=0).rolling(rn,min_periods=rn).mean()
        f8_rsi=100-100/(1+up/down.replace(0,np.nan)); f8_sma5=c[f8_names].rolling(5,min_periods=5).mean()
    for t, day in enumerate(d):
        due = t == 0 or (t % cadence) == offset % cadence
        if family == "F3":
            sigs = [close_idx[t] > trends[int(n)][t] for n in params["trends"]]
            sigs += [close_idx[t] / close_idx[t-int(n)] - 1 > 0 if t >= int(n) and close_idx[t-int(n)] else False for n in params["moms"]]
            exposure = params["min_exposure"] + (params["max_exposure"]-params["min_exposure"])*sum(bool(x) for x in sigs)/len(sigs)
            if t and not due and abs(exposure-float(out[t-1,pos[idx]])) < params["rebalance_threshold"]:
                out[t] = out[t-1]
                continue
            out[t, pos[idx]] = exposure
            if short: out[t, pos[short]] = 1-exposure
            continue
        if family == "F8":
            for s,(entry,age) in list(mr_held.items()):
                age+=1
                mode=params.get("exit_mode","sma5")
                rsi_exit=f8_rsi[s].iloc[t]>float(mode[3:]) if mode.startswith("rsi") else False
                day_exit=age>=int(mode[4:]) if mode.startswith("days") else False
                stop=float(params.get("stop",.07))
                if (mode=="sma5" and c[s].iloc[t] > f8_sma5[s].iloc[t]) or rsi_exit or day_exit or age>=10 or (stop>0 and c[s].iloc[t] <= entry*(1-stop)):
                    mr_held.pop(s)
                else: mr_held[s]=(entry,age)
            if due:
                trend_n=int(params.get("trend",200))
                choices=[s for s in f8_names if s not in mr_held and pd.notna(f8_rsi[s].iloc[t]) and f8_rsi[s].iloc[t] < params["threshold"] and (not trend_n or c[s].iloc[t] > asset_trends[trend_n][s].iloc[t])]
                for s in choices[:max(0,params["slots"]-len(mr_held))]: mr_held[s]=(float(c[s].iloc[t]),0)
            for s in mr_held: out[t,pos[s]]=params["slot_weight"]
            if short: out[t,pos[short]]=max(0,1-out[t].sum())
            continue
        # The crash gate is evaluated every close, including between scheduled
        # rebalances.  A trigger takes effect on the following target row and
        # remains until the separately configured recovery threshold is met.
        if family in ("F4", "F13", "F10") and int(params.get("crash_window", 0)):
            cw = int(params["crash_window"])
            drop = close_idx[t] / close_idx[t-cw] - 1 if t >= cw and close_idx[t-cw] else np.nan
            if not crash_active and np.isfinite(drop) and drop <= float(params.get("crash_cut", -.10)):
                crash_active = True
            elif crash_active and np.isfinite(drop) and drop >= float(params.get("crash_release", 0)):
                crash_active = False
            if crash_active:
                held = []
                if short: out[t, pos[short]] = 1.0
                continue
        if family=="F1" and t:
            prev=c.iloc[t-1].to_numpy(dtype=float);now=c.iloc[t].to_numpy(dtype=float)
            ratio=np.divide(now,prev,out=np.ones_like(now),where=np.isfinite(now)&np.isfinite(prev)&(now>0)&(prev>0))
            drift=f1_hold*ratio;total=drift.sum()
            if total>0:f1_hold=drift/total
        if not due and t:
            out[t] = out[t-1]
            continue
        if family == "F1":
            basket = [s for s in params["basket"] if s in syms]
            if basket:
                if params["weighting"] == "inverse_vol":
                    x = pd.Series({s: 1/max(float(vol[s].iloc[t]), .05) if pd.notna(vol[s].iloc[t]) else 1 for s in basket})
                    x /= x.sum()
                else:
                    values=list(params.get("weights",[]))[:len(basket)]
                    if len(values)<len(basket): values += [1.0]*(len(basket)-len(values))
                    x = pd.Series(values, index=basket, dtype=float)
                x = x / x.sum() * params.get("invested", 1.)
                desired=np.zeros(len(syms),dtype=float);desired[[pos[s] for s in x.index]]=x.values
                band=float(params.get("band",0))
                changed=not np.any(f1_hold) or np.any(np.abs(f1_hold-desired)>band*np.maximum(desired,1e-8))
                if band and not changed and t:out[t]=out[t-1]
                else:out[t]=desired;f1_hold=desired.copy()
        elif family in ("F2", "F11"):
            mode=params.get("universe_mode","index_sector_theme")
            assets = indices if mode=="index_only" else indices+sectors
            if mode=="index_sector" and panel.market=="US":
                themes={"MTUM","USMV","QUAL","VLUE","DBC","EFA","EEM","VNQ","XBI","ITA","KRE","XHB","XME","SMH","SOXX","IBB"}
                assets=[s for s in assets if s not in themes]
            elif mode=="index_sector" and panel.market=="KR":
                assets=[s for s in assets if s not in {"305720","449450"}]
            if mode=="index_sector_theme" and family=="F2": assets=indices+sectors
            if family == "F11":
                assets = [s for s in ("069500", "229200", "360750", "133690", "132030", "261240", "148070", "153130") if s in syms]
            scored = [(s, float(mom[s].iloc[t])) for s in assets if pd.notna(mom[s].iloc[t])]
            if params.get("trend", 0):
                tn=int(params["trend"]);scored = [(s,v) for s,v in scored if c[s].iloc[t] > asset_trends[tn][s].iloc[t]]
            picks = sorted(scored, key=lambda x:x[1], reverse=True)[:int(params["k"])]
            floor=params.get("absolute_floor",0)
            if floor=="bill_return": floor=float(mom[short].iloc[t]) if short and pd.notna(mom[short].iloc[t]) else 0
            for s,v in picks:
                if v > floor: out[t,pos[s]] = 1/max(1,len(picks))
                elif short: out[t,pos[short]] += 1/max(1,len(picks))
        elif family in ("F4", "F5", "F6", "F10", "F13"):
            if family == "F6": out[t,pos[idx]] = params["core"]
            if family == "F6" and params.get("satellite") == "F2":
                assets=indices+sectors
                ranked_assets=sorted([s for s in assets if pd.notna(mom[s].iloc[t])],key=lambda s:mom[s].iloc[t],reverse=True)
                chosen_assets=[s for s in ranked_assets[:params["k"]] if mom[s].iloc[t]>0]
                for s in chosen_assets: out[t,pos[s]] += min(.2,(1-params["core"])/max(1,len(chosen_assets)))
                continue
            excluded=set(params.get("exclude_symbols",()))
            allowed = [s for s in stocks if s not in excluded]
            if family == "F5" or (family=="F6" and params.get("satellite")=="F5"):
                top_sectors = sorted([s for s in sectors if pd.notna(sector_mom[s].iloc[t])], key=lambda s:sector_mom[s].iloc[t], reverse=True)[:params["sector_count"]]
                # Static, conservative mapping only; unknown names are excluded.
                mapping = STOCK_SECTOR.get(panel.market, {})
                allowed = [s for s in stocks if mapping.get(s) in top_sectors]
            trend_mode=params.get("trend_filter",0)
            universe_above=(pd.notna(stock_universe_sma.iloc[t]) and stock_universe_mean.iloc[t]>stock_universe_sma.iloc[t])
            eligible = [s for s in allowed if s in panel.stock_eligible and bool(stock_elig_values[t,stocks.index(s)]) and pd.notna(mom[s].iloc[t]) and (not trend_mode or (trend_mode=="universe200" and universe_above) or (trend_mode==200 and close_idx[t]>index_sma[t]))]
            signal = params.get("signal", "return")
            def signal_value(s):
                ret = float(mom[s].iloc[t])
                if signal == "return_vol": return ret / max(float(vol[s].iloc[t]), .05)
                if signal == "high52":
                    peak = high52[s].iloc[t]
                    return float(c[s].iloc[t] / peak) if pd.notna(peak) and peak else -np.inf
                if signal == "rank_average": return ret + float(c[s].iloc[t] / high52[s].iloc[t])
                return ret
            ranks = sorted(eligible, key=signal_value, reverse=True)
            k = params.get("k", 5)
            if family in ("F4","F13","F10") and held:
                # Buffer is a multiplicative rank threshold and the search
                # space includes fractional values such as 1.5.
                buffer_n = int(np.ceil(int(k) * float(params.get("buffer", 2))))
                keep = [s for s in held if s in ranks[:buffer_n]]
                chosen = keep + [s for s in ranks if s not in keep][:max(0,k-len(keep))]
            elif family=="F5" or (family=="F6" and params.get("satellite")=="F5"):
                chosen=[]; per_sector=int(params.get("per_sector",2)); selected_top=set(top_sectors)
                for sector in top_sectors:
                    members=[s for s in ranks if STOCK_SECTOR.get(panel.market,{}).get(s)==sector]
                    chosen.extend(members[:per_sector])
            else:
                chosen = ranks[:k]
                limit=int(params.get("sector_limit",0))
                if limit:
                    counts={}; capped=[]
                    for s in chosen:
                        sector=STOCK_SECTOR.get(panel.market,{}).get(s,"OTHER")
                        if counts.get(sector,0)<limit:capped.append(s);counts[sector]=counts.get(sector,0)+1
                    chosen=capped
            held = chosen
            stock_exposure = float(params.get("stock_exposure", 1.0))
            if family == "F10":
                trends_ok = [close_idx[t] > trends[int(n)][t] for n in params.get("trends", [100,200])]
                moms_ok = [close_idx[t] / close_idx[t-int(n)] - 1 > 0 for n in params.get("moms", [63,126]) if t >= int(n)]
                sigs = trends_ok + moms_ok
                stock_exposure = float(params.get("min_exposure",0)) + (float(params.get("max_exposure",1))-float(params.get("min_exposure",0))) * (sum(sigs)/max(1,len(sigs)))
            if chosen:
                if params.get("weighting") == "inverse_vol":
                    x = pd.Series({s:1/max(float(vol[s].iloc[t]),.05) if pd.notna(vol[s].iloc[t]) else 1 for s in chosen}); x/=x.sum()
                    raw=x.to_dict()
                else:
                    raw={s:1/len(chosen) for s in chosen}
                cap_raw=params.get("max_weight",.10)
                cap=float(cap_raw) if cap_raw is not None else 1/max(1,len(chosen))
                invest=stock_exposure * (1-float(params.get("core",0)))
                uncapped={s:float(v)*invest for s,v in raw.items()}
                for s,v in uncapped.items(): out[t,pos[s]] += min(cap,float(v))
                residual=max(0,invest-float(out[t,[pos[s] for s in stocks]].sum()))
                if short and params.get("remainder_to","short")=="short": out[t,pos[short]]+=residual
                elif params.get("remainder_to")=="index": out[t,pos[idx]]+=residual
            if family == "F6": out[t,pos[idx]] = params["core"]
            if family == "F10" and short: out[t,pos[short]] += max(0,1-stock_exposure)
            if family == "F5" and not chosen: out[t,pos[idx]] = 1
        elif family == "F7":
            mode=params.get("trend_mode","sma200")
            if mode.startswith("sma"):
                n=int(mode[3:]);trendline=f7_trends[n][t]
                weak_signal=bool(pd.notna(trendline) and c[idx].iloc[t]<trendline)
            else:
                n=126;weak_signal=bool(t>=n and c[idx].iloc[t]/c[idx].iloc[t-n]-1<0)
            confirm=int(params.get("confirm_days",1))
            if weak_signal:weak_count+=1;strong_count=0
            else:strong_count+=1;weak_count=0
            if weak_count>=confirm:weak_state=True
            if strong_count>=confirm:weak_state=False
            defense=params.get("defensive_mode","defensive_sector")
            defensive_names=[s for s in params.get("defensive_symbols",()) if s in sectors]
            if defense=="lowvol_etf":defensive_names=sorted(sectors,key=lambda s:vol[s].iloc[t] if pd.notna(vol[s].iloc[t]) else np.inf)[:int(params.get("k",3))]
            elif defense=="lowvol_stock":defensive_names=sorted([s for s in stocks if s in panel.stock_eligible and bool(stock_elig_values[t,stocks.index(s)])],key=lambda s:vol[s].iloc[t] if pd.notna(vol[s].iloc[t]) else np.inf)[:int(params.get("k",3))]
            elif defense=="bill_mix":defensive_names=(defensive_names[:max(1,int(params.get("k",3))-1)]+([short] if short else []))
            basket=defensive_names if weak_state and defensive_names else ([s for s in indices+sectors if s in params.get("defensive_symbols",())] or [idx])
            ranked=sorted([s for s in basket if pd.notna(mom[s].iloc[t])],key=lambda s:mom[s].iloc[t],reverse=True)[:int(params.get("k",3))]
            for s in ranked:out[t,pos[s]]=1/max(1,len(ranked))
        elif family == "F12":
            rv=float(vol[idx].iloc[t]) if pd.notna(vol[idx].iloc[t]) else float(params["target_vol"])
            exposure=min(float(params.get("cap",1)),float(params["target_vol"])/max(rv,1e-8))
            if t and not due and abs(exposure-float(out[t-1,pos[idx]]))<float(params["threshold"]): exposure=float(out[t-1,pos[idx]])
            out[t,pos[idx]]=exposure
            if short: out[t,pos[short]]=1-exposure
    return pd.DataFrame(np.clip(out,0,1),index=d,columns=syms)


def candidates(market: str, family: str) -> list[dict]:
    if family == "F1":
        bases = ((["069500","153130","132030","261240","114260"], ["069500","153130","148070","132030"], ["069500","153130","114260"])
                 if market == "KR" else (["SPY","SHY","GLD","IEF"], ["SPY","BIL","GLD","TIP"], ["SPY","SHY","IEF"]))
        return [{"basket":b,"weighting":mode,"weights":[.4,.3,.1,.1,.1],"invested":1.,"cadence":cad,"vol_window":vw}
                for b,mode,cad,vw in [(bases[0],"fixed",21,63),(bases[1],"inverse_vol",21,63),(bases[2],"fixed",63,126),(bases[0],"inverse_vol",63,126)]]
    if family == "F2": return [{"lookback":lb,"k":k,"cadence":cad,"trend":tr} for lb,k,cad,tr in [(63,1,21,0),(126,2,21,0),(252,3,21,0),(126,3,42,0),(63,3,21,0),(252,2,63,0)]]
    if family == "F3": return [{"trends":tr,"moms":mo,"min_exposure":mi,"max_exposure":ma,"rebalance_threshold":th,"cadence":cad} for tr,mo,mi,ma,th,cad in [([100,200],[63,126],0,.8,.1,21),([50,150,200],[63,126],.1,1,.1,21),([100,200],[126,252],0,1,.2,42),([50,100,200],[126],.2,.8,.05,21)]]
    if family in ("F4","F5","F6"):
        specs=[(63,3,21,"equal",False),(126,5,21,"equal",False),(252,5,21,"inverse_vol",True),(126,10,42,"inverse_vol",True),(63,5,42,"equal",True),(252,3,21,"equal",False),(126,5,21,"inverse_vol",True),(252,10,42,"equal",True)]
        out=[]
        for j,(lb,k,cad,wt,skip) in enumerate(specs):
            p={"lookback":lb,"k":k,"cadence":cad,"weighting":wt,"buffer":2,"sector_count":3,"core":.5 if family=="F6" else 0,"skip_recent":skip,"crash_window":20 if family=="F4" and j%2 else 0,"crash_cut":-.10,"satellite":"F2" if family=="F6" and j==7 else "F4"}
            out.append(p)
        return out
    if family == "F7":
        defensive=("XLP","XLU","XLV","USMV") if market=="US" else ("091170","140700","143860")
        return [{"lookback":lb,"cadence":cad,"k":k,"trend":tr,"defensive_symbols":defensive} for lb,cad,k,tr in [(63,21,3,100),(126,21,5,200),(252,63,3,150)]]
    if family == "F8": return [{"rsi":n,"threshold":th,"trend":tr,"slots":sl,"slot_weight":.1,"stop":.07,"cadence":1} for n,th,tr,sl in [(2,10,200,4),(3,15,150,4),(2,15,200,6),(3,10,100,4)]]
    return []
