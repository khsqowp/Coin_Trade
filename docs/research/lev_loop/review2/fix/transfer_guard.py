"""PROPOSAL (not deployed): idempotent, self-verifying handling of wallet transfers + kill re-confirmation.

Why: on 2026-10-12 05:50 UTC the live bot re-applied an already-applied +74.01 USDT TRANSFER to hwm (170.18 -> 244.19) while equity was unchanged
(135.63 -> 135.49), computed dd 44.5% instead of 20.4%, and market-closed all 16 positions (false kill, 8.5 h halt + ~2 days flat).
Root hazards in momentum_rotation_loop._apply_external_transfers (ln 529-550):
  H1  the only idempotency key is a single timestamp cursor (`last_transfer_check_ms`); if that value is ever lower than an already-applied
      transfer (state restored/edited/key missing -> `or 0` => startTime=1) every historic TRANSFER row is applied again.
  H2  nothing checks that a transfer actually moved equity (a real +74 must move equity by ~+74 within the same ~15 s window).
  H3  the kill test runs in the SAME cycle as the baseline shift and uses only baselines (hwm) that a transfer can corrupt; there is no independent
      drawdown evidence and no re-confirmation.
  H4  ordering/lag: equity is read before the income query and Binance income rows can lag the wallet change; on a WITHDRAWAL equity drops first,
      hwm is not shifted yet -> dd jumps by w/hwm -> kill in that cycle. A failed income query (418 ban / recvWindow) takes the same path.
Design (stdlib only, all functions pure on `state` dict + injected callables):
  1  ledger of applied tranIds (idempotent), cursor never regresses (max with transfer_seen_max_ms), cursor initialised to NOW when the key is missing.
  2  continuity check: a transfer is applied only if equity moved by ~net since the previous cycle's sample; otherwise it is parked as PENDING
     (retried each cycle, dropped as phantom after PENDING_MAX_MS and logged).
  3  kill re-confirmation (`confirm_kill`): defer while a transfer is pending / just applied-unverified / an unexplained wallet jump exists;
     block+repair when an independent drawdown computed from RAW equity samples (adjusted only by ledgered transfers) is far below the kill threshold.
"""
from __future__ import annotations

PENDING_MAX_MS = 600_000          # a recorded transfer that never shows up in equity within 10 min is treated as phantom
FRESH_PREV_MS = 120_000           # previous equity sample must be at most 2 min old to verify continuity
CONT_REL_EQ = 0.04                # allowed market noise in one sample window (fraction of equity)
CONT_REL_NET = 0.35               # ... or fraction of the transfer size
WALLET_JUMP_REL = 0.03            # unexplained wallet (equity-upnl) change threshold, fraction of equity (min abs 1.0 USDT)
DEFER_MAX_MS = 600_000            # a kill may be deferred at most 10 min by the wallet-jump rule
IND_DD_SLACK = 0.05               # independent dd must be >= kill_dd - slack to confirm
LEDGER_CAP = 500
BASELINES = ("inception_equity_usdt", "session_start_equity_usdt", "hwm_usdt", "profit_peak_equity_usdt")


def row_key(r: dict) -> str:
    tid = r.get("tranId")
    if tid not in (None, "", 0, "0"):
        return f"id:{tid}"
    return f"tm:{r.get('time')}:{r.get('income')}:{r.get('asset', 'USDT')}"


def _ledger(state):
    return state.setdefault("transfer_ledger", [])


def _known(state, key):
    return any(e["k"] == key for e in _ledger(state))


def _record(state, key, t, amt, now_ms, status):
    led = _ledger(state)
    led.append({"k": key, "t": int(t), "amt": float(amt), "at": int(now_ms), "s": status})
    if len(led) > LEDGER_CAP:
        del led[: len(led) - LEDGER_CAP]


def _shift_baselines(state, net):
    for key in BASELINES:
        if state.get(key) is not None:
            state[key] = float(state[key]) + net


def _tol(equity, net):
    return max(CONT_REL_EQ * equity, CONT_REL_NET * abs(net), 0.5)


def init_cursor(state, now_ms, log):
    """cursor-init-to-now when missing; never let the cursor fall below the highest transfer time ever applied/seen."""
    cur = state.get("last_transfer_check_ms")
    if cur is None or int(cur) <= 0:
        state["last_transfer_check_ms"] = int(now_ms)
        state["transfer_cursor_reinit_ms"] = int(now_ms)
        log(f"[LIVE][GUARD] last_transfer_check_ms 누락 — 과거 이체 재적용 방지를 위해 지금({int(now_ms)})으로 초기화")
        cur = now_ms
    if state.get("transfer_seen_max_ms") is None and int(cur) > 0:
        state["transfer_seen_max_ms"] = int(cur)          # migration: the pre-guard cursor is the first floor
    seen = int(state.get("transfer_seen_max_ms") or 0)
    if seen > int(cur):
        log(f"[LIVE][GUARD] last_transfer_check_ms({int(cur)}) < 이미 반영한 이체 시각({seen}) — 커서 되돌림 감지, {seen} 로 복구")
    state["last_transfer_check_ms"] = max(int(cur), seen)
    return state["last_transfer_check_ms"]


def _verify(state, equity, net, now_ms):
    """-> (verdict, matched_unexplained). verdict True/False when verifiable, None when the previous sample is too old."""
    un = state.get("tg_unexplained")          # equity already moved in an earlier cycle (income record lagged the wallet change)
    if un and abs(un["amt"] - net) <= _tol(equity, net):
        return True, un
    pe, pt = state.get("tg_prev_equity"), state.get("tg_prev_ms")
    if pe is None or pt is None or now_ms - int(pt) > FRESH_PREV_MS:
        return None, None
    return abs((equity - float(pe)) - net) <= _tol(equity, net), None


def apply_external_transfers(state, fetch_rows, equity, now_ms, log, upnl=None):
    """Drop-in replacement for _apply_external_transfers. fetch_rows(start_ms) -> list of income rows (raises on API failure).
    Returns a status string; also records tg_prev_* for the next cycle (call EVERY cycle, before the dd/kill evaluation)."""
    status = "none"
    explained = 0.0
    cur = init_cursor(state, now_ms, log)
    state["tg_applied_unverified_ms"] = state.get("tg_applied_unverified_ms")
    # ---- 1. retry pending (equity may lag the income record)
    pend = state.get("tg_pending")
    if pend:
        ok = abs((equity - pend["eq0"]) - pend["net"]) <= _tol(equity, pend["net"])
        if ok:
            _shift_baselines(state, pend["net"])
            for k, t, a in pend["rows"]:
                _record(state, k, t, a, now_ms, "applied-late")
            state["tg_pending"] = None
            explained += pend["net"]
            log(f"[LIVE][GUARD] 보류 이체 {pend['net']:+.2f} USDT: equity 반영 확인 후 적용")
            status = "applied-late"
        elif now_ms - pend["since"] > PENDING_MAX_MS:
            for k, t, a in pend["rows"]:
                _record(state, k, t, a, now_ms, "phantom")
            state["tg_pending"] = None
            log(f"[LIVE][GUARD] 이체 {pend['net']:+.2f} USDT: {PENDING_MAX_MS // 60000}분간 equity 에 반영되지 않음 — 허상(재적용)으로 판단, 폐기")
            status = "phantom"
        else:
            status = "pending"
    # ---- 2. fetch new rows
    try:
        rows = fetch_rows(cur + 1)
    except Exception as exc:  # noqa: BLE001
        state["tg_fetch_failed_ms"] = int(now_ms)
        log(f"[LIVE][GUARD] 입출금 이력 조회 실패 — 이번 사이클 kill 은 재확인 대상: {exc}")
        _stamp(state, equity, upnl, now_ms, explained)
        return "fetch_failed"
    rows = [r for r in (rows or []) if r.get("incomeType", "TRANSFER") == "TRANSFER"]
    new = []
    seen_keys = set()
    for r in rows:
        k = row_key(r)
        if k in seen_keys or _known(state, k) or (state.get("tg_pending") and any(k == p[0] for p in state["tg_pending"]["rows"])):
            continue
        seen_keys.add(k)
        new.append((k, int(r["time"]), float(r["income"])))
    if rows:
        top = max(int(r["time"]) for r in rows)
        state["transfer_seen_max_ms"] = max(int(state.get("transfer_seen_max_ms") or 0), top)
        state["last_transfer_check_ms"] = max(state["last_transfer_check_ms"], top)
    if new:
        net = sum(a for _, _, a in new)
        if abs(net) > 0.0:
            v, matched = _verify(state, equity, net, now_ms)
            if v is False:
                if state.get("tg_pending"):   # merge into existing pending
                    state["tg_pending"]["rows"] += new
                    state["tg_pending"]["net"] += net
                else:
                    state["tg_pending"] = {"rows": new, "net": net, "eq0": float(state.get("tg_prev_equity", equity)), "since": int(now_ms)}
                log(f"[LIVE][GUARD] 이체 {net:+.2f} USDT 가 equity 변화(Δ={equity - float(state.get('tg_prev_equity', equity)):+.2f})로 확인되지 않음 — 보류(재적용 의심), 베이스라인 미변경")
                status = "pending"
            else:
                _shift_baselines(state, net)
                if matched is not None and matched.get("hwm0") is not None:
                    # wallet moved BEFORE the record: the loop's hwm=max(hwm,equity) may already contain a deposit -> rebuild from the pre-jump hwm
                    state["hwm_usdt"] = max(float(matched["hwm0"]) + net, float(equity))
                for k, t, a in new:
                    _record(state, k, t, a, now_ms, "applied" if v else "applied-unverified")
                if v is None:
                    state["tg_applied_unverified_ms"] = int(now_ms)
                explained += net
                log(f"[LIVE] 지갑 이체 감지: {net:+.2f} USDT — 입출금은 손익이 아니라서 수익률 베이스라인을 그만큼 같이 옮김"
                    + ("" if v else " (직전 표본이 오래돼 equity 연속성 미검증)"))
                status = "applied" if v else "applied-unverified"
        else:
            for k, t, a in new:
                _record(state, k, t, a, now_ms, "zero")
    _stamp(state, equity, upnl, now_ms, explained)
    return status


def _sig(state):
    """anything that trades (rebalance / kill / manual flatten / halt release) changes this signature -> wallet may move by realised pnl."""
    return [state.get("last_rebalance_ts"), bool(state.get("halted")), state.get("manual_flat_ts"), state.get("kill_ts"), len(state.get("positions") or {})]


def _stamp(state, equity, upnl, now_ms, explained=0.0):
    """track the UNEXPLAINED wallet change (equity-upnl vs previous cycle, minus transfers applied) as a persistent item until a transfer record explains it."""
    pe, pu, pt = state.get("tg_prev_equity"), state.get("tg_prev_upnl"), state.get("tg_prev_ms")
    raw = 0.0
    if upnl is not None and pe is not None and pu is not None and pt is not None and now_ms - int(pt) <= FRESH_PREV_MS and state.get("tg_prev_sig") == _sig(state):
        raw = (equity - float(upnl)) - (float(pe) - float(pu))
    un = state.get("tg_unexplained")
    amt = (un["amt"] if un else 0.0) + raw - explained
    if abs(amt) <= max(WALLET_JUMP_REL * equity, 1.0):
        state["tg_unexplained"] = None
    else:
        state["tg_unexplained"] = {"amt": amt, "since": (un["since"] if un else int(now_ms)),
                                   "hwm0": (un.get("hwm0") if un else state.get("hwm_usdt"))}
    state["tg_prev_equity"] = float(equity)
    state["tg_prev_upnl"] = None if upnl is None else float(upnl)
    state["tg_prev_ms"] = int(now_ms)
    state["tg_prev_sig"] = _sig(state)


def _adjusted_hwm(state, equity):
    """independent hwm from RAW equity samples: each sample is moved to today's baseline by the ledgered transfers applied AFTER it."""
    led = [e for e in _ledger(state) if e["s"].startswith("applied")]
    epoch = int(state.get("hwm_epoch_ms") or 0)
    best = float(equity)
    for h in state.get("equity_history") or []:
        t = _ts_ms(h["ts"])
        if t < epoch:
            continue
        adj = float(h["equity_usdt"]) + sum(e["amt"] for e in led if e["t"] > t)
        best = max(best, adj)
    return best


def _ts_ms(iso):
    from datetime import datetime
    return int(datetime.fromisoformat(iso).timestamp() * 1000)


def confirm_kill(state, equity, now_ms, kill_dd):
    """Call right where `dd >= KILL_DD` is detected. Returns (verdict, info) with verdict in
    OK | DEFER | BLOCK_REPAIR. On DEFER: skip the kill this cycle (no trading); on BLOCK_REPAIR: set hwm=info['hwm'] and re-evaluate."""
    if state.get("tg_pending"):
        return "DEFER", {"why": "transfer pending (record seen, equity not confirmed)"}
    if state.get("tg_applied_unverified_ms") and now_ms - int(state["tg_applied_unverified_ms"]) <= FRESH_PREV_MS:
        return "DEFER", {"why": "transfer applied without equity continuity check"}
    un = state.get("tg_unexplained")
    if un and now_ms - int(un["since"]) <= DEFER_MAX_MS:
        why = "income query failing while " if (state.get("tg_fetch_failed_ms") and now_ms - int(state["tg_fetch_failed_ms"]) <= FRESH_PREV_MS) else ""
        return "DEFER", {"why": f"{why}unexplained wallet change {un['amt']:+.2f} USDT (transfer record not visible yet)"}
    hwm_ind = _adjusted_hwm(state, equity)
    ind_dd = 1.0 - equity / hwm_ind if hwm_ind > 0 else 0.0
    if ind_dd < kill_dd - IND_DD_SLACK:
        return "BLOCK_REPAIR", {"hwm": hwm_ind, "ind_dd": ind_dd, "why": f"independent dd {ind_dd:.1%} (raw equity history + ledger) << kill {kill_dd:.0%}"}
    return "OK", {"ind_dd": ind_dd}
