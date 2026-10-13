"""One-time local-first setup for the packaged desktop application.

Only the launcher provides MOIMETRO_SETUP_TOKEN. The secret is transferred in a
URL fragment, never in an HTTP request or access log, and used once.
"""
from __future__ import annotations

import hmac
import os
import sqlite3
from typing import Optional
from typing_extensions import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.security import password_hash
from app.storage import audit, get_db, now

router = APIRouter(prefix="/api/setup")
DB = Annotated[sqlite3.Connection, Depends(get_db)]


class InitialAdmin(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=12, max_length=256)


@router.get("/status")
def setup_status(db: DB):
    remaining = db.execute("SELECT NOT EXISTS(SELECT 1 FROM users LIMIT 1)").fetchone()[0]
    secret = os.environ.get("MOIMETRO_SETUP_TOKEN", "")
    return {"required": bool(remaining), "available": bool(remaining and len(secret) >= 32)}


@router.post("/admin", status_code=201)
def setup_initial_admin(
    payload: InitialAdmin,
    request: Request,
    db: DB,
    x_setup_token: Optional[str] = Header(default=None),
):
    # This route is intentionally unavailable on LAN and from plain Uvicorn.
    host = request.client.host if request.client else ""
    if host not in ("127.0.0.1", "::1"):
        raise HTTPException(403, "Configuración inicial solo desde este equipo.")
    expected = os.environ.get("MOIMETRO_SETUP_TOKEN", "")
    if len(expected) < 32 or not x_setup_token or not hmac.compare_digest(
        expected, x_setup_token
    ):
        raise HTTPException(403, "Token de configuración inválido.")
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                raise HTTPException(409, "El sistema ya está configurado.")
            new_user = db.execute(
                "INSERT INTO users(username,password_hash,role,created_at) VALUES(?,?,?,?)",
                (payload.username, password_hash(payload.password), "admin", now()),
            )
            audit(db, new_user.lastrowid, "bootstrap", "user", new_user.lastrowid)
    except sqlite3.IntegrityError:
        raise HTTPException(409, "El usuario ya existe.")
    # Revoke the one-time token as soon as the initial account is created.
    os.environ.pop("MOIMETRO_SETUP_TOKEN", None)
    return {"ok": True, "username": payload.username}
