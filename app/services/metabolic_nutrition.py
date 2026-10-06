"""METABOLIC NUTRITION: rule-based draft nutrition plans for professional review.

Energy uses Mifflin-St Jeor with an activity factor; macro, fibre, sugar, saturated
fat and sodium targets follow common ADA/AHA/WHO guidance. Every output is a
draft that the nutritionist edits and approves before the patient sees it.
"""

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.services.metabolic_movement import _value

GENERATOR_VERSION = "nutrition-0.1.0"

PROTEIN_SOURCES = {
    "omnivore": ["fish", "poultry", "eggs", "low_fat_dairy", "legumes_protein"],
    "other": ["fish", "poultry", "eggs", "low_fat_dairy", "legumes_protein"],
    "pescatarian": ["fish", "eggs", "low_fat_dairy", "legumes_protein"],
    "vegetarian": ["eggs", "low_fat_dairy", "legumes_protein", "tofu_tempeh"],
    "vegan": ["legumes_protein", "tofu_tempeh", "nuts_seeds"],
}


def split_items(text: Optional[str]) -> List[str]:
    items = [s.strip() for s in re.split(r"[,;\n]", text or "") if s.strip()]
    return [s[:120] for s in items][:20]


def _unique(values: Iterable[str]) -> List[str]:
    seen, out = set(), []
    for v in values:
        key = v.lower()
        if key not in seen:
            seen.add(key)
            out.append(v)
    return out


def energy_estimate(
    sex: Optional[str],
    age: Optional[int],
    weight_kg: Optional[float],
    height_cm: Optional[float],
    activity_min_week: Optional[int],
) -> Optional[Tuple[int, int]]:
    """(BMR, total daily energy) in kcal, or None without sex/age/weight/height."""
    if None in (age, weight_kg, height_cm) or sex not in ("M", "F"):
        return None
    bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + (5 if sex == "M" else -161)
    if activity_min_week is None or activity_min_week < 60:
        factor = 1.2
    elif activity_min_week < 150:
        factor = 1.375
    else:
        factor = 1.55
    return round(bmr), round(bmr * factor)


def generate_nutrition_plan(
    result: Dict[str, Any],
    profile: Any,
    allergies: List[str],
) -> Tuple[Dict[str, Any], List[str]]:
    """Rule-based draft nutrition plan and the reasons (keys) that shaped it."""
    patient = result.get("patient", {})
    sex, age = patient.get("sex"), patient.get("age")
    history = result.get("history") or {}

    def v(key):
        return _value(result, key)

    weight, height, bmi, waist = v("weight"), v("height"), v("bmi"), v("waist")
    glucose, hba1c, tg = v("glucose"), v("hba1c"), v("triglycerides")
    hdl, ldl, total_chol = v("hdl"), v("ldl"), v("total_cholesterol")
    alt, ggt, creatinine, uric = v("alt"), v("ggt"), v("creatinine"), v("uric_acid")
    systolic, diastolic = v("systolic"), v("diastolic")
    activity = getattr(profile, "physical_activity_minutes_week", None)
    pattern = getattr(profile, "diet_pattern", None) or "omnivore"
    male = sex == "M"

    rationale: List[str] = []
    safety = ["professional_review", "no_extreme_diets"]

    central = sex in ("M", "F") and waist is not None and waist >= (90 if male else 80)
    lose = (bmi or 0) >= 25 or central
    rationale.append("weight_loss" if lose else "maintenance")

    energy: Dict[str, Any] = {"deficit_kcal": 0}
    estimate = energy_estimate(sex, age, weight, height, activity)
    kcal = None
    if estimate is None:
        rationale.append("missing_anthropometry")
    else:
        bmr, tdee = estimate
        deficit = (500 if (bmi or 0) >= 30 else 300) if lose else 0
        kcal = int(round(max(tdee - deficit, 1500 if male else 1200) / 50) * 50)
        energy = {
            "kcal_target": kcal,
            "deficit_kcal": max(tdee - kcal, 0),
            "bmr_kcal": bmr,
            "tdee_kcal": tdee,
        }

    renal = creatinine is not None and creatinine >= (1.3 if sex != "F" else 1.1)
    if renal:
        rationale.append("renal_review")
        safety.append("renal_review")
        g_kg = (0.8, 0.8)
    else:
        g_kg = (1.2, 1.5) if lose else (1.0, 1.2)
    reference = None
    if weight and height:
        ideal = 22.5 * (height / 100) ** 2
        reference = ideal + 0.25 * (weight - ideal) if weight > ideal else weight

    diabetes = bool(history.get("has_diabetes"))
    glycemic = (
        (glucose or 0) >= 100
        or (hba1c or 0) >= 5.7
        or diabetes
        or bool(history.get("has_prediabetes"))
    )
    high_tg = (tg or 0) >= 150
    low_hdl = hdl is not None and hdl < (40 if male else 50)
    high_ldl = (
        (ldl or 0) >= 130
        or (total_chol or 0) >= 200
        or bool(history.get("has_dyslipidemia"))
    )
    cvd = bool(history.get("has_cardiovascular_disease"))
    bp = (
        (systolic or 0) >= 130
        or (diastolic or 0) >= 80
        or bool(history.get("has_hypertension"))
    )
    uric_high = uric is not None and uric >= (7.0 if sex != "F" else 6.0)
    liver = (
        bool(history.get("has_fatty_liver"))
        or (alt or 0) >= (40 if sex != "F" else 31)
        or (ggt or 0) >= 60
    )

    limit = ["sugary_drinks", "ultraprocessed", "refined_flours", "fried_foods"]
    if pattern in ("omnivore", "other"):
        limit.append("processed_meat")
    prioritize = ["vegetables", "legumes", "whole_grains", "fruit_whole"]
    prioritize += PROTEIN_SOURCES.get(pattern, PROTEIN_SOURCES["omnivore"])
    prioritize += ["nuts_seeds", "olive_oil", "water"]

    if glycemic:
        rationale.append("glycemic")
        limit += ["fruit_juice", "sweets"]
    if diabetes:
        safety.append("diabetes_meds")
    if high_tg:
        rationale.append("triglycerides")
        limit += ["alcohol", "sweets"]
    if high_ldl or low_hdl or cvd:
        rationale.append("lipids")
        limit.append("saturated_fats")
        if pattern not in ("vegetarian", "vegan"):
            prioritize.insert(4, "oily_fish")
    if bp:
        rationale.append("blood_pressure")
        limit += ["added_salt", "salty_snacks"]
    if uric_high:
        rationale.append("uric_acid")
        limit += ["fructose_drinks", "organ_meats", "alcohol"]
    if liver:
        rationale.append("liver")
        limit += ["alcohol", "fructose_drinks"]
    if getattr(profile, "alcohol", None) in ("weekly", "daily"):
        limit.append("alcohol")
    if pattern == "vegan":
        safety.append("b12_review")

    avoid = _unique(
        list(allergies) + split_items(getattr(profile, "food_intolerances", None))
    )
    if avoid:
        rationale.append("allergies")
        safety.append("allergy_check")

    macros = {
        "protein_g_kg_min": g_kg[0],
        "protein_g_kg_max": g_kg[1],
        "protein_g_min": round(reference * g_kg[0]) if reference else None,
        "protein_g_max": round(reference * g_kg[1]) if reference else None,
        "carbs_pct_min": 35 if glycemic else 45,
        "carbs_pct_max": 45 if glycemic else 55,
        "fat_pct_min": 25,
        "fat_pct_max": 35,
        "fiber_g_min": max(30 if male else 25, round(kcal * 14 / 1000) if kcal else 0),
        "added_sugar_g_max": 25 if (glycemic or high_tg or uric_high or liver) else 50,
        "saturated_fat_pct_max": 7 if (high_ldl or cvd) else 10,
        "sodium_mg_max": 1500 if bp else 2000,
    }
    meals = {
        "meals_per_day": getattr(profile, "meals_per_day", None) or 3,
        "snacks_per_day": 1 if glycemic else 0,
        "plate_model": True,
        "protein_each_meal": True,
        "regular_schedule": glycemic,
    }

    targets: List[str] = []
    if getattr(profile, "sugary_drinks_per_week", None):
        targets.append("sugary_drinks_zero")
    fruit_veg = getattr(profile, "fruit_veg_servings_day", None)
    if fruit_veg is None or fruit_veg < 5:
        targets.append("fruit_veg_5")
    if (getattr(profile, "ultraprocessed_per_week", None) or 0) > 3:
        targets.append("ultraprocessed_down")
    if lose:
        targets.append("weight_5pct")
    if central:
        targets.append("waist_down")
    targets.append("water_daily")

    plan = {
        "energy": energy,
        "macros": macros,
        "meals": meals,
        "hydration_l": round(min(max(weight * 0.03, 1.5), 3.0), 1) if weight else 2.0,
        "prioritize": _unique(prioritize),
        "limit": _unique(limit),
        "avoid": avoid,
        "dislikes": split_items(getattr(profile, "food_dislikes", None)),
        "targets": targets,
        "safety": safety,
    }
    return plan, rationale
