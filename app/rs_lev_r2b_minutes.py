"""R2-B step 3c: within the market's worst hour per stress day, minute-of-extreme dispersion across the 45 symbols (last price)."""
import json, os, numpy as np
R2B = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "research", "lev_loop", "R2B")
days = json.load(open(os.path.join(R2B, "data", "days.json")))["days"]
print("day | mkt-worst hour (UTC) | median down wick %% | n | minute-of-LOW median [IQR] | pairs |dt|<=2 | <=5 | <=10 | minute-of-HIGH (up-wick hour) median [IQR] | pairs<=5 | L-low vs H-high same-hour minutes: corr of (low-min, high-min) across symbols")
for d in days:
    z = np.load(os.path.join(R2B, "data", d + ".npz")); a = z["last"]; N = a.shape[0]
    cov = np.isfinite(a[:, :, 3]).sum(1) >= 1400
    o, h, l, c = (a[cov][:, :, k].reshape(cov.sum(), 24, 60) for k in range(4))
    prev = np.concatenate([o[:, :1, 0], c[:, :-1, 59]], axis=1)
    dn = (prev - l.min(2)) / prev; up = (h.max(2) - prev) / prev
    hd = int(np.argmax(np.median(dn, axis=0))); hu = int(np.argmax(np.median(up, axis=0)))
    m_lo = np.argmin(l[:, hd, :], axis=1); m_hi = np.argmax(h[:, hu, :], axis=1)
    def pairs(m, k): 
        dd = np.abs(m[:, None] - m[None, :])[np.triu_indices(len(m), 1)]; return (dd <= k).mean()
    iqr = lambda m: np.percentile(m, [25, 75])
    # same hour minute-of-high vs minute-of-low in the down hour
    m_hi_same = np.argmax(h[:, hd, :], axis=1)
    cr = np.corrcoef(m_lo, m_hi_same)[0, 1]
    print(f"{d} | {hd:02d} | {100*np.median(dn[:,hd]):.1f} | {cov.sum()} | {np.median(m_lo):.0f} [{iqr(m_lo)[0]:.0f},{iqr(m_lo)[1]:.0f}] | {pairs(m_lo,2):.2f} | {pairs(m_lo,5):.2f} | {pairs(m_lo,10):.2f} | up-hour {hu:02d}: {np.median(m_hi):.0f} [{iqr(m_hi)[0]:.0f},{iqr(m_hi)[1]:.0f}] | {pairs(m_hi,5):.2f} | {cr:.2f}")
