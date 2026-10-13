"""Integration tests use fictional identities and disposable local SQLite databases."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.security import password_hash
from app.storage import connect, now


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MOIMETRO_DB_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("MOIMETRO_DEVICE_KEY", "local-testing-only-device-key-32chars")
    monkeypatch.setenv("MOIMETRO_DEVICE_ID", "esp32-01")
    with TestClient(app) as test:
        with connect() as db:
            db.execute(
                "INSERT INTO users(username,password_hash,role,created_at) VALUES(?,?,?,?)",
                ("admin", password_hash("password-for-test-admin-123"), "admin", now()),
            )
        yield test


def login(client, user="admin", password="password-for-test-admin-123"):
    response = client.post("/api/auth/login", json={"username": user, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["token"]}


def patient(client, headers):
    response = client.post("/api/patients", headers=headers, json={
        "document_type": "V", "document_number": "12345678",
        "full_name": "Paciente de Prueba", "birth_date": "2000-01-15",
    })
    assert response.status_code == 201, response.text
    return response.json()["id"]


def visit(client, headers, patient_id):
    response = client.post("/api/encounters", headers=headers, json={
        "patient_id": patient_id, "reason": "Consulta ficticia para pruebas"
    })
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_authentication_and_unique_document(client):
    assert client.get("/api/patients").status_code == 401
    wrong = client.post("/api/auth/login", json={"username": "admin", "password": "incorrecta"})
    assert wrong.status_code == 401
    headers = login(client)
    pid = patient(client, headers)
    lookup = client.get(f"/api/patients/{pid}", headers=headers)
    assert lookup.json()["document_number"] == "12345678"
    duplicate = client.post("/api/patients", headers=headers, json={
        "document_type": "V", "document_number": "12345678",
        "full_name": "Nombre Duplicado",
    })
    assert duplicate.status_code == 409


def test_capture_patient_identity_and_close(client):
    headers = login(client)
    patient_id = patient(client, headers)
    encounter_id = visit(client, headers, patient_id)
    r = client.post(f"/api/encounters/{encounter_id}/capture", headers=headers)
    assert r.status_code == 201
    session = r.json()["session_id"]
    assert client.post(f"/api/encounters/{encounter_id}/capture", headers=headers).status_code == 409
    device_headers = {"X-Device-Key": "local-testing-only-device-key-32chars"}
    assert client.get("/api/device/active-session", headers=device_headers).json()["session_id"] == session
    batch = {"session_id": session, "device_id": "esp32-01",
             "samples": [{"kind": "pulse_bpm", "quality": "ok", "value": 78.0}]}
    assert client.post("/api/device/measurements", headers=device_headers,
                       json=batch).status_code == 201
    measurements = client.get("/api/measurements", headers=headers,
                              params={"encounter_id": encounter_id}).json()
    reading = measurements[0]
    assert reading["encounter_id"] == encounter_id
    assert reading["origin"] == "device" and reading["status"] == "pending"
    assert client.post(f"/api/measurements/{reading['id']}/accept", headers=headers).status_code == 200
    assert client.post(f"/api/measurements/{reading['id']}/accept", headers=headers).status_code == 409
    assert client.post(f"/api/encounters/{encounter_id}/close", headers=headers).status_code == 409
    # A still-pending reading cannot be accepted after the visit has closed.
    assert client.post("/api/device/measurements", headers=device_headers,
                       json=batch).status_code == 201
    pending_id = client.get("/api/measurements", headers=headers,
                            params={"encounter_id": encounter_id}).json()[0]["id"]
    assert client.post(f"/api/capture/{session}/stop", headers=headers).status_code == 200
    assert client.post(f"/api/encounters/{encounter_id}/close", headers=headers).status_code == 200
    assert client.post(f"/api/measurements/{pending_id}/accept", headers=headers).status_code == 409
    assert client.post("/api/device/measurements", headers=device_headers,
                       json=batch).status_code == 409


def test_device_spo2_rejected_and_sensor_invalidity(client):
    headers = login(client)
    encounter_id = visit(client, headers, patient(client, headers))
    session = client.post(f"/api/encounters/{encounter_id}/capture", headers=headers).json()["session_id"]
    device = {"X-Device-Key": "local-testing-only-device-key-32chars"}
    base = {"session_id": session, "device_id": "esp32-01"}
    fake_spo2 = {**base, "samples": [{"kind": "spo2_pct", "quality": "ok", "value": 98}]}
    assert client.post("/api/device/measurements", headers=device,
                       json=fake_spo2).status_code == 422
    invalid = {**base, "samples": [{"kind": "pulse_bpm", "quality": "no_contact", "value": 0}]}
    assert client.post("/api/device/measurements", headers=device,
                       json=invalid).status_code == 422
    signal_lost = {**base, "samples": [{"kind": "pulse_bpm", "quality": "no_contact", "value": None}]}
    assert client.post("/api/device/measurements", headers=device,
                       json=signal_lost).status_code == 201
    assert client.get("/api/measurements", headers=headers,
                      params={"encounter_id": encounter_id}).json()[0]["status"] == "rejected"
    assert client.get(f"/api/encounters/{encounter_id}/triage", headers=headers).json()["priority"] is None


def test_roles_manual_provenance_and_closed_immutability(client):
    headers = login(client)
    encounter_id = visit(client, headers, patient(client, headers))
    manual = client.post(f"/api/encounters/{encounter_id}/manual-measurements", headers=headers,
                         json={"kind": "spo2_pct", "value": 97, "notes": "Oxímetro externo de prueba"})
    assert manual.status_code == 201
    reading = client.get("/api/measurements", params={"encounter_id": encounter_id},
                         headers=headers).json()[0]
    assert reading["origin"] == "manual" and reading["status"] == "accepted"
    new = client.post("/api/admin/users", headers=headers, json={
        "username": "recepcionista", "password": "password-for-reception-123", "role": "reception"
    })
    assert new.status_code == 201
    limited = login(client, "recepcionista", "password-for-reception-123")
    assert client.post(f"/api/encounters/{encounter_id}/manual-measurements", headers=limited,
                       json={"kind": "pulse_bpm", "value": 80, "notes": "Dispositivo externo"}).status_code == 403
    assert client.patch(f"/api/encounters/{encounter_id}", headers=limited,
                        json={"assessment": "", "diagnosis": "", "treatment": ""}).status_code == 403
    assert client.post(f"/api/encounters/{encounter_id}/close", headers=headers).status_code == 200
    assert client.patch(f"/api/encounters/{encounter_id}", headers=headers,
                        json={"assessment": "Después", "diagnosis": "",
                              "treatment": ""}).status_code == 409


def test_patient_history_is_private_and_role_protected(client):
    admin = login(client)
    pid = patient(client, admin)
    empty = client.get(f"/api/patients/{pid}/history", headers=admin)
    assert empty.status_code == 200
    assert empty.json()["allergies"] == ""
    saved = client.put(f"/api/patients/{pid}/history", headers=admin, json={
        "allergies": "Alergia sintética para pruebas",
        "background": "Antecedente ficticio, sin paciente real",
    })
    assert saved.status_code == 200
    result = client.get(f"/api/patients/{pid}/history", headers=admin).json()
    assert result["background"].startswith("Antecedente ficticio")
    staff = client.post("/api/admin/users", headers=admin, json={
        "username": "readonly_staff", "password": "password-for-reception-123",
        "role": "reception",
    })
    assert staff.status_code == 201
    limited = login(client, "readonly_staff", "password-for-reception-123")
    denied = client.put(f"/api/patients/{pid}/history", headers=limited, json={
        "allergies": "", "background": "",
    })
    assert denied.status_code == 403


def test_consistent_backup_and_repeated_backup_refused(client, tmp_path):
    from app.manage import backup_to, check_backup
    import sqlite3
    admin = login(client)
    patient(client, admin)
    location = tmp_path / "backup.sqlite3"
    backup_to(location)
    check_backup(location)
    with sqlite3.connect(location) as copied:
        assert copied.execute("SELECT COUNT(*) FROM patients").fetchone()[0] == 1
    with pytest.raises(ValueError, match="existe"):
        backup_to(location)


def test_installer_first_run_requires_loopback_and_one_time_token(client, monkeypatch):
    from types import SimpleNamespace
    from app.api.setup import InitialAdmin, setup_initial_admin
    from app.storage import connect
    token = "one-time-test-token-with-more-than-32-chars"
    monkeypatch.setenv("MOIMETRO_SETUP_TOKEN", token)
    with connect() as db:
        db.execute("DELETE FROM users")
    status = client.get("/api/setup/status")
    assert status.status_code == 200
    assert status.json() == {"required": True, "available": True}
    # TestClient has host 'testclient': it must NOT be allowed to initialize accounts.
    request = {"username": "localadmin", "password": "test-admin-password-123"}
    assert client.post("/api/setup/admin", json=request, headers={
        "X-Setup-Token": token
    }).status_code == 403
    with connect() as db:
        result = setup_initial_admin(
            InitialAdmin(**request),
            SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
            db,
            x_setup_token=token,
        )
        assert result["ok"] is True
        row = db.execute("SELECT username,role FROM users").fetchone()
        assert row["username"] == "localadmin" and row["role"] == "admin"
    assert client.get("/api/setup/status").json()["required"] is False
    assert "MOIMETRO_SETUP_TOKEN" not in __import__("os").environ


def test_windows_launcher_uses_per_user_persistent_storage(tmp_path, monkeypatch):
    from app.launcher import configure_user_data
    from app.storage import db_path
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    folder = configure_user_data()
    assert folder.name == "Moimetro"
    assert db_path().parent == folder / "data"
    assert db_path().parent.is_dir()
    assert "Moimetro" in str(db_path())


def test_large_directory_seek_pagination_and_filters(client):
    """Every API response remains bounded; no full patient table in the browser."""
    headers = login(client)
    from app.storage import connect, now
    with connect() as db:
        db.executemany(
            """INSERT INTO patients(document_type,document_number,full_name,created_at)
               VALUES(?,?,?,?)""",
            [("V" if n % 2 == 0 else "E",
              "99{:05d}".format(n),
              "Paciente sintético {:05d}".format(n), now())
             for n in range(213)]
        )
    assert client.get("/api/patients/directory").status_code == 401
    seen = []
    before = None
    for _ in range(10):
        params = {"limit": 25}
        if before:
            params["before"] = before
        response = client.get("/api/patients/directory", headers=headers, params=params)
        assert response.status_code == 200, response.text
        page = response.json()
        assert len(page["items"]) <= 25
        seen.extend(patient["id"] for patient in page["items"])
        assert seen == sorted(seen, reverse=True)
        before = page["next_cursor"]
        if before is None:
            break
    assert len(seen) == 213 and len(set(seen)) == 213
    assert before is None

    filtered = client.get("/api/patients/directory", headers=headers, params={
        "document_type": "E", "q": "9900", "limit": 50
    })
    assert filtered.status_code == 200
    assert all(item["document_type"] == "E" and
               item["document_number"].startswith("9900")
               for item in filtered.json()["items"])
    assert client.get("/api/patients/directory", headers=headers,
                      params={"limit": 100}).status_code == 422
    assert client.get("/api/patients/directory", headers=headers,
                      params={"before": -1}).status_code == 422
    assert client.get("/api/patients/directory", headers=headers,
                      params={"document_type": "invalid"}).status_code == 422

    # Search characters are literal, not uncontrolled SQL LIKE wildcards.
    for term in ("%", "_", "\\"):
        result = client.get("/api/patients/directory", headers=headers,
                            params={"q": term})
        assert result.status_code == 200
        assert result.json()["items"] == []


def test_long_patient_history_is_paginated_and_scoped(client):
    headers = login(client)
    from app.storage import connect, now
    with connect() as db:
        db.executemany(
            """INSERT INTO patients(document_type,document_number,full_name,created_at)
               VALUES(?,?,?,?)""",
            [("V", "88{:05d}".format(i), "Paciente simulado {}".format(i), now())
             for i in range(2)]
        )
        patients = [r[0] for r in db.execute("SELECT id FROM patients ORDER BY id")]
        user_id = db.execute("SELECT id FROM users LIMIT 1").fetchone()[0]
        db.executemany(
            """INSERT INTO encounters(patient_id,created_by,reason,opened_at)
               VALUES(?,?,?,?)""",
            [(patients[0], user_id, "Consulta sintética", now()) for _ in range(63)]
            + [(patients[1], user_id, "Otra historia", now()) for _ in range(3)]
        )
        indices = {
            index[1] for index in db.execute("PRAGMA index_list('patients')")
        }
        assert "idx_patients_name_prefix" in indices
        assert "idx_patients_document_prefix" in indices

    seen = []
    before = None
    for _ in range(5):
        params = {"patient_id": patients[0], "limit": 15}
        if before is not None:
            params["before"] = before
        response = client.get("/api/encounters/directory", headers=headers, params=params)
        assert response.status_code == 200
        page = response.json()
        assert len(page["items"]) <= 15
        assert all(visit["patient_id"] == patients[0] for visit in page["items"])
        seen.extend(visit["id"] for visit in page["items"])
        before = page["next_cursor"]
        if before is None:
            break
    assert len(seen) == 63 and len(set(seen)) == 63
    assert client.get("/api/encounters/directory", headers=headers,
                      params={"patient_id": patients[0], "limit": 999}).status_code == 422
    assert client.get("/api/encounters/directory",
                      params={"patient_id": patients[0]}).status_code == 401
