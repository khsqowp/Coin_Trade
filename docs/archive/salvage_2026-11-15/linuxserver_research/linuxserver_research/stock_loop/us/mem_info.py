from .common import *  # noqa
from .hyp7 import member_mask, added_dates
P, E = load_world()
M, un = member_mask(P)
print("panel names", len(P.codes), "unmatched/undated", len(un), un[:20], "wikipedia names", len(added_dates()))
print("avg members per day", M.sum(1).mean(), "at 2010-01", M[0].sum(), "at 2024-11", M[-1].sum())
