"""Crear cuenta inicial: python -m app.manage create-admin --username admin"""
import argparse
import getpass
import sqlite3
from app.security import password_hash
from app.storage import connect, init_db, now

def main():
    parser = argparse.ArgumentParser(description="Administración local de Moímetro")
    commands = parser.add_subparsers(dest="command", required=True)
    admin = commands.add_parser("create-admin")
    admin.add_argument("--username", default="admin")
    args = parser.parse_args()
    username = args.username.strip()
    if not 3 <= len(username) <= 50 or not username.replace("_", "").isalnum():
        parser.error("Nombre de usuario inválido.")
    init_db()
    pw = getpass.getpass("Contraseña segura (mín. 12 caracteres): ")
    confirm = getpass.getpass("Repetir contraseña: ")
    if pw != confirm:
        parser.error("Las contraseñas no coinciden.")
    try:
        hashed = password_hash(pw)
    except ValueError as exc:
        parser.error(str(exc))
    try:
        with connect() as db:
            db.execute(
                "INSERT INTO users(username,password_hash,role,created_at) VALUES(?,?,?,?)",
                (username, hashed, "admin", now())
            )
    except sqlite3.IntegrityError:
        parser.error("Ese usuario ya existe.")
    print("Administrador creado.")

if __name__ == "__main__":
    main()
