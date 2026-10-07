"""Weekly programme layout, adherence scoring and inactivity alert."""

from datetime import date, datetime, timedelta
from types import SimpleNamespace

from app.models.clinical import Vitals
from app.models.metabolic import AdherenceLog, ExercisePlan, NutritionPlan
from app.services.metabolic_dashboard import is_inactive
from app.services.metabolic_week import build_week, week_start

EXERCISE = {
    "aerobic": {
        "days_per_week": 3,
        "minutes": 30,
        "intensity": "moderate",
        "types": ["brisk_walking", "cycling"],
    },
    "strength": {
        "days_per_week": 2,
        "sets_min": 2,
        "sets_max": 3,
        "reps_min": 8,
        "reps_max": 12,
        "exercises": ["sit_to_stand"],
    },
    "mobility": {"days_per_week": 5, "minutes": 10},
    "balance": {"days_per_week": 2, "minutes": 10},
    "daily": {"steps_start": 7000, "walk_after_meals": True},
}
NUTRITION = {"meals": {"snacks_per_day": 1}, "avoid": [], "dislikes": []}


def recipe(id, category):
    return SimpleNamespace(
        id=id, name=f"R{id}", category=category, kcal=300, image_url=None
    )


def log(d, item, done=True):
    return SimpleNamespace(log_date=d, item=item, done=done)


def test_week_layout_and_score():
    monday = date(2026, 10, 5)
    today = monday + timedelta(days=2)
    recipes = [recipe(i, c) for i, c in enumerate(["breakfast", "lunch", "dinner"])]
    week = build_week(
        monday + timedelta(days=3),
        exercise=EXERCISE,
        nutrition=NUTRITION,
        recipes=recipes,
        logs=[log(monday, "exercise"), log(monday, "walk"), log(monday, "nutrition")],
        measured={"weight": {monday + timedelta(days=1)}, "waist": set()},
        today=today,
    )
    assert week["start"] == "2026-10-05" and week["is_current"]
    days = week["days"]
    assert [i for i, d in enumerate(days) if d["aerobic"]] == [0, 2, 4]
    assert [i for i, d in enumerate(days) if d["strength"]] == [1, 3]
    assert days[0]["aerobic"]["type"] == "brisk_walking"
    assert days[0]["steps_target"] == 7000 and days[0]["walk_after_meals"]
    assert set(days[0]["meals"]) == {"breakfast", "lunch", "dinner"}
    assert [i["item"] for i in days[6]["items"]] == ["walk", "nutrition"]
    assert days[3]["is_future"] and not days[2]["is_future"]
    weekly = {w["item"]: w for w in week["weekly"]}
    assert weekly["weight"]["done"] and weekly["weight"]["source"] == "vitals"
    assert not weekly["waist"]["done"]
    # 3 elapsed days × 3 items + weight done = 10 expected, 3 + 1 done.
    assert week["adherence"] == {
        "done": 4,
        "expected": 10,
        "planned": 21,
        "percent": 40,
    }


def test_week_without_plans_and_since():
    monday = date(2026, 10, 5)
    empty = build_week(
        monday,
        exercise=None,
        nutrition=None,
        recipes=[],
        logs=[],
        measured={},
        today=monday + timedelta(days=10),
    )
    assert empty["weekly"] == [] and empty["adherence"]["percent"] is None
    late = build_week(
        monday,
        exercise=EXERCISE,
        nutrition=None,
        recipes=[],
        logs=[],
        measured={},
        today=monday + timedelta(days=10),
        exercise_since=monday + timedelta(days=5),
    )
    assert [bool(d["items"]) for d in late["days"]] == [False] * 5 + [True] * 2
    # Week is over: weekly items count even if missing.
    assert late["adherence"]["expected"] == 2 + 2


def test_week_endpoint_and_logging(
    authenticated_client, db_session, test_user, test_patient
):
    base = f"/api/v1/metabolic/patients/{test_patient.id}"
    today = date.today()
    empty = authenticated_client.get(f"{base}/week")
    assert empty.status_code == 200, empty.text
    assert empty.json()["plans"] == {"exercise": None, "nutrition": None}

    approved = datetime.combine(
        week_start(today) - timedelta(days=7), datetime.min.time()
    )
    db_session.add_all(
        [
            ExercisePlan(
                patient_id=test_patient.id,
                status="approved",
                plan=EXERCISE,
                approved_at=approved,
            ),
            ExercisePlan(patient_id=test_patient.id, status="draft", plan={}),
            NutritionPlan(
                patient_id=test_patient.id,
                status="approved",
                plan=NUTRITION,
                rationale=["glycemic"],
                approved_at=approved,
            ),
            Vitals(
                patient_id=test_patient.id,
                recorded_date=datetime.combine(today, datetime.min.time()),
                waist_circumference=36.0,
            ),
        ]
    )
    db_session.commit()
    week = authenticated_client.get(f"{base}/week").json()
    assert week["plans"]["exercise"] and week["plans"]["nutrition"]
    today_card = next(d for d in week["days"] if d["is_today"])
    assert {i["item"] for i in today_card["items"]} >= {"walk", "nutrition"}
    assert today_card["meals"]["breakfast"]["id"]
    assert {w["item"]: w["done"] for w in week["weekly"]}["waist"]

    put = authenticated_client.put(
        f"{base}/adherence",
        json={"log_date": today.isoformat(), "item": "walk", "done": True},
    )
    assert put.status_code == 200, put.text
    assert put.json()["source"] == "patient"
    authenticated_client.put(
        f"{base}/adherence",
        json={"log_date": today.isoformat(), "item": "walk", "done": False},
    )
    assert db_session.query(AdherenceLog).count() == 1
    future = (today + timedelta(days=1)).isoformat()
    assert (
        authenticated_client.put(
            f"{base}/adherence", json={"log_date": future, "item": "walk"}
        ).status_code
        == 422
    )
    assert (
        authenticated_client.put(
            f"{base}/adherence",
            json={"log_date": today.isoformat(), "item": "smoking"},
        ).status_code
        == 422
    )
    history = authenticated_client.get(
        f"{base}/adherence/history", params={"weeks": 3}
    ).json()["weeks"]
    assert len(history) == 3 and history[-1]["start"] == week["start"]
    assert history[0]["percent"] is None

    assert is_inactive(db_session, test_patient.id, today)
    authenticated_client.put(
        f"{base}/adherence",
        json={"log_date": today.isoformat(), "item": "exercise", "done": True},
    )
    assert not is_inactive(db_session, test_patient.id, today)
