#!/usr/bin/env python3
"""V2 TRAIN runner; calculations are shared with the immutable V1 record."""

from __future__ import annotations

import volreg_r1_lib as research


research.RUNNER_PATH = research.Path(__file__).resolve()


if __name__ == "__main__":
    raise SystemExit(research.main())
