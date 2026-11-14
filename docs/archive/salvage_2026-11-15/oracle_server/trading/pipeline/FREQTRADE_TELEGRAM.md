# Freqtrade Telegram alerts (owner action, NOT done by the pipeline)

The pipeline has its own one-way notifier (`src/tp/notify.py`, `./run.sh notify ...`). Freqtrade's built-in Telegram
bot is different: it needs the bot token inside the Freqtrade container AND it accepts inbound commands. A Telegram
token was exposed in a log earlier, so wire this up only AFTER rotating it.

1. Rotate the token: BotFather -> `/revoke` (or `/token`) for the bot, then put the NEW token in `~/trading/.env`
   (owner-managed file; the pipeline never writes it). Update `pipeline/secrets/notify.env` too (see below).
2. Do not put the token into `config.json` (it is bind-mounted and easy to leak). Use a separate 600 env file that
   only the freqtrade service reads, e.g. `~/trading/freqtrade/telegram.env`:
   ```
   FREQTRADE__TELEGRAM__ENABLED=true
   FREQTRADE__TELEGRAM__TOKEN=<new token>
   FREQTRADE__TELEGRAM__CHAT_ID=<your chat id>
   ```
   `chmod 600 ~/trading/freqtrade/telegram.env`
3. Back up first: `cp ~/trading/docker-compose.yml ~/trading/docker-compose.yml.bak-$(date +%s)`
4. In `docker-compose.yml`, service `freqtrade`, add:
   ```
   env_file: ["./freqtrade/telegram.env"]
   ```
   (Freqtrade maps `FREQTRADE__TELEGRAM__*` env vars onto `config["telegram"]`.) Keep `dry_run: true`; `force_entry_enable`
   is already false so `/forcelong` etc. stay disabled. Freqtrade only answers the configured chat id.
5. Apply (only the owner): `cd ~/trading && docker compose up -d --force-recreate freqtrade`, then `/status` in Telegram.
6. Never `docker compose config` / `docker inspect` into a shared log after this: both print env values.

Notifier tokens for the pipeline live in `pipeline/secrets/notify.env` (600): `TP_TELEGRAM_BOT_TOKEN`, `TP_TELEGRAM_CHAT_ID`.
Re-create it from `.env` names (never print values):
`TELEGRAM_KHSQOWP_COINBOT_HTTP_API` -> `TP_TELEGRAM_BOT_TOKEN`, `TELEGRAM_USER_INFO_ID` -> `TP_TELEGRAM_CHAT_ID`.
