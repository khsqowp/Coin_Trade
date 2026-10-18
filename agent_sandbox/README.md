# Autonomous futures trading experiment

This is an **offline-tested experiment**, not a validated strategy or a profitable trading system. The harness controls a virtual 1000 USDT account. An LLM proposes decisions; the harness validates, measures and executes them. Live exchange operations are restricted to Binance USDS-M futures **TESTNET**, using paper money.

Nothing is installed, scheduled, deployed or committed automatically. No Docker or ccxt is used. Flat modules run from this directory with Python 3.13, stdlib and `requests`. Tests require `pytest`.

## Safety and credentials

Every HTTP request checks that its URL uses HTTPS and the exact hostname `testnet.binancefuture.com`. Redirects are disabled. Mainnet, lookalike hosts, credentials in URLs and alternate ports are refused. One-way position mode is required; hedge mode is refused.

Only `BINANCE_FUTURE_TESTNET_API_KEY` and `BINANCE_FUTURE_TESTNET_SECRET_KEY` supply exchange credentials. Mainnet key variables are ignored. An explicitly supplied `--env-file` parses only those two names, preserving existing environment values. All input files and configurable state directories must be inside this project. The program never discovers dotenv files automatically.

The LLM subprocess receives a scrubbed environment: names containing KEY, SECRET or TOKEN are removed, except OPENAI_* and CODEX_* authentication/configuration variables. It runs `codex exec` in a fresh empty directory with `--sandbox read-only --skip-git-repo-check --ephemeral --color never`, an output file, and the prompt on stdin. It uses existing Codex authentication; `--ignore-user-config` is deliberately absent. Timeout, nonzero exit and malformed output mean no action. It cannot access an exchange object or receive testnet credentials from the harness.

**Read-only sandboxing can still read the filesystem. Keep exchange keys out of files readable by the agent.** An empty working directory and environment scrubbing are not filesystem isolation or a network firewall. Existing Codex configuration, enabled tools, authentication files and web search require operator review. Do not alias exchange secrets to OPENAI_* or CODEX_* variables. Strong isolation requires a separately restricted OS identity or environment, configured by the operator. This project does not automatically create one.

A persisted sliding-window throttle limits requests to 20 per minute across processes sharing the state directory. HTTP 418/429 writes `ban.json`, stops immediately and is never retried. `Retry-After` seconds or a Binance banned-until epoch sets the ban expiry; an unknown duration gets a conservative 60-second fallback. Requests during an active ban never send. Read/data requests with network connection/timeouts and 5xx have at most three attempts with 1- and 2-second inter-attempt waits (the exponential sequence is 1, 2, 4; there is no fourth attempt). Order submissions are not blindly retried: after a timeout or 5xx, the harness queries the durable clientOrderId. Unresolved submissions block further trading until their status is confirmed or investigated manually. Other 4xx responses never retry. All transport exceptions printed by entry points are generic or redacted.

## Risk controls

Defaults are configurable through `config.json`, merged over the defaults in `config.py`; `config.example.json` contains the complete configuration. A custom file is selected with `--config`. Configured `state_dir` must resolve inside this directory.

- Virtual equity starts at 1000 USDT for each generation; weekly target is +100 USDT net of trading fees.
- Leverage is an integer from 1 to 10. At most five own positions, one per symbol.
- `size_pct_equity` is a margin allocation: 10% equity at 3x leverage means 300 USDT notional on a 1000 account.
- A long stop must be below the mark; a short stop must be above it. Every open requires a positive stop. Take-profit must be on the profitable side of the mark.
- Risk at stop is `abs(mark - stop) / mark * notional`, capped at 5% of current virtual equity. A modification rechecks this cap and the stop side.
- Gross mark exposure is capped at 3x equity. Symbol minimum quantity/notional and step/tick filters apply. Orders are rechecked after rounding and after earlier actions have changed capital.
- Data older than 300 seconds blocks open/modify. Opens are blocked during daily sit-out. Owned closes remain available under stale data; foreign symbol quarantine overrides trading permission.
- A 15% loss from the first valuation of the UTC day triggers flattening and sit-out through the next UTC midnight. The harness checks this on each tick, so it is not continuous loss protection.

Decisions are all-or-nothing JSON schema validations: unknown keys/types, missing stops, boolean numbers, non-finite numbers, overlong text or more than ten actions reject the entire output. Valid decisions undergo per-action sequential risk checks. An empty actions list is valid.

An accepted testnet open sets leverage, executes a market order, and places a mandatory reduce-only STOP_MARKET using MARK_PRICE. If stop placement fails, an immediate reduce-only market close is attempted and a CRITICAL record is written. A ban or exchange failure can prevent emergency flattening; inspect the testnet account manually in that case. A modification places its new stop before canceling the old stop, and places a new TP before canceling the old TP. Owned closes cancel only owned `ags_` orders and submit a reduce-only market order. Exchange mutations raise in dry-run mode; simulation makes zero exchange order calls. Execution mode is persisted and cannot change in an existing state directory: use different state directories for dry-run and testnet-orders.

## Virtual capital and generations

Virtual equity is generation start capital + realized PnL from own fills - own trading fees + mark unrealized PnL from own positions. Raw testnet wallet equity is informational only. Funding transfers, slippage and liquidation are not modeled as virtual-account costs.

In testnet-orders mode, order registrations and clientOrderIds beginning `ags_` identify this harness's fills. Another bot's `ags_` orders are excluded unless registered by the current generation. Fill IDs deduplicate imports; a durable pending-fill journal recovers interruptions between accounting and JSONL writes. Trade cursors paginate histories. Durable submission/opening journals recover acknowledged entries and restore mandatory protection after interruption. Confirmed flat lifecycles cancel registered sibling stop/TP orders before the symbol may reopen. Each tick compares own signed quantity and entry price with exchange `positionRisk`. Manual or other-bot activity marks a symbol foreign, logs a warning, and quarantines it for the remainder of the generation and subsequent generations. The harness does not overwrite foreign positions or cancel foreign orders. Unresolved foreign overlap with an owned position blocks retirement instead of pretending flattening succeeded. Separate testnet accounts are preferable. A long outage or missing order registration can make reconciliation fail; manually investigate rather than bypassing it.

Dry-run market fills use the current mark and the taker fee (0.05% per side). Completed 15m candles since the prior tick evaluate stops and TP at their trigger prices. A candle touching both triggers fills the stop first. Candles starting before the position existed are excluded because their highs/lows cannot be attributed to the holding period. A candle with a position opened mid-bar is therefore not modeled until the next full bar. No slippage is modeled. Candle OHLC comes from trade-price klines, while live triggers use MARK_PRICE; this is an approximation.

Weeks run Monday 00:00 UTC to the next Monday 00:00 UTC. Boundary equity is the last equity curve sample at or before that boundary, not a fabricated retrospective price. Its timestamp is reported. A missing or stale boundary sample makes the evaluation approximate. Exactly +100 survives. Survival carries positions and notes and updates `week_start_equity`. A lower result flattens, archives logs and final report, wipes active notes, and starts generation N+1 with fresh virtual 1000 USDT. A generation started mid-week is evaluated at the next Monday, recorded as `partial_week=true`. Several missed weeks are processed in order; a week without samples carries the prior equity baseline and can retire an inactive generation. Retirement orders occur when the harness resumes, not retrospectively at the boundary. Flatten failures block advancing the generation.

Weekly reports include PnL, target difference, survival, sampled drawdown, completed trades, net win rate, fees, best/worst attributable closed decisions and rejection counts. Partial fills are grouped into flat-to-flat trades, including both entry and exit fees. Open trades do not receive a final decision ranking. Reports first created by a tick have unavailable benchmark placeholders; the week-close script enriches them idempotently.

## Data and benchmarks

Core symbols (BTCUSDT, ETHUSDT) and owned symbols receive 15m, 1h, 4h and 1d summaries. Other watchlist symbols receive 1h/4h. Closed bars supply Wilder RSI/ATR, SMA-seeded EMA, MACD and population-standard-deviation Bollinger bands, returns and 24 compact OHLCV bars. Warm-up shortages produce nulls. One all-symbol premiumIndex call supplies mark prices and funding. Open interest for core/held symbols fails soft except bans.

`btc_buy_hold` measures the first period open to the last period close in percent; it is an unleveraged price baseline without trading fees. Random-trader runs use 1h bars, deterministic seeds, a 10% chance to open each hour with slots free, random symbol/direction, 10% margin, 3x leverage, 2 ATR stop and 3 ATR TP. They enforce configured risk/exposure/concurrency/daily limits and charge taker fees on both sides. Opens occur at an observed bar close; later bars trigger exits, with stop-first ties. The distribution reports mean/median/p10/p90 USDT PnL and share meeting the target. Offline candle-only benchmarks lack exchange symbol filters. Week close fetches ten watchlist 1h series with warm-up history, through the same throttle.

Web search availability depends on Codex CLI configuration. There is no liquidation-map API in the harness; the agent can only web-search for such information. Testnet prices and liquidity differ from mainnet. Hourly observations, incomplete historical data, sampled drawdown, outages, delayed live fills and protection failures limit the measurement. No performance guarantee is made.

## State layout

`state/` contains:

- `current.json`: generation, start/week/day capital, timestamps, sit-out, own position ledger, fees/realized PnL, execution mode, fill/cursor/submission recovery bookkeeping, cumulative paper PnL and foreign symbols.
- `generations.json`: completed weekly evaluations and benchmark status.
- `ticks.jsonl`, `decisions.jsonl`, `orders.jsonl`, `fills.jsonl`, `equity.jsonl`, `rejections.jsonl`: append-only run evidence, partitioned by generation in each record.
- `notes/gen_<N>.md`: active notes (old active file wiped after retirement).
- `archive/gen_<N>/`: retired snapshot, own logs, historical notes and final report.
- `reports/gen_<N>_week_<ISO>.md`: weekly measurement report.
- `throttle.json`, `ban.json`, `.throttle.lock`, `.run.lock`: cross-process request controls and serialization.

Atomic JSON writes use temporary files, fsync and rename. Both scripts hold the same `fcntl` run lock. Different state directories do not share throttle or ledger ownership: use one state directory per account and do not run a second harness on the same symbols. JSON snapshots and JSONL appends are not a transactional database; durable journals handle the tested interruption points, but unresolved exchange acknowledgements may still require manual reconciliation. Do not delete/reset state while there are owned testnet positions.

## Commands

Run from this directory. Prepare Codex authentication separately. For network data, both dry-run and testnet-orders require the two testnet key variables in the harness environment. Dry-run still fetches authenticated account information.

```sh
/opt/anaconda3/bin/python run_tick.py --dry-run
/opt/anaconda3/bin/python run_tick.py \
  --dry-run --config config.example.json \
  --env-file credentials.env
/opt/anaconda3/bin/python run_tick.py --testnet-orders
/opt/anaconda3/bin/python run_week_close.py --dry-run
/opt/anaconda3/bin/python run_week_close.py --testnet-orders
/opt/anaconda3/bin/python -m pytest -q
```

`--testnet-orders` explicitly enables real testnet orders; it is mutually exclusive with `--dry-run` and cannot be combined with an offline fixture. Entry-point exit codes: 0 success, 2 safety refusal, 3 ban, 1 other failure. Malformed LLM output logs a no-action decision and returns 0.

For reproducible offline runs:

```sh
/opt/anaconda3/bin/python run_tick.py \
  --dry-run --offline-fixture fixture.json \
  --fake-llm decision.json --now 2024-01-01T12:00:00Z
/opt/anaconda3/bin/python run_week_close.py \
  --dry-run --offline-fixture fixture.json --now 2024-01-08T00:05:00Z
```

Fixture shape (klines are `[openTimeMs, open, high, low, close, volume, optionalCloseTimeMs]`; supply sufficient complete historical bars for indicators):

```json
{
  "account": {"equity": 50000, "positions": []},
  "premium_index": [{"symbol": "BTCUSDT", "markPrice": "100", "lastFundingRate": "0.0001"}],
  "symbol_info": {"BTCUSDT": {"tickSize": "0.01", "stepSize": "0.001", "minQty": 0.001, "minNotional": 5}},
  "candles": {"BTCUSDT": {"15m": [[1704109500000, 100, 101, 99, 100, 10]], "1h": [], "4h": [], "1d": []}},
  "open_interest": {"BTCUSDT": 1000}
}
```

`--now` must include a timezone. Omit it for real operation. Tests patch network and subprocess calls where appropriate; all market observations and execution responses are offline/mocked. Pytest temporary artifacts stay inside `.pytest_tmp/`.

## Scheduling templates (not installed)

Replace `/ABS/PROJECT` with this directory and configure credential delivery for the harness. Do not put secrets in the plist or in a file readable by the agent. This is the hourly tick plist template:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>experiment.futures.tick</string>
  <key>ProgramArguments</key><array>
    <string>/opt/anaconda3/bin/python</string><string>/ABS/PROJECT/run_tick.py</string><string>--dry-run</string>
  </array>
  <key>WorkingDirectory</key><string>/ABS/PROJECT</string>
  <key>StartInterval</key><integer>3600</integer>
  <key>StandardOutPath</key><string>/ABS/PROJECT/state/tick.stdout.log</string>
  <key>StandardErrorPath</key><string>/ABS/PROJECT/state/tick.stderr.log</string>
</dict></plist>
```

The weekly Monday 00:05 UTC week-close template below assumes the Mac's local timezone is UTC:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>experiment.futures.week-close</string>
  <key>ProgramArguments</key><array>
    <string>/opt/anaconda3/bin/python</string><string>/ABS/PROJECT/run_week_close.py</string><string>--dry-run</string>
  </array>
  <key>WorkingDirectory</key><string>/ABS/PROJECT</string>
  <key>StartCalendarInterval</key><dict>
    <key>Weekday</key><integer>1</integer><key>Hour</key><integer>0</integer><key>Minute</key><integer>5</integer>
  </dict>
</dict></plist>
```

**launchd uses local time**, not UTC scheduling through a TZ environment variable. On Asia/Seoul (UTC+9), Monday 00:05 UTC is Monday 09:05 local: change Hour to 9. For a timezone with daylight saving, adjust schedules when the offset changes or use a UTC-aware scheduler. The harness still evaluates UTC week boundaries regardless of invocation time. Create output directories before manually loading any plist. The templates intentionally do not install services.

Cron examples for a scheduler supporting `CRON_TZ` (set both scheduler and process timezone):

```cron
CRON_TZ=UTC
TZ=UTC
0 * * * * cd /ABS/PROJECT && /opt/anaconda3/bin/python run_tick.py --dry-run >> state/tick.stdout.log 2>&1
5 0 * * 1 cd /ABS/PROJECT && /opt/anaconda3/bin/python run_week_close.py --dry-run >> state/week.stdout.log 2>&1
```

`TZ=UTC` alone may change the process timezone without changing cron scheduling. macOS cron may not support CRON_TZ; run its scheduler in UTC or translate the weekly schedule to local time (Asia/Seoul: `5 9 * * 1`). No cron entry is added automatically.
