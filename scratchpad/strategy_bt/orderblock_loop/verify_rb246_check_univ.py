import sys, numpy as np
sys.path.insert(0, "/Users/user/CODE/Coin_Trade/scratchpad/strategy_bt/orderblock_loop")
import verify_rb246_independent as V
syms=V.load_universe(); P=V.load_panel(syms); funds=[V.load_funding(s) for s in syms]
W={"top_k":3,"rs":84,"reg":100}
top3={"RUNEUSDT","SOLUSDT","INJUSDT"}
univ=np.array([s not in top3 for s in syms])
a,ia=V.run(P,W,funds); b,ib=V.run(P,W,funds,univ=univ)
print("full n",len(a),ia,"| ex-top3 n",len(b),ib)
print("symbols traded full:", sorted({syms[x['j']] for x in a}-set())[:0], "any top3 in ex-run:", any(syms[x['j']] in top3 for x in b))
print("ex-top3 trades share top3 in full:", sum(syms[x['j']] in top3 for x in a))
