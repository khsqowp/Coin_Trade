"""Offline live-path protection tests; all exchange calls use the 2x FakeClient."""
import copy
import json
from datetime import datetime, timedelta, timezone

import pytest
from test_momentum_2x import setup, state, seed, PRICES, NOW, daily, m


@pytest.fixture
def enabled(setup, monkeypatch):
    monkeypatch.setattr(m, 'PROFIT_LOCK', True)
    monkeypatch.setattr(m, 'PROFIT_LOCK_ACTIVATION', .20)
    monkeypatch.setattr(m, 'PROFIT_LOCK_TRAIL', .25)
    monkeypatch.setattr(m, 'PROFIT_LOCK_COOLDOWN_DAYS', 3)
    return setup


def clock(monkeypatch, when):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return when
    monkeypatch.setattr(m, 'datetime', Clock)
    monkeypatch.setattr(m, 'now_iso', lambda: when.isoformat())


def cycle(client, s, monkeypatch, day, equity):
    clock(monkeypatch, NOW + timedelta(days=day))
    client.equity = equity
    m._run_cycle_live(s, PRICES)


def trigger(client, monkeypatch):
    s = state()
    seed(client, s)
    s['last_rebalance_ts'] = NOW.isoformat()
    cycle(client, s, monkeypatch, 0, 142 * 1.3)
    cycle(client, s, monkeypatch, 1, 142 * 1.3 * .75)
    return s


def test_trigger(enabled, monkeypatch):
    s = trigger(enabled, monkeypatch)
    assert len(enabled.orders) == 16
    assert all(o[3]['reduceOnly'] for o in enabled.orders)
    assert s['profit_lock_active'] and s['profit_lock_armed']
    assert s['profit_lock_trigger_count'] == 1
    assert s['profit_lock_trigger_equity_usdt'] == pytest.approx(138.45)
    assert s['profit_peak_equity_usdt'] == pytest.approx(184.6)
    assert s['profit_lock_drop_pct'] == pytest.approx(.25)
    assert s['profit_lock_trigger_ts'] == (NOW + timedelta(days=1)).isoformat()
    assert s['profit_lock_until'] == (NOW + timedelta(days=4)).isoformat()
    assert not s['positions'] and not s['profit_lock_flatten_pending']
    json.dumps(s)


@pytest.mark.parametrize('peak,drop', [(1.19, .30), (1.3, .20)])
def test_no_trigger(enabled, monkeypatch, peak, drop):
    s = state()
    s['last_rebalance_ts'] = NOW.isoformat()
    cycle(enabled, s, monkeypatch, 0, 142 * peak)
    cycle(enabled, s, monkeypatch, 1, 142 * peak * (1-drop))
    assert not s['profit_lock_active'] and not enabled.orders


def test_unarmed_loss_kill(enabled, monkeypatch):
    s = state()
    seed(enabled, s)
    cycle(enabled, s, monkeypatch, 0, 142 * 1.19)
    cycle(enabled, s, monkeypatch, 1, 142 * 1.19 * .64)
    assert s['halted'] and s['profit_lock_trigger_count'] == 0


def test_cooldown_restart_and_expiry(enabled, monkeypatch):
    s = trigger(enabled, monkeypatch)
    enabled.orders.clear()
    m.save_state(s)
    s = m.load_state()
    for day in [1, 2, 3]:
        cycle(enabled, s, monkeypatch, day, 138.45)
        assert s['profit_lock_active'] and not enabled.orders
    m._manual_enter(s, PRICES)
    assert not enabled.orders
    cycle(enabled, s, monkeypatch, 4, 138.45)
    assert not s['profit_lock_active'] and s['profit_lock_until'] is None
    assert s['profit_peak_equity_usdt'] == s['hwm_usdt'] == 138.45
    assert not s['profit_lock_armed'] and len(enabled.orders) == 16
    m.save_state(s)
    s = m.load_state()
    enabled.orders.clear()
    cycle(enabled, s, monkeypatch, 4, 138.45)
    assert s['profit_peak_equity_usdt'] == 138.45 and not enabled.orders


def test_loss_precedence_same_day_and_while_locked(enabled, monkeypatch):
    s = state()
    seed(enabled, s)
    cycle(enabled, s, monkeypatch, 0, 184.6)
    cycle(enabled, s, monkeypatch, 1, 110)
    assert s['halted'] and not s['profit_lock_active']
    assert s['profit_lock_last_eval_date'] == NOW.date().isoformat()
    s = trigger(enabled, monkeypatch)
    cycle(enabled, s, monkeypatch, 2, 110)
    assert s['halted'] and s['profit_lock_trigger_count'] == 1


def test_crash_tracking_and_expiry_stays_flat(enabled, monkeypatch):
    s = trigger(enabled, monkeypatch)
    enabled.orders.clear()
    monkeypatch.setattr(m, '_fetch_btc_daily_closes', lambda: daily(end=m.datetime.now(timezone.utc).date().isoformat(), crash=True))
    cycle(enabled, s, monkeypatch, 2, 138.45)
    assert s['crash_flat'] and not enabled.orders
    cycle(enabled, s, monkeypatch, 4, 138.45)
    assert not s['profit_lock_active'] and s['crash_flat']
    assert not enabled.orders and not s['positions']


def test_daily_gate(enabled, monkeypatch):
    s = state()
    s['last_rebalance_ts'] = NOW.isoformat()
    cycle(enabled, s, monkeypatch, 0, 184.6)
    cycle(enabled, s, monkeypatch, 0, 138.45)
    assert not s['profit_lock_active']
    assert s['profit_peak_equity_usdt'] == pytest.approx(184.6)
    cycle(enabled, s, monkeypatch, 1, 138.45)
    assert s['profit_lock_active']


def test_transfer_peak_shift(enabled, monkeypatch):
    s = state()
    s['last_rebalance_ts'] = NOW.isoformat()
    cycle(enabled, s, monkeypatch, 0, 184.6)
    monkeypatch.setattr(enabled, 'fapiPrivateGetIncome', lambda params: [dict(time=1, income='-60')])
    cycle(enabled, s, monkeypatch, 1, 124.6)
    assert s['inception_equity_usdt'] == 82
    assert s['profit_peak_equity_usdt'] == pytest.approx(124.6)
    assert not s['profit_lock_active']


def test_failed_flatten_restart_retry(enabled, monkeypatch):
    enabled.fail_closes = 100
    s = trigger(enabled, monkeypatch)
    assert s['profit_lock_flatten_pending']
    m.save_state(s)
    s = m.load_state()
    enabled.fail_closes = 0
    cycle(enabled, s, monkeypatch, 1, 138.45)
    assert not s['profit_lock_flatten_pending'] and not enabled.positions
    enabled.orders.clear()
    cycle(enabled, s, monkeypatch, 2, 138.45)
    assert not enabled.orders


def test_off_matches_original_orders(setup, monkeypatch):
    from pathlib import Path
    # Portable reference: original path is obtained by removing only the new hook.
    text = Path(m.__file__).read_text()
    text = text.replace('    if _profit_lock_cycle(state, client, owned, equity, now):\n        return\n    dd = state["drawdown"]  # PROFIT 만료는 hwm/dd를 현재 equity로 재설정한다.\n', '')
    namespace = {'__name__': 'profit_off_reference'}
    exec(compile(text, m.__file__, 'exec'), namespace)
    namespace.update({name: getattr(m, name) for name in vars(m) if name.isupper()})
    for name in ['datetime', 'now_iso', 'log_event', '_fetch_btc_daily_closes', '_rebalance_live', '_apply_external_transfers']:
        namespace[name] = getattr(m, name)
    monkeypatch.setattr(m, 'PROFIT_LOCK', False)
    s = state()
    seed(setup, s)
    s['last_rebalance_ts'] = NOW.isoformat()
    initial = copy.deepcopy(s)
    held = copy.deepcopy(setup.positions)
    for day, equity in [(0,184.6), (1,138.45), (4,138.45)]:
        cycle(setup, s, monkeypatch, day, equity)
    actual = json.dumps(setup.orders)
    setup.positions = held
    setup.orders.clear()
    for day, equity in [(0,184.6), (1,138.45), (4,138.45)]:
        clock(monkeypatch, NOW + timedelta(days=day))
        namespace['datetime'] = m.datetime
        namespace['now_iso'] = m.now_iso
        setup.equity = equity
        namespace['_run_cycle_live'](initial, PRICES)
    assert json.dumps(setup.orders) == actual
    assert not any(k.startswith('profit_lock') for k in s)


def test_orig_activation_after_rearm_and_utc_date(enabled):
    s = state()
    assert m.profit_lock_eval(s, 184.6, NOW) is None
    assert m.profit_lock_eval(s, 138.45, NOW + timedelta(days=1)) == 'trigger'
    assert m.profit_lock_eval(s, 138.45, NOW + timedelta(days=4)) == 'expire'
    # 20% above re-arm equity remains below the original inception activation.
    assert m.profit_lock_eval(s, 166.14, NOW + timedelta(days=5)) is None
    assert not s['profit_lock_armed']
    local = datetime(2026, 10, 17, 1, tzinfo=timezone(timedelta(hours=9)))
    assert m.profit_lock_eval(s, 170.4, local) is None
    assert s['profit_lock_last_eval_date'] == '2026-10-16'
    assert not s['profit_lock_armed']  # Same UTC day is not sampled twice.
    assert m.profit_lock_eval(s, 170.4, local + timedelta(days=1)) is None
    assert s['profit_lock_armed']


def test_code_default_is_off():
    import ast
    from pathlib import Path
    tree = ast.parse(Path(m.__file__).read_text())
    assignment = next(n for n in tree.body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == 'PROFIT_LOCK' for t in n.targets))
    env_get = assignment.value.left.func.value
    assert env_get.args[0].value == 'MOMENTUM_ROTATION_PROFIT_LOCK'
    assert env_get.args[1].value == 'false'
