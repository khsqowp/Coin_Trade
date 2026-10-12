"""Confirm a pair at its later date, within three symbol trading bars."""
from app.frvp_signal_core import find_signals as technical_signals
from app.volume_spike_signal_core import find_signals as volume_signals
from app.technical_portfolio_engine import simulate_portfolio


def find_signals(frame):
    technical=technical_signals(frame)
    volume=volume_signals(frame,volume_multiple=3.,max_price_change_pct=3.)
    t=technical.SIGNAL; v=volume.SIGNAL
    technical['SIGNAL']=(t & v.rolling(4,min_periods=1).max().astype(bool)) | (v & t.rolling(4,min_periods=1).max().astype(bool))
    # Rank by the latest qualifying volume event, known on confirmation day.
    technical['VOL_RATIO']=volume.VOL_RATIO.where(v).ffill(limit=3).fillna(0.)
    return technical
