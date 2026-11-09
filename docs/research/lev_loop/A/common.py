"""BACKTESTER-A shared setup (research only, offline)."""
import os, sys
SCR = "/private/tmp/claude-501/-Users-user-Desktop-CODE-Ochestration/b40d7700-4bab-493b-9b2c-b8bac464cd8e/scratchpad"
os.environ.setdefault("RS_FINAL_SCRATCH", SCR + "/panel")
os.environ.setdefault("NUMBA_CACHE_DIR", SCR + "/nbc")
sys.dont_write_bytecode = True
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.insert(0, ROOT)
import numpy as np, pandas as pd
from app.rs_final_data import load_panel
from app.rs_lev_a_engine import SimA, stress_panel
HERE = os.path.dirname(os.path.abspath(__file__))
