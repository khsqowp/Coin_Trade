from __future__ import annotations

import os
import logging
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

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
    logger.info("ready; input=%s; output=%s; poll=%ss", source_path, output_path, interval)
    while True:
        try:
            state = read_json(source_path)
            changed = process_snapshot(state, output, forecaster)
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
