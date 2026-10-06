"""Recipe library seeding, ranking and permissions."""

from types import SimpleNamespace

from app.models.clinical import Allergy
from app.models.metabolic import MetabolicProfile, NutritionPlan, Recipe
from app.services.metabolic_recipe_library import library_recipes
from app.services.metabolic_recipes import allergen_keys, recommend

URL = "/api/v1/metabolic/recipes"


def fake(id, name, category="lunch", diets=None, allergens=(), tags=(), kcal=300):
    return SimpleNamespace(
        id=id,
        name=name,
        category=category,
        diets=diets or ["omnivore", "other", "pescatarian", "vegetarian", "vegan"],
        allergens=list(allergens),
        tags=list(tags),
        ingredients=[name],
        kcal=kcal,
    )


def test_library_is_complete():
    recipes = library_recipes()
    assert {r["category"] for r in recipes} == {
        "breakfast",
        "lunch",
        "dinner",
        "snack",
        "drink",
    }
    assert len({r["slug"] for r in recipes}) == len(recipes)
    for r in recipes:
        assert r["ingredients"] and r["steps"] and r["image_credit"]
        assert r["kcal"] is not None and r["fiber_g"] is not None


def test_allergen_keywords():
    assert allergen_keys(["Mariscos", "lactosa", "Maní"]) == [
        "lactose",
        "peanut",
        "shellfish",
    ]
    assert allergen_keys(["Penicilina"]) == []


def test_recommend_filters_and_ranks():
    vegan_only = ["vegan", "vegetarian", "pescatarian", "omnivore", "other"]
    recipes = [
        fake(1, "Pollo", diets=["omnivore", "other"], tags=["high_protein"]),
        fake(2, "Avena", diets=vegan_only, allergens=["gluten"], tags=["low_gi"]),
        fake(3, "Lentejas", diets=vegan_only, tags=["low_gi", "high_fiber"]),
        fake(4, "Hummus", diets=vegan_only, allergens=["sesame"], tags=["low_gi"]),
        fake(5, "Batido de pepino", diets=vegan_only, tags=["no_added_sugar"]),
    ]
    out = recommend(
        recipes,
        diet_pattern="vegan",
        avoid=["gluten"],
        dislikes=["pepino"],
        rationale=["glycemic"],
        assigned_ids=[4],
    )
    ids = [i["recipe"].id for i in out["items"]]
    assert ids == [4, 3]
    assert out["excluded"] == {"diet": 1, "allergen": 1, "dislike": 1}
    assert out["items"][1]["reasons"] == ["low_gi", "high_fiber"]
    assert out["items"][0]["assigned"] and out["items"][0]["conflicts"] == []


def test_assigned_recipe_keeps_conflict_flag():
    out = recommend(
        [fake(1, "Ceviche", allergens=["fish"])],
        diet_pattern=None,
        avoid=["pescado"],
        dislikes=[],
        rationale=[],
        assigned_ids=[1],
    )
    assert out["items"][0]["conflicts"] == ["fish"]


def test_library_seed_and_permissions(authenticated_client, db_session, test_user):
    r = authenticated_client.get(URL)
    assert r.status_code == 200, r.text
    assert len(r.json()) == len(library_recipes())
    authenticated_client.get(URL)
    assert db_session.query(Recipe).count() == len(library_recipes())
    assert {
        x["category"]
        for x in authenticated_client.get(URL, params={"category": "drink"}).json()
    } == {"drink"}

    body = {
        "name": "Ensalada de atún",
        "category": "lunch",
        "kcal": 350,
        "ingredients": ["1 lata de atún"],
        "steps": ["Mezclar"],
        "tags": ["high_protein"],
    }
    assert authenticated_client.post(URL, json=body).status_code == 403
    test_user.role = "nutritionist"
    db_session.commit()
    created = authenticated_client.post(URL, json=body)
    assert created.status_code == 200, created.text
    custom = created.json()
    assert custom["slug"].startswith("ensalada-de-atun-") and not custom["is_library"]
    assert (
        authenticated_client.post(URL, json={**body, "category": "brunch"}).status_code
        == 422
    )
    assert (
        authenticated_client.post(
            URL, json={**body, "image_url": "javascript:alert(1)"}
        ).status_code
        == 422
    )

    library_id = r.json()[0]["id"]
    assert authenticated_client.delete(f"{URL}/{library_id}").json()["hidden"]
    assert authenticated_client.delete(f"{URL}/{custom['id']}").json()["deleted"]
    authenticated_client.get(URL)
    assert db_session.query(Recipe).count() == len(library_recipes())

    test_user.role = "user"
    db_session.commit()
    ids = [x["id"] for x in authenticated_client.get(URL).json()]
    assert library_id not in ids
    assert authenticated_client.get(f"{URL}/{library_id}").status_code == 404


def test_recommended_uses_only_approved_plan_for_patient(
    authenticated_client, db_session, test_user, test_patient
):
    url = f"/api/v1/metabolic/patients/{test_patient.id}/recipes/recommended"
    db_session.add(MetabolicProfile(patient_id=test_patient.id, diet_pattern="vegan"))
    db_session.add(
        Allergy(
            patient_id=test_patient.id,
            allergen="Soya",
            reaction="Urticaria",
            status="active",
        )
    )
    db_session.commit()
    r = authenticated_client.get(url, params={"limit": 50})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["basis"] == "profile" and data["diet_pattern"] == "vegan"
    for item in data["items"]:
        assert "vegan" in item["recipe"]["diets"]
        assert "soy" not in item["recipe"]["allergens"]
    assert data["excluded"]["allergen"] >= 1

    salmon = db_session.query(Recipe).filter(Recipe.slug == "bowl-salmon").one()
    db_session.add(
        NutritionPlan(
            patient_id=test_patient.id,
            status="draft",
            plan={"avoid": [], "dislikes": [], "recipe_ids": [salmon.id]},
            rationale=["triglycerides"],
        )
    )
    db_session.commit()
    assert authenticated_client.get(url).json()["basis"] == "profile"

    test_user.role = "nutritionist"
    db_session.commit()
    pro = authenticated_client.get(url).json()
    assert pro["basis"] == "draft_plan"
    first = pro["items"][0]
    assert first["recipe"]["slug"] == "bowl-salmon" and first["assigned"]
    assert "diet" in first["conflicts"]
