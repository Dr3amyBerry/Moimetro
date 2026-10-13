"""User authorization and device credential validation."""
from __future__ import annotations
import hashlib
import hmac
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException
from app.storage import get_db

ITERATIONS = 600_000
TOKEN_HOURS = 8

def password_hash(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Se requieren mínimo 12 caracteres.")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return "pbkdf2_sha256$%d$%s$%s" % (ITERATIONS, salt.hex(), digest.hex())

def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, rounds, salt, digest = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        comparison = hashlib.pbkdf2_hmac("sha256", password.encode(),
                                         bytes.fromhex(salt), int(rounds))
        return hmac.compare_digest(comparison, bytes.fromhex(digest))
    except (ValueError, TypeError):
        return False

def issue_token(db: sqlite3.Connection, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expiration = (datetime.now(timezone.utc) + timedelta(hours=TOKEN_HOURS)).isoformat()
    db.execute("INSERT INTO tokens(token_hash,user_id,expires_at) VALUES(?,?,?)",
               (token_hash, user_id, expiration))
    return token

def require_user(authorization: str | None = Header(default=None),
                 db: sqlite3.Connection = Depends(get_db)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Debe iniciar sesión.")
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(401, "Token inválido.")
    hashed = hashlib.sha256(token.encode()).hexdigest()
    found = db.execute(
        """SELECT u.id,u.username,u.role,u.active FROM tokens t
           JOIN users u ON u.id=t.user_id
           WHERE t.token_hash=? AND t.expires_at>?""",
        (hashed, datetime.now(timezone.utc).isoformat())
    ).fetchone()
    if not found or not found["active"]:
        raise HTTPException(401, "Sesión vencida o inválida.")
    return dict(found)

def only(*roles):
    def dependency(user: dict = Depends(require_user)):
        if user["role"] not in roles:
            raise HTTPException(403, "Permiso insuficiente.")
        return user
    return dependency

def require_device(x_device_key: str | None = Header(default=None)) -> str:
    expected = os.environ.get("MOIMETRO_DEVICE_KEY", "")
    if len(expected) < 32:
        raise HTTPException(503, "Clave de dispositivo no configurada.")
    if not x_device_key or not hmac.compare_digest(x_device_key, expected):
        raise HTTPException(401, "Dispositivo no autorizado.")
    return os.environ.get("MOIMETRO_DEVICE_ID", "esp32-01")
