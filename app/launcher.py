"""Windows launcher for the self-contained, per-user Moímetro desktop installer.

The exe starts a loopback-only service, opens the installed browser and keeps a
small taskbar controller. No Python installation, terminal, admin elevation or
internet connection is required at runtime.
"""
from __future__ import annotations

import json
import multiprocessing
import os
import secrets
import socket
import subprocess
import sys
import threading
import traceback
import urllib.request
import webbrowser
from pathlib import Path

PORT = 8765
URL = "http://127.0.0.1:{}".format(PORT)


def user_data_dir() -> Path:
    """Keep files outside Program Files; upgrading/uninstalling preserves data."""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        if not base:
            base = str(Path.home() / "AppData" / "Local")
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "Moimetro"


def configure_user_data() -> Path:
    base = user_data_dir()
    data = base / "data"
    data.mkdir(parents=True, exist_ok=True)
    # The installer cannot silently redirect the DB to bundled Program Files.
    os.environ["MOIMETRO_DB_PATH"] = str(data / "moimetro.sqlite3")
    return base


def installed_browsers():
    """Prioritize installed standalone browsers; IE is not compatible with the UI."""
    roots = [os.environ.get("PROGRAMFILES", ""),
             os.environ.get("PROGRAMFILES(X86)", ""),
             os.environ.get("LOCALAPPDATA", "")]
    relative = [
        "Mozilla Firefox/firefox.exe",
        "Microsoft/Edge/Application/msedge.exe",
        "Google/Chrome/Application/chrome.exe",
    ]
    seen = set()
    for relative_path in relative:
        for root in roots:
            if not root:
                continue
            path = Path(root) / relative_path
            normalized = str(path).lower()
            if normalized not in seen and path.is_file():
                seen.add(normalized)
                yield path


def open_ui(address):
    for candidate in installed_browsers():
        try:
            subprocess.Popen([str(candidate), address], close_fds=True)
            return True
        except OSError:
            continue
    return bool(webbrowser.open(address, new=1))


def wait_for_ready(timeout_seconds=12):
    """Only verify that our service is alive; never send a setup token in HTTP."""
    import time
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(URL + "/api/health", timeout=0.3) as response:
                body = json.loads(response.read().decode("utf-8"))
                if body.get("status") == "ok" and body.get("network_mode") == "local":
                    return True
        except (OSError, ValueError, RuntimeError):
            time.sleep(0.15)
    return False


def main():
    multiprocessing.freeze_support()
    if os.name != "nt":
        raise SystemExit("El instalador de escritorio es para Windows.")
    import tkinter as tk
    from tkinter import messagebox
    try:
        user_dir = configure_user_data()
        # No SO_REUSEADDR: never reuse another user's loopback service.
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            listener.bind(("127.0.0.1", PORT))
            listener.listen(100)
        except OSError:
            listener.close()
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo("Moímetro",
                                "Moímetro ya está abierto o el puerto local está ocupado.")
            root.destroy()
            return
    except OSError as error:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Moímetro", "No se pudo preparar el almacenamiento: {}".format(error))
        root.destroy()
        return

    # The setup token lives only in process memory and in a browser URL fragment.
    token = secrets.token_urlsafe(32)
    os.environ["MOIMETRO_SETUP_TOKEN"] = token
    from app.main import app
    import uvicorn

    config = uvicorn.Config(app, host="127.0.0.1", port=PORT,
                            log_config=None, access_log=False,
                            server_header=False, workers=1)
    server = uvicorn.Server(config)
    failure = []

    def serve():
        try:
            server.run(sockets=[listener])
        except Exception:
            failure.append(traceback.format_exc())
        finally:
            listener.close()

    thread = threading.Thread(target=serve, daemon=True, name="moimetro-local-api")
    thread.start()

    root = tk.Tk()
    root.title("Moímetro")
    root.geometry("360x193")
    root.resizable(False, False)
    root.configure(bg="#f4f5f6")
    root.option_add("*Font", "SegoeUI 10")
    tk.Label(root, text="Moímetro", bg="#f4f5f6", fg="#292d32",
             font=("Segoe UI", 16, "bold")).pack(pady=(23, 5))
    status = tk.StringVar(value="Iniciando servicio local...")
    tk.Label(root, textvariable=status, bg="#f4f5f6", fg="#535b64",
             wraplength=330).pack(pady=(0, 13))
    actions = tk.Frame(root, bg="#f4f5f6")
    actions.pack()

    def reopen():
        if not open_ui(URL):
            messagebox.showwarning("Moímetro",
                                   "Se necesita un navegador compatible (Firefox, Edge o Chrome).\n"
                                   "Internet Explorer no es compatible.")

    open_button = tk.Button(actions, text="Abrir programa", command=reopen,
                            state="disabled", padx=14, pady=5)
    open_button.pack(side="left", padx=5)

    def finish():
        status.set("Cerrando Moímetro...")
        open_button.configure(state="disabled")
        server.should_exit = True
        def check_closed():
            if thread.is_alive():
                root.after(100, check_closed)
            else:
                root.destroy()
        root.after(100, check_closed)

    tk.Button(actions, text="Salir", command=finish,
              padx=18, pady=5).pack(side="left", padx=5)
    root.protocol("WM_DELETE_WINDOW", finish)

    def startup_check():
        if failure:
            status.set("Error al iniciar el servicio.")
            # Only local troubleshooting data; never copy patient records to logs.
            try:
                log_dir = user_dir / "logs"
                log_dir.mkdir(parents=True, exist_ok=True)
                (log_dir / "startup.log").write_text(failure[0], encoding="utf-8")
            except OSError:
                pass
            messagebox.showerror("Moímetro", "Error al iniciar. Consulte la carpeta de registros.")
            finish()
            return
        if not thread.is_alive():
            status.set("No se pudo iniciar el servicio local.")
            return
        if wait_for_ready(timeout_seconds=0.4):
            status.set("Programa en ejecución. Puede minimizar esta ventana.")
            open_button.configure(state="normal")
            target = URL + "/#setup=" + token
            if open_ui(target):
                root.iconify()
            else:
                messagebox.showwarning("Moímetro",
                                       "Instale un navegador compatible y pulse Abrir programa.")
            return
        root.after(350, startup_check)

    root.after(200, startup_check)
    root.mainloop()


if __name__ == "__main__":
    main()
