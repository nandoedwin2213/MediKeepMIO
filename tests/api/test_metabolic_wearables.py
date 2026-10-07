"""Wearable exports: Apple Health / Google Fit parsing, import, week and profile."""

import io
import zipfile
from datetime import date, timedelta

from app.models.clinical import Vitals
from app.models.metabolic import MetabolicProfile, WearableDaily
from app.services.metabolic_wearables import (
    WearableParseError,
    clean_days,
    parse_apple_xml,
    parse_daily_csv,
)
from app.services.metabolic_week import build_week

BASE = "/api/v1/metabolic/patients/{}"
D1 = date.today() - timedelta(days=3)
D2 = D1 + timedelta(days=1)


def _stamp(day, time="08:00:00"):
    return f"{day.isoformat()} {time} -0500"


APPLE = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE HealthData [
<!ELEMENT HealthData (ExportDate,Me,(Record|Workout)*)>
<!ATTLIST Record type CDATA #REQUIRED>
]>
<HealthData locale="es_EC">
 <ExportDate value="{_stamp(D2)}"/>
 <Record type="HKQuantityTypeIdentifierStepCount" sourceName="iPhone" unit="count" startDate="{_stamp(D1)}" endDate="{_stamp(D1)}" value="3000"/>
 <Record type="HKQuantityTypeIdentifierStepCount" sourceName="iPhone" unit="count" startDate="{_stamp(D1, '18:00:00')}" endDate="{_stamp(D1, '18:30:00')}" value="5000"/>
 <Record type="HKQuantityTypeIdentifierStepCount" sourceName="Apple Watch" unit="count" startDate="{_stamp(D1)}" endDate="{_stamp(D1)}" value="7600"/>
 <Record type="HKQuantityTypeIdentifierAppleExerciseTime" sourceName="Apple Watch" unit="min" startDate="{_stamp(D1)}" endDate="{_stamp(D1)}" value="35"/>
 <Record type="HKQuantityTypeIdentifierActiveEnergyBurned" sourceName="Apple Watch" unit="kJ" startDate="{_stamp(D1)}" endDate="{_stamp(D1)}" value="1046"/>
 <Record type="HKQuantityTypeIdentifierRestingHeartRate" sourceName="Apple Watch" unit="count/min" startDate="{_stamp(D1)}" endDate="{_stamp(D1)}" value="62"/>
 <Record type="HKQuantityTypeIdentifierBodyMass" sourceName="Balanza" unit="lb" startDate="{_stamp(D1, '07:00:00')}" endDate="{_stamp(D1, '07:00:00')}" value="200"/>
 <Record type="HKCategoryTypeIdentifierSleepAnalysis" sourceName="Apple Watch" startDate="{_stamp(D1, '23:00:00')}" endDate="{_stamp(D2, '03:00:00')}" value="HKCategoryValueSleepAnalysisAsleepCore"/>
 <Record type="HKCategoryTypeIdentifierSleepAnalysis" sourceName="Apple Watch" startDate="{_stamp(D2, '03:00:00')}" endDate="{_stamp(D2, '06:30:00')}" value="HKCategoryValueSleepAnalysisAsleepREM"/>
 <Record type="HKCategoryTypeIdentifierSleepAnalysis" sourceName="Apple Watch" startDate="{_stamp(D1, '22:00:00')}" endDate="{_stamp(D2, '07:00:00')}" value="HKCategoryValueSleepAnalysisInBed"/>
 <Record type="HKQuantityTypeIdentifierStepCount" sourceName="iPhone" unit="count" startDate="{_stamp(D2)}" endDate="{_stamp(D2)}" value="4200"/>
</HealthData>
"""

FIT = (
    "Date,Move Minutes count,Calories (kcal),Step count,Average heart rate (bpm),Average weight (kg)\n"
    f"{D1.isoformat()},42,2100,9100,78,81.5\n"
    f"{D2.isoformat()},10,1900,3100,,\n"
)


def _zip(xml: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("apple_health_export/export.xml", xml)
        z.writestr("apple_health_export/export_cda.xml", "<x/>")
    return buf.getvalue()


def test_parse_apple_health_dedupes_sources_and_sleep():
    days = parse_apple_xml(io.BytesIO(APPLE.encode()))
    first = days[D1]
    assert first["steps"] == 8000  # iPhone 3000+5000 vs Watch 7600 -> max
    assert first["exercise_minutes"] == 35
    assert round(first["active_kcal"]) == 250
    assert abs(first["weight_kg"] - 90.72) < 0.01
    assert first["resting_hr"] == 62
    assert days[D2]["sleep_hours"] == 7.5  # asleep stages only, assigned to wake day


def test_parse_rejects_entities():
    bomb = '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><x>&a;</x>'
    try:
        parse_apple_xml(io.BytesIO(bomb.encode()))
    except WearableParseError:
        pass
    else:
        raise AssertionError("entity declarations must be rejected")


def test_parse_google_fit_and_spanish_csv():
    days = parse_daily_csv(FIT)
    assert days[D1]["steps"] == 9100 and days[D1]["exercise_minutes"] == 42
    assert days[D1]["weight_kg"] == 81.5 and "weight_kg" not in days[D2]
    es = parse_daily_csv(
        f"Fecha;Pasos;Minutos activos;Horas de sueño\n{D1.strftime('%d/%m/%Y')};8.500;30;6,5\n"
    )
    assert es[D1] == {"steps": 8500, "exercise_minutes": 30, "sleep_hours": 6.5}
    cleaned = clean_days(
        {D1: {"steps": 250000}, D2 + timedelta(days=30): {"steps": 10}}, date.today()
    )
    assert cleaned["days"] == [] and cleaned["warnings"] == {
        "future": 1,
        "implausible_steps": 1,
    }


def test_wearable_parse_import_and_apply(
    authenticated_client, db_session, test_patient
):
    url = BASE.format(test_patient.id)
    r = authenticated_client.post(
        url + "/wearables/parse",
        files={"file": ("export.zip", _zip(APPLE), "application/zip")},
    )
    assert r.status_code == 200, r.text
    parsed = r.json()
    assert parsed["source"] == "apple_health" and len(parsed["days"]) == 2
    assert db_session.query(WearableDaily).count() == 0

    body = {"source": "apple_health", "days": parsed["days"]}
    r = authenticated_client.post(url + "/wearables/import", json=body)
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 2
    r = authenticated_client.post(url + "/wearables/import", json=body)
    assert r.json() == {**r.json(), "created": 0, "updated": 2}
    assert db_session.query(WearableDaily).count() == 2
    weights = (
        db_session.query(Vitals)
        .filter(Vitals.import_source == "wearable_apple_health")
        .all()
    )
    assert len(weights) == 1 and abs(weights[0].weight - 200) < 0.1

    r = authenticated_client.post(
        url + "/wearables/parse",
        files={"file": ("Daily activity metrics.csv", FIT, "text/csv")},
    )
    assert r.json()["source"] == "google_fit"
    authenticated_client.post(
        url + "/wearables/import",
        json={"source": "google_fit", "days": r.json()["days"]},
    )

    data = authenticated_client.get(url + "/wearables").json()
    first = next(d for d in data["days"] if d["date"] == D1.isoformat())
    assert first["steps"] == 9100 and set(first["sources"]) == {
        "apple_health",
        "google_fit",
    }
    steps = data["summary"]["metrics"]["steps"]
    assert steps["value"] == round((9100 + 4200) / 2) and steps["level"] == "borderline"
    assert steps["bands"][0]["max"] == 5000

    future = {
        "source": "csv",
        "days": [{"date": (date.today() + timedelta(days=1)).isoformat(), "steps": 10}],
    }
    assert authenticated_client.post(
        url + "/wearables/import", json=future
    ).status_code in (400, 422)

    r = authenticated_client.post(url + "/wearables/apply-profile")
    assert r.status_code == 200, r.text
    profile = (
        db_session.query(MetabolicProfile)
        .filter(MetabolicProfile.patient_id == test_patient.id)
        .first()
    )
    db_session.refresh(profile)
    assert (
        profile.physical_activity_minutes_week
        == r.json()["physical_activity_minutes_week"]
    )
    assert profile.sleep_hours == 7.5


def test_week_marks_items_from_wearables():
    monday = date(2026, 9, 7)
    plan = {
        "aerobic": {"days_per_week": 3, "minutes": 30},
        "daily": {"steps_start": 6000},
    }
    week = build_week(
        monday,
        exercise=plan,
        nutrition=None,
        recipes=[],
        logs=[],
        measured={"weight": set(), "waist": set()},
        today=date(2026, 9, 13),
        activity={
            monday: {"steps": 6500, "exercise_minutes": 31},
            monday + timedelta(days=1): {"steps": 5000},
        },
    )
    mon = {i["item"]: i for i in week["days"][0]["items"]}
    assert mon["walk"] == {"item": "walk", "done": True, "source": "wearable"}
    assert mon["exercise"]["done"] is True and week["days"][0]["steps"] == 6500
    tue = {i["item"]: i for i in week["days"][1]["items"]}
    assert tue["walk"]["done"] is False
