import sys, tempfile, pathlib, json
sys.path.insert(0, "/app/src")
from tp import bt, store
from tp.fixtures import FIXTURES
df = store.get_ohlcv("BTC/USDT", "1d")
res = {}
for n, fx in FIXTURES.items():
    p = pathlib.Path("/tmp") / (n + ".py"); p.write_text(fx["code"])
    try:
        fn = bt.load_signal_fn(p)
        la = bt.lookahead_check(fn, df)
        st = bt.evaluate(df, fn, 365)
        res[n] = {"label": fx["label"], "trunc_detected": not la["passed"], "mism": la["mismatches"], "err": la["errors"],
                  "full_sharpe": st["full"]["sharpe"], "trades": st["full"]["trades"], "oos_sharpe": st["out_of_sample"]["sharpe"], "mdd": st["full"]["mdd"]}
    except Exception as e:
        res[n] = {"error": repr(e)[:150]}
for k, v in res.items(): print(k, v)
