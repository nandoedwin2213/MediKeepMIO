"""API tests for the metabolic risk engine endpoints."""

from datetime import date, datetime

from app.models.clinical import Vitals
from app.models.labs import LabResult, LabTestComponent
from app.models.metabolic import MetabolicAssessment

BASE = "/api/v1/metabolic"


def add_ir_panel(
    db, patient_id, glucose=100, insulin=20, unit_g="mg/dL", unit_i="µU/mL"
):
    result = LabResult(
        patient_id=patient_id,
        test_name="Panel IR",
        completed_date=date(2026, 9, 1),
        created_at=datetime(2026, 9, 1),
        status="completed",
    )
    db.add(result)
    db.flush()
    for name, value, unit in (
        ("Fasting Glucose", glucose, unit_g),
        ("Fasting Insulin", insulin, unit_i),
        ("Triglycerides", 160, "mg/dL"),
        ("HDL Cholesterol", 35, "mg/dL"),
    ):
        db.add(
            LabTestComponent(
                lab_result_id=result.id,
                test_name=name,
                value=value,
                unit=unit,
                result_type="quantitative",
            )
        )
    db.add(
        Vitals(
            patient_id=patient_id,
            recorded_date=datetime(2026, 9, 1, 8),
            weight=176.37,
            height=66.93,
            waist_circumference=37.4,
            hip_circumference=39.37,
            systolic_bp=125,
            diastolic_bp=80,
        )
    )
    db.commit()


class TestMetabolicEvaluate:
    def test_evaluate_computes_and_stores_once(
        self, authenticated_client, db_session, test_patient
    ):
        add_ir_panel(db_session, test_patient.id)
        r = authenticated_client.post(f"{BASE}/patients/{test_patient.id}/evaluate")
        assert r.status_code == 200, r.text
        body = r.json()
        ind = body["result"]["indicators"]
        assert ind["homa_ir"]["value"] == 4.94
        assert ind["waist"]["value"] == 95.0
        assert ind["waist_hip"]["value"] == 0.95
        assert body["result"]["metabolic_syndrome"]["status"] == "compatible"
        assert body["saved"] is True

        again = authenticated_client.post(
            f"{BASE}/patients/{test_patient.id}/evaluate"
        ).json()
        assert again["assessment_id"] == body["assessment_id"]
        assert db_session.query(MetabolicAssessment).count() == 1

        history = authenticated_client.get(
            f"{BASE}/patients/{test_patient.id}/assessments"
        )
        assert history.status_code == 200
        assert history.json()[0]["algorithm_version"] == "1.0.0"

    def test_si_units_are_converted(
        self, authenticated_client, db_session, test_patient
    ):
        add_ir_panel(
            db_session,
            test_patient.id,
            glucose=5,
            insulin=60,
            unit_g="mmol/L",
            unit_i="pmol/L",
        )
        body = authenticated_client.post(
            f"{BASE}/patients/{test_patient.id}/evaluate"
        ).json()
        assert body["result"]["indicators"]["homa_ir"]["value"] == 2.22

    def test_other_user_cannot_evaluate(self, admin_client, test_patient):
        r = admin_client.post(f"{BASE}/patients/{test_patient.id}/evaluate")
        assert r.status_code in (403, 404)


class TestMetabolicConfig:
    def test_user_can_read_but_not_update(self, authenticated_client):
        r = authenticated_client.get(f"{BASE}/config")
        assert r.status_code == 200 and r.json()["version"] == 0
        assert (
            authenticated_client.put(f"{BASE}/config", json={"config": {}}).status_code
            == 403
        )

    def test_admin_creates_new_version(self, admin_client):
        cfg = admin_client.get(f"{BASE}/config/default").json()["config"]
        cfg["score_min_coverage"] = 0.5
        r = admin_client.put(f"{BASE}/config", json={"config": cfg, "notes": "test"})
        assert r.status_code == 200, r.text
        assert r.json()["version"] == 1
        assert (
            admin_client.get(f"{BASE}/config").json()["config"]["score_min_coverage"]
            == 0.5
        )

    def test_invalid_config_rejected(self, admin_client):
        bad = {
            "indicators": {
                "homa_ir": {"bands": [{"level": "normal", "min": 5, "max": 1}]}
            }
        }
        assert admin_client.put(f"{BASE}/config", json={"config": bad}).status_code in (
            400,
            422,
        )


class TestMetabolicProfile:
    def test_profile_roundtrip_feeds_engine(self, authenticated_client, test_patient):
        empty = authenticated_client.get(f"{BASE}/patients/{test_patient.id}/profile")
        assert empty.status_code == 200 and empty.json()["smoking"] is None
        payload = {
            "has_hypertension": True,
            "physical_activity_minutes_week": 30,
            "smoking": "current",
            "sleep_hours": 5.5,
        }
        r = authenticated_client.put(
            f"{BASE}/patients/{test_patient.id}/profile", json=payload
        )
        assert r.status_code == 200, r.text
        assert r.json()["smoking"] == "current"
        result = authenticated_client.post(
            f"{BASE}/patients/{test_patient.id}/evaluate"
        ).json()["result"]
        factors = {f["key"]: f["level"] for f in result["factors"]}
        assert factors["smoking"] == "high" and factors["physical_activity"] == "high"
        bp = next(
            c
            for c in result["metabolic_syndrome"]["criteria"]
            if c["id"] == "blood_pressure"
        )
        assert bp["met"] is True

    def test_profile_validation(self, authenticated_client, test_patient):
        r = authenticated_client.put(
            f"{BASE}/patients/{test_patient.id}/profile", json={"alcohol": "lots"}
        )
        assert r.status_code == 422


def test_patient_sex_change_stores_new_assessment(
    authenticated_client, db_session, test_patient
):
    add_ir_panel(db_session, test_patient.id)
    url = f"{BASE}/patients/{test_patient.id}/evaluate"
    first = authenticated_client.post(url).json()
    test_patient.gender = "F" if first["result"]["patient"]["sex"] != "F" else "M"
    db_session.commit()
    second = authenticated_client.post(url).json()
    assert second["result"]["patient"]["sex"] != first["result"]["patient"]["sex"]
    assert second["assessment_id"] != first["assessment_id"]


def test_progress_endpoint_compares_assessments(
    authenticated_client, db_session, test_patient
):
    add_ir_panel(db_session, test_patient.id)
    url = f"{BASE}/patients/{test_patient.id}"
    authenticated_client.post(f"{url}/evaluate")
    empty = authenticated_client.get(f"{url}/progress").json()
    assert len(empty["timeline"]) == 1 and empty["change"] is None
    db_session.add(
        Vitals(
            patient_id=test_patient.id,
            recorded_date=datetime(2026, 12, 1, 8),
            weight=165.35,
            height=66.93,
            waist_circumference=33.46,
            hip_circumference=39.37,
            systolic_bp=115,
            diastolic_bp=75,
        )
    )
    db_session.commit()
    authenticated_client.post(f"{url}/evaluate")
    r = authenticated_client.get(f"{url}/progress")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["timeline"]) == 2
    waist = {row["key"]: row for row in body["progress"]}["waist"]
    assert waist["from"] == 95.0 and waist["to"] == 85.0
    assert waist["direction"] == "improved"
    assert body["change"]["score_delta"] > 0
    assert any(d["key"] == "waist" for d in body["change"]["drivers"])
    windows = {w["key"]: w for w in body["windows"]}
    assert (
        windows["d90"]["snapshot"]["assessment_id"]
        == body["timeline"][1]["assessment_id"]
    )


def test_progress_requires_access(admin_client, test_patient):
    r = admin_client.get(f"{BASE}/patients/{test_patient.id}/progress")
    assert r.status_code in (403, 404)
