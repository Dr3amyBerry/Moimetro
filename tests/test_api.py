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
    assert client.post(f"/api/capture/{session}/stop", headers=headers).status_code == 200
    assert client.post(f"/api/encounters/{encounter_id}/close", headers=headers).status_code == 200
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
