import math
from statistics import NormalDist
_n = NormalDist()
def norm_cdf(x): return _n.cdf(float(x))
def norm_ppf(p): return _n.inv_cdf(float(p))
