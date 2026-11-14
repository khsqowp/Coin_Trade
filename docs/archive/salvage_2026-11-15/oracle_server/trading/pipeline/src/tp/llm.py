"""Thin direct-HTTP LLM client (Anthropic / DeepSeek / OpenAI). Every attempt is ledgered.

Safety: per-call timeout, bounded retries (default 2), per-process call cap,
budget check before every attempt, secrets scrubbed from all error text.
"""
import json
import os
import time

import requests

from . import budget
from .config import MAX_CALLS_PER_PROCESS, scrub
from .pricing import cost as price_cost

_calls = 0


class LLMError(RuntimeError):
    pass


def provider_of(model):
    for prefix, prov in (("claude", "anthropic"), ("deepseek", "deepseek"), ("gpt", "openai")):
        if model.startswith(prefix):
            return prov
    raise LLMError("unsupported model family: %s" % model)


# Parameters verified by smoke tests (see runs/smoke_params.json) -- model-specific quirks.
EXTRA = {
    "claude-haiku-5-5": {"thinking": {"type": "disabled"}},
    "claude-sonnet-5-5": {"thinking": {"type": "between_tools"}},
    "deepseek-flash": {"thinking": {"type": "disabled"}},
    "gpt-5.4-mini": {"reasoning_effort": "none"},
}
# models that reject a custom temperature
NO_TEMPERATURE = {"claude-haiku-5-5", "claude-sonnet-5-5", "gpt-5.4-mini"}


def _endpoint(prov):
    return {
        "anthropic": ("https://api.anthropic.com/v1/messages", "ANTHROPIC_API_KEY"),
        "deepseek": ("https://api.deepseek.com/chat/completions", "DEEPSEEK_API_KEY"),
        "openai": ("https://api.openai.com/v1/chat/completions", "CHATGPT_API_KEY"),
    }[prov]


def _build(prov, model, system, messages, tools, max_tokens, temperature, json_mode):
    extra = dict(EXTRA.get(model, {}))
    if prov == "anthropic":
        p = {"model": model, "max_tokens": max_tokens, "messages": messages}
        if system:
            p["system"] = system
        if tools:
            p["tools"] = [{"name": t["name"], "description": t["description"],
                           "input_schema": t["parameters"]} for t in tools]
        if model not in NO_TEMPERATURE:
            p["temperature"] = temperature
        p.update(extra)
        return p
    msgs = ([{"role": "system", "content": system}] if system else []) + messages
    p = {"model": model, "messages": msgs}
    p["max_completion_tokens" if prov == "openai" else "max_tokens"] = max_tokens
    if tools:
        p["tools"] = [{"type": "function", "function": t} for t in tools]
    if json_mode and not tools:
        p["response_format"] = {"type": "json_object"}
    if model not in NO_TEMPERATURE:
        p["temperature"] = temperature
    p.update(extra)
    return p


def _parse(prov, data):
    if prov == "anthropic":
        text = "".join(b.get("text", "") for b in data["content"] if b["type"] == "text")
        calls = [{"id": b["id"], "name": b["name"], "args": b["input"]}
                 for b in data["content"] if b["type"] == "tool_use"]
        u = data["usage"]
        return text, calls, {"role": "assistant", "content": data["content"]}, \
            u["input_tokens"], u["output_tokens"], data.get("stop_reason")
    ch = data["choices"][0]
    m = ch["message"]
    calls = []
    for tc in m.get("tool_calls") or []:
        try:
            args = json.loads(tc["function"]["arguments"] or "{}")
        except ValueError:
            args = {"_invalid_json": tc["function"]["arguments"][:200]}
        calls.append({"id": tc["id"], "name": tc["function"]["name"], "args": args})
    keep = {k: v for k, v in m.items() if v is not None and k in ("role", "content", "tool_calls")}
    u = data["usage"]
    return m.get("content") or "", calls, keep, u["prompt_tokens"], u["completion_tokens"], ch.get("finish_reason")


def tool_result_messages(model, results):
    """results: list of (call_id, text). Returns provider-native messages to append."""
    if provider_of(model) == "anthropic":
        return [{"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": i, "content": t} for i, t in results]}]
    return [{"role": "tool", "tool_call_id": i, "content": t} for i, t in results]


def chat(model, system, messages, *, tools=None, max_tokens=2000, temperature=0.0,
         json_mode=False, timeout=90, retries=2, role="", run_id="", purpose=""):
    global _calls
    prov = provider_of(model)
    url, keyname = _endpoint(prov)
    key = os.environ.get(keyname)
    if not key:
        raise LLMError("missing env %s in this container" % keyname)
    headers = {"content-type": "application/json"}
    if prov == "anthropic":
        headers.update({"x-api-key": key, "anthropic-version": "2023-06-01"})
    else:
        headers["authorization"] = "Bearer " + key
    payload = _build(prov, model, system, messages, tools, max_tokens, temperature, json_mode)

    last_err = ""
    for attempt in range(retries + 1):
        budget.check()
        _calls += 1
        if _calls > MAX_CALLS_PER_PROCESS:
            raise LLMError("per-process call cap reached")
        t0 = time.time()
        status, in_tok, out_tok, err = None, 0, 0, ""
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=timeout)
            status = r.status_code
            if status == 200:
                data = r.json()
                text, calls, amsg, in_tok, out_tok, stop = _parse(prov, data)
                c = price_cost(model, in_tok, out_tok)
                lat = time.time() - t0
                budget.record(role=role, run_id=run_id, purpose=purpose, model=model, ok=True, status=200,
                              in_tok=in_tok, out_tok=out_tok, cost=c, latency=round(lat, 2), attempt=attempt)
                return {"text": text, "tool_calls": calls, "assistant_msg": amsg, "in_tok": in_tok,
                        "out_tok": out_tok, "cost": c, "latency": lat, "stop": stop}
            err = scrub(r.text)
        except requests.RequestException as e:
            err = "%s: %s" % (type(e).__name__, scrub(e))
        except (KeyError, ValueError) as e:
            err = "parse %s: %s" % (type(e).__name__, scrub(e))
        last_err = err
        budget.record(role=role, run_id=run_id, purpose=purpose, model=model, ok=False, status=status,
                      in_tok=0, out_tok=0, cost=0.0, latency=round(time.time() - t0, 2),
                      attempt=attempt, error=err[:200])
        retryable = status is None or status == 429 or (status or 0) >= 500
        if not retryable or attempt == retries:
            break
        time.sleep(2 * (2 ** attempt))
    raise LLMError("LLM call failed (%s, status=%s): %s" % (model, status, last_err))
