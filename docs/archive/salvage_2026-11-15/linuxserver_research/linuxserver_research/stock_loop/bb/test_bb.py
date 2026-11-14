"""Tiny synthetic checks; run with python test_bb.py (no pytest required)."""
import numpy as np
from bb import bollinger,simulate_entries,portfolio,candidates,signal_mask

C=np.array([[10.],[10.],[10.],[10.],[10.],[10.],[10.],[10.],[10.],[10.],[10.],[10.],[10.],[10.],[10.],[10.],[10.],[10.],[10.],[10.],[9.],[10.],[10.],[10.]],dtype=np.float32)
lo,mid,up=bollinger(C,20,2)
assert np.isnan(lo[:19]).all() and np.isfinite(lo[19:]).all()
class P: pass
p=P();p.C=np.full((24,1),10.,np.float32);p.O=p.C.copy();p.H=p.C.copy();p.L=p.C.copy();p.valid=np.ones((24,1),bool);p.session=np.zeros(24,int);p.last=np.full(24,23)
p.L[21,0]=8;p.O[21,0]=9
bands=(np.full((24,1),9.5),np.full((24,1),10.),np.full((24,1),10.5))
s=simulate_entries(p,bands,{'target':'upper','stop':.01},'base')
assert s['reason'][19,0]=='stop'
assert s['exit_px'][19,0] <= s['entry_px'][19,0]*.99
# A base entry is at t+1, so validity is checked on that entry row.
p.valid[20,0]=False
s_invalid=simulate_entries(p,bands,{'target':'upper','stop':.01},'base')
assert np.isnan(s_invalid['entry_px'][19,0])

# Three symbols across two sessions must match running each symbol independently.
T,N=60,3
multi=P(); multi.C=np.full((T,N),10.,np.float32); multi.O=multi.C.copy()
multi.H=multi.C.copy(); multi.L=multi.C.copy(); multi.valid=np.ones((T,N),bool)
multi.session=np.repeat([0,1],30); multi.last=np.where(np.arange(T)<30,29,59)
multi.bod=np.tile(np.arange(30),2); multi.value20=np.array([1.,2.,3.])
multi.name='synthetic'; multi.T=T; multi.N=N; multi.warm_sessions=0
multi.prevclose=np.full((T,N),10.,np.float32); multi.prevclose[0]=np.nan
multi.L[8,0]=8.; multi.O[8,0]=9.
multi.H[15,1]=11.; multi.L[35,2]=8.; multi.O[35,2]=9.
multi_bands=(np.full((T,N),9.5),np.full((T,N),10.),np.full((T,N),10.5))
rank,active,warm=candidates(multi)
mask=signal_mask(multi,multi_bands[0],rank,active,warm,'A1','base')
assert mask.shape==(T,N)

# Optimistic fills use only the preceding bar's candidate state, within each session.
rank_state=np.full((T,N),10.,float); active_state=np.zeros((T,N),bool)
rank_state[4,0]=25.; active_state[4,0]=True
rank_state[5,0]=70.; active_state[5,0]=False
rank_state[29,1]=25.; active_state[29,1]=True
rank_state[30,1]=25.; active_state[30,1]=True
opt_lo=np.full((T,N),9.5); multi.L[:]=8.
opt_mask=signal_mask(multi,opt_lo,rank_state,active_state,warm,'A0','opt')
assert opt_mask[5,0]  # Prior row qualifies despite current row failing.
assert not opt_mask[6,0]  # Current row qualifies, prior row does not.
assert not opt_mask[30,1]  # First row of a session has no prior state.
base_mask=signal_mask(multi,opt_lo,rank_state,active_state,warm,'A0','base')
assert not base_mask[5,0] and base_mask[4,0]

# US activity uses the prior 10-20 sessions at the same bar of day.
T,N=14*6,2
activity=P(); activity.C=np.full((T,N),10.,np.float32)
activity.V=np.ones((T,N),np.float32); activity.V[-6:,0]=2.
activity.session=np.repeat(np.arange(14),6); activity.bod=np.tile(np.arange(6),14)
activity.valid=np.ones((T,N),bool); activity.name='us'; activity.T=T; activity.N=N
activity.warm_sessions=10; activity.prevclose=activity.C.copy()
activity.prevclose[0]=np.nan
_,activity_active,_=candidates(activity)
assert not activity_active[:10*6].any()
assert activity_active[-6:,0].all()
assert not activity_active[-6:,1].any()

for fill in ('base','opt'):
    combined=simulate_entries(multi,multi_bands,{'target':'upper','stop':.01},fill)
    for j in range(N):
        single=P()
        for key in ('C','O','H','L','valid'):
            setattr(single,key,getattr(multi,key)[:,j:j+1].copy())
        for key in ('session','last','bod'):
            setattr(single,key,getattr(multi,key).copy())
        single.T=T; single.N=1; single.name=multi.name; single.warm_sessions=0
        single.prevclose=multi.prevclose[:,j:j+1].copy(); single.value20=multi.value20[j:j+1].copy()
        one=simulate_entries(single,tuple(b[:,j:j+1] for b in multi_bands),
                             {'target':'upper','stop':.01},fill)
        for key in combined:
            np.testing.assert_array_equal(combined[key][:,j],one[key][:,0])

# Concurrent intervals are inclusive: five positions may be accepted, the sixth is rejected.
N=6; signals=np.ones((1,N),bool); gross=np.ones((1,N),float)*.01
trades={'entry_idx':np.zeros((1,N)), 'exit_idx':np.ones((1,N))*3,
        'gross':gross,'entry_px':np.ones((1,N)), 'exit_px':np.ones((1,N))*1.01,
        'reason':np.full((1,N),'target',object)}
accepted=portfolio(trades,signals,priority_seed=7)
assert len(accepted)==5
print('synthetic checks passed')
