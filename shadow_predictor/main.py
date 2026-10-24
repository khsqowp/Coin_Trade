from __future__ import annotations

import os
import logging
import sqlite3
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from archive_store import ShadowArchiveStore
from core import KronosForecaster, atomic_write_json, process_snapshot, read_json


def main() -> None:
    source_path = Path(os.getenv("SHADOW_SOURCE_STATE", "/input/crypto_paper_strategies_6symbols.json"))
    output_path = Path(os.getenv("SHADOW_OUTPUT_STATE", "/output/shadow_predictions.json"))
    interval = max(5, int(os.getenv("SHADOW_POLL_SECONDS", "10")))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[RotatingFileHandler(output_path.parent / "shadow_predictor.log", maxBytes=2_000_000, backupCount=3),
                  logging.StreamHandler()],
    )
    logger = logging.getLogger("shadow_predictor")
    forecaster = KronosForecaster(
        model_id=os.getenv("KRONOS_MODEL_ID", "NeoQuasar/Kronos-mini"),
        tokenizer_id=os.getenv("KRONOS_TOKENIZER_ID", "NeoQuasar/Kronos-Tokenizer-2k"),
        context_length=min(300, int(os.getenv("KRONOS_CONTEXT_LENGTH", "300"))),
    )
    output = read_json(output_path) if output_path.exists() else {}
    default_archive_db = Path("/archive/shadow_archive.sqlite3")
    if not default_archive_db.parent.is_dir():
        default_archive_db = output_path.parent / "shadow_archive.sqlite3"
    archive_db_path = Path(os.getenv("SHADOW_ARCHIVE_DB", str(default_archive_db)))
    legacy_archive_db = output_path.parent / "shadow_archive.sqlite3"
    if archive_db_path.resolve() != legacy_archive_db.resolve() and legacy_archive_db.exists() and not archive_db_path.exists():
        archive_db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(legacy_archive_db) as old_db, sqlite3.connect(archive_db_path) as new_db:
            old_db.backup(new_db)
            integrity = new_db.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"legacy shadow archive migration failed integrity check: {integrity}")
        logger.info("migrated local archive spool from %s to %s; source retained", legacy_archive_db, archive_db_path)
    archive = ShadowArchiveStore(archive_db_path)
    try:
        imported = archive.record_output(output)
        logger.info("archive spool ready; imported_existing_events=%d", imported)
    except Exception:
        logger.exception("could not initialize shadow archive spool; forecasts continue without durable archive")
    logger.info("ready; input=%s; output=%s; poll=%ss", source_path, output_path, interval)
    while True:
        try:
            state = read_json(source_path)
            changed = process_snapshot(state, output, forecaster)
            try:
                archived = archive.record_output(output)
                if archived:
                    logger.info("durable archive spool added events=%d", archived)
            except Exception:
                logger.exception("could not persist shadow events to local archive spool")
            if changed:
                atomic_write_json(output_path, output)
                logger.info("updated source=%s pending=%d scores=%d", state.get("updated_at"),
                            len(output.get("pending", [])), len(output.get("scores", [])))
        except (FileNotFoundError, PermissionError, ValueError, OSError) as exc:
            logger.warning("shadow input/output error: %s: %s", type(exc).__name__, exc)
        except Exception:
            logger.exception("unhandled shadow predictor error")
        time.sleep(interval)


if __name__ == "__main__":
    main()
