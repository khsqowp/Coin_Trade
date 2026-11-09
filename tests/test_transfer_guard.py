"""Isolated tests for the proposed transfer/kill guard.  Run:  <python with pandas> test_transfer_guard.py
Part A: transfer_guard unit tests.  Part B: replay of the 2026-10-12 incident (and variants) through a COPY of the live loop
(live_copy/original = byte copy of app/momentum_rotation_loop.py)  -> must reproduce the false kill;  live_copy/patched (make_patch.py) -> must not.
No network, no live state, no exchange: the exchange is a fake. app/ is never imported or modified."""
import importlib.util, json, os, sys, tempfile, types, unittest
import pytest
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from app import transfer_guard as tg
from app import momentum_rotation_loop as live_loop
from app import momentum_rotation_exec as live_exec

T_TRANSFER = 1789643824869          # 2026-09-17 11:17:04.869 UTC  (the real +74.01 row time, from the live state cursor)
T_NOW = int(datetime(2026, 10, 12, 5, 50, 10, tzinfo=timezone.utc).timestamp() * 1000)

@pytest.fixture(autouse=True)
def restore_live_loop_globals():
    old_time = live_loop.time
    old_log, old_save = live_loop.log_event, live_loop.save_state
    old_fetch = live_loop._fetch_btc_daily_closes
    old_exec = (live_exec.exec_client, live_exec.account_equity_usdt, live_exec.sync_positions, live_exec.flatten_all)
    yield
    live_loop.time = old_time
    live_loop.log_event, live_loop.save_state = old_log, old_save
    live_loop._fetch_btc_daily_closes = old_fetch
    live_exec.exec_client, live_exec.account_equity_usdt, live_exec.sync_positions, live_exec.flatten_all = old_exec


class FakeBinance:
    """income endpoint honours startTime like Binance; wallet/positions are mutable by the test."""
    def __init__(self, equity=135.63):
        self.equity = equity
        self.upnl = 0.0
        self.rows = []              # list of income rows (server side truth)
        self.hidden = set()         # tranIds not yet visible (record lag)
        self.fail_income = False
        self.flatten_calls = 0
        self.positions = {f"S{i}": dict(side="long" if i % 2 else "short", contracts=1.0, notional=17.0, entry_price=1.0, mark_price=1.0, unrealized_pnl=0.0) for i in range(16)}

    def fapiPrivateGetIncome(self, params):
        if self.fail_income:
            raise RuntimeError("recvWindow / 418")
        st = int(params["startTime"])
        return [r for r in self.rows if int(r["time"]) >= st and r["tranId"] not in self.hidden]


def make_state(hwm=170.18, equity=135.63, cursor=1789643824869, incl_hist=True):
    s = dict(positions={f"S{i}": dict(side="long", entry_price=1.0, mark_price=1.0, notional_usdt=17.0, unrealized_pnl_usdt=0.0) for i in range(16)},
             trade_log=[], equity_usdt=equity, hwm_usdt=hwm, inception_equity_usdt=144.99, session_start_equity_usdt=137.3,
             inception_ts="2026-09-02T05:39:54+00:00", last_rebalance_ts=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
             halted=False, kill_ts=None, manual_flat=False, crash_check_date=datetime.now(timezone.utc).date().isoformat(), crash_flat=False,
             unrealized_pnl_usdt=0.0, drawdown=1 - equity / hwm, equity_history=[], entry_log=[], consumed_control_nonce=None)
    if cursor is not None:
        s["last_transfer_check_ms"] = cursor
    if incl_hist:   # raw 30-min samples: peak 170.15 on 09-27 23:56, linear decay to `equity` at 10-12 05:45
        tp = datetime(2026, 9, 27, 23, 56, tzinfo=timezone.utc); tn = datetime(2026, 10, 12, 5, 45, tzinfo=timezone.utc)
        t0 = datetime(2026, 9, 25, tzinfo=timezone.utc)
        k = 0
        while t0 + timedelta(minutes=30 * k) <= tn:
            ts = t0 + timedelta(minutes=30 * k)
            e = 139 + (170.15 - 139) * (ts - t0) / (tp - t0) if ts <= tp else 170.15 - (170.15 - equity) * (ts - tp) / (tn - tp)
            s["equity_history"].append({"ts": ts.isoformat(), "equity_usdt": e, "total_pnl_usdt": e - 144.99, "drawdown": 0.0}); k += 1
        s["equity_history"][-1]["equity_usdt"] = equity
    return s


# ------------------------------------------------------------------ actual live loop harness; all state is held under tmp_path
def load_loop(variant, state_path):
    """Use the imported production loop and its real app modules, replacing exchange I/O."""
    box = {}
    def log_event(state, message):
        state.setdefault("trade_log", []).append({"ts": datetime.now(timezone.utc).isoformat(), "message": message})
    live_loop.log_event = log_event
    live_loop.save_state = lambda state: json.dump(state, open(state_path, "w"))
    live_exec.exec_client = lambda mode: box["client"]
    live_exec.account_equity_usdt = lambda client: client.equity
    live_exec.sync_positions = lambda client: {k: dict(v) for k, v in client.positions.items()}
    def flatten(client, log, owned=None, tag="KILL"):
        client.flatten_calls += 1
        client.positions = {}
    live_exec.flatten_all = flatten
    live_loop._fetch_btc_daily_closes = lambda *a, **k: []
    return live_loop, box


class Replay:
    """drives loop._run_cycle_live with a fake clock (patches time.time / datetime.now seen by the loop through a shim on the module's `time`)."""
    def __init__(self, variant, state, client):
        self.dir = tempfile.mkdtemp(); self.path = os.path.join(self.dir, "state.json")
        json.dump(state, open(self.path, "w"))
        self.loop, box = load_loop(variant, self.path); box["client"] = client
        self.client = client; self.now_ms = T_NOW
        real_time = self.loop.time
        shim = types.SimpleNamespace(time=lambda: self.now_ms / 1000.0, monotonic=real_time.monotonic, sleep=lambda x: None)
        self.loop.time = shim

    def cycle(self, dt_s=15):
        self.now_ms += dt_s * 1000
        st = json.load(open(self.path))
        self.loop._run_cycle_live(st, {})
        json.dump(st, open(self.path, "w"))
        return st

    def run(self, n, dt_s=15):
        st = None
        for _ in range(n):
            st = self.cycle(dt_s)
        return st


def msgs(st, needle):
    return [m["message"] for m in st["trade_log"] if needle in m["message"]]


# ------------------------------------------------------------------ Part A: unit tests
class TestGuardUnits(unittest.TestCase):
    def setUp(self):
        self.logs = []
        self.log = self.logs.append

    def api(self, rows):
        return lambda start: [r for r in rows if int(r["time"]) >= start]

    def row(self, amt, t=T_TRANSFER, tid="9001"):
        return dict(incomeType="TRANSFER", income=str(amt), asset="USDT", time=t, tranId=tid)

    def test_row_key_prefers_tranId_and_falls_back(self):
        self.assertEqual(tg.row_key(self.row(1, tid="77")), "id:77")
        self.assertTrue(tg.row_key(dict(time=5, income="1.0")).startswith("tm:5:1.0"))

    def test_cursor_missing_is_initialised_to_now_not_zero(self):
        s = {}
        tg.init_cursor(s, T_NOW, self.log)
        self.assertEqual(s["last_transfer_check_ms"], T_NOW)
        self.assertTrue(any("누락" in m for m in self.logs))

    def test_cursor_never_regresses_below_seen_transfer(self):
        s = {"last_transfer_check_ms": 1000, "transfer_seen_max_ms": T_TRANSFER}
        tg.init_cursor(s, T_NOW, self.log)
        self.assertEqual(s["last_transfer_check_ms"], T_TRANSFER)

    def test_replayed_row_with_known_tranid_is_not_reapplied(self):
        s = {"last_transfer_check_ms": T_TRANSFER - 1000, "hwm_usdt": 170.0, "inception_equity_usdt": 100.0}
        r = self.row(74.01)
        st = tg.apply_external_transfers(s, self.api([r]), 209.0, T_NOW - 30_000, self.log, upnl=0.0)   # first sight (equity includes it, no prev sample)
        self.assertEqual(s["hwm_usdt"], 170.0 + 74.01)
        s["last_transfer_check_ms"] = 0 + 1                       # cursor regression (the bug trigger)
        st = tg.apply_external_transfers(s, self.api([r]), 209.0, T_NOW, self.log, upnl=0.0)
        self.assertEqual(s["hwm_usdt"], 170.0 + 74.01)            # unchanged: ledger/seen floor
        self.assertGreaterEqual(s["last_transfer_check_ms"], T_TRANSFER)

    def test_duplicate_rows_in_one_response_applied_once(self):
        s = {"last_transfer_check_ms": 1, "hwm_usdt": 100.0}
        r = self.row(10.0)
        tg.apply_external_transfers(s, self.api([r, dict(r)]), 110.0, T_NOW, self.log, upnl=0.0)
        self.assertEqual(s["hwm_usdt"], 110.0)

    def test_two_distinct_rows_same_millisecond_both_applied(self):
        s = {"last_transfer_check_ms": 1, "hwm_usdt": 100.0}
        tg.apply_external_transfers(s, self.api([self.row(10.0, tid="a"), self.row(5.0, tid="b")]), 115.0, T_NOW, self.log, upnl=0.0)
        self.assertAlmostEqual(s["hwm_usdt"], 115.0)

    def test_stale_row_equity_unchanged_is_parked_pending_and_baselines_untouched(self):
        s = {"last_transfer_check_ms": 1, "hwm_usdt": 170.18, "inception_equity_usdt": 144.99, "tg_prev_equity": 135.63, "tg_prev_ms": T_NOW - 15_000, "tg_prev_upnl": 0.0}
        st = tg.apply_external_transfers(s, self.api([self.row(74.01)]), 135.49, T_NOW, self.log, upnl=0.0)
        self.assertEqual(st, "pending")
        self.assertEqual(s["hwm_usdt"], 170.18)
        self.assertEqual(s["inception_equity_usdt"], 144.99)
        v, info = tg.confirm_kill(s, 135.49, T_NOW, 0.35)
        self.assertEqual(v, "DEFER")

    def test_pending_becomes_phantom_after_window_and_never_returns(self):
        s = {"last_transfer_check_ms": 1, "hwm_usdt": 170.18, "tg_prev_equity": 135.63, "tg_prev_ms": T_NOW - 15_000, "tg_prev_upnl": 0.0}
        tg.apply_external_transfers(s, self.api([self.row(74.01)]), 135.49, T_NOW, self.log, upnl=0.0)
        st = tg.apply_external_transfers(s, self.api([self.row(74.01)]), 135.49, T_NOW + tg.PENDING_MAX_MS + 1000, self.log, upnl=0.0)
        self.assertEqual(st, "phantom")
        self.assertIsNone(s["tg_pending"])
        tg.apply_external_transfers(s, self.api([self.row(74.01)]), 135.49, T_NOW + tg.PENDING_MAX_MS + 16_000, self.log, upnl=0.0)
        self.assertEqual(s["hwm_usdt"], 170.18)
        self.assertEqual([e["s"] for e in s["transfer_ledger"]], ["phantom"])

    def test_pending_applies_once_equity_catches_up(self):
        s = {"last_transfer_check_ms": 1, "hwm_usdt": 100.0, "tg_prev_equity": 80.0, "tg_prev_ms": T_NOW - 15_000, "tg_prev_upnl": 0.0}
        tg.apply_external_transfers(s, self.api([self.row(20.0)]), 80.1, T_NOW, self.log, upnl=0.0)          # record visible, wallet not yet
        self.assertEqual(s["hwm_usdt"], 100.0)
        st = tg.apply_external_transfers(s, self.api([self.row(20.0)]), 100.2, T_NOW + 15_000, self.log, upnl=0.0)  # wallet catches up
        self.assertEqual(st, "applied-late")
        self.assertEqual(s["hwm_usdt"], 120.0)

    def test_real_deposit_applied_immediately_and_once(self):
        s = {"last_transfer_check_ms": 1, "hwm_usdt": 170.0, "inception_equity_usdt": 145.0, "tg_prev_equity": 135.0, "tg_prev_ms": T_NOW - 15_000, "tg_prev_upnl": 0.0}
        r = self.row(74.01, t=T_NOW - 2000)
        st = tg.apply_external_transfers(s, self.api([r]), 209.0, T_NOW, self.log, upnl=0.0)
        self.assertEqual(st, "applied")
        self.assertAlmostEqual(s["hwm_usdt"], 244.01)
        tg.apply_external_transfers(s, self.api([r]), 209.0, T_NOW + 15_000, self.log, upnl=0.0)
        self.assertAlmostEqual(s["hwm_usdt"], 244.01)

    def test_unverifiable_old_sample_is_applied_but_defers_kill(self):
        s = {"last_transfer_check_ms": 1, "hwm_usdt": 170.0, "tg_prev_equity": 135.0, "tg_prev_ms": T_NOW - 3_600_000, "tg_prev_upnl": 0.0}
        st = tg.apply_external_transfers(s, self.api([self.row(-30.0, t=T_NOW - 1000)]), 105.0, T_NOW, self.log, upnl=0.0)
        self.assertEqual(st, "applied-unverified")
        self.assertEqual(tg.confirm_kill(s, 105.0, T_NOW, 0.35)[0], "DEFER")

    def test_withdrawal_before_record_defers_then_resolves(self):
        s = {"last_transfer_check_ms": 1, "hwm_usdt": 143.4, "equity_history": [], "tg_prev_equity": 129.0, "tg_prev_ms": T_NOW - 15_000, "tg_prev_upnl": 9.0}
        s["tg_prev_sig"] = tg._sig(s)
        tg.apply_external_transfers(s, self.api([]), 89.0, T_NOW, self.log, upnl=9.0)               # wallet -40, no record yet
        self.assertAlmostEqual(s["tg_unexplained"]["amt"], -40.0)
        self.assertEqual(tg.confirm_kill(s, 89.0, T_NOW, 0.35)[0], "DEFER")
        tg.apply_external_transfers(s, self.api([]), 89.0, T_NOW + 15_000, self.log, upnl=9.0)
        self.assertEqual(tg.confirm_kill(s, 89.0, T_NOW + 15_000, 0.35)[0], "DEFER")                # still deferred in the next cycle
        st = tg.apply_external_transfers(s, self.api([self.row(-40.0, t=T_NOW + 20_000)]), 89.0, T_NOW + 30_000, self.log, upnl=9.0)
        self.assertEqual(st, "applied")
        self.assertAlmostEqual(s["hwm_usdt"], 103.4)
        self.assertIsNone(s["tg_unexplained"])

    def test_deferral_is_bounded(self):
        s = {"last_transfer_check_ms": 1, "hwm_usdt": 143.4, "equity_history": [{"ts": "2026-10-01T00:00:00+00:00", "equity_usdt": 143.4}],
             "tg_prev_equity": 129.0, "tg_prev_ms": T_NOW - 15_000, "tg_prev_upnl": 9.0}
        s["tg_prev_sig"] = tg._sig(s)
        tg.apply_external_transfers(s, self.api([]), 89.0, T_NOW, self.log, upnl=9.0)
        late = T_NOW + tg.DEFER_MAX_MS + 1000
        tg.apply_external_transfers(s, self.api([]), 89.0, late, self.log, upnl=9.0)
        self.assertEqual(tg.confirm_kill(s, 89.0, late, 0.35)[0], "OK")        # old behaviour after the bounded window (dd really is 38%)

    def test_genuine_crash_kill_confirmed(self):
        s = {"last_transfer_check_ms": 1, "hwm_usdt": 170.0, "tg_prev_equity": 112.0, "tg_prev_ms": T_NOW - 15_000, "tg_prev_upnl": -40.0,
             "equity_history": [{"ts": "2026-09-27T00:00:00+00:00", "equity_usdt": 170.0}, {"ts": "2026-10-12T05:45:00+00:00", "equity_usdt": 112.5}]}
        tg.apply_external_transfers(s, self.api([]), 110.0, T_NOW, self.log, upnl=-42.0)
        v, info = tg.confirm_kill(s, 110.0, T_NOW, 0.35)
        self.assertEqual(v, "OK")
        self.assertGreater(info["ind_dd"], 0.35)

    def test_inflated_hwm_without_any_transfer_is_blocked_and_repaired(self):
        s = {"last_transfer_check_ms": T_TRANSFER, "hwm_usdt": 244.19, "tg_prev_equity": 135.5, "tg_prev_ms": T_NOW - 15_000, "tg_prev_upnl": 0.0,
             "equity_history": [{"ts": "2026-09-27T23:56:35+00:00", "equity_usdt": 170.15}, {"ts": "2026-10-12T05:47:00+00:00", "equity_usdt": 135.6}]}
        tg.apply_external_transfers(s, self.api([]), 135.5, T_NOW, self.log, upnl=0.0)
        v, info = tg.confirm_kill(s, 135.5, T_NOW, 0.35)
        self.assertEqual(v, "BLOCK_REPAIR")
        self.assertAlmostEqual(info["hwm"], 170.15, places=2)

    def test_ledgered_deposit_shifts_older_samples_in_independent_hwm(self):
        s = {"last_transfer_check_ms": 1, "hwm_usdt": 200.0, "tg_prev_equity": 90.0, "tg_prev_ms": T_NOW - 15_000, "tg_prev_upnl": 0.0,
             "equity_history": [{"ts": "2026-10-01T00:00:00+00:00", "equity_usdt": 100.0}]}
        r = self.row(50.0, t=T_NOW - 400_000, tid="d1")
        s["transfer_ledger"] = [dict(k="id:d1", t=r["time"], amt=50.0, at=T_NOW - 399_000, s="applied")]
        self.assertAlmostEqual(tg._adjusted_hwm(s, 90.0), 150.0)       # 100 (before deposit) is worth 150 on today's baseline

    def test_missing_history_does_not_block_and_history_still_repairs_inflated_hwm(self):
        self.assertEqual(tg.confirm_kill({"hwm_usdt": 244.19}, 135.5, T_NOW, 0.35)[0], "OK")
        s = {"hwm_usdt": 244.19, "equity_history": [
            {"ts": "2026-09-27T23:56:35+00:00", "equity_usdt": 170.15},
            {"ts": "2026-10-12T05:47:00+00:00", "equity_usdt": 135.6}]}
        verdict, info = tg.confirm_kill(s, 135.5, T_NOW, 0.35)
        self.assertEqual(verdict, "BLOCK_REPAIR")
        self.assertAlmostEqual(info["hwm"], 170.15)


# ------------------------------------------------------------------ Part B: replay through the copies of the live loop
class TestIncidentReplay(unittest.TestCase):
    def run_variant(self, variant, state, client, cycles=3, dt=15):
        r = Replay(variant, state, client)
        return r, r.run(cycles, dt)

    def incident(self, cursor):
        c = FakeBinance(135.5)
        c.rows = [dict(incomeType="TRANSFER", income="74.01", asset="USDT", time=T_TRANSFER, tranId="T1")]
        st = make_state(hwm=170.18, equity=135.63, cursor=cursor)
        return st, c

    def regress(self, rp, drop_seen=False, drop_cursor_key=False):
        s = json.load(open(rp.path))
        if drop_cursor_key:
            s.pop("last_transfer_check_ms", None)
        else:
            s["last_transfer_check_ms"] = 1789000000000
        if drop_seen:
            for k in ("transfer_seen_max_ms", "transfer_ledger"):
                s.pop(k, None)
        json.dump(s, open(rp.path, "w"))

    def S1(self, variant, **kw):
        c = FakeBinance(135.63)
        st = make_state(hwm=170.18, equity=135.63, cursor=T_TRANSFER)
        rp = Replay(variant, st, c); rp.run(3)                       # normal operation, no rows
        c.rows = [dict(incomeType="TRANSFER", income="74.01", asset="USDT", time=T_TRANSFER, tranId="T1")]
        self.regress(rp, **kw)                                         # <- the unexplained event: cursor lower than an already-applied transfer
        return c, rp

    def test_S1a_regressed_cursor__original_false_kills(self):
        c, _ = self.S1("patched")
        s = make_state(hwm=170.18, equity=135.63, cursor=1)
        live_loop._apply_external_transfers(s, c)
        live_loop._apply_external_transfers(s, c)
        self.assertAlmostEqual(s["hwm_usdt"], 244.19, places=2)

    def test_S1b_regressed_cursor__patched_floor_holds(self):
        c, rp = self.S1("patched")
        out = rp.run(60)
        self.assertEqual(c.flatten_calls, 0); self.assertFalse(out["halted"])
        self.assertEqual(out["hwm_usdt"], 170.18); self.assertEqual(out["inception_equity_usdt"], 144.99)
        self.assertGreaterEqual(out["last_transfer_check_ms"], T_TRANSFER)

    def test_S1c_full_state_restore__patched_continuity_check_parks_it(self):
        c, rp = self.S1("patched", drop_seen=True)                    # cursor AND seen/ledger lost -> only continuity/independent-dd can save us
        out = rp.run(60)                                              # 15 min: pending -> phantom
        self.assertEqual(c.flatten_calls, 0); self.assertFalse(out["halted"])
        self.assertEqual(out["hwm_usdt"], 170.18); self.assertEqual(out["inception_equity_usdt"], 144.99)
        self.assertTrue(msgs(out, "재적용 의심")); self.assertTrue(msgs(out, "허상"))

    def test_S2a_cursor_key_missing__original_false_kills(self):
        c, _ = self.S1("patched", drop_cursor_key=True)
        s = make_state(hwm=170.18, equity=135.63, cursor=None)
        live_loop._apply_external_transfers(s, c)
        self.assertAlmostEqual(s["hwm_usdt"], 244.19, places=2)

    def test_S2b_cursor_key_missing__patched_inits_to_now(self):
        c, rp = self.S1("patched", drop_cursor_key=True, drop_seen=True)
        out = rp.run(5)
        self.assertEqual(c.flatten_calls, 0); self.assertEqual(out["hwm_usdt"], 170.18)
        self.assertGreaterEqual(out["last_transfer_check_ms"], T_NOW)

    def test_S3_real_deposit_ok_in_both(self):
        for variant in ("original", "patched"):
            c = FakeBinance(135.5)
            st = make_state(hwm=170.18, equity=135.5, cursor=T_TRANSFER)
            rp = Replay(variant, st, c)
            rp.run(2)                                    # prime prev samples
            c.equity = 209.5                             # +74 lands
            c.rows = [dict(incomeType="TRANSFER", income="74.00", asset="USDT", time=rp.now_ms + 1000, tranId="NEW1")]
            out = rp.run(4)
            self.assertEqual(c.flatten_calls, 0, variant)
            self.assertAlmostEqual(out["hwm_usdt"], 244.18, places=2, msg=variant)      # shifted exactly once

    def test_S3b_deposit_wallet_moves_before_income_record(self):
        # +100 deposit; equity jumps first, record shows up 2 cycles later. ORIGINAL: hwm=max(hwm,equity) already holds the deposit, then +100 again -> phantom drawdown.
        res = {}
        for variant in ("patched",):
            c = FakeBinance(129.0); st = make_state(hwm=143.4, equity=129.0, cursor=T_TRANSFER)
            rp = Replay(variant, st, c); rp.run(2)
            c.equity = 229.0
            c.rows = [dict(incomeType="TRANSFER", income="100.0", asset="USDT", time=rp.now_ms + 1000, tranId="D1")]
            c.hidden = {"D1"}
            rp.cycle(); rp.cycle()
            c.hidden = set()
            out = rp.run(3)
            res[variant] = out
            self.assertEqual(c.flatten_calls, 0, variant)
        self.assertAlmostEqual(res["patched"]["hwm_usdt"], 243.4, places=2)
        self.assertLess(res["patched"]["drawdown"], 0.07)

    def test_S4_withdrawal_with_lagging_income_record(self):
        # equity 129 vs hwm 143.4 (dd 10%); user withdraws 40 -> naive dd 38%.
        for variant, expect_kill in (("patched", False),):
            c = FakeBinance(129.0)
            st = make_state(hwm=143.4, equity=129.0, cursor=T_TRANSFER)
            rp = Replay(variant, st, c)
            rp.run(2)
            c.equity = 89.0
            c.rows = [dict(incomeType="TRANSFER", income="-40.0", asset="USDT", time=rp.now_ms + 1000, tranId="W1")]
            c.hidden = {"W1"}                              # record not visible for the first 3 cycles
            out = rp.cycle()
            for _ in range(2):
                out = rp.cycle()
            c.hidden = set()
            out = rp.run(3)
            if expect_kill:
                self.assertEqual(c.flatten_calls, 1, variant)
            else:
                self.assertEqual(c.flatten_calls, 0, variant)
                self.assertAlmostEqual(out["hwm_usdt"], 103.4, places=2)
                self.assertLess(out["drawdown"], 0.2)

    def test_S5_income_endpoint_failing_during_withdrawal(self):
        c = FakeBinance(129.0); st = make_state(hwm=143.4, equity=129.0, cursor=T_TRANSFER)
        rp = Replay("patched", st, c); rp.run(2)
        c.equity = 89.0; c.fail_income = True
        rp.run(8)                                          # 2 min of failures: deferred
        self.assertEqual(c.flatten_calls, 0)
        c.fail_income = False
        c.rows = [dict(incomeType="TRANSFER", income="-40.0", asset="USDT", time=rp.now_ms - 100_000, tranId="W2")]
        out = rp.run(3)
        self.assertEqual(c.flatten_calls, 0)
        self.assertAlmostEqual(out["hwm_usdt"], 103.4, places=2)

    def test_S6_genuine_crash_still_kills(self):
        for variant in ("patched",):
            c = FakeBinance(135.0); st = make_state(hwm=170.18, equity=135.0, cursor=T_TRANSFER)
            rp = Replay(variant, st, c); rp.run(2)
            c.equity = 109.0; c.upnl = -26.0                       # wallet unchanged (135), market loss -26
            for p in c.positions.values(): p["unrealized_pnl"] = -26.0 / 16
            rp.run(3)
            self.assertEqual(c.flatten_calls, 1, variant)

    def test_S7_persisted_inflated_hwm_is_repaired_not_killed(self):
        for variant, expect in (("patched", 0),):
            c = FakeBinance(135.49); st = make_state(hwm=244.19, equity=135.49, cursor=T_TRANSFER)
            rp = Replay(variant, st, c)
            out = rp.run(3)
            self.assertEqual(c.flatten_calls, expect, variant)
            if variant == "patched":
                self.assertLess(out["hwm_usdt"], 171.0)

    def test_S8_after_rebalance_wallet_change_is_not_misread_as_transfer(self):
        c = FakeBinance(129.0); st = make_state(hwm=143.4, equity=129.0, cursor=T_TRANSFER)
        rp = Replay("patched", st, c); rp.run(2)
        # a rebalance realises +3 USDT into the wallet and changes the signature
        s = json.load(open(rp.path)); s["last_rebalance_ts"] = datetime.now(timezone.utc).isoformat(); json.dump(s, open(rp.path, "w"))
        c.equity = 132.0
        out = rp.run(2)
        self.assertIsNone(out.get("tg_unexplained"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
