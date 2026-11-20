"""24/7 UTC boundary scheduler. Retries failed cycles with bounded backoff."""
import logging, os, time
from datetime import datetime, timezone
from .config import SYMBOLS, get_profile
from .engine import Engine
from .fetch import fetch, gaps

logging.basicConfig(level=logging.INFO,format='%(asctime)sZ %(levelname)s %(message)s')
logging.Formatter.converter=time.gmtime
LOG=logging.getLogger('forward-test')
def once(db_path=None, profile=None):
    profile=profile or get_profile()
    e=Engine(db_path,profile=profile); now=int(time.time()*1000)
    e.initialize_forward_start(now)
    for symbol in SYMBOLS:
        old=e.db.execute('SELECT MAX(ts) FROM candles WHERE symbol=?',(symbol,)).fetchone()[0]
        start=int(old)+profile.interval_ms if old is not None else (
            now-profile.initial_history_days*86_400_000 if profile.initial_history_days else
            int(datetime(2022,1,1,tzinfo=timezone.utc).timestamp()*1000))
        # Check and repair historical holes from the first missing interval.
        existing=e.frame(symbol)
        if len(existing) and gaps(existing,profile.interval_ms): start=gaps(existing,profile.interval_ms)[0][0]
        data=fetch(symbol,start,now_ms=now,profile=profile)
        if len(data):e.put_candles(symbol,data)
        LOG.info('%s fetched=%d total=%d',symbol,len(data),len(e.frame(symbol)))
    refs={}
    import requests
    for symbol in SYMBOLS:
        try:
            r=requests.get('https://api.binance.com/api/v3/ticker/price',params={'symbol':symbol},timeout=10); r.raise_for_status(); refs[symbol]=float(r.json()['price'])
        except Exception: LOG.warning('%s ticker unavailable; using last closed close for audit reference',symbol)
    return e.run(ref_prices=refs)
def main():
    profile=get_profile(); db=os.getenv('FORWARD_DB',profile.db_path); delay=1
    while True:
        try:
            n=once(db,profile=profile); LOG.info('cycle complete, bars_processed=%d',n); delay=1
            now=time.time(); next_boundary=(int(now*1000)//profile.interval_ms+1)*profile.interval_ms/1000+20
            time.sleep(max(1,next_boundary-time.time()))
        except Exception:
            LOG.exception('cycle failed; retrying in %ds',delay)
            try:
                e=Engine(db,profile=profile); now=time.time(); prev=e.db.execute('SELECT bars_processed FROM heartbeat WHERE id=1').fetchone()[0]
                e.db.execute('UPDATE heartbeat SET last_run=?,last_error=? WHERE id=1',(now,'cycle failed; see container log')); e.db.execute('INSERT INTO runs VALUES(?,0,0,?)',(now,'cycle failed')); e.db.commit(); e.write_status()
            except Exception: LOG.exception('failed to persist cycle error')
            time.sleep(delay); delay=min(delay*2,300)
if __name__=='__main__':main()
