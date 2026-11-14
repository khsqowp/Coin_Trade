"""Per-1M-token prices (USD). Source: each provider's official pricing page, checked 2026-10-25.

 - Anthropic  https://platform.claude.com/docs/en/about-claude/pricing   (haiku-5-5: prompts <=100k tokens)
 - DeepSeek   https://api-docs.deepseek.com/quick_start/pricing          (cache-miss input; peak = 2x off-peak)
 - OpenAI     https://platform.openai.com/docs/pricing                   (standard, short context)
 - Gemini     https://ai.google.dev/gemini-api/docs/pricing              (paid tier, through 2026-12-31)
Cached-input discounts are ignored (conservative: everything billed at full input price).
Thinking/reasoning tokens are billed as output tokens.
"""
import datetime as dt

PRICES = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "gpt-5.4-mini": (0.75, 4.50),
    "gemini-3.8-flash": (0.75, 3.75),
}
DEEPSEEK = {"deepseek-flash": ((0.15, 0.60), (0.30, 1.20))}  # (off-peak, peak)


def _is_peak(now):
    # Peak: 01-04 and 06-10 UTC, Mon-Fri (Chinese holidays ignored => conservative)
    return now.weekday() < 5 and (1 <= now.hour < 4 or 6 <= now.hour < 10)


def price(model, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    if model in DEEPSEEK:
        off, peak = DEEPSEEK[model]
        return peak if _is_peak(now) else off
    if model in PRICES:
        return PRICES[model]
    raise KeyError("no verified price for model %s" % model)


def cost(model, in_tok, out_tok, now=None):
    pi, po = price(model, now)
    return (in_tok * pi + out_tok * po) / 1e6
