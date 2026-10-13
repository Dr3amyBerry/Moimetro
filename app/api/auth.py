"""Access control: the bootstrap admin creates staff accounts by API."""
from __future__ import annotations
import hashlib
import sqlite3
from collections import defaultdict
from time import monotonic
from typing import Dict, List, Literal, Optional
from typing_extensions import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from app.security import issue_token, only, require_user, verify_password, password_hash
from app.storage import audit, get_db, now, rows

router = APIRouter(prefix="/api")
DB = Annotated[sqlite3.Connection, Depends(get_db)]
User = Annotated[dict, Depends(require_user)]
Admin = Annotated[dict, Depends(only("admin"))]
_failed: Dict[str, List[float]] = defaultdict(list)

class Login(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=1, max_length=256)

@router.post("/auth/login")
def login(payload: Login, request: Request, response: Response, db: DB):
    key = (request.client.host if request.client else "unknown") + ":" + payload.username.casefold()
    instant = monotonic()
    _failed[key] = [t for t in _failed[key] if instant - t < 300]
    if len(_failed[key]) >= 5:
        raise HTTPException(429, "Demasiados intentos: espere cinco minutos.")
    user = db.execute("SELECT * FROM users WHERE username=?", (payload.username,)).fetchone()
    if not user or not user["active"] or not verify_password(payload.password, user["password_hash"]):
        _failed[key].append(instant)
        raise HTTPException(401, "Credenciales inválidas.")
    _failed.pop(key, None)
    token = issue_token(db, user["id"])
    audit(db, user["id"], "login", "user", user["id"])
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {"token": token, "username": user["username"], "role": user["role"],
            "expires_in": 28800}

@router.post("/auth/logout")
def logout(db: DB, user: User, authorization: str = Header()):
    hashed = hashlib.sha256(authorization[7:].strip().encode()).hexdigest()
    db.execute("DELETE FROM tokens WHERE token_hash=?", (hashed,))
    audit(db, user["id"], "logout", "user", user["id"])
    db.commit()
    return {"ok": True}

@router.get("/auth/me")
def whoami(user: User):
    return {"id": user["id"], "username": user["username"], "role": user["role"]}

class StaffCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=12, max_length=256)
    role: Literal["admin", "reception", "nurse", "clinician"]

@router.get("/admin/users")
def staff_directory(
    db: DB,
    admin: Admin,
    q: str = Query(default="", max_length=50),
    limit: int = Query(default=20, ge=1, le=50),
    before: Optional[int] = Query(default=None, ge=1),
):
    """Admin-only staff listing; passwords and sessions are never returned."""
    where = []
    params = []
    if q.strip():
        prefix = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        where.append("username LIKE ? ESCAPE '\\'")
        params.append(prefix)
    if before is not None:
        where.append("id < ?")
        params.append(before)
    query = ("SELECT id,username,role,active,created_at FROM users"
             + (" WHERE " + " AND ".join(where) if where else "")
             + " ORDER BY id DESC LIMIT ?")
    found = rows(db.execute(query, (*params, limit + 1)))
    has_more = len(found) > limit
    visible = found[:limit]
    audit(db, admin["id"], "list", "user", "directory")
    db.commit()
    return {"items": visible, "next_cursor": visible[-1]["id"] if has_more else None}


@router.post("/admin/users", status_code=201)
def create_staff(payload: StaffCreate, db: DB, admin: Admin):
    try:
        with db:
            cursor = db.execute(
                "INSERT INTO users(username,password_hash,role,created_at) VALUES(?,?,?,?)",
                (payload.username, password_hash(payload.password), payload.role, now()))
            audit(db, admin["id"], "create", "user", cursor.lastrowid)
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Usuario duplicado.")
    return {"id": cursor.lastrowid, "role": payload.role, "username": payload.username}

class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


@router.post("/auth/change-password")
def change_own_password(payload: PasswordChange, db: DB, user: User):
    """Require the current secret and invalidate *all* active sessions."""
    account = db.execute("SELECT password_hash FROM users WHERE id=?", (user["id"],)).fetchone()
    if not account or not verify_password(payload.current_password, account["password_hash"]):
        raise HTTPException(403, "Contraseña actual incorrecta.")
    if payload.current_password == payload.new_password:
        raise HTTPException(422, "La contraseña nueva debe ser diferente.")
    replacement = password_hash(payload.new_password)
    with db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("UPDATE users SET password_hash=? WHERE id=?", (replacement, user["id"]))
        db.execute("DELETE FROM tokens WHERE user_id=?", (user["id"],))
        audit(db, user["id"], "change_password", "user", user["id"])
    return {"ok": True, "sessions_revoked": True}


class StaffEdit(BaseModel):
    role: Optional[Literal["admin", "reception", "nurse", "clinician"]] = None
    active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=12, max_length=256)


@router.patch("/admin/users/{user_id}")
def update_staff(user_id: int, payload: StaffEdit, db: DB, admin: Admin):
    """Only admins can change staff; prevent self-lockout and revoke sessions."""
    if payload.role is None and payload.active is None and payload.password is None:
        raise HTTPException(422, "Indique un cambio.")
    new_hash = password_hash(payload.password) if payload.password is not None else None
    with db:
        db.execute("BEGIN IMMEDIATE")
        target = db.execute(
            "SELECT id,username,role,active FROM users WHERE id=?", (user_id,)
        ).fetchone()
        if not target:
            raise HTTPException(404, "Cuenta inexistente.")
        role = payload.role if payload.role is not None else target["role"]
        active = int(payload.active) if payload.active is not None else int(target["active"])
        if user_id == admin["id"]:
            if role != target["role"] or not active:
                raise HTTPException(409, "No puede quitarse su acceso administrador.")
            if new_hash is not None:
                raise HTTPException(409, "Cambie su contraseña desde su perfil.")
        if target["role"] == "admin" and target["active"] and (
            role != "admin" or not active
        ):
            count = db.execute(
                "SELECT COUNT(*) FROM users WHERE role='admin' AND active=1"
            ).fetchone()[0]
            if count <= 1:
                raise HTTPException(409, "Debe permanecer un administrador activo.")
        if new_hash is not None:
            db.execute(
                "UPDATE users SET role=?,active=?,password_hash=? WHERE id=?",
                (role, active, new_hash, user_id),
            )
        else:
            db.execute(
                "UPDATE users SET role=?,active=? WHERE id=?",
                (role, active, user_id),
            )
        changed_access = (role != target["role"] or active != target["active"] or
                          new_hash is not None)
        if changed_access:
            db.execute("DELETE FROM tokens WHERE user_id=?", (user_id,))
        audit(db, admin["id"], "update_access", "user", user_id)
    return {"id": user_id, "username": target["username"],
            "role": role, "active": bool(active),
            "sessions_revoked": changed_access}


@router.get("/admin/audit")
def recent_audit(db: DB, admin: Admin):
    return rows(db.execute("SELECT * FROM audit_events ORDER BY id DESC LIMIT 200"))
