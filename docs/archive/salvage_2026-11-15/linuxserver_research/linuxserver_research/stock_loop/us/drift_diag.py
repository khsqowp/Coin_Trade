"""US open->close vs close->open drift per year (DEV only, diagnostic)."""
from .common import *  # noqa
from .hyp4 import frozen_mask


def main():
    P, E = load_world()
    spy = E.codes.index("SPY")
    oc = E.close[:, spy] / E.open[:, spy] - 1
    co = E.open[1:, spy] / E.close[:-1, spy] - 1
    m = frozen_mask(P, "2014-12-31", 100)
    ocu = np.where(m, P.close / P.open - 1, np.nan)
    cou = np.where(m[:-1], P.open[1:] / P.close[:-1] - 1, np.nan)
    d = pd.DataFrame({"spy_oc": oc[1:], "spy_co": co, "f14_oc": np.nanmean(ocu, axis=1)[1:], "f14_co": np.nanmean(cou, axis=1)}, index=P.dates[1:])
    y = d.groupby(d.index.year).mean() * 100
    print(y.round(3).to_string()); print("all", (d.mean() * 100).round(3).to_dict())
    y.to_csv(ROOT / "results" / "US_drift_by_year_dev.csv")


if __name__ == "__main__":
    main()
