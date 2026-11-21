# Research dashboard ("strategy brain") — plan

Purpose: read-only visual status page for the strategy research. NOT a trading engine, no order paths,
no API keys. The user is non-specialist: the page must be readable without statistics jargon.

## Scope and stages
| Stage | What | Where | Exposure |
|-------|------|-------|----------|
| 1 | Build locally (Mac) from existing result files | `trading/research_dashboard/` | localhost only |
| 2 | Upload source to linuxserver, run as compose service | `docker-compose.trading.yml` profile `dashboard` | LAN only: `192.168.0.12:8765` |
| 3 | Public subdomain (later, after user says it is mature) | Cloudflare Tunnel route + auth | needs user to add route; protect with existing auth or Cloudflare Access |

Stage 2/3 are manual deploy (auto_deploy skips trading paths). Port 8765 was free on linuxserver (checked 2026-11-21).
Bind to the LAN IP explicitly (`192.168.0.12:8765:80`), never `0.0.0.0` publish through the tunnel until stage 3.

## What the page shows
- **Graph**: node = one strategy (spec id + timeframe + side). Edge = "behaves like" (see Edges). Layout = force graph, clusters visible.
  A cluster of 8 daily trend strategies must look like ONE blob, because it was one bet.
- **Colour = verdict**: gray not-tested/unimplemented, red failed, orange raw-pass but downgraded, yellow adjusted-pass,
  green forward-running, bright green forward-confirmed (none yet).
- **Node size = verification depth** (number of independent tests passed: null, plateau, adjusted, A1, B1..B6, execution
  stress, regime), NOT backtest return. Backtest return is a secondary number in the detail card only.
  Reason: sizing by return highlights the most overfit strategy.
- **Forward band (top of page, large)**: for each running paper forward test (l5_4h, l5_12h, jbb_1h): trades, days running,
  equity curve, vs backtest expectation, days/trades left to verdict threshold. This is the only real out-of-sample evidence.
- **Detail card** on click: one-sentence what it does (from archive spec), source URL, params, train/test return,
  null percentile, tests passed/failed with plain-language reasons, per-year bars (B1), forward status if any.
- **Always-visible counters**: total strategies archived (491), spec-complete (209), implemented/tested (~104), trials counted,
  and a fixed sentence: "x of y passed after multiple-testing correction". Prevents survivorship illusion.
- **Filters**: family, timeframe, verdict, symbol class. Default sort: verification depth, then forward result. Never default-sort by return.
- Plain-language legend and a "what does this mean" drawer. No unexplained acronyms on the main view.

## Data pipeline (static JSON, regenerated)
`build_data.py` reads (read-only):
- `trading/strategy_archive/*/strategies/*.json` (node metadata)
- `trading/scratchpad/strategy_bt/results/ledger.csv`, `results/slice_*/summary.csv`
- `verify/`, `verify2a/`, `verify2b/` csvs and REPORT verdicts; `regime/results/results.csv`
- forward tests: copy `forward.db` read-only from linuxserver (`rsync` of `trading-forward-test*/forward.db`, never write back),
  compute status via existing `forward_test.status` code.
Output: `dist/data.json` (+ `data.schema.md`). Frontend is a static `index.html` + ESM modules + locally vendored Three.js r160 and OrbitControls (no CDN, works offline on LAN). A deterministic in-repository 3D force layout places correlated strategies closer; metadata similarity remains explicitly approximate. Page auto-refreshes data.json every 60 s.
Server stage: tiny nginx container serves `dist/`; a sidecar loop (or cron on linuxserver) reruns `build_data.py` every 5 min
with forward DBs mounted read-only.

### Edges
- Phase 1 (cheap): similarity from metadata = same family + same timeframe + same symbol set + same direction.
- Phase 2: return-series correlation from per-strategy trade logs. The harness currently keeps summary rows only; trade logs
  must be exported (small harness change by Codex, no change to results). Edge if correlation > 0.5, thickness = correlation.
  Until then label edges "approximate (metadata similarity)".

## Implementation notes
- Owner: Codex implements, Claude reviews. Tests: schema validation of data.json, unit test that node size never reads return,
  snapshot test on a small fixture. Python 3 for builder (existing `bb_stoch_stc/.venv`).
- No secrets, no write access to forward DBs, no calls to exchanges.
- Nginx config: GET only, `Cache-Control: no-store` on data.json.
- Acceptance for stage 1: opens at `http://localhost:8765`, all 4 sections render with real data, a non-specialist can answer
  "which strategies are real winners?" correctly from the page (answer today: none confirmed).

## Stage 3 checklist (later, not now)
1. User confirms. 2. Auth in front (reuse `orchestration_session` JWT at `lab` or Cloudflare Access). 3. User adds Cloudflare route
(Tunnels -> Ochestration -> Routes -> Published application, service `http://<container>:80`). 4. Remove LAN-only bind note.
5. Confirm no internal paths/emails leak in data.json.
