"""Mechanical gates for held-out strategy evidence."""
def decide(test_null_percentile, plateau, test_trades, test_return, positive_symbols, symbols=5):
    reasons=[]
    if test_null_percentile is None or test_null_percentile<95: reasons.append("NULL_PCTL")
    if plateau!="ROBUST": reasons.append("PLATEAU")
    if test_trades<30: reasons.append("TRADES")
    if test_return<=0: reasons.append("RETURN")
    if positive_symbols<3: reasons.append("SYMBOLS")
    return {"verdict":"PASS" if not reasons else "FAIL","reason_codes":reasons}

def sidak_requirement(n_slice_strategies):
    n=max(1,int(n_slice_strategies)); return 100*(1-0.05/n)

def adjusted_decide(test_null_percentile, plateau, test_trades, test_return, positive_symbols, n_slice_strategies, symbols=5):
    result=decide(test_null_percentile,plateau,test_trades,test_return,positive_symbols,symbols)
    req=sidak_requirement(n_slice_strategies)
    reasons=[]
    if test_null_percentile is None or test_null_percentile < req: reasons.append("ADJUSTED_NULL_PCTL")
    reasons.extend(x for x in result["reason_codes"] if x!="NULL_PCTL")
    return {"verdict":"PASS" if not reasons else "FAIL","reason_codes":reasons,"required_percentile":req}
