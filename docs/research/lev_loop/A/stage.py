"""usage: stage.py IS|OOS|FULL  -> res_<WIN>.pkl  (all cells, all scenarios/modes)"""
from lib import *
import pickle, sys, time
if __name__ == '__main__':
    win = sys.argv[1]
    tasks = []
    for cell in CELLS:
        for (o, p) in PATHS:
            for kmode in (1, 3):
                for sc in SCEN:
                    tasks.append((cell, win, sc, kmode, o, p, sc == "BASE"))
            tasks.append((cell, win, "BASE", 0, o, p, True))
    t = time.time(); res = run_batch(tasks)
    pickle.dump(res, open(f"res_{win}.pkl", "wb"))
    print(win, len(res), "runs", round(time.time() - t, 1), "s")

