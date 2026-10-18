import json
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import momentum_rotation_loop as m
from app import momentum_rotation_exec as execution
from app import momentum_state as storage

FETCH_BTC_DAILY_CLOSES = m._fetch_btc_daily_closes

NOW = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)
SYMBOLS = ['BTC', 'ETH'] + [f'S{i}' for i in range(18)]
RANKED = pd.Series(range(20, 0, -1), index=SYMBOLS, dtype=float)
PRICES = {b: 10.0 for b in SYMBOLS}


class FakeClient:
    def __init__(self, equity=142):
        self.equity = equity
        self.positions = {}
        self.orders = []
        self.leverages = []
        self.minimums = {}
        self.fail_closes = 0

    def market(self, symbol):
        return {'limits': {'cost': {'min': self.minimums.get(symbol.split('/')[0], 5)},
                           'amount': {'min': 0}}}

    def set_leverage(self, leverage, symbol):
        self.leverages.append((leverage, symbol))

    def amount_to_precision(self, symbol, amount):
        return f'{amount:.8f}'

    def _order(self, symbol, amount, side, params=None):
        base = symbol.split('/')[0]
        if params and params.get('reduceOnly') and self.fail_closes:
            self.fail_closes -= 1
            raise RuntimeError('모의 청산 실패')
        self.orders.append((base, side, amount, params or {}))
        if params and params.get('reduceOnly'):
            self.positions.pop(base, None)
        else:
            self.positions[base] = dict(symbol=symbol, contracts=amount, side=side,
                                       notional=amount * PRICES[base], entryPrice=PRICES[base],
                                       markPrice=PRICES[base], unrealizedPnl=0.0)

    def create_market_buy_order(self, symbol, amount, params=None):
        self._order(symbol, amount, 'long', params)

    def create_market_sell_order(self, symbol, amount, params=None):
        self._order(symbol, amount, 'short', params)

    def fetch_positions(self):
        return list(self.positions.values())

    def fetch_balance(self):
        return {'info': {'totalMarginBalance': self.equity}}

    def fapiPrivateGetIncome(self, params):
        return []


def daily(end='2026-10-11', crash=False):
    values = [100.] * 30
    if crash:
        values[-2] = 70.
    return pd.Series(values, index=pd.date_range(end=end, periods=30, tz='UTC'))


@pytest.fixture
def setup(monkeypatch, tmp_path):
    client = FakeClient()
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW
    monkeypatch.setattr(m, 'datetime', Clock)
    monkeypatch.setattr(m, 'now_iso', lambda: NOW.isoformat())
    for key, value in dict(LEVERAGE=4, DEPLOY_PCT=.5, TOP_K=8, MAX_DEPLOY_USDT=0,
                           DELEVER_DD=1., CRASH_FILTER=True, CRASH_LOOKBACK_DAYS=14,
                           CRASH_THRESHOLD=-.1, KILL_COOLDOWN_DAYS=14, KILL_DD=.35,
                           RESET_HALT=False, LIVE=True, REBALANCE_EVERY_DAYS=3).items():
        monkeypatch.setattr(m, key, value)
    monkeypatch.setattr(execution, 'exec_client', lambda mode: client)
    monkeypatch.setattr(m, '_fetch_momentum_ranking', lambda: RANKED.copy())
    monkeypatch.setattr(m, '_fetch_btc_daily_closes', daily)
    monkeypatch.setattr(m, 'log_event', lambda s, message: s.setdefault('logs', []).append(message))
    monkeypatch.setattr(storage, 'STATE_PATH', tmp_path / 'state.json')
    monkeypatch.setattr(m, 'save_state', storage.save_state)
    monkeypatch.setattr(m, 'load_state', storage.load_state)
    monkeypatch.setattr(m, '_fetch_current_prices', lambda: PRICES)
    return client


def state():
    return dict(inception_ts=(NOW - timedelta(days=60)).isoformat(), hwm_usdt=142.,
                inception_equity_usdt=142., positions={}, halted=False)


def seed(client, s):
    targets = {b: 'long' for b in SYMBOLS[:8]}
    targets.update({b: 'short' for b in SYMBOLS[-8:]})
    for base, side in targets.items():
        client._order(f'{base}/USDT:USDT', 1.775, side)
    s['positions'] = {b: dict(side=p['side'], entry_price=10., mark_price=10.,
                              notional_usdt=17.75, unrealized_pnl_usdt=0.)
                      for b, p in client.positions.items()}
    client.orders.clear()


def test_two_x_sizing_and_orders(setup):
    sizing = m.compute_sizing(142, 4, .5, 0, 8)
    assert sizing['notional_per_pos'] == pytest.approx(17.75)
    assert sizing['gross_multiple'] == pytest.approx(2., abs=1e-9)
    assert sizing['margin_use'] <= .5
    assert sizing['k_eff'] == 8
    s = state()
    m._rebalance_live(s, PRICES, 4)
    assert len(setup.orders) == 16
    assert all(amount * PRICES[b] == pytest.approx(17.75, abs=1e-6)
               for b, side, amount, params in setup.orders)
    assert s['gross_multiple_target'] == 2.
    assert s['gross_multiple_realized'] == pytest.approx(2.)
    assert any('목표 총명목배율 2.000000' in line for line in s['logs'])
    assert 'broker' not in s


def test_delever(setup, monkeypatch):
    assert m._effective_leverage(.25) == 4
    assert m.compute_sizing(142, m._effective_leverage(.25), .5, 0, 8) == m.compute_sizing(142, m._effective_leverage(0), .5, 0, 8)
    monkeypatch.setattr(m, 'DELEVER_DD', .2)
    assert m._effective_leverage(.25) == 1
    assert m._effective_leverage(.1) == 4


@pytest.mark.parametrize('equity', [18.75, 18, 30, 40, 142, 500])
def test_k_shrink(equity):
    x = m.compute_sizing(equity, 4, .5, 0, 8)
    assert x['gross'] == equity * 2
    assert x['flat'] == (equity * 2 / 6 < 6.25)
    if x['flat']:
        assert x['k_eff'] == x['notional_per_pos'] == 0
    else:
        assert x['k_eff'] >= 3
        assert x['notional_per_pos'] >= 6.25 - 1e-9
    if equity == 40:
        assert x['k_eff'] < 8
        assert x['gross'] == 80


def test_min_cost_substitution_and_exhaustion():
    targets, scores, skipped = m.select_targets(RANKED, 8, 17.75, lambda b: {'BTC': 100, 'ETH': 20}.get(b, 5))
    assert len(targets) == 16
    assert 'BTC' not in targets and 'ETH' not in targets
    assert targets['S0'] == 'long' and targets['S7'] == 'long'
    assert len(skipped) == 2 and '필요 $100' in skipped[0]
    assert set(scores) == set(targets)
    for count in [14, 10]:
        subset = RANKED.iloc[:count]
        targets, _, _ = m.select_targets(subset, 8, 17.75, lambda b: 5)
        longs = {b for b, side in targets.items() if side == 'long'}
        shorts = {b for b, side in targets.items() if side == 'short'}
        assert len(longs) == len(shorts)
        assert not longs & shorts
        assert len(longs) == (count - 8 if count - 8 >= 3 else 0)


def test_min_notional(setup, monkeypatch):
    setup.minimums['BTC'] = 100
    assert m._symbol_min_notional(setup, 'BTC', 10) == 100
    monkeypatch.setattr(setup, 'market', lambda symbol: {'limits': {'amount': {'min': 3}}})
    assert m._symbol_min_notional(setup, 'BTC', 10) == 30
    monkeypatch.setattr(setup, 'market', lambda symbol: 1 / 0)
    assert m._symbol_min_notional(setup, 'BTC', 10) == 5


@pytest.fixture(scope='module')
def hourly():
    path = Path(__file__).resolve().parents[1] / '.rs_cache/vision/klines_1h/BTCUSDT.csv.gz'
    frame = pd.read_csv(path, compression='gzip', header=None, usecols=[0, 4])
    return pd.Series(frame[4].astype(float).to_numpy(), index=pd.to_datetime(frame[0], unit='ms', utc=True)).sort_index()


def test_real_crash_history(setup, hourly, tmp_path):
    closes = hourly.resample('1D').last().dropna()
    s, flagged, events = {}, [], []
    for day in closes.index[closes.index >= '2021-07-01']:
        now = day + pd.Timedelta(days=1, seconds=10)
        event = m.update_crash_flag(s, lambda: closes, now)
        if s.get('crash_flat'):
            flagged.append(day.date().isoformat())
        if event:
            events.append((day.date().isoformat(), event))
    for start, end in [('2022-06-01', '2022-06-30'), ('2022-11-01', '2022-11-30'), ('2025-02-01', '2025-03-15')]:
        assert any(start <= day <= end for day in flagged)
    assert events and events[0][1] == 'enter'
    assert all(a[1] != b[1] for a, b in zip(events, events[1:]))
    assert any(event == 'exit' for _, event in events)
    artifact = tmp_path / 'crash_dates.json'
    artifact.write_text(json.dumps(dict(flagged=flagged, events=events), indent=2))
    print('급락 날짜:', json.dumps(flagged))
    print('급락 전환 기록:', artifact)


def test_partial_bar(hourly):
    now = pd.Timestamp('2022-06-13 15:00:00', tz='UTC')
    closes = hourly.loc[:now].resample('1D').last().dropna()
    baseline = m.btc_crash_signal(closes, now, 14, -.1)
    assert baseline['asof'] == '2022-06-12'
    for multiplier in [.5, 1.5]:
        changed = closes.copy()
        changed.iloc[-1] *= multiplier
        assert m.btc_crash_signal(changed, now, 14, -.1) == baseline


def test_crash_retries_and_disabled(setup, monkeypatch):
    s = {}
    def broken():
        raise RuntimeError('모의 조회 실패')
    assert m.update_crash_flag(s, broken, NOW) is None
    assert 'crash_check_date' not in s
    assert m.update_crash_flag(s, lambda: daily().iloc[-3:], NOW) is None
    assert 'crash_check_date' not in s
    assert m.update_crash_flag(s, lambda: daily(crash=True), NOW) == 'enter'
    assert m.update_crash_flag(s, broken, NOW) is None
    monkeypatch.setattr(m, 'CRASH_FILTER', False)
    # 필터를 끄면 남아있던 crash_flat 플래그는 해제돼야 한다(영구 flat 방지)
    assert m.update_crash_flag(s, broken, NOW + timedelta(days=1)) == 'exit'
    assert s['crash_flat'] is False
    assert m.update_crash_flag(s, broken, NOW + timedelta(days=1)) is None


def test_crash_enter_hold_exit(setup, monkeypatch):
    s = state()
    seed(setup, s)
    s['last_rebalance_ts'] = (NOW - timedelta(days=1)).isoformat()
    monkeypatch.setattr(m, '_fetch_btc_daily_closes', lambda: daily(crash=True))
    m._run_cycle_live(s, PRICES)
    assert s['crash_flat'] and not s['positions']
    assert len(setup.orders) == 16
    assert all(order[3]['reduceOnly'] for order in setup.orders)
    setup.orders.clear()
    m._run_cycle_live(s, PRICES)
    assert not setup.orders and not setup.leverages
    s['crash_check_date'] = '2026-10-10'
    s['manual_flat'] = True
    calls = []
    def fresh():
        calls.append(True)
        return RANKED.iloc[::-1] * -1
    monkeypatch.setattr(m, '_fetch_momentum_ranking', fresh)
    monkeypatch.setattr(m, '_fetch_btc_daily_closes', daily)
    m._run_cycle_live(s, PRICES)
    assert calls and len(setup.orders) == 16
    assert s['last_rebalance_ts'] == NOW.isoformat()
    assert not s['manual_flat'] and not s['crash_flatten_pending']
    assert s['positions']['S17']['side'] == 'long'


def test_crash_failed_close_and_manual_override(setup, monkeypatch):
    s = state()
    seed(setup, s)
    setup.fail_closes = 40
    monkeypatch.setattr(m, '_fetch_btc_daily_closes', lambda: daily(crash=True))
    m._run_cycle_live(s, PRICES)
    assert s['crash_flatten_pending']
    setup.fail_closes = 0
    m._run_cycle_live(s, PRICES)
    assert not s['positions'] and not s['crash_flatten_pending']
    m._manual_enter(s, PRICES)
    assert len(s['positions']) == 16
    setup.orders.clear()
    setup.leverages.clear()
    m._run_cycle_live(s, PRICES)
    assert not setup.orders and not setup.leverages
    assert len(s['positions']) == 16


def test_kill_persistence_cooldown_and_reset(setup, monkeypatch):
    s = state()
    seed(setup, s)
    s['hwm_usdt'] = 230
    m._run_cycle_live(s, PRICES)
    assert s['halted'] and s['kill_ts'] == NOW.isoformat()
    assert not s['positions']
    assert len(setup.orders) == 16 and all(o[3]['reduceOnly'] for o in setup.orders)
    m.save_state(s)
    s = m.load_state()
    assert s['kill_ts'] == NOW.isoformat()
    setup.orders.clear()
    m._run_cycle_live(s, PRICES)
    assert not setup.orders
    s['kill_ts'] = (NOW - timedelta(days=13)).isoformat()
    m._run_cycle_live(s, PRICES)
    assert s['halted'] and not setup.orders
    s['kill_ts'] = (NOW - timedelta(days=15)).isoformat()
    m._run_cycle_live(s, PRICES)
    assert not s['halted'] and s['hwm_usdt'] == setup.equity
    assert s['kill_ts'] is None and len(setup.orders) == 16
    s.update(halted=True, hwm_usdt=1000, kill_ts=NOW.isoformat(), last_rebalance_ts=None)
    monkeypatch.setattr(m, 'RESET_HALT', True)
    m._run_cycle_live(s, PRICES)
    assert not s['halted'] and s['kill_ts'] is None and s['hwm_usdt'] == setup.equity


def test_legacy_halt_and_disabled_cooldown(setup, monkeypatch):
    s = state()
    s['halted'] = True
    m._run_cycle_live(s, PRICES)
    assert s['kill_ts'] == NOW.isoformat() and s['halted']
    s['kill_ts'] = (NOW - timedelta(days=15)).isoformat()
    monkeypatch.setattr(m, 'KILL_COOLDOWN_DAYS', 0)
    m._run_cycle_live(s, PRICES)
    assert s['halted'] and not setup.orders


@pytest.mark.parametrize('checked', [True, False])
def test_restart_safety(setup, checked):
    s = state()
    seed(setup, s)
    s['last_rebalance_ts'] = (NOW - timedelta(days=1)).isoformat()
    if checked:
        s['crash_check_date'] = NOW.date().isoformat()
    before = json.loads(json.dumps(s['positions']))
    m.save_state(s)
    s = m.load_state()
    m._run_cycle_live(s, PRICES)
    assert not setup.orders and not setup.leverages
    assert s['positions'] == before and not s['halted']


def test_flat_and_insufficient_data(setup, monkeypatch):
    s = state()
    seed(setup, s)
    setup.equity = 18
    monkeypatch.setattr(m, '_fetch_momentum_ranking', lambda: RANKED.iloc[:10])
    m._rebalance_live(s, PRICES, 4)
    assert not setup.orders and len(s['positions']) == 16
    monkeypatch.setattr(m, '_fetch_momentum_ranking', lambda: RANKED)
    m._rebalance_live(s, PRICES, 4)
    assert not s['positions'] and s['effective_k'] == 0
    assert all(o[3]['reduceOnly'] for o in setup.orders)


def test_btc_fetch_signature(setup, monkeypatch):
    calls = []
    def fetch(symbol, timeframe, since_iso):
        calls.append((symbol, timeframe, since_iso))
        return pd.DataFrame({'Close': daily()})
    monkeypatch.setattr(m, 'fetch_perp_ohlcv', fetch)
    assert FETCH_BTC_DAILY_CLOSES().equals(daily())
    assert calls == [('BTC/USDT:USDT', '1d', (NOW - timedelta(days=24)).isoformat())]


def test_deploy_caps_and_zero():
    assert m.compute_sizing(142, 4, 0, 0, 8)['deploy'] == 142
    capped = m.compute_sizing(142, 4, .5, 40, 8)
    assert capped['deploy'] == 40 and capped['gross'] == 160
    assert m.compute_sizing(0, 4, .5, 0, 8)['flat']
    assert m.compute_sizing(18.75, 4, .5, 0, 8)['k_eff'] == 3


def test_rebalance_min_cost_substitution(setup):
    setup.minimums.update(BTC=100, ETH=20)
    s = state()
    m._rebalance_live(s, PRICES, 4)
    assert 'BTC' not in s['positions'] and 'ETH' not in s['positions']
    assert len(s['positions']) == 16 and s['effective_k'] == 8
    assert any('BTC(long' in line for line in s['logs'])
    assert any('ETH(long' in line for line in s['logs'])


def test_selection_empty_closes_owned_only(setup):
    s = state()
    seed(setup, s)
    setup.positions['OTHER'] = dict(symbol='OTHER/USDT:USDT', contracts=1,
                                    side='long', notional=10, entryPrice=10,
                                    markPrice=10, unrealizedPnl=0)
    setup.minimums.update({b: 100 for b in SYMBOLS})
    m._rebalance_live(s, PRICES, 4)
    assert not s['positions'] and s['effective_k'] == 0
    assert set(setup.positions) == {'OTHER'}
    assert len(setup.orders) == 16


def test_crash_pending_restart(setup, monkeypatch):
    s = state()
    seed(setup, s)
    setup.fail_closes = 100
    monkeypatch.setattr(m, '_fetch_btc_daily_closes', lambda: daily(crash=True))
    m._run_cycle_live(s, PRICES)
    m.save_state(s)
    s = m.load_state()
    s['positions'] = {}
    setup.fail_closes = 0
    m._run_cycle_live(s, PRICES)
    assert not setup.positions and not s['crash_flatten_pending']


def test_manual_delever(setup, monkeypatch):
    s = state()
    s['hwm_usdt'] = setup.equity / .75
    monkeypatch.setattr(m, 'DELEVER_DD', .2)
    m._manual_enter(s, PRICES)
    assert setup.leverages and all(lev == 1 for lev, _ in setup.leverages)
