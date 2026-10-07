"""FISAI Metabolic AI: explanation codes, supervised approval and what-if simulator."""

from datetime import date

from app.services.metabolic_ai import apply_priorities, build_insight
from app.services.metabolic_config import default_config
from tests.api.test_metabolic import add_ir_panel

BASE = "/api/v1/metabolic/patients/{}"


def ind(level, value=1.0, unit=None):
    return {"level": level, "value": value, "unit": unit}


def test_insight_combination_and_priorities():
    result = {
        "indicators": {
            "waist": ind("high", 104, "cm"),
            "triglycerides": ind("high", 210, "mg/dL"),
            "physical_activity": ind("borderline", 60),
            "hba1c": ind("normal", 5.3, "%"),
            "blood_pressure": ind("normal", "118/76", "mmHg"),
            "systolic": ind("normal", 118),
        },
        "score": {"value": 58, "level": "moderate"},
        "alerts": [],
    }
    change = {
        "score_delta": 6,
        "from_date": date(2026, 6, 1),
        "from_score": 52,
        "to_score": 58,
        "drivers": [{"key": "waist", "direction": "improved", "impact": 40}],
    }
    out = build_insight(result, default_config(), change)
    assert out["pattern"] == "combination" and not out["needs_review"]
    assert [c["key"] for c in out["concerns"]] == [
        "waist",
        "triglycerides",
        "physical_activity",
    ]
    codes = [p["code"] for p in out["priorities"]]
    assert codes == [
        "reduce_waist",
        "increase_activity",
        "carb_quality",
        "strength",
        "repeat_labs",
    ]
    assert {s["key"] for s in out["strengths"]} >= {"hba1c", "blood_pressure"}
    assert out["change"]["score_delta"] == 6
    assert out["change"]["from_date"] == "2026-06-01"
    assert out["change"]["drivers"][0] == {
        "key": "waist",
        "direction": "improved",
        "from": None,
        "to": None,
        "delta": None,
        "unit": None,
    }
    edited = apply_priorities(out, ["strength", "reduce_waist", "strength", "sleep"])
    assert [p["code"] for p in edited["priorities"]] == [
        "strength",
        "reduce_waist",
        "sleep",
    ]
    assert edited["priorities"][1]["because"] == ["waist"] and edited["edited"]


def test_insight_patterns():
    cfg = default_config()
    assert build_insight({"indicators": {}, "score": {}}, cfg)["pattern"] == (
        "insufficient"
    )
    fine = {"indicators": {"waist": ind("normal")}, "score": {"value": 90}}
    assert build_insight(fine, cfg)["pattern"] == "favorable"
    urgent = {"indicators": {"hba1c": ind("veryHigh", 9)}, "score": {"value": 40}}
    out = build_insight(urgent, cfg)
    assert out["pattern"] == "needs_review" and out["needs_review"]


def test_simulator(authenticated_client, db_session, test_patient):
    url = BASE.format(test_patient.id) + "/simulate"
    add_ir_panel(db_session, test_patient.id)
    r = authenticated_client.post(
        url, json={"waist": -10, "triglycerides": -60, "physical_activity": 150}
    )
    assert r.status_code == 200, r.text
    sim = r.json()
    assert sim["educational"] and sim["before"]["value"] is not None
    assert sim["score_delta"] >= 0
    changes = {c["key"]: c for c in sim["changes"]}
    assert changes["waist"]["from"] == 95.0 and changes["waist"]["to"] == 85.0
    assert changes["triglycerides"]["to"] == 100
    assert changes["tyg"]["direction"] == "improved"
    assert sim["applied"]["physical_activity"] == {
        "delta": 150,
        "from": 0.0,
        "missing": False,
    }
    assert sim["applied"]["waist"]["missing"] is False
    nothing = authenticated_client.post(url, json={}).json()
    assert nothing["changes"] == [] and nothing["score_delta"] == 0
    assert authenticated_client.post(url, json={"waist": 5}).status_code == 422
    # Simulation never stores data.
    after = authenticated_client.post(url, json={}).json()
    assert after["before"] == sim["before"]


def test_insight_workflow(authenticated_client, db_session, test_user, test_patient):
    url = BASE.format(test_patient.id) + "/insights"
    add_ir_panel(db_session, test_patient.id)
    assert authenticated_client.post(url + "/generate").status_code == 403

    test_user.role = "doctor"
    db_session.commit()
    r = authenticated_client.post(url + "/generate")
    assert r.status_code == 200, r.text
    draft = r.json()
    assert draft["status"] == "draft" and draft["engine_version"] == "insight-0.1.0"
    assert draft["content"]["concerns"]
    r = authenticated_client.put(
        f"{url}/{draft['id']}",
        json={"note": "Control en 3 meses", "priorities": ["reduce_waist"]},
    )
    assert r.status_code == 200, r.text
    assert [p["code"] for p in r.json()["content"]["priorities"]] == ["reduce_waist"]
    bad = authenticated_client.put(
        f"{url}/{draft['id']}", json={"priorities": ["diagnose_diabetes"]}
    )
    assert bad.status_code == 422

    test_user.role = "user"
    db_session.commit()
    assert authenticated_client.get(url).json() == []

    test_user.role = "doctor"
    db_session.commit()
    first = authenticated_client.post(f"{url}/{draft['id']}/approve").json()
    assert first["status"] == "approved" and first["approved_by_user_id"]
    assert authenticated_client.delete(f"{url}/{draft['id']}").status_code == 409
    assert (
        authenticated_client.put(f"{url}/{draft['id']}", json={"note": "x"}).status_code
        == 409
    )
    second = authenticated_client.post(url + "/generate").json()
    authenticated_client.post(f"{url}/{second['id']}/approve")

    test_user.role = "user"
    db_session.commit()
    visible = authenticated_client.get(url).json()
    assert [i["id"] for i in visible] == [second["id"]]
