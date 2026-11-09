"""Isolated demonstration (no live code touched): app/watchdog.run_with_timeout abandons a hung cycle thread; app/momentum_state.save_state later lets that
zombie thread overwrite NEWER state with its stale in-memory copy (the watchdog docstring claims 'no contamination' -- it is wrong).
Shows (1) the lost update with a verbatim copy of the live watchdog + state save/load semantics, (2) a compare-and-swap (state_seq) fix."""
import json, os, tempfile, threading, time, unittest

# --- verbatim semantics of app/watchdog.run_with_timeout
def run_with_timeout(func, timeout_seconds, on_timeout):
    error = []
    def _target():
        try: func()
        except BaseException as exc: error.append(exc)
    th = threading.Thread(target=_target, daemon=True); th.start(); th.join(timeout_seconds)
    if th.is_alive():
        on_timeout(); return
    if error: raise error[0]

class Store:
    """current live semantics: whole-file read / whole-file replace."""
    def __init__(self, path): self.path = path
    def load(self): return json.load(open(self.path))
    def save(self, st): json.dump(st, open(self.path, "w"))

class CasStore(Store):
    """proposed: every save bumps state_seq and refuses to overwrite a newer on-disk seq (lost-update protection)."""
    class Stale(Exception): pass
    def load(self):
        st = super().load(); st.setdefault("state_seq", 0); st["_loaded_seq"] = st["state_seq"]; return st
    def save(self, st):
        disk = super().load().get("state_seq", 0)
        if disk > st.get("_loaded_seq", 0): raise self.Stale(f"disk seq {disk} > loaded {st.get('_loaded_seq')}")
        st2 = {k: v for k, v in st.items() if k != "_loaded_seq"}; st2["state_seq"] = disk + 1; super().save(st2)

class T(unittest.TestCase):
    def scenario(self, store_cls):
        d = tempfile.mkdtemp(); p = os.path.join(d, "s.json"); store = store_cls(p)
        json.dump({"halted": False, "hwm_usdt": 143.0, "last_transfer_check_ms": 100}, open(p, "w"))
        gate = threading.Event(); outcome = {}
        def hung_cycle():                      # cycle A: loads state, then hangs in a network call
            st = store.load(); gate.wait(5)    # (stale copy: halted False, cursor 100)
            try: store.save(st); outcome["A"] = "saved"
            except Exception as e: outcome["A"] = f"refused:{type(e).__name__}"
        run_with_timeout(hung_cycle, 0.2, lambda: outcome.setdefault("timeout", True))
        stB = store.load()                      # cycle B (next cycle) kills + applies transfer
        stB.update(halted=True, hwm_usdt=244.19, last_transfer_check_ms=999); store.save(stB)
        gate.set(); time.sleep(0.3)             # zombie A finishes -> save()
        return outcome, store.load()
    def test_live_semantics_lose_the_update(self):
        o, final = self.scenario(Store)
        self.assertEqual(o["A"], "saved")
        self.assertFalse(final["halted"]); self.assertEqual(final["last_transfer_check_ms"], 100)    # kill flag AND transfer cursor rolled back
    def test_cas_refuses_the_zombie_write(self):
        o, final = self.scenario(CasStore)
        self.assertTrue(o["A"].startswith("refused")); self.assertTrue(final["halted"]); self.assertEqual(final["last_transfer_check_ms"], 999)
if __name__ == "__main__": unittest.main(verbosity=2)
