"""Patient registry and longitudinal encounter records. Offline only."""
from __future__ import annotations
import sqlite3
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.security import only, require_user
from app.storage import audit, get_db, now, rows

router = APIRouter(prefix="/api")
DB = Annotated[sqlite3.Connection, Depends(get_db)]
User = Annotated[dict, Depends(require_user)]
Clinician = Annotated[dict, Depends(only("clinician", "admin"))]

class PatientCreate(BaseModel):
    document_type: Literal["V", "E", "P", "OTRO"] = "V"
    document_number: str = Field(min_length=4, max_length=25, pattern=r"^[A-Za-z0-9-]+$")
    full_name: str = Field(min_length=2, max_length=150)
    birth_date: date | None = None
    phone: str | None = Field(default=None, max_length=40)

def patient_or_404(db, patient_id: int):
    row = db.execute("SELECT * FROM patients WHERE id=?", (patient_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Paciente inexistente.")
    return row

def encounter_or_404(db, encounter_id: int):
    row = db.execute("SELECT * FROM encounters WHERE id=?", (encounter_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Consulta inexistente.")
    return row

@router.get("/patients")
def list_patients(db: DB, user: User, q: str = Query(default="", max_length=100)):
    search = q.strip()
    if search:
        result = rows(db.execute(
            "SELECT * FROM patients WHERE document_number LIKE ? OR full_name LIKE ? ORDER BY full_name LIMIT 40",
            (f"%{search}%", f"%{search}%")
        ))
    else:
        result = rows(db.execute("SELECT * FROM patients ORDER BY id DESC LIMIT 30"))
    audit(db, user["id"], "search", "patients", "list")
    db.commit()
    return result

@router.post("/patients", status_code=201)
def new_patient(payload: PatientCreate, db: DB, user: User):
    number = payload.document_number.strip().upper()
    full_name = payload.full_name.strip()
    if len(full_name) < 2 or (payload.birth_date and payload.birth_date > date.today()):
        raise HTTPException(422, "Datos de paciente inválidos.")
    try:
        with db:
            cursor = db.execute(
                """INSERT INTO patients(document_type,document_number,full_name,birth_date,phone,created_at)
                   VALUES(?,?,?,?,?,?)""",
                (payload.document_type, number, full_name,
                 payload.birth_date.isoformat() if payload.birth_date else None,
                 payload.phone, now()))
            audit(db, user["id"], "create", "patient", cursor.lastrowid)
    except sqlite3.IntegrityError:
        raise HTTPException(409, "El documento ya está registrado.")
    return {"id": cursor.lastrowid}

@router.get("/patients/{patient_id}")
def get_patient(patient_id: int, db: DB, user: User):
    row = dict(patient_or_404(db, patient_id))
    audit(db, user["id"], "read", "patient", patient_id)
    db.commit()
    return row

class EncounterCreate(BaseModel):
    patient_id: int = Field(gt=0)
    reason: str = Field(min_length=3, max_length=1000)

@router.post("/encounters", status_code=201)
def new_encounter(payload: EncounterCreate, db: DB, user: User):
    patient_or_404(db, payload.patient_id)
    if len(payload.reason.strip()) < 3:
        raise HTTPException(422, "Indique el motivo de consulta.")
    with db:
        cursor = db.execute(
            "INSERT INTO encounters(patient_id,created_by,reason,opened_at) VALUES(?,?,?,?)",
            (payload.patient_id, user["id"], payload.reason.strip(), now()))
        audit(db, user["id"], "create", "encounter", cursor.lastrowid)
    return {"id": cursor.lastrowid}

@router.get("/encounters")
def patient_encounters(patient_id: int, db: DB, user: User):
    patient_or_404(db, patient_id)
    result = rows(db.execute(
        "SELECT * FROM encounters WHERE patient_id=? ORDER BY opened_at DESC,id DESC",
        (patient_id,)))
    audit(db, user["id"], "list", "encounter", patient_id)
    db.commit()
    return result

@router.get("/encounters/{encounter_id}")
def get_encounter(encounter_id: int, db: DB, user: User):
    row = dict(encounter_or_404(db, encounter_id))
    audit(db, user["id"], "read", "encounter", encounter_id)
    db.commit()
    return row

class ClinicalUpdate(BaseModel):
    assessment: str = Field(max_length=10000)
    diagnosis: str = Field(max_length=10000)
    treatment: str = Field(max_length=10000)

@router.patch("/encounters/{encounter_id}")
def update_encounter(encounter_id: int, payload: ClinicalUpdate, db: DB, user: Clinician):
    encounter = encounter_or_404(db, encounter_id)
    if encounter["status"] != "open":
        raise HTTPException(409, "No puede editarse una consulta cerrada.")
    with db:
        db.execute("UPDATE encounters SET assessment=?,diagnosis=?,treatment=? WHERE id=?",
                   (payload.assessment, payload.diagnosis, payload.treatment, encounter_id))
        audit(db, user["id"], "update", "encounter", encounter_id)
    return {"ok": True}

@router.post("/encounters/{encounter_id}/close")
def close_encounter(encounter_id: int, db: DB, user: Clinician):
    with db:
        db.execute("BEGIN IMMEDIATE")
        encounter = encounter_or_404(db, encounter_id)
        if encounter["status"] != "open":
            raise HTTPException(409, "Consulta ya cerrada.")
        active = db.execute(
            "SELECT COUNT(*) FROM capture_sessions WHERE encounter_id=? AND ended_at IS NULL",
            (encounter_id,)).fetchone()[0]
        if active:
            raise HTTPException(409, "Finalice la captura antes de cerrar.")
        db.execute("UPDATE encounters SET status='closed',closed_at=? WHERE id=?",
                   (now(), encounter_id))
        audit(db, user["id"], "close", "encounter", encounter_id)
    return {"ok": True}


class HistoryUpdate(BaseModel):
    allergies: str = Field(max_length=10000)
    background: str = Field(max_length=10000)

@router.get("/patients/{patient_id}/history")
def get_history(patient_id: int, db: DB, user: User):
    patient_or_404(db, patient_id)
    record = db.execute("SELECT * FROM patient_histories WHERE patient_id=?", (patient_id,)).fetchone()
    audit(db, user["id"], "read", "history", patient_id)
    db.commit()
    return dict(record) if record else {"patient_id": patient_id, "allergies": "", "background": "",
                                         "updated_at": None, "updated_by": None}

@router.put("/patients/{patient_id}/history")
def update_history(patient_id: int, payload: HistoryUpdate, db: DB, user: Clinician):
    patient_or_404(db, patient_id)
    with db:
        db.execute(
            """INSERT INTO patient_histories(patient_id,allergies,background,updated_at,updated_by)
               VALUES(?,?,?,?,?)
               ON CONFLICT(patient_id) DO UPDATE SET
               allergies=excluded.allergies,background=excluded.background,
               updated_at=excluded.updated_at,updated_by=excluded.updated_by""",
            (patient_id, payload.allergies, payload.background, now(), user["id"]))
        audit(db, user["id"], "update", "history", patient_id)
    return {"ok": True}


class PatientEdit(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    birth_date: date | None = None
    phone: str | None = Field(default=None, max_length=40)

@router.patch("/patients/{patient_id}")
def edit_patient(patient_id: int, payload: PatientEdit, db: DB, user: User):
    patient_or_404(db, patient_id)
    full_name = payload.full_name.strip()
    if len(full_name) < 2 or (payload.birth_date and payload.birth_date > date.today()):
        raise HTTPException(422, "Datos del paciente inválidos.")
    with db:
        db.execute("UPDATE patients SET full_name=?,birth_date=?,phone=? WHERE id=?",
                   (full_name, payload.birth_date.isoformat() if payload.birth_date else None,
                    payload.phone, patient_id))
        audit(db, user["id"], "update", "patient", patient_id)
    return {"ok": True}
