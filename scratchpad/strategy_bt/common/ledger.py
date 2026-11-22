"""Append-safe CSV ledger using an advisory POSIX file lock."""
import csv, fcntl, os
from pathlib import Path

FIELDS=["strategy_id","timeframe","n_candidates_tested","n_slice_strategies","raw_requirement_percentile","adjusted_requirement_percentile","timestamp_utc"]
def append_row(path,row):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("a+",newline="",encoding="utf-8") as f:
        fcntl.flock(f.fileno(),fcntl.LOCK_EX); f.seek(0,os.SEEK_END); empty=f.tell()==0
        w=csv.DictWriter(f,fieldnames=FIELDS,extrasaction="ignore")
        if empty:w.writeheader()
        w.writerow({k:row.get(k,"") for k in FIELDS}); f.flush(); os.fsync(f.fileno()); fcntl.flock(f.fileno(),fcntl.LOCK_UN)
