"""Unit tests for metabolic progress: windows, baseline comparison and change drivers."""

from datetime import datetime
from types import SimpleNamespace

from app.services.metabolic_progress import build_progress


def assessment(aid, day, score, waist, tg, waist_level, tg_level, activity=None):
    indicators = {
        "waist": {"value": waist, "unit": "cm", "level": waist_level},
        "triglycerides": {"value": tg, "unit": "mg/dL", "level": tg_level},
    }
    components = [
        {
            "key": "waist",
            "level": waist_level,
            "points": {"normal": 100, "high": 35, "veryHigh": 10}[waist_level],
            "weight": 20,
        },
    ]
    if activity:
        indicators["physical_activity"] = {
            "value": activity[0],
            "unit": "min/sem",
            "level": activity[1],
        }
    return SimpleNamespace(
        id=aid,
        assessed_at=datetime(2027, 1, 1, aid),
        score=score,
        risk_level="high",
        result={
            "inputs": {
                "waist": {"value": waist, "date": day, "source": "vitals"},
                "sitting": {"value": 9, "date": "2027-01-01", "source": "profile"},
            },
            "indicators": indicators,
            "score": {"components": components},
        },
    )


def test_empty():
    assert build_progress([]) == {
        "timeline": [],
        "windows": [],
        "progress": [],
        "change": None,
    }


def test_windows_progress_and_drivers():
    data = [
        assessment(1, "2026-01-01", 30, 105, 210, "veryHigh", "high"),
        assessment(2, "2026-02-05", 35, 101, 190, "veryHigh", "borderline"),
        assessment(3, "2026-04-10", 52, 98, 155, "high", "borderline", (160, "normal")),
    ]
    result = build_progress(reversed(data))
    windows = {w["key"]: w["snapshot"] for w in result["windows"]}
    assert windows["baseline"]["assessment_id"] == 1
    assert windows["d30"]["assessment_id"] == 2
    assert windows["d60"] is None
    assert windows["d90"]["assessment_id"] == 3
    d90 = {w["key"]: w for w in result["windows"]}["d90"]["comparison"]
    assert {r["key"]: r["to"] for r in d90}["waist"] == 98
    assert windows["m6"] is None and windows["m12"] is None
    assert windows["latest"]["assessment_id"] == 3

    progress = {row["key"]: row for row in result["progress"]}
    assert progress["waist"]["from"] == 105 and progress["waist"]["to"] == 98
    assert progress["waist"]["direction"] == "improved"
    assert progress["triglycerides"]["delta"] == -55

    change = result["change"]
    assert change["score_delta"] == 17
    assert change["drivers"][0]["key"] == "waist"
    assert change["drivers"][0]["direction"] == "improved"
    assert change["drivers"][0]["delta"] == -3
    assert {c["key"] for c in change["other_changes"]} == {"triglycerides"}


def test_worsening_detected_for_higher_is_better():
    data = [
        assessment(1, "2026-01-01", 50, 98, 150, "high", "borderline", (200, "normal")),
        assessment(2, "2026-01-20", 50, 98, 150, "high", "borderline", (120, "normal")),
    ]
    rows = {r["key"]: r for r in build_progress(data)["progress"]}
    assert rows["physical_activity"]["direction"] == "worsened"
    assert rows["waist"]["direction"] == "same"


def test_recalculation_on_same_data_date_replaces_previous():
    data = [
        assessment(1, "2026-01-01", 30, 105, 210, "veryHigh", "high"),
        assessment(2, "2026-03-01", 45, 98, 155, "high", "borderline"),
        assessment(3, "2026-03-01", 40, 98, 155, "high", "borderline"),
    ]
    result = build_progress(data)
    assert [s["assessment_id"] for s in result["timeline"]] == [1, 3]
    assert result["change"]["to_score"] == 40
