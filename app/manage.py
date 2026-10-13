"""Operaciones administrativas locales: cuentas y copias de seguridad."""
import argparse
import getpass
import sqlite3
from pathlib import Path
from urllib.parse import quote

from app.security import password_hash
from app.storage import connect, db_path, init_db, now


def create_admin(username: str, parser):
    username = username.strip()
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
                (username, hashed, "admin", now()))
    except sqlite3.IntegrityError:
        parser.error("Ese usuario ya existe.")
    print("Administrador creado.")


def check_backup(path: Path):
    path = path.expanduser().resolve()
    if not path.is_file():
        raise ValueError("No existe el archivo de respaldo.")
    # Explicit read-only access prevents accidentally creating an empty SQLite file.
    uri = "file:" + quote(str(path), safe="/:") + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as db:
        status = db.execute("PRAGMA integrity_check").fetchone()[0]
        if status != "ok":
            raise ValueError("Integridad SQLite incorrecta: " + status)
        essential = {"patients", "encounters", "measurements", "users"}
        present = {
            row[0] for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")
        }
        if not essential.issubset(present):
            raise ValueError("La copia no contiene el esquema Moímetro.")
    print("Integridad SQLite correcta (no valida la recuperación operativa).")


def backup_to(path: Path):
    init_db()
    dest = path.expanduser().resolve()
    if dest == db_path():
        raise ValueError("El respaldo no puede reemplazar la base en uso.")
    if dest.exists():
        raise ValueError("El archivo de respaldo ya existe: no se sobrescribirá.")
    if dest.suffix.lower() not in {".sqlite3", ".db"}:
        raise ValueError("Use extensión .sqlite3 o .db.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with connect() as source, sqlite3.connect(dest) as target:
            source.backup(target)
        try:
            dest.chmod(0o600)
        except OSError:
            pass  # Windows ACLs must be configured separately.
        check_backup(dest)
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    print("Respaldo creado: " + str(dest))
    print("Atención: el respaldo NO está cifrado; guárdelo en medio seguro.")


def main():
    parser = argparse.ArgumentParser(description="Administración local de Moímetro")
    sub = parser.add_subparsers(dest="command", required=True)
    admin = sub.add_parser("create-admin", help="Crear administrador")
    admin.add_argument("--username", default="admin")
    copy = sub.add_parser("backup", help="Crear copia coherente de SQLite")
    copy.add_argument("--output", required=True, type=Path)
    verify = sub.add_parser("verify-backup", help="Comprobar integridad estructural de copia")
    verify.add_argument("--input", required=True, type=Path)
    args = parser.parse_args()

    try:
        if args.command == "create-admin":
            create_admin(args.username, parser)
        elif args.command == "backup":
            backup_to(args.output)
        elif args.command == "verify-backup":
            check_backup(args.input)
    except (OSError, sqlite3.Error, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
