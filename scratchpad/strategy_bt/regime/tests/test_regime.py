import numpy as np
import pandas as pd
from regime.run_regime import (adx14, trend_score, labels, ambiguous, lookup_labels,
                               resample_4h, _walkforward, up_set, down_set)
from regime.run_regime import _regime_lut

def synthetic(n=520):
    ix=pd.date_range('2017-01-01',periods=n,freq='D')
    c=100*np.exp(np.cumsum(.0008+.01*np.sin(np.arange(n)/17)))
    return pd.DataFrame({'open':c*.999,'high':c*1.01,'low':c*.99,'close':c,'volume':np.ones(n)},index=ix)

def test_causality_and_timestamp_lag():
    d=synthetic(); s,a=trend_score(d); m=400
    changed=d.copy(); changed.iloc[m+1:,changed.columns.get_loc('close')]*=np.linspace(1.2,2,len(d)-m-1)
    s2,a2=trend_score(changed)
    for k in (2,3,5,7):
        l,l2=labels(s,a,k),labels(s2,a2,k)
        np.testing.assert_equal(l[:m+1],l2[:m+1])
        t=d.index[m+1]+pd.Timedelta(hours=5)
        before=lookup_labels([t],d.index,l)
        altered=changed.copy(); altered.loc[d.index[m+1]:,'close']*=1.5
        ss,aa=trend_score(altered); after=lookup_labels([t],altered.index,labels(ss,aa,k))
        np.testing.assert_equal(before,after)

def test_bucket_edges_and_sets():
    s=np.array([-4,-3,-1,0,1,3,4.]); a=np.full(len(s),30.)
    assert labels(s,a,5).tolist()==[0,1,2,2,3,4,4]
    assert labels(np.array([-4,-3,-1,0,1,3,4.]),a,7).tolist()==[0,1,3,3,5,6,6]
    assert down_set(2)=={0} and up_set(2)=={1}
    assert np.array([down_set(2).__contains__(r) for r in (0,1)]).tolist()==[True,False]

def test_v2_k2_short_only_kept_in_down_label():
    down=_regime_lut(2,'short')[np.array([0,1])]
    assert down.tolist()==[True,False]

def test_walkforward_vectorized_matches_bruteforce():
    rng=np.random.default_rng(81); n=900
    dates=pd.date_range('2018-01-01',periods=1100,freq='D')
    entry=pd.to_datetime(rng.integers(0,len(dates),n),unit='D',origin=dates[0])
    regime=rng.integers(0,4,n); candidate=rng.integers(0,5,n)
    pct=rng.normal(.08,.7,n); exit_=entry+pd.to_timedelta(rng.integers(-20,100,n),unit='D')
    frame=pd.DataFrame({'candidate':candidate,'entry_time':entry,'exit_time':exit_,'regime':regime,'pct':pct})
    pool=np.array([0,1,2,3]); keep,choices=_walkforward(frame,np.array([]),5,pool,dates)
    expected=np.zeros(n,bool); expected_choices=[]; t=pd.Timestamp('2018-07-01')
    while t < dates[-1]+pd.Timedelta(days=1):
        end=t+pd.DateOffset(months=6); train=(frame.exit_time<t)&frame.candidate.isin(pool)
        future=(frame.entry_time>=t)&(frame.entry_time<end)
        for r in sorted(frame.loc[future,'regime'].unique()):
            best=None; bestsum=0.; count=0
            for cid in sorted(pool):
                m=train&(frame.regime==r)&(frame.candidate==cid); sm=frame.loc[m,'pct'].sum()
                if int(m.sum())>=15 and sm>0 and (best is None or sm>bestsum):best,bestsum,count=cid,sm,int(m.sum())
            if best is not None: expected|=(future&(frame.regime==r)&(frame.candidate==best)).to_numpy()
            expected_choices.append((t,int(r),best,count,float(bestsum)))
        t=end
    assert np.array_equal(keep,expected)
    actual=[(x['retrain_date'],x['regime'],x['chosen_candidate'],x['train_trades'],x['train_sum']) for x in choices]
    assert [(x[:4]) for x in actual]==[(x[:4]) for x in expected_choices]
    np.testing.assert_allclose([x[4] for x in actual],[x[4] for x in expected_choices],rtol=1e-13,atol=1e-13)

def test_v3_trailing_mean_is_lagged_and_causal():
    d=synthetic(620); score,adx=trend_score(d); day=500
    mean_score=pd.Series(score).rolling(180,min_periods=1).mean().shift(1).to_numpy()
    mean_adx=pd.Series(adx).rolling(180,min_periods=1).mean().shift(1).to_numpy()
    changed=d.copy(); changed.iloc[day:,changed.columns.get_loc('close')]*=np.linspace(1.5,3,len(d)-day)
    score2,adx2=trend_score(changed)
    mean_score2=pd.Series(score2).rolling(180,min_periods=1).mean().shift(1).to_numpy()
    mean_adx2=pd.Series(adx2).rolling(180,min_periods=1).mean().shift(1).to_numpy()
    assert mean_score[day]==mean_score2[day] and mean_adx[day]==mean_adx2[day]
    assert not np.isclose(mean_score[day+1],mean_score2[day+1])

def test_shift_preserves_histogram_and_cyclic_runs():
    x=np.array([0,0,0,1,1,2,2,2,2,1,1,0]); y=np.roll(x,4)
    assert sorted(np.bincount(x,minlength=3))==sorted(np.bincount(y,minlength=3))
    assert np.array_equal(np.bincount(x,minlength=3),np.bincount(y,minlength=3))
    # Cyclic transition count is invariant, hence cyclic run count is invariant.
    assert np.sum(x!=np.roll(x,1))==np.sum(y!=np.roll(y,1))

def test_adx_sanity():
    d=synthetic(100); a=adx14(d.high,d.low,d.close)
    assert np.isnan(a[:27]).all(); assert np.isfinite(a[27:]).all()
    assert ((a[27:]>=0)&(a[27:]<=100)).all()

def test_walkforward_excludes_exit_at_retrain():
    T=pd.Timestamp('2019-01-01')
    tr=pd.DataFrame({'candidate':[0,1,1], 'entry_time':[T,T,T], 'exit_time':[T-pd.Timedelta(days=1),T-pd.Timedelta(days=1),T+pd.Timedelta(days=1)], 'regime':[0,0,0], 'pct':[1.,2.,100.]})
    # Min-trade rule requires 15 so duplicate historical trades.
    tr.loc[0,'pct']=2.; tr.loc[1,'pct']=1.
    hist=tr.iloc[[0,1]].loc[np.repeat([0,1],15)].reset_index(drop=True)
    tr=pd.concat([hist,tr.iloc[[2]]],ignore_index=True)
    tr.loc[tr.index<30,'entry_time']=T-pd.Timedelta(days=1)
    keep,_=_walkforward(tr,np.array([]),2,np.array([0,1]),pd.DatetimeIndex([T,T+pd.Timedelta(days=2)]))
    assert not bool(keep.iloc[-1] if hasattr(keep,'iloc') else keep[-1])

def test_resample_only_complete_groups():
    ix=pd.date_range('2020-01-01',periods=9,freq='h')
    d=pd.DataFrame({'open':np.arange(9.),'high':np.arange(9.)+2,'low':np.arange(9.)-1,'close':np.arange(9.)+1,'volume':1.},index=ix)
    r=resample_4h(d)
    assert len(r)==2
    assert r.iloc[0].open==0 and r.iloc[0].close==4 and r.iloc[0].volume==4
