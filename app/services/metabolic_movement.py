"""METABOLIC MOVEMENT: functional test interpretation and rule-based exercise plan drafts.

Drafts are suggestions for a professional to edit and approve; they are never shown to
the patient until approved.
"""

from typing import Any, Dict, List, Optional, Tuple

GENERATOR_VERSION = "movement-0.1.0"
REFERENCES_VERSION = "functional-refs-0.1.0"

# 30-second chair stand, "below average" thresholds (CDC STEADI, ages 60-94).
# Below 60 years the 60-64 threshold is used as a conservative minimum.
STS_BELOW_AVERAGE = {
    "male": ((60, 14), (65, 12), (70, 12), (75, 11), (80, 10), (85, 8), (90, 7)),
    "female": ((60, 12), (65, 11), (70, 10), (75, 10), (80, 9), (85, 8), (90, 4)),
}
# Low grip strength (EWGSOP2).
GRIP_LOW = {"male": 27.0, "female": 16.0}
# Usual gait speed (EWGSOP2 severity <= 0.8 m/s; < 1.0 m/s as reduced).
GAIT_LOW, GAIT_REDUCED = 0.8, 1.0
# Six-minute walk as % of predicted (Enright & Sherrill 1998).
WALK_LOW_PCT, WALK_REDUCED_PCT = 60.0, 80.0
# Borg CR10 effort categories.
RPE_BANDS = (
    {"level": "light", "min": None, "max": 3},
    {"level": "moderate", "min": 3, "max": 5},
    {"level": "vigorous", "min": 5, "max": 7},
    {"level": "very_hard", "min": 7, "max": None},
)


def _band_level(value: float, bands: List[dict]) -> Optional[str]:
    for b in bands:
        lo, hi = b["min"], b["max"]
        if (lo is None or value >= lo) and (hi is None or value < hi):
            return b["level"]
    return None


def sts_threshold(age: Optional[int], sex: Optional[str]) -> Optional[int]:
    rows = STS_BELOW_AVERAGE.get(sex or "")
    if not rows:
        return None
    threshold = rows[0][1]
    for start, value in rows:
        if age is not None and age >= start:
            threshold = value
    return threshold


def predicted_walk_m(
    age: Optional[int],
    sex: Optional[str],
    height_cm: Optional[float],
    weight_kg: Optional[float],
) -> Optional[float]:
    if None in (age, height_cm, weight_kg) or sex not in ("male", "female"):
        return None
    if sex == "male":
        value = 7.57 * height_cm - 5.02 * age - 1.76 * weight_kg - 309
    else:
        value = 2.11 * height_cm - 2.29 * weight_kg - 5.78 * age + 667
    return round(value) if value > 0 else None


def functional_indicators(
    fa: Any,
    age: Optional[int],
    sex: Optional[str],
    height_cm: Optional[float] = None,
    weight_kg: Optional[float] = None,
) -> Dict[str, Any]:
    """Level and reference bands for each functional test that has a value."""
    out: Dict[str, Any] = {}

    def add(key, value, unit, bands, extra=None):
        level = _band_level(value, bands) if bands else None
        out[key] = {"value": value, "unit": unit, "level": level, "bands": bands}
        if extra:
            out[key].update(extra)

    if fa.sit_to_stand_30s is not None:
        t = sts_threshold(age, sex)
        bands = (
            [
                {"level": "low", "min": None, "max": t},
                {"level": "adequate", "min": t, "max": None},
            ]
            if t
            else []
        )
        add("sit_to_stand", fa.sit_to_stand_30s, "reps", bands)
    if fa.grip_strength_kg is not None:
        t = GRIP_LOW.get(sex or "")
        bands = (
            [
                {"level": "low", "min": None, "max": t},
                {"level": "adequate", "min": t, "max": None},
            ]
            if t
            else []
        )
        add("grip", fa.grip_strength_kg, "kg", bands)
    if fa.gait_speed_m_s is not None:
        add(
            "gait_speed",
            fa.gait_speed_m_s,
            "m/s",
            [
                {"level": "low", "min": None, "max": GAIT_LOW},
                {"level": "reduced", "min": GAIT_LOW, "max": GAIT_REDUCED},
                {"level": "adequate", "min": GAIT_REDUCED, "max": None},
            ],
        )
    if fa.walk_test_m is not None:
        predicted = predicted_walk_m(age, sex, height_cm, weight_kg)
        pct = round(fa.walk_test_m / predicted * 100) if predicted else None
        bands = [
            {"level": "low", "min": None, "max": WALK_LOW_PCT},
            {"level": "reduced", "min": WALK_LOW_PCT, "max": WALK_REDUCED_PCT},
            {"level": "adequate", "min": WALK_REDUCED_PCT, "max": None},
        ]
        out["walk_test"] = {
            "value": fa.walk_test_m,
            "unit": "m",
            "predicted_m": predicted,
            "percent_predicted": pct,
            "level": _band_level(pct, bands) if pct is not None else None,
            "bands": bands if pct is not None else [],
            "band_unit": "%",
        }
    if fa.rpe is not None:
        add("rpe", fa.rpe, "CR10", list(RPE_BANDS))
    return out


def _value(result: Dict[str, Any], key: str) -> Optional[float]:
    for section in ("indicators", "inputs"):
        v = result.get(section, {}).get(key, {}).get("value")
        if isinstance(v, (int, float)):
            return v
    return None


def generate_plan(
    result: Dict[str, Any],
    profile: Any,
    functional: Optional[Dict[str, Any]],
) -> Tuple[Dict[str, Any], List[str]]:
    """Rule-based draft prescription and the reasons (keys) that shaped it."""
    age = result.get("patient", {}).get("age")
    bmi = _value(result, "bmi")
    systolic = _value(result, "systolic")
    diastolic = _value(result, "diastolic")
    activity = getattr(profile, "physical_activity_minutes_week", None)
    pain = getattr(profile, "pain_level", None) or 0
    limitations = (getattr(profile, "musculoskeletal_limitations", None) or "").strip()
    sitting = getattr(profile, "sitting_hours_day", None)
    cvd = bool(getattr(profile, "has_cardiovascular_disease", False))
    functional = functional or {}
    levels = {k: v.get("level") for k, v in functional.items()}

    rationale: List[str] = []
    safety = ["stop_symptoms"]
    caution = (
        cvd
        or bool(result.get("alerts"))
        or (systolic or 0) >= 160
        or (diastolic or 0) >= 100
    )
    if caution:
        rationale.append("medical_clearance")
        safety.insert(0, "medical_clearance")
    low_impact = (bmi or 0) >= 35 or pain >= 5 or bool(limitations)
    if low_impact:
        rationale.append("low_impact")
        safety.append("low_impact")
    if pain > 0 or limitations:
        safety.append("pain_rule")

    if activity is None:
        rationale.append("activity_unknown")
    start = activity is None or activity < 60 or caution or pain >= 7
    weak_lower = levels.get("sit_to_stand") == "low" or levels.get("gait_speed") in (
        "low",
        "reduced",
    )
    weak_grip = levels.get("grip") == "low"
    low_capacity = levels.get("walk_test") in ("low", "reduced")

    impact_types = (
        ["stationary_bike", "aquatic", "walking_flat"]
        if low_impact
        else ["brisk_walking", "cycling", "dancing"]
    )
    if start or low_capacity:
        rationale.append("start_gradually")
        aerobic = {
            "days_per_week": 3,
            "minutes": 15,
            "intensity": "light_moderate",
            "rpe_min": 3,
            "rpe_max": 4,
            "types": impact_types,
        }
        progression = ["aerobic_build"]
    elif activity < 150:
        rationale.append("below_150")
        aerobic = {
            "days_per_week": 5,
            "minutes": 30,
            "intensity": "moderate",
            "rpe_min": 4,
            "rpe_max": 5,
            "types": impact_types,
        }
        progression = ["aerobic_150"]
    else:
        rationale.append("active")
        aerobic = {
            "days_per_week": 5,
            "minutes": 40,
            "intensity": "moderate_vigorous",
            "rpe_min": 5,
            "rpe_max": 7,
            "types": impact_types + ([] if low_impact else ["intervals"]),
        }
        progression = ["aerobic_maintain"]

    muscle_groups = ["lower_limbs", "upper_limbs", "core"]
    exercises = ["sit_to_stand", "wall_pushups", "band_rows", "glute_bridge"]
    if weak_lower:
        rationale.append("weak_lower_limbs")
        exercises += ["calf_raises", "step_ups"]
    if weak_grip:
        rationale.append("weak_grip")
        muscle_groups.append("grip")
        exercises.append("grip_squeeze")
    strength = {
        "days_per_week": 3 if (activity or 0) >= 150 and not caution else 2,
        "sets_min": 1 if start else 2,
        "sets_max": 2 if start else 3,
        "reps_min": 12 if start else 8,
        "reps_max": 15 if start else 12,
        "rpe_min": 5 if start else 6,
        "rpe_max": 6 if start else 7,
        "muscle_groups": muscle_groups,
        "exercises": exercises,
    }
    progression.append("strength_load")

    needs_balance = (age or 0) >= 65 or weak_lower
    if needs_balance:
        rationale.append("balance_priority")
    balance = {
        "days_per_week": 3 if needs_balance else 2,
        "minutes": 10,
        "exercises": ["single_leg_stance", "tandem_walk"]
        + (["sit_to_stand_slow"] if weak_lower else []),
    }
    mobility = {
        "days_per_week": 7 if (pain or limitations) else 5,
        "minutes": 10,
        "focus": ["hips", "spine", "shoulders"],
    }

    break_sitting = sitting is not None and sitting >= 6
    if break_sitting:
        rationale.append("sitting")
    daily = {
        "steps_start": 7000 if (activity or 0) >= 150 else 5000,
        "steps_target": 10000 if (activity or 0) >= 150 else 7000,
        "walk_after_meals": True,
        "break_sitting": break_sitting,
    }
    progression.append("steps_build")

    plan = {
        "aerobic": aerobic,
        "strength": strength,
        "mobility": mobility,
        "balance": balance,
        "daily": daily,
        "progression": progression,
        "safety": safety,
    }
    return plan, rationale
