"""METABOLIC MOVEMENT: functional references, plan rules and approval workflow."""

from types import SimpleNamespace

from app.models.metabolic import MetabolicProfile
from app.services.metabolic_movement import (
    functional_indicators,
    generate_plan,
    predicted_walk_m,
    sts_threshold,
)

BASE = "/api/v1/metabolic/patients/{}"


def fa(**kw):
    fields = dict(
        sit_to_stand_30s=None,
        grip_strength_kg=None,
        gait_speed_m_s=None,
        walk_test_m=None,
        rpe=None,
    )
    fields.update(kw)
    return SimpleNamespace(**fields)


def test_sts_threshold_by_age_and_sex():
    assert sts_threshold(45, "M") == 14
    assert sts_threshold(72, "F") == 10
    assert sts_threshold(88, "M") == 8
    assert sts_threshold(70, None) is None


def test_functional_levels():
    ind = functional_indicators(
        fa(sit_to_stand_30s=9, grip_strength_kg=30, gait_speed_m_s=0.9, rpe=4),
        70,
        "M",
    )
    assert ind["sit_to_stand"]["level"] == "low"
    assert ind["grip"]["level"] == "adequate"
    assert ind["gait_speed"]["level"] == "reduced"
    assert ind["rpe"]["level"] == "moderate"
    female = functional_indicators(fa(grip_strength_kg=15), 50, "F")
    assert female["grip"]["level"] == "low"
    unknown = functional_indicators(fa(grip_strength_kg=15), 50, None)
    assert unknown["grip"]["level"] is None and unknown["grip"]["bands"] == []


def test_six_minute_walk_percent_predicted():
    predicted = predicted_walk_m(60, "M", 175, 80)
    assert predicted == round(7.57 * 175 - 5.02 * 60 - 1.76 * 80 - 309)
    ind = functional_indicators(fa(walk_test_m=predicted * 0.7), 60, "M", 175, 80)
    assert ind["walk_test"]["percent_predicted"] == 70
    assert ind["walk_test"]["level"] == "reduced"
    no_anthro = functional_indicators(fa(walk_test_m=400), 60, "M")
    assert no_anthro["walk_test"]["level"] is None


def result(**indicators):
    return {
        "patient": {"age": indicators.pop("age", 50), "sex": "M"},
        "indicators": {k: {"value": v} for k, v in indicators.items()},
        "inputs": {},
        "alerts": [],
    }


def test_sedentary_with_pain_starts_low_impact():
    profile = SimpleNamespace(
        physical_activity_minutes_week=20,
        pain_level=6,
        musculoskeletal_limitations="rodilla",
        sitting_hours_day=9,
        has_cardiovascular_disease=False,
    )
    plan, why = generate_plan(result(bmi=36), profile, None)
    assert plan["aerobic"]["days_per_week"] == 3
    assert plan["aerobic"]["minutes"] == 15
    assert "aquatic" in plan["aerobic"]["types"]
    assert {"low_impact", "pain_rule", "stop_symptoms"} <= set(plan["safety"])
    assert plan["daily"]["break_sitting"] is True
    assert {"start_gradually", "low_impact", "sitting"} <= set(why)


def test_active_patient_and_cardiovascular_caution():
    active = SimpleNamespace(
        physical_activity_minutes_week=200,
        pain_level=0,
        musculoskeletal_limitations=None,
        sitting_hours_day=4,
        has_cardiovascular_disease=False,
    )
    plan, _ = generate_plan(result(bmi=24), active, None)
    assert plan["aerobic"]["minutes"] == 40 and "intervals" in plan["aerobic"]["types"]
    assert plan["strength"]["days_per_week"] == 3
    active.has_cardiovascular_disease = True
    plan, why = generate_plan(result(bmi=24), active, None)
    assert plan["safety"][0] == "medical_clearance"
    assert plan["aerobic"]["intensity"] == "light_moderate"
    assert "medical_clearance" in why


def test_weak_functional_tests_shape_strength_and_balance():
    functional = {"sit_to_stand": {"level": "low"}, "grip": {"level": "low"}}
    plan, why = generate_plan(result(age=58), None, functional)
    assert "grip" in plan["strength"]["muscle_groups"]
    assert "step_ups" in plan["strength"]["exercises"]
    assert plan["balance"]["days_per_week"] == 3
    assert {"weak_lower_limbs", "weak_grip", "balance_priority"} <= set(why)


def test_functional_crud(authenticated_client, test_patient):
    url = BASE.format(test_patient.id) + "/functional"
    r = authenticated_client.post(url, json={"assessed_at": "2026-09-01T09:00:00"})
    assert r.status_code == 422
    r = authenticated_client.post(
        url,
        json={
            "assessed_at": "2026-09-01T09:00:00",
            "sit_to_stand_30s": 11,
            "gait_speed_m_s": 1.2,
        },
    )
    assert r.status_code == 200, r.text
    indicators = r.json()["indicators"]
    assert indicators["gait_speed"]["level"] == "adequate"
    assert indicators["sit_to_stand"]["level"] == "low"
    assert indicators["sit_to_stand"]["bands"]
    listing = authenticated_client.get(url).json()
    assert len(listing["items"]) == 1 and listing["references_version"]
    fid = listing["items"][0]["id"]
    assert authenticated_client.delete(f"{url}/{fid}").status_code == 200
    assert authenticated_client.get(url).json()["items"] == []


def test_plan_workflow(authenticated_client, db_session, test_user, test_patient):
    url = BASE.format(test_patient.id) + "/exercise-plans"
    assert authenticated_client.post(url + "/generate").status_code == 403

    db_session.add(
        MetabolicProfile(patient_id=test_patient.id, physical_activity_minutes_week=30)
    )
    test_user.role = "physio"
    db_session.commit()
    r = authenticated_client.post(url + "/generate")
    assert r.status_code == 200, r.text
    draft = r.json()
    assert draft["status"] == "draft" and draft["generator_version"]
    assert draft["plan"]["aerobic"]["days_per_week"] == 3

    edited = dict(draft["plan"])
    edited["aerobic"] = {**edited["aerobic"], "minutes": 20}
    r = authenticated_client.put(f"{url}/{draft['id']}", json={"plan": edited})
    assert r.status_code == 200 and r.json()["plan"]["aerobic"]["minutes"] == 20
    bad = {**edited, "strength": {**edited["strength"], "reps_min": 20, "reps_max": 5}}
    assert (
        authenticated_client.put(f"{url}/{draft['id']}", json={"plan": bad}).status_code
        == 422
    )

    test_user.role = "user"
    db_session.commit()
    assert authenticated_client.get(url).json() == []

    test_user.role = "physio"
    db_session.commit()
    first = authenticated_client.post(f"{url}/{draft['id']}/approve").json()
    assert first["status"] == "approved" and first["approved_at"]
    assert (
        authenticated_client.put(
            f"{url}/{draft['id']}", json={"plan": edited}
        ).status_code
        == 409
    )
    second = authenticated_client.post(url, json={"plan": edited}).json()
    authenticated_client.post(f"{url}/{second['id']}/approve")
    statuses = {p["id"]: p["status"] for p in authenticated_client.get(url).json()}
    assert statuses == {draft["id"]: "archived", second["id"]: "approved"}

    test_user.role = "user"
    db_session.commit()
    visible = authenticated_client.get(url).json()
    assert [p["id"] for p in visible] == [second["id"]]
