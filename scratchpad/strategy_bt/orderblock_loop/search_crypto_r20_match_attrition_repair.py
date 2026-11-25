"""One preregistered repair execution of the R18 attrition-only diagnostic."""
from __future__ import annotations

import hashlib
from pathlib import Path

import search_crypto_r19_match_attrition_audit as core

HERE = Path(__file__).resolve().parent
core.ROUND = "R20-coin"
core.PREREG_PATH = HERE / "PREREG_R20_R18_MATCH_ATTRITION_REPAIR.md"
core.DETAIL_PREREG_NAME = core.PREREG_PATH.name
core.EXTRA_CODE_NAMES = ("search_crypto_r20_match_attrition_repair.py",)
core.LOCK_NAME = ".ob_attrition_train_trials.lock"
core.EXPECTED_ROWS = 1_676
core.EXPECTED_N = 1_677
core.CONFIG = {
    **core.CONFIG,
    "experiment": "R20-R18-CONTROL-CANDIDATE-ATTRITION-REPAIR",
    "bonferroni_n": core.EXPECTED_N,
}
core._PREREG_SHA = hashlib.sha256(core.PREREG_PATH.read_bytes()).hexdigest()
core._MASTER_SHA = hashlib.sha256(core.MASTER_PATH.read_bytes()).hexdigest()


if __name__ == "__main__":
    core.run()
