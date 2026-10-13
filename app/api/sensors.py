"""Acquisition API. Device readings require operator review; no automated medical triage."""
from __future__ import annotations
import math
import os
import secrets
import sqlite3
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.records import encounter_or_404
from app.security import only, require_device, require_user
from app.storage import audit, get_db, now, rows

router = APIRouter(prefix="/api")
DB = Annotated[sqlite3.Connection, Depends(get_db)]
User = Annotated[dict, Depends(require_user)]
CanRecord = Annotated[dict, Depends(only("nurse", "clinician", "admin"))]
Device = Annotated[str, Depends(require_device)]

@router.post("/encounters/{encounter_id}/capture", status_code=201)
def start_capture(encounter_id: int, db: DB, user: CanRecord):
    device_id = os.environ.get("MOIMETRO_DEVICE_ID", "esp32-01")
    session_id = secrets.token_urlsafe(18)
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            encounter = encounter_or_404(db, encounter_id)
            if encounter["status"] != "open":
                raise HTTPException(409, "Consulta cerrada.")
            db.execute(
                "INSERT INTO capture_sessions(id,encounter_id,device_id,started_at) VALUES(?,?,?,?)",
                (session_id, encounter_id, device_id, now()))
            audit(db, user["id"], "start", "capture", session_id)
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Este dispositivo ya tiene una sesión activa.")
    return {"session_id": session_id, "device_id": device_id}

@router.get("/encounters/{encounter_id}/capture")
def current_capture(encounter_id: int, db: DB, user: User):
    encounter_or_404(db, encounter_id)
    found = db.execute(
        "SELECT * FROM capture_sessions WHERE encounter_id=? ORDER BY started_at DESC LIMIT 1",
        (encounter_id,)).fetchone()
    return dict(found) if found else None

@router.post("/capture/{session_id}/stop")
def stop_capture(session_id: str, db: DB, user: CanRecord):
    with db:
        cursor = db.execute(
            "UPDATE capture_sessions SET ended_at=? WHERE id=? AND ended_at IS NULL",
            (now(), session_id))
        if cursor.rowcount == 0:
            raise HTTPException(404, "Sesión inexistente o finalizada.")
        audit(db, user["id"], "stop", "capture", session_id)
    return {"ok": True}

@router.get("/device/active-session")
def device_session(db: DB, device_id: Device):
    session = db.execute(
        "SELECT id FROM capture_sessions WHERE device_id=? AND ended_at IS NULL",
        (device_id,)).fetchone()
    return {"session_id": session["id"] if session else None}

Kind = Literal["body_temp_c", "pulse_bpm", "spo2_pct", "ambient_temp_c", "humidity_pct"]
Quality = Literal["ok", "no_contact", "unavailable", "error", "stale"]
UNITS = {
    "body_temp_c": "°C", "pulse_bpm": "BPM", "spo2_pct": "%",
    "ambient_temp_c": "°C", "humidity_pct": "%",
}
# Sanity bounds for corrupted input, NOT medical diagnosis or normal ranges.
BOUNDS = {
    "body_temp_c": (15, 50), "pulse_bpm": (20, 255), "spo2_pct": (0, 100),
    "ambient_temp_c": (-40, 80), "humidity_pct": (0, 100),
}

class DeviceSample(BaseModel):
    kind: Kind
    quality: Quality
    value: float | None = None

class DeviceBatch(BaseModel):
    session_id: str = Field(min_length=10, max_length=100)
    device_id: str = Field(min_length=1, max_length=80)
    samples: list[DeviceSample] = Field(min_length=1, max_length=10)

def validate_sample(kind: str, quality: str, value: float | None):
    if quality != "ok":
        if value is not None:
            raise HTTPException(422, "Una lectura inválida no puede incluir un número.")
        return
    if value is None or not math.isfinite(value):
        raise HTTPException(422, "Lectura sin número finito.")
    low, high = BOUNDS[kind]
    if not low <= value <= high:
        raise HTTPException(422, "Lectura fuera del rango físico de control.")

@router.post("/device/measurements", status_code=201)
def ingest_device(payload: DeviceBatch, db: DB, device_id: Device):
    if payload.device_id != device_id:
        raise HTTPException(403, "Identificador de dispositivo incorrecto.")
    # Never accept fabricated device oxygen saturation.
    if any(sample.kind == "spo2_pct" for sample in payload.samples):
        raise HTTPException(422, "SpO₂ por dispositivo deshabilitado hasta validación.")
    for sample in payload.samples:
        validate_sample(sample.kind, sample.quality, sample.value)
    with db:
        db.execute("BEGIN IMMEDIATE")
        capture = db.execute(
            """SELECT c.*,e.status AS encounter_status FROM capture_sessions c
               JOIN encounters e ON e.id=c.encounter_id
               WHERE c.id=? AND c.device_id=?""",
            (payload.session_id, device_id)).fetchone()
        if not capture or capture["ended_at"] or capture["encounter_status"] != "open":
            raise HTTPException(409, "No hay una sesión válida activa.")
        for sample in payload.samples:
            db.execute(
                """INSERT INTO measurements
                   (encounter_id,capture_session_id,device_id,kind,value,unit,quality,origin,status,received_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (capture["encounter_id"], payload.session_id, device_id,
                 sample.kind, sample.value, UNITS[sample.kind], sample.quality,
                 "device", "pending" if sample.quality == "ok" else "rejected", now()))
    return {"recorded": len(payload.samples), "status": "pending_review"}

@router.get("/measurements")
def readings(encounter_id: int, db: DB, user: User):
    encounter_or_404(db, encounter_id)
    result = rows(db.execute(
        "SELECT * FROM measurements WHERE encounter_id=? ORDER BY id DESC LIMIT 200",
        (encounter_id,)))
    audit(db, user["id"], "list", "measurements", encounter_id)
    db.commit()
    return result

@router.post("/measurements/{measurement_id}/accept")
def accept_reading(measurement_id: int, db: DB, user: CanRecord):
    with db:
        # Atomic compare-and-set; an already processed or closed visit never changes.
        cursor = db.execute(
            """UPDATE measurements SET status='accepted',accepted_at=?,accepted_by=?
               WHERE id=? AND status='pending' AND quality='ok'
               AND EXISTS (SELECT 1 FROM encounters e
                           WHERE e.id=measurements.encounter_id AND e.status='open')""",
            (now(), user["id"], measurement_id))
        if cursor.rowcount != 1:
            raise HTTPException(409, "Lectura inexistente, inválida, cerrada o ya procesada.")
        audit(db, user["id"], "accept", "measurement", measurement_id)
    return {"ok": True}

@router.post("/measurements/{measurement_id}/reject")
def reject_reading(measurement_id: int, db: DB, user: CanRecord):
    with db:
        cursor = db.execute(
            """UPDATE measurements SET status='rejected' WHERE id=? AND status='pending'
               AND EXISTS (SELECT 1 FROM encounters e
                           WHERE e.id=measurements.encounter_id AND e.status='open')""",
            (measurement_id,))
        if cursor.rowcount != 1:
            raise HTTPException(409, "Lectura inexistente, cerrada o ya procesada.")
        audit(db, user["id"], "reject", "measurement", measurement_id)
    return {"ok": True}

class ManualMeasurement(BaseModel):
    kind: Kind
    value: float
    notes: str = Field(min_length=8, max_length=500)

@router.post("/encounters/{encounter_id}/manual-measurements", status_code=201)
def add_manual(encounter_id: int, payload: ManualMeasurement, db: DB, user: CanRecord):
    validate_sample(payload.kind, "ok", payload.value)
    with db:
        db.execute("BEGIN IMMEDIATE")
        encounter = encounter_or_404(db, encounter_id)
        if encounter["status"] != "open":
            raise HTTPException(409, "Consulta cerrada.")
        cursor = db.execute(
            """INSERT INTO measurements
               (encounter_id,kind,value,unit,quality,origin,status,notes,received_at,accepted_at,accepted_by)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (encounter_id, payload.kind, payload.value, UNITS[payload.kind],
             "ok", "manual", "accepted", payload.notes, now(), now(), user["id"]))
        audit(db, user["id"], "manual", "measurement", cursor.lastrowid)
    return {"id": cursor.lastrowid, "origin": "manual"}

@router.get("/encounters/{encounter_id}/triage")
def triage_disabled(encounter_id: int, db: DB, user: User):
    encounter_or_404(db, encounter_id)
    return {
        "status": "not_validated", "priority": None,
        "message": "Triaje automatizado deshabilitado hasta validar protocolos y revisión clínica."
    }
