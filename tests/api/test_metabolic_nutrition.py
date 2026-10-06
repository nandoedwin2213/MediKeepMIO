"""METABOLIC NUTRITION: plan rules, preferences and approval workflow."""

from types import SimpleNamespace

from app.models.clinical import Allergy
from app.models.metabolic import MetabolicProfile
from app.services.metabolic_nutrition import (
    energy_estimate,
    generate_nutrition_plan,
    split_items,
)

BASE = "/api/v1/metabolic/patients/{}"


def result(sex="F", age=50, history=None, **values):
    inputs = {k: {"value": v} for k, v in values.items()}
    return {
        "patient": {"sex": sex, "age": age},
        "inputs": inputs,
        "history": history or {},
    }


def profile(**kw):
    fields = dict(
        physical_activity_minutes_week=None,
        diet_pattern=None,
        food_intolerances=None,
        food_dislikes=None,
        meals_per_day=None,
        alcohol=None,
        sugary_drinks_per_week=None,
        fruit_veg_servings_day=None,
        ultraprocessed_per_week=None,
    )
    fields.update(kw)
    return SimpleNamespace(**fields)


def test_energy_estimate_mifflin():
    assert energy_estimate("F", 50, 90, 160, None) == (1489, 1787)
    assert energy_estimate("M", 40, 80, 175, 200)[1] == round(1699 * 1.55)
    assert energy_estimate(None, 40, 80, 175, 200) is None


def test_obese_glycemic_patient_gets_deficit_and_carb_quality():
    plan, why = generate_nutrition_plan(
        result(weight=90, height=160, bmi=35.2, waist=104, glucose=112, tg=0),
        profile(sugary_drinks_per_week=5, fruit_veg_servings_day=2),
        [],
    )
    assert plan["energy"]["kcal_target"] == 1300
    assert plan["energy"]["deficit_kcal"] == 487
    assert plan["macros"]["carbs_pct_max"] == 45
    assert plan["macros"]["added_sugar_g_max"] == 25
    assert plan["meals"]["regular_schedule"] is True
    assert {"weight_loss", "glycemic"} <= set(why)
    assert {"sugary_drinks_zero", "fruit_veg_5", "weight_5pct", "waist_down"} <= set(
        plan["targets"]
    )
    assert "fruit_juice" in plan["limit"]


def test_risk_specific_rules():
    plan, why = generate_nutrition_plan(
        result(
            sex="M",
            weight=80,
            height=178,
            bmi=25.2,
            ldl=160,
            systolic=138,
            uric_acid=7.5,
            creatinine=1.6,
        ),
        profile(diet_pattern="vegan", food_intolerances="lactosa; gluten"),
        ["Maní"],
    )
    assert plan["macros"]["protein_g_kg_max"] == 0.8
    assert plan["macros"]["sodium_mg_max"] == 1500
    assert plan["macros"]["saturated_fat_pct_max"] == 7
    assert plan["avoid"] == ["Maní", "lactosa", "gluten"]
    assert "oily_fish" not in plan["prioritize"] and "tofu_tempeh" in plan["prioritize"]
    assert {"renal_review", "b12_review", "allergy_check"} <= set(plan["safety"])
    assert {
        "lipids",
        "blood_pressure",
        "uric_acid",
        "renal_review",
        "allergies",
    } <= set(why)


def test_missing_anthropometry_keeps_qualitative_plan():
    plan, why = generate_nutrition_plan(result(), profile(), [])
    assert "missing_anthropometry" in why and plan["energy"].get("kcal_target") is None
    assert plan["macros"]["protein_g_min"] is None and plan["hydration_l"] == 2.0
    assert split_items(" a, b ;\nc,, ") == ["a", "b", "c"]


def test_profile_diet_preferences(authenticated_client, test_patient):
    url = BASE.format(test_patient.id) + "/profile"
    r = authenticated_client.put(
        url, json={"diet_pattern": "vegetarian", "meals_per_day": 4}
    )
    assert r.status_code == 200, r.text
    assert r.json()["diet_pattern"] == "vegetarian"
    assert (
        authenticated_client.put(url, json={"diet_pattern": "keto"}).status_code == 422
    )


def test_nutrition_plan_workflow(
    authenticated_client, db_session, test_user, test_patient
):
    url = BASE.format(test_patient.id) + "/nutrition-plans"
    assert authenticated_client.post(url + "/generate").status_code == 403

    db_session.add(
        MetabolicProfile(patient_id=test_patient.id, food_intolerances="lactosa")
    )
    db_session.add(
        Allergy(
            patient_id=test_patient.id,
            allergen="Mariscos",
            reaction="Urticaria",
            status="active",
        )
    )
    db_session.add(
        Allergy(
            patient_id=test_patient.id,
            allergen="Penicilina",
            reaction="Rash",
            status="resolved",
        )
    )
    test_user.role = "nutritionist"
    db_session.commit()
    r = authenticated_client.post(url + "/generate")
    assert r.status_code == 200, r.text
    draft = r.json()
    assert draft["status"] == "draft" and draft["generator_version"]
    assert draft["plan"]["avoid"] == ["Mariscos", "lactosa"]

    edited = dict(draft["plan"])
    edited["macros"] = {**edited["macros"], "fiber_g_min": 35}
    r = authenticated_client.put(f"{url}/{draft['id']}", json={"plan": edited})
    assert r.status_code == 200 and r.json()["plan"]["macros"]["fiber_g_min"] == 35
    bad = {
        **edited,
        "macros": {**edited["macros"], "fat_pct_min": 40, "fat_pct_max": 20},
    }
    assert (
        authenticated_client.put(f"{url}/{draft['id']}", json={"plan": bad}).status_code
        == 422
    )

    test_user.role = "user"
    db_session.commit()
    assert authenticated_client.get(url).json() == []

    test_user.role = "nutritionist"
    db_session.commit()
    first = authenticated_client.post(f"{url}/{draft['id']}/approve").json()
    assert first["status"] == "approved"
    assert authenticated_client.delete(f"{url}/{draft['id']}").status_code == 409
    second = authenticated_client.post(url, json={"plan": edited}).json()
    authenticated_client.post(f"{url}/{second['id']}/approve")

    test_user.role = "user"
    db_session.commit()
    assert [p["id"] for p in authenticated_client.get(url).json()] == [second["id"]]
