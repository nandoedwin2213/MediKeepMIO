"""Tests for the professional metabolic dashboard."""

from datetime import date

from app.services.metabolic_dashboard import is_professional, summarize
from tests.api.test_metabolic import add_ir_panel

URL = "/api/v1/metabolic/professional/dashboard"


class _U:
    def __init__(self, role):
        self.role = role


def test_role_gate():
    assert is_professional(_U("doctor"))
    assert is_professional(_U("Physio"))
    assert is_professional(_U("nutritionist"))
    assert not is_professional(_U("user"))
    assert not is_professional(_U(None))


def test_patient_role_forbidden(authenticated_client, test_patient):
    assert authenticated_client.get(URL).status_code == 403


def test_doctor_sees_own_patients(
    authenticated_client, db_session, test_user, test_patient
):
    test_user.role = "doctor"
    db_session.commit()
    add_ir_panel(db_session, test_patient.id)
    r = authenticated_client.get(URL)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 1
    assert sum(body["by_level"].values()) == 1
    row = body["patients"][0]
    assert row["patient_id"] == test_patient.id
    assert row["name"] == "Test User"
    assert row["last_data_date"] is not None
    assert "no_data" not in row["alerts"]


def test_admin_without_patients(admin_client):
    body = admin_client.get(URL).json()
    assert body["total"] == 0 and body["patients"] == []


def test_summarize_alerts():
    result = {
        "score": {"value": 35, "level": "high"},
        "inputs": {"glucose": {"date": "2026-01-01", "source": "lab"}},
        "indicators": {"hba1c": {"level": "veryHigh"}},
        "alerts": [{"id": "glucose_critical"}],
        "factors": [{"key": "waist", "level": "veryHigh"}],
    }
    row = summarize(result, {"score_delta": -8}, date(2026, 6, 1))
    assert row["alerts"] == [
        "high_risk",
        "risk_increased",
        "critical",
        "hba1c",
        "stale",
    ]
    assert row["days_since_data"] == 151
    assert row["top_factors"][0]["key"] == "waist"
    empty = summarize({"score": {}, "inputs": {}}, None, date(2026, 6, 1))
    assert empty["level"] == "unknown" and empty["alerts"] == ["no_data"]
