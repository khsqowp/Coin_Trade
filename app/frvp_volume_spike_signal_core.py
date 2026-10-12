"""Same-day causal intersection; volume ratio ranks accepted hybrid signals."""
from app.frvp_signal_core import find_signals as technical_signals
from app.volume_spike_signal_core import find_signals as volume_signals
from app.technical_portfolio_engine import simulate_portfolio


def find_signals(frame):
    technical=technical_signals(frame)
    volume=volume_signals(frame, volume_multiple=3., max_price_change_pct=3.)
    technical['SIGNAL']=technical.SIGNAL & volume.SIGNAL
    technical['VOL_RATIO']=volume.VOL_RATIO.fillna(0.)
    return technical
