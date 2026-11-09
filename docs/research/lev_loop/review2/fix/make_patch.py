"""Builds live_copy/patched/momentum_rotation_loop.py from live_copy/original/ (a COPY of the live file) and writes proposal.diff. Never touches app/."""
import difflib, os
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "live_copy/original/momentum_rotation_loop.py")).read()
out = src
# 1) import
a = "from app.momentum_state import load_state, log_event, now_iso, save_state\n"
assert a in out
out = out.replace(a, a + "from app import transfer_guard\n", 1)
# 2) transfer application: guarded, needs equity + upnl of this cycle
a = "    _apply_external_transfers(state, client)\n    now = datetime.now(timezone.utc)\n"
assert a in out
b = ('    _upnl = sum(p["unrealized_pnl"] for p in sync_positions(client).values())\n'
     '    transfer_guard.apply_external_transfers(\n'
     '        state, lambda ms: client.fapiPrivateGetIncome({"incomeType": "TRANSFER", "startTime": ms, "limit": 1000}),\n'
     '        equity, int(time.time() * 1000), lambda m: log_event(state, m), upnl=_upnl)\n'
     '    now = datetime.now(timezone.utc)\n')
out = out.replace(a, b, 1)
# 3) kill re-confirmation
a = '    if dd >= KILL_DD:\n        log_event(state, f"[LIVE] 킬 스위치 발동'
assert a in out
b = ('    if dd >= KILL_DD:\n'
     '        verdict, info = transfer_guard.confirm_kill(state, equity, int(time.time() * 1000), KILL_DD)\n'
     '        if verdict == "DEFER":\n'
     '            log_event(state, f"[LIVE][GUARD] 킬 보류 — dd {dd*100:.1f}% 이지만 {info[\'why\']}")\n'
     '            return\n'
     '        if verdict == "BLOCK_REPAIR":\n'
     '            log_event(state, f"[LIVE][GUARD] 킬 차단 — 상태 hwm {hwm:.2f} 은 원시 equity 이력과 불일치: {info[\'why\']}. hwm 을 {info[\'hwm\']:.2f} 로 복구")\n'
     '            hwm = max(info["hwm"], equity)\n'
     '            state["hwm_usdt"] = hwm\n'
     '            dd = 1.0 - equity / hwm\n'
     '            state["drawdown"] = dd\n'
     '    if dd >= KILL_DD:\n        log_event(state, f"[LIVE] 킬 스위치 발동')
out = out.replace(a, b, 1)
os.makedirs(os.path.join(HERE, "live_copy/patched"), exist_ok=True)
open(os.path.join(HERE, "live_copy/patched/momentum_rotation_loop.py"), "w").write(out)
d = "".join(difflib.unified_diff(src.splitlines(True), out.splitlines(True), "app/momentum_rotation_loop.py", "app/momentum_rotation_loop.py (proposed)"))
open(os.path.join(HERE, "proposal.diff"), "w").write(d)
print(d)
