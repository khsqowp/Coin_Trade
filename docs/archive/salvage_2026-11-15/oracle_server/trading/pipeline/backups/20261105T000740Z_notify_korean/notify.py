"""One-way Telegram notifier for the research pipeline. NO inbound handling (no getUpdates/webhook/commands).

- Disabled unless both TP_TELEGRAM_BOT_TOKEN and TP_TELEGRAM_CHAT_ID are present in the environment.
- Only the Bot API method `sendMessage` is ever called; plain text (no parse_mode), link previews off.
- Every outgoing text and every error string passes through `scrub_message`, which removes known secret values
  (anything in the environment whose name looks secret-ish), Telegram token shapes, API-key shapes, long
  hex/base64-like tokens and `bot<token>` URL fragments. The bot token appears in the request URL, so
  exceptions from `requests` are NEVER logged raw.
- Messages are summaries (numbers, verdicts, rule names, run ids); strategy code and hypotheses' free text are
  truncated and scrubbed; no env dump, no file contents.
"""
import json
import os
import re
import time

import requests

API = "https://api.telegram.org"
TOKEN_ENV, CHAT_ENV = "TP_TELEGRAM_BOT_TOKEN", "TP_TELEGRAM_CHAT_ID"
MAX_LEN = 3500
TIMEOUT = 15
RETRIES = 2
MAX_INLINE_WAIT = 5      # never sleep longer than this inside send(); a longer 429 retry_after is returned to the caller instead

_SECRET_NAME = re.compile(r"(KEY|SECRET|TOKEN|PASSWORD|PASSWD|API_ID|HTTP_API)", re.I)
_PATTERNS = [
    re.compile(r"\bbot\d{5,}:[A-Za-z0-9_\-]{20,}"),                 # URL fragment with token
    re.compile(r"\b\d{6,}:[A-Za-z0-9_\-]{30,}\b"),                  # Telegram bot token shape
    re.compile(r"sk-[A-Za-z0-9_\-]{10,}"),                          # OpenAI/Anthropic/DeepSeek style
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),                         # Google
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{12,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token|password|passwd)\b\s*[:=]\s*\S{8,}"),   # "key: value" leaks
    re.compile(r"\b[A-Fa-f0-9]{40,}\b"),                            # long hex (hashes of secrets, keys)
    re.compile(r"\b[A-Za-z0-9+/_\-]{48,}={0,2}"),                   # long base64/url-safe blobs
]


def _secret_values(extra=()):
    vals = set(v for v in extra if v)
    for k, v in os.environ.items():
        if v and len(v) >= 6 and _SECRET_NAME.search(k):
            vals.add(v)
    for k in (TOKEN_ENV, CHAT_ENV):
        if os.environ.get(k):
            vals.add(os.environ[k])
    return sorted(vals, key=len, reverse=True)


def scrub_message(text, extra_secrets=(), limit=MAX_LEN):
    s = str(text)
    for v in _secret_values(extra_secrets):
        s = s.replace(v, "***")
    for p in _PATTERNS:
        s = p.sub("***", s)
    s = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", s)
    return s if len(s) <= limit else s[:limit - 12] + "\n...[cut]"


def config():
    tok, chat = os.environ.get(TOKEN_ENV, "").strip(), os.environ.get(CHAT_ENV, "").strip()
    return {"enabled": bool(tok and chat), "token": tok, "chat_id": chat}


def send(text, *, dry=False, _post=None):
    """Returns {'sent': bool, 'reason': str}. Never raises, never echoes secrets."""
    cfg = config()
    if not cfg["enabled"]:
        return {"sent": False, "reason": "disabled: Telegram token/chat id not configured"}
    msg = scrub_message(text)
    if dry:
        return {"sent": False, "reason": "dry run", "preview": msg}
    post = _post or requests.post
    url = "%s/bot%s/sendMessage" % (API, cfg["token"])
    last, retry_after = "", None
    for attempt in range(RETRIES + 1):
        wait = 1.5 * (attempt + 1)
        try:
            r = post(url, json={"chat_id": cfg["chat_id"], "text": msg, "disable_web_page_preview": True},
                     timeout=TIMEOUT)
            if r.status_code == 200:
                return {"sent": True, "reason": "ok"}
            try:
                j = r.json()
                desc = j.get("description", "")
                ra = (j.get("parameters") or {}).get("retry_after")
            except Exception:
                desc, ra = "", None
            last = "http %s %s" % (r.status_code, desc[:120])
            if r.status_code not in (429, 500, 502, 503, 504):
                break
            if r.status_code == 429:
                m = re.search(r"retry after (\d+)", desc, re.I)
                ra = ra if isinstance(ra, int) and not isinstance(ra, bool) else (int(m.group(1)) if m else None)
                if ra is not None:
                    retry_after = ra
                    if ra > MAX_INLINE_WAIT:
                        break          # honouring it is the caller's job (the watchdog backs off); do not sleep / hammer here
                    wait = max(ra, 1)
        except Exception as e:      # message can contain the URL (= token): only the class name is kept
            last = type(e).__name__
        if attempt < RETRIES:
            time.sleep(wait)          # no pointless sleep after the final attempt
    res = {"sent": False, "reason": scrub_message("send failed: " + last, limit=200)}
    if retry_after is not None:
        res["retry_after"] = retry_after       # extra key only on 429; the {'sent','reason'} contract is unchanged for other callers
    return res


# ------------------------------------------------------------------ message builders (pure functions)
def _pct(x):
    return "n/a" if x is None else "%.1f%%" % (100 * x)


def format_run_summary(run_id, market, hyp, bt, audit, ablation, gate, cost_run, budget_info, candidate=None):
    L = ["[pipeline] run %s (%s)" % (run_id, market)]
    L.append("hypothesis: %s | %s" % ((hyp or {}).get("name", "?")[:80], (hyp or {}).get("symbol", "?")))
    rules = [r.get("name") for r in (hyp or {}).get("rules", []) if isinstance(r, dict)]
    if rules:
        L.append("rules: " + ", ".join(rules))
    if bt:
        f, o, b = bt["full"], bt["out_of_sample"], bt.get("buy_and_hold", {})
        L.append("backtest full: ret %s sharpe %.2f mdd %s trades %d" % (_pct(f["total_return"]), f["sharpe"], _pct(f["mdd"]), f["trades"]))
        L.append("OOS: ret %s sharpe %.2f mdd %s trades %d | buy&hold ret %s mdd %s" % (
            _pct(o["total_return"]), o["sharpe"], _pct(o["mdd"]), o["trades"], _pct(b.get("total_return")), _pct(b.get("mdd"))))
    if audit:
        sev = sorted({f["severity"] for f in audit.get("findings", [])})
        L.append("auditor: %s (findings %d%s)" % (audit["verdict"], len(audit.get("findings", [])),
                                                  ", " + "/".join(sev) if sev else ""))
    else:
        L.append("auditor: n/a")
    if ablation:
        from .ablation import summarize
        L.append("ablation: " + summarize(ablation))
    if gate:
        L.append("risk gate: %s" % gate["decision"])
        for r in gate.get("reasons", [])[:6]:
            L.append("  - " + r[:110])
        for w in gate.get("warnings", [])[:3]:
            L.append("  ! " + w[:110])
    L.append("cost: run $%.4f | task spent $%.4f of $%.2f (stop at 80%%)" % (
        cost_run, budget_info["task_spent"], budget_info["allowance"]))
    if candidate:
        L.append("DRY-RUN CANDIDATE registered: %s (not deployed; owner approval needed)" % candidate["id"])
    return "\n".join(L)


def format_budget_warning(task_spent, allowance, frac=0.8):
    return ("[pipeline] BUDGET WARNING: task spend $%.4f reached %.0f%% of the $%.2f allowance; LLM calls are stopped automatically."
            % (task_spent, 100 * task_spent / allowance, allowance))


def format_candidate(cand):
    return ("[pipeline] dry-run candidate registered: %s\nstrategy file: %s\nNOT deployed. To swap the dry-run bot "
            "(owner approval required) run on the server:\n%s\nrollback:\n%s" % (
                cand["id"], cand["strategy_file"], cand["swap_command"], cand["rollback_command"]))
