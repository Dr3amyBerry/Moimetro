"""Local SQLite database for Moímetro. Keep all patient data outside Git."""
from __future__ import annotations
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def connect():
    file = Path(os.environ.get("MOIMETRO_DB_PATH", "data/moimetro.sqlite3")).expanduser().resolve()
    file.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(file), timeout=10, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=10000")
    return db

def get_db():
    db = connect()
    try:
        yield db
    finally:
        db.close()

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
 role TEXT NOT NULL CHECK(role IN ('admin','reception','nurse','clinician')),
 active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tokens (
 token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS patients (
 id INTEGER PRIMARY KEY, document_type TEXT NOT NULL, document_number TEXT NOT NULL,
 full_name TEXT NOT NULL, birth_date TEXT, phone TEXT, created_at TEXT NOT NULL,
 UNIQUE(document_type,document_number)
);
CREATE TABLE IF NOT EXISTS encounters (
 id INTEGER PRIMARY KEY, patient_id INTEGER NOT NULL REFERENCES patients(id),
 created_by INTEGER NOT NULL REFERENCES users(id), reason TEXT NOT NULL,
 assessment TEXT NOT NULL DEFAULT '', diagnosis TEXT NOT NULL DEFAULT '',
 treatment TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'open'
 CHECK(status IN ('open','closed')), opened_at TEXT NOT NULL, closed_at TEXT
);
CREATE TABLE IF NOT EXISTS capture_sessions (
 id TEXT PRIMARY KEY, encounter_id INTEGER NOT NULL REFERENCES encounters(id),
 device_id TEXT NOT NULL, started_at TEXT NOT NULL, ended_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS only_one_active_capture ON capture_sessions(device_id)
 WHERE ended_at IS NULL;
CREATE TABLE IF NOT EXISTS measurements (
 id INTEGER PRIMARY KEY, encounter_id INTEGER NOT NULL REFERENCES encounters(id),
 capture_session_id TEXT REFERENCES capture_sessions(id), device_id TEXT,
 kind TEXT NOT NULL CHECK(kind IN ('body_temp_c','pulse_bpm','spo2_pct','ambient_temp_c','humidity_pct')),
 value REAL, unit TEXT NOT NULL,
 quality TEXT NOT NULL CHECK(quality IN ('ok','no_contact','unavailable','error','stale')),
 origin TEXT NOT NULL CHECK(origin IN ('device','manual')),
 status TEXT NOT NULL CHECK(status IN ('pending','accepted','rejected')),
 notes TEXT NOT NULL DEFAULT '', received_at TEXT NOT NULL,
 accepted_at TEXT, accepted_by INTEGER REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_encounters_patient ON encounters(patient_id,opened_at);
CREATE INDEX IF NOT EXISTS idx_measurements_encounter ON measurements(encounter_id,received_at);
CREATE TABLE IF NOT EXISTS audit_events (
 id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id), action TEXT NOT NULL,
 resource TEXT NOT NULL, resource_id TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_events(created_at);
"""

def init_db():
    with connect() as db:
        db.executescript(SCHEMA)
        db.execute("PRAGMA journal_mode=WAL")

def audit(db, user_id, action, resource, resource_id):
    db.execute("INSERT INTO audit_events(user_id,action,resource,resource_id,created_at) VALUES(?,?,?,?,?)",
               (user_id, action, resource, str(resource_id), now()))

def rows(cursor):
    return [dict(row) for row in cursor.fetchall()]
