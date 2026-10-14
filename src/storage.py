"""SQLite experiment store with immutable dataset snapshots."""
import hashlib
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data" / "quantlab.sqlite"


class ExperimentStore:
    def __init__(self, path=None):
        self.path = Path(path or os.environ.get("QUANTLAB_DB_PATH", DEFAULT_PATH))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS datasets (hash TEXT PRIMARY KEY, csv TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS experiments (id TEXT PRIMARY KEY, owner TEXT NOT NULL, created TEXT NOT NULL, config TEXT NOT NULL, result TEXT NOT NULL, dataset_hash TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS drafts (owner TEXT PRIMARY KEY, payload TEXT NOT NULL);
            """)

    def connect(self):
        return sqlite3.connect(self.path, timeout=20)

    def save(self, owner, config, result, data):
        csv = data.to_csv(index_label="Date")
        fingerprint = hashlib.sha256(csv.encode()).hexdigest()
        identifier = uuid.uuid4().hex
        safe = {key: value for key, value in config.items() if key not in {"api_key", "csv_text"}}
        saved_result = {**result, "experiment_id": identifier, "dataset_hash": fingerprint, "engine_version": "3"}
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO datasets VALUES (?,?)", (fingerprint, csv))
            db.execute("INSERT INTO experiments VALUES (?,?,?,?,?,?)", (identifier, owner, datetime.now(timezone.utc).isoformat(), json.dumps(safe), json.dumps(saved_result, allow_nan=False), fingerprint))
        return saved_result

    def list(self, owner):
        with self.connect() as db:
            rows = db.execute("SELECT id,created,result FROM experiments WHERE owner=? ORDER BY created DESC LIMIT 100", (owner,)).fetchall()
        return [dict(id=identifier, created=created, ticker=r["ticker"], strategy=r["strategy_name"], metrics=r["metrics"], start=r["dates"][0], end=r["dates"][-1]) for identifier, created, text in rows for r in [json.loads(text)]]

    def get(self, owner, identifier):
        with self.connect() as db:
            row = db.execute("SELECT config,result,dataset_hash FROM experiments WHERE id=? AND owner=?", (identifier, owner)).fetchone()
        if not row:
            raise KeyError("Experiment not found.")
        return dict(config=json.loads(row[0]), result=json.loads(row[1]), dataset_hash=row[2])

    def dataset(self, owner, identifier):
        record = self.get(owner, identifier)
        with self.connect() as db:
            return db.execute("SELECT csv FROM datasets WHERE hash=?", (record["dataset_hash"],)).fetchone()[0]

    def save_draft(self, owner, payload):
        # Browser code deliberately omits keys; enforce this on the server too.
        payload = {key: value for key, value in payload.items() if key in {"fields", "parameters", "csvText", "csvName", "updatedAt"}}
        if not isinstance(payload.get("fields", {}), dict) or not isinstance(payload.get("parameters", {}), dict):
            raise ValueError("Draft fields and parameters must be objects.")
        payload["fields"] = {key: value for key, value in payload.get("fields", {}).items() if key != "api_key"}
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO drafts VALUES (?,?)", (owner, json.dumps(payload)))

    def draft(self, owner):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM drafts WHERE owner=?", (owner,)).fetchone()
        return json.loads(row[0]) if row else None
