"""Append-only prediction and experiment SQLite stores."""
import sqlite3
import json
from pathlib import Path

DATA = Path(__file__).parent / "data"


def connect_store(path=None):
    """Create predictions and scores tables with immutable prediction rows."""
    target = Path(path or DATA / "predictions.sqlite")
    target.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(target)
    db.executescript("""
    CREATE TABLE IF NOT EXISTS predictions(id INTEGER PRIMARY KEY, payload TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS scores(prediction_id INTEGER NOT NULL, payload TEXT NOT NULL,
      FOREIGN KEY(prediction_id) REFERENCES predictions(id));
    CREATE TRIGGER IF NOT EXISTS predictions_no_update BEFORE UPDATE ON predictions
      BEGIN SELECT RAISE(ABORT,'predictions are append-only'); END;
    CREATE TRIGGER IF NOT EXISTS predictions_no_delete BEFORE DELETE ON predictions
      BEGIN SELECT RAISE(ABORT,'predictions are append-only'); END;
    """)
    return db


def append_prediction(db, prediction):
    """Append one immutable JSON prediction and return its row id."""
    cur = db.execute("INSERT INTO predictions(payload) VALUES(?)",
                     (json.dumps(prediction, sort_keys=True, allow_nan=False),))
    db.commit()
    return cur.lastrowid


def record_score(db, prediction_id, score):
    """Append a deterministic score without changing its prediction."""
    db.execute("INSERT INTO scores VALUES(?,?)",
               (prediction_id, json.dumps(score, sort_keys=True, allow_nan=False)))
    db.commit()


def connect_trials(path=None):
    """Create trial registry with monotonically assigned IDs."""
    target = Path(path or DATA / "trials.sqlite")
    target.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(target)
    db.execute("CREATE TABLE IF NOT EXISTS trials(trial_id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "ts TEXT,model TEXT,prompt_version TEXT,code_sha TEXT,split TEXT,hypothesis TEXT,n_predictions INTEGER)")
    columns = {row[1] for row in db.execute("PRAGMA table_info(trials)")}
    if "data_fingerprint" not in columns:
        db.execute("ALTER TABLE trials ADD COLUMN data_fingerprint TEXT")
    db.commit()
    return db


def record_trial(db, ts, model, prompt_version, code_sha, split, hypothesis, n_predictions,
                 data_fingerprint=None):
    """Record one experiment or sealed-data access event."""
    cur = db.execute("INSERT INTO trials(ts,model,prompt_version,code_sha,split,hypothesis,n_predictions,data_fingerprint)"
                     " VALUES(?,?,?,?,?,?,?,?)", (ts, model, prompt_version, code_sha, split,
                                                   hypothesis, int(n_predictions), data_fingerprint))
    db.commit()
    return cur.lastrowid


def cumulative_trial_count(db):
    """Return the cumulative number of recorded trials."""
    return int(db.execute("SELECT COUNT(*) FROM trials").fetchone()[0])
