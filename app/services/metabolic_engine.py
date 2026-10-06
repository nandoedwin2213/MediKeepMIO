"""Metabolic Risk Engine.

Collects the latest labs, vitals and habits of a patient, normalizes units,
computes metabolic indices, classifies them with the active clinical
configuration and builds an internal 0-100 follow-up score, risk factors,
metabolic syndrome criteria and safety alerts.

The score is an internal follow-up indicator, not a validated diagnostic tool.
"""

import hashlib
import json
import math
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.clinical import Vitals
from app.models.labs import LabResult, LabTestComponent
from app.models.metabolic import (
    MetabolicAssessment,
    MetabolicEngineConfig,
    MetabolicProfile,
)
from app.models.patient import Patient
from app.services.metabolic_config import ALGORITHM_VERSION, default_config

LB_TO_KG = 0.45359237
IN_TO_CM = 2.54

SEVERITY = {"veryHigh": 4, "high": 3, "borderline": 2, "low": 2, "normal": 0}

LAB_ALIASES: Dict[str, List[str]] = {
    "glucose": [
        "fasting glucose",
        "glucose",
        "glucosa",
        "glucosa en ayunas",
        "glucose, fasting",
        "fasting blood glucose",
        "glu",
        "gluc",
        "fbg",
    ],
    "insulin": [
        "fasting insulin",
        "insulin",
        "insulina",
        "insulina en ayunas",
        "insulina basal",
    ],
    "hba1c": [
        "hemoglobin a1c",
        "hba1c",
        "a1c",
        "hemoglobina glicosilada",
        "hemoglobina glucosilada",
        "glycated hemoglobin",
    ],
    "triglycerides": ["triglycerides", "triglicéridos", "trigliceridos", "trig", "tg"],
    "hdl": ["hdl cholesterol", "hdl", "hdl-c", "colesterol hdl"],
    "ldl": [
        "ldl cholesterol",
        "ldl",
        "ldl-c",
        "colesterol ldl",
        "ldl cholesterol (calculated)",
    ],
    "total_cholesterol": [
        "total cholesterol",
        "cholesterol",
        "colesterol total",
        "colesterol",
        "chol",
    ],
    "alt": ["alt", "alt (sgpt)", "sgpt", "tgp", "alanine aminotransferase"],
    "ast": ["ast", "ast (sgot)", "sgot", "tgo", "aspartate aminotransferase"],
    "ggt": [
        "ggt",
        "gamma gt",
        "gamma-glutamyl transferase",
        "gamma glutamil transferasa",
    ],
    "creatinine": ["creatinine", "creatinina", "creat"],
    "uric_acid": ["uric acid", "ácido úrico", "acido urico", "urate"],
}
_ALIAS_INDEX = {alias: var for var, aliases in LAB_ALIASES.items() for alias in aliases}

_MG_DL = {"mg/dl": 1.0, "": 1.0}
UNIT_FACTORS: Dict[str, Dict[str, float]] = {
    "glucose": {**_MG_DL, "mmol/l": 18.016},
    "insulin": {
        "µu/ml": 1.0,
        "uu/ml": 1.0,
        "µiu/ml": 1.0,
        "uiu/ml": 1.0,
        "mu/l": 1.0,
        "miu/l": 1.0,
        "": 1.0,
        "pmol/l": 1 / 6,
    },
    "hba1c": {"%": 1.0, "": 1.0},
    "triglycerides": {**_MG_DL, "mmol/l": 88.57},
    "hdl": {**_MG_DL, "mmol/l": 38.67},
    "ldl": {**_MG_DL, "mmol/l": 38.67},
    "total_cholesterol": {**_MG_DL, "mmol/l": 38.67},
    "alt": {"u/l": 1.0, "iu/l": 1.0, "ui/l": 1.0, "": 1.0},
    "ast": {"u/l": 1.0, "iu/l": 1.0, "ui/l": 1.0, "": 1.0},
    "ggt": {"u/l": 1.0, "iu/l": 1.0, "ui/l": 1.0, "": 1.0},
    "creatinine": {**_MG_DL, "µmol/l": 1 / 88.4, "umol/l": 1 / 88.4},
    "uric_acid": {**_MG_DL, "µmol/l": 1 / 59.48, "umol/l": 1 / 59.48, "mmol/l": 16.81},
}
CANONICAL_UNITS = {
    "glucose": "mg/dL",
    "insulin": "µU/mL",
    "hba1c": "%",
    "triglycerides": "mg/dL",
    "hdl": "mg/dL",
    "ldl": "mg/dL",
    "total_cholesterol": "mg/dL",
    "alt": "U/L",
    "ast": "U/L",
    "ggt": "U/L",
    "creatinine": "mg/dL",
    "uric_acid": "mg/dL",
    "weight": "kg",
    "height": "cm",
    "waist": "cm",
    "hip": "cm",
    "bmi": "kg/m²",
    "systolic": "mmHg",
    "diastolic": "mmHg",
    "physical_activity": "min/sem",
    "sitting": "h/día",
    "sleep": "h",
    "sugary_drinks": "/sem",
    "ultraprocessed": "/sem",
    "fruit_veg": "/día",
}

# Indicators that become "What is affecting your metabolism?" cards.
FACTOR_KEYS = (
    "waist",
    "waist_height",
    "waist_hip",
    "homa_ir",
    "tyg",
    "glucose",
    "hba1c",
    "triglycerides",
    "hdl",
    "tg_hdl",
    "ldl",
    "blood_pressure",
    "bmi",
    "alt",
    "uric_acid",
    "physical_activity",
    "sitting",
    "sleep",
    "smoking",
    "alcohol",
    "sugary_drinks",
    "ultraprocessed",
    "fruit_veg",
)


def normalize_unit(unit: Optional[str]) -> str:
    return (unit or "").strip().lower().replace("μ", "µ").replace(" ", "")


def convert_lab_value(
    variable: str, value: float, unit: Optional[str]
) -> Optional[float]:
    """Convert a lab value to the canonical unit, or None if the unit is unknown."""
    u = normalize_unit(unit)
    if variable == "hba1c" and u == "mmol/mol":
        return value / 10.929 + 2.15
    factor = UNIT_FACTORS.get(variable, {}).get(u)
    return None if factor is None else value * factor


def normalize_sex(gender: Optional[str]) -> Optional[str]:
    g = (gender or "").strip().lower()
    if g in ("m", "male", "masculino", "hombre"):
        return "M"
    if g in ("f", "female", "femenino", "mujer"):
        return "F"
    return None


def _age(birth_date: Optional[date], today: date) -> Optional[int]:
    if not birth_date:
        return None
    return (
        today.year
        - birth_date.year
        - ((today.month, today.day) < (birth_date.month, birth_date.day))
    )


def _iso(d: Any) -> Optional[str]:
    return d.isoformat() if isinstance(d, (date, datetime)) else None


def get_active_config(
    db: Session,
) -> Tuple[int, Dict[str, Any], Optional[MetabolicEngineConfig]]:
    row = (
        db.query(MetabolicEngineConfig)
        .order_by(MetabolicEngineConfig.version.desc())
        .first()
    )
    if row is None:
        return 0, default_config(), None
    return row.version, row.config, row


def classify(
    config: Dict[str, Any], key: str, value: Any, sex: Optional[str]
) -> Tuple[Optional[str], Optional[list]]:
    indicator = config.get("indicators", {}).get(key)
    if not indicator or value is None:
        return None, None
    if "map" in indicator:
        return indicator["map"].get(value), None
    bands = indicator.get("bands")
    if bands is None and "by_sex" in indicator:
        bands = indicator["by_sex"].get(sex) if sex else None
    if not bands:
        return None, None
    for band in bands:
        lo, hi = band.get("min"), band.get("max")
        if (lo is None or value >= lo) and (hi is None or value < hi):
            return band["level"], bands
    return None, bands


def _compare(value: float, op: str, threshold: float) -> bool:
    return {
        ">=": value >= threshold,
        ">": value > threshold,
        "<=": value <= threshold,
        "<": value < threshold,
    }[op]


# --- data collection -------------------------------------------------------


def collect_lab_points(
    db: Session, patient_id: int
) -> Tuple[Dict[str, list], Dict[int, Dict[str, dict]], list]:
    """Return lab points per variable (newest first), per lab result, and warnings."""
    rows = (
        db.query(LabTestComponent, LabResult)
        .join(LabResult, LabTestComponent.lab_result_id == LabResult.id)
        .filter(LabResult.patient_id == patient_id, LabTestComponent.value.isnot(None))
        .all()
    )
    by_var: Dict[str, list] = {}
    by_result: Dict[int, Dict[str, dict]] = {}
    warnings: list = []
    for component, result in rows:
        names = [
            component.test_name,
            component.canonical_test_name,
            component.abbreviation,
        ]
        variable = next(
            (
                _ALIAS_INDEX[n.strip().lower()]
                for n in names
                if n and n.strip().lower() in _ALIAS_INDEX
            ),
            None,
        )
        if variable is None:
            continue
        converted = convert_lab_value(variable, component.value, component.unit)
        if converted is None:
            warnings.append(
                {"code": "unknown_unit", "variable": variable, "unit": component.unit}
            )
            continue
        when = (
            result.completed_date
            or (result.created_at.date() if result.created_at else None)
            or (component.created_at.date() if component.created_at else None)
        )
        point = {
            "value": converted,
            "unit": CANONICAL_UNITS[variable],
            "raw_value": component.value,
            "raw_unit": component.unit,
            "date": _iso(when),
            "source": "lab",
            "source_id": component.id,
            "lab_result_id": result.id,
            "_sort": (when or date.min, result.id, component.id),
        }
        by_var.setdefault(variable, []).append(point)
        by_result.setdefault(result.id, {})[variable] = point
    for points in by_var.values():
        points.sort(key=lambda p: p["_sort"], reverse=True)
    return by_var, by_result, warnings


def latest_same_sample(
    by_result: Dict[int, Dict[str, dict]], variables: List[str]
) -> Optional[Dict[str, dict]]:
    """Most recent lab result that contains all ``variables``."""
    candidates = [
        vals for vals in by_result.values() if all(v in vals for v in variables)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda vals: max(vals[v]["_sort"] for v in variables))


def collect_vitals(db: Session, patient: Patient) -> Dict[str, dict]:
    rows = (
        db.query(Vitals)
        .filter(Vitals.patient_id == patient.id)
        .order_by(Vitals.recorded_date.desc(), Vitals.id.desc())
        .all()
    )
    out: Dict[str, dict] = {}

    def point(row: Vitals, value: float, unit: str, raw: float) -> dict:
        return {
            "value": value,
            "unit": unit,
            "raw_value": raw,
            "date": _iso(row.recorded_date),
            "source": row.import_source or "vitals",
            "source_id": row.id,
        }

    for row in rows:
        if "weight" not in out and row.weight:
            out["weight"] = point(row, row.weight * LB_TO_KG, "kg", row.weight)
        if "height" not in out and row.height:
            out["height"] = point(row, row.height * IN_TO_CM, "cm", row.height)
        if "waist" not in out and row.waist_circumference:
            out["waist"] = point(
                row, row.waist_circumference * IN_TO_CM, "cm", row.waist_circumference
            )
        if "hip" not in out and getattr(row, "hip_circumference", None):
            out["hip"] = point(
                row, row.hip_circumference * IN_TO_CM, "cm", row.hip_circumference
            )
        if "systolic" not in out and row.systolic_bp and row.diastolic_bp:
            out["systolic"] = point(
                row, float(row.systolic_bp), "mmHg", row.systolic_bp
            )
            out["diastolic"] = point(
                row, float(row.diastolic_bp), "mmHg", row.diastolic_bp
            )
        if "hba1c" not in out and row.a1c:
            out["hba1c"] = point(row, float(row.a1c), "%", row.a1c)
    if "height" not in out and patient.height:
        out["height"] = {
            "value": patient.height * IN_TO_CM,
            "unit": "cm",
            "raw_value": patient.height,
            "date": None,
            "source": "patient",
            "source_id": patient.id,
        }
    return out


PROFILE_FIELDS = {
    "physical_activity": "physical_activity_minutes_week",
    "sitting": "sitting_hours_day",
    "sleep": "sleep_hours",
    "sugary_drinks": "sugary_drinks_per_week",
    "ultraprocessed": "ultraprocessed_per_week",
    "fruit_veg": "fruit_veg_servings_day",
    "smoking": "smoking",
    "alcohol": "alcohol",
}


def collect_profile(profile: Optional[MetabolicProfile]) -> Dict[str, dict]:
    if profile is None:
        return {}
    out = {}
    for key, field in PROFILE_FIELDS.items():
        value = getattr(profile, field)
        if value is not None and value != "":
            out[key] = {
                "value": value,
                "unit": CANONICAL_UNITS.get(key),
                "date": _iso(profile.updated_at),
                "source": "profile",
                "source_id": profile.id,
            }
    return out


# --- evaluation ------------------------------------------------------------


def _public(point: dict) -> dict:
    return {k: v for k, v in point.items() if not k.startswith("_")}


def evaluate_data(
    config: Dict[str, Any],
    config_version: int,
    sex: Optional[str],
    age: Optional[int],
    lab_by_var: Dict[str, list],
    lab_by_result: Dict[int, Dict[str, dict]],
    vitals: Dict[str, dict],
    habits: Dict[str, dict],
    history: Optional[Dict[str, Any]] = None,
    warnings: Optional[list] = None,
) -> Dict[str, Any]:
    """Pure evaluation step (no database access) so it can be unit tested."""
    history = history or {}
    inputs: Dict[str, dict] = {}
    indicators: Dict[str, dict] = {}

    for variable, points in lab_by_var.items():
        inputs[variable] = _public(points[0])
    for key, point in vitals.items():
        if key == "hba1c" and "hba1c" in inputs:
            lab_date = inputs["hba1c"].get("date") or ""
            if (point.get("date") or "")[:10] <= lab_date:
                continue
        inputs[key] = point
    inputs.update(habits)

    def value(key: str) -> Optional[float]:
        return inputs[key]["value"] if key in inputs else None

    def add(
        key: str,
        val: Optional[float],
        unit: Optional[str],
        used: List[str],
        digits: int,
        when: Optional[str] = None,
    ):
        if val is None:
            return
        rounded = round(val, digits) if isinstance(val, float) else val
        level, bands = classify(config, key, rounded, sex)
        indicators[key] = {
            "value": rounded,
            "unit": unit,
            "level": level,
            "bands": bands,
            "inputs": used,
            "date": when
            or next(
                (
                    inputs[u].get("date")
                    for u in used
                    if u in inputs and inputs[u].get("date")
                ),
                None,
            ),
        }

    # Direct measurements
    for key, digits in (
        ("glucose", 0),
        ("insulin", 1),
        ("hba1c", 1),
        ("triglycerides", 0),
        ("hdl", 0),
        ("ldl", 0),
        ("total_cholesterol", 0),
        ("alt", 0),
        ("ast", 0),
        ("ggt", 0),
        ("creatinine", 2),
        ("uric_acid", 1),
        ("waist", 1),
        ("systolic", 0),
        ("diastolic", 0),
    ):
        add(key, value(key), CANONICAL_UNITS.get(key), [key], digits)
    for key in (
        "physical_activity",
        "sitting",
        "sleep",
        "sugary_drinks",
        "ultraprocessed",
        "fruit_veg",
        "smoking",
        "alcohol",
    ):
        if key in inputs:
            v = inputs[key]["value"]
            add(
                key,
                float(v) if isinstance(v, (int, float)) else v,
                CANONICAL_UNITS.get(key),
                [key],
                1,
            )

    # Anthropometric indices
    weight, height, waist, hip = (
        value("weight"),
        value("height"),
        value("waist"),
        value("hip"),
    )
    bmi = weight / (height / 100) ** 2 if weight and height else None
    if bmi is not None:
        inputs["bmi"] = {
            "value": round(bmi, 2),
            "unit": "kg/m²",
            "date": inputs["weight"].get("date"),
            "source": "derived",
        }
    add("bmi", bmi, "kg/m²", ["weight", "height"], 1)
    add(
        "waist_height",
        waist / height if waist and height else None,
        None,
        ["waist", "height"],
        2,
    )
    add("waist_hip", waist / hip if waist and hip else None, None, ["waist", "hip"], 2)

    # Blood pressure: worst of systolic and diastolic
    if "systolic" in indicators and "diastolic" in indicators:
        sys_i, dia_i = indicators["systolic"], indicators["diastolic"]
        worst = max(
            (sys_i["level"], dia_i["level"]), key=lambda lv: SEVERITY.get(lv or "", -1)
        )
        indicators["blood_pressure"] = {
            "value": f"{int(sys_i['value'])}/{int(dia_i['value'])}",
            "unit": "mmHg",
            "level": worst,
            "bands": None,
            "inputs": ["systolic", "diastolic"],
            "date": sys_i["date"],
        }

    # Lab indices from the same sample
    sample = latest_same_sample(lab_by_result, ["glucose", "insulin"])
    if sample:
        g, i = sample["glucose"]["value"], sample["insulin"]["value"]
        when = sample["glucose"]["date"]
        if g > 0 and i > 0:
            add("homa_ir", g * i / 405, None, ["glucose", "insulin"], 2, when)
            add(
                "quicki",
                1 / (math.log10(i) + math.log10(g)),
                None,
                ["glucose", "insulin"],
                3,
                when,
            )
    sample = latest_same_sample(lab_by_result, ["glucose", "triglycerides"])
    tyg = None
    if sample:
        g, tg = sample["glucose"]["value"], sample["triglycerides"]["value"]
        if g > 0 and tg > 0:
            tyg = math.log(tg * g / 2)
            add(
                "tyg",
                tyg,
                None,
                ["glucose", "triglycerides"],
                2,
                sample["glucose"]["date"],
            )
            if bmi:
                add(
                    "tyg_bmi",
                    tyg * bmi,
                    None,
                    ["glucose", "triglycerides", "weight", "height"],
                    1,
                    sample["glucose"]["date"],
                )
    sample = latest_same_sample(lab_by_result, ["triglycerides", "hdl"])
    if sample and sample["hdl"]["value"] > 0:
        add(
            "tg_hdl",
            sample["triglycerides"]["value"] / sample["hdl"]["value"],
            None,
            ["triglycerides", "hdl"],
            2,
            sample["triglycerides"]["date"],
        )
    sample = latest_same_sample(lab_by_result, ["glucose", "triglycerides", "hdl"])
    if sample and bmi:
        g, tg, hdl = (sample[k]["value"] for k in ("glucose", "triglycerides", "hdl"))
        if hdl > 1 and g > 0 and tg > 0:
            add(
                "mets_ir",
                math.log(2 * g + tg) * bmi / math.log(hdl),
                None,
                ["glucose", "triglycerides", "hdl", "weight", "height"],
                1,
                sample["glucose"]["date"],
            )

    syndrome = _metabolic_syndrome(config, sex, inputs, history)
    score = _score(config, indicators)
    factors = sorted(
        (
            {
                "key": key,
                "level": indicators[key]["level"],
                "value": indicators[key]["value"],
                "unit": indicators[key]["unit"],
            }
            for key in FACTOR_KEYS
            if key in indicators and indicators[key]["level"]
        ),
        key=lambda f: (
            -SEVERITY.get(f["level"], 0),
            -config.get("score_weights", {}).get(f["key"], 0),
        ),
    )
    alerts = []
    for rule in config.get("alerts", []):
        v = value(rule["metric"])
        if isinstance(v, (int, float)) and _compare(v, rule["op"], rule["value"]):
            alerts.append(
                {
                    "id": rule["id"],
                    "metric": rule["metric"],
                    "value": round(v, 2),
                    "op": rule["op"],
                    "threshold": rule["value"],
                }
            )

    return {
        "algorithm_version": ALGORITHM_VERSION,
        "config_version": config_version,
        "patient": {"sex": sex, "age": age},
        "inputs": inputs,
        "indicators": indicators,
        "metabolic_syndrome": syndrome,
        "score": score,
        "factors": factors,
        "alerts": alerts,
        "warnings": warnings or [],
    }


def _metabolic_syndrome(config, sex, inputs, history) -> Dict[str, Any]:
    spec = config.get("metabolic_syndrome", {})
    required = spec.get("required", 3)
    criteria = []
    for criterion in spec.get("criteria", []):
        rules = criterion.get("any", [criterion])
        met: Optional[bool] = None
        values = {}
        for rule in rules:
            v = inputs.get(rule["metric"], {}).get("value")
            threshold = rule["value"]
            if isinstance(threshold, dict):
                threshold = threshold.get(sex) if sex else None
            if v is None or threshold is None:
                continue
            values[rule["metric"]] = round(v, 2)
            hit = _compare(v, rule["op"], threshold)
            met = hit if met is None else (met or hit)
        if criterion.get("history") and history.get(criterion["history"]):
            met = True
            values["history"] = criterion["history"]
        criteria.append({"id": criterion["id"], "met": met, "values": values})
    met_count = sum(1 for c in criteria if c["met"] is True)
    unknown = sum(1 for c in criteria if c["met"] is None)
    if met_count >= required:
        status = "compatible"
    elif met_count + unknown < required:
        status = "not_compatible"
    else:
        status = "indeterminate"
    return {
        "status": status,
        "met": met_count,
        "evaluated": len(criteria) - unknown,
        "total": len(criteria),
        "required": required,
        "criteria": criteria,
    }


def _score(config, indicators) -> Dict[str, Any]:
    weights = config.get("score_weights", {})
    points = config.get("level_points", {})
    total_weight = sum(weights.values()) or 1
    components = []
    for key, weight in weights.items():
        level = indicators.get(key, {}).get("level")
        if level is None or weight <= 0:
            continue
        components.append(
            {
                "key": key,
                "level": level,
                "points": points.get(level, 0),
                "weight": weight,
            }
        )
    used = sum(c["weight"] for c in components)
    coverage = round(used / total_weight, 2)
    if not components or coverage < config.get("score_min_coverage", 0):
        return {
            "value": None,
            "level": None,
            "coverage": coverage,
            "components": components,
        }
    value = round(sum(c["points"] * c["weight"] for c in components) / used)
    level = None
    for band in sorted(
        config.get("risk_bands", []), key=lambda b: b["min"], reverse=True
    ):
        if value >= band["min"]:
            level = band["level"]
            break
    return {
        "value": value,
        "level": level,
        "coverage": coverage,
        "components": components,
    }


def history_flags(profile: Optional[MetabolicProfile]) -> Dict[str, Any]:
    if profile is None:
        return {}
    fields = (
        "has_diabetes",
        "has_prediabetes",
        "has_hypertension",
        "has_dyslipidemia",
        "has_fatty_liver",
        "has_obesity",
        "has_cardiovascular_disease",
        "family_diabetes",
    )
    return {f: getattr(profile, f) for f in fields if getattr(profile, f) is not None}


def evaluate_patient(db: Session, patient: Patient) -> Dict[str, Any]:
    config_version, config, _ = get_active_config(db)
    lab_by_var, lab_by_result, warnings = collect_lab_points(db, patient.id)
    profile = (
        db.query(MetabolicProfile)
        .filter(MetabolicProfile.patient_id == patient.id)
        .first()
    )
    result = evaluate_data(
        config,
        config_version,
        normalize_sex(patient.gender),
        _age(patient.birth_date, date.today()),
        lab_by_var,
        lab_by_result,
        collect_vitals(db, patient),
        collect_profile(profile),
        history_flags(profile),
        warnings,
    )
    result["history"] = history_flags(profile)
    return result


def fingerprint(result: Dict[str, Any]) -> str:
    payload = {
        "inputs": {
            k: (v.get("value"), v.get("date"), v.get("source_id"))
            for k, v in result["inputs"].items()
        },
        "history": result.get("history"),
        "patient": result.get("patient"),
        "config_version": result["config_version"],
        "algorithm_version": result["algorithm_version"],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()


def save_if_changed(
    db: Session, patient_id: int, result: Dict[str, Any], user_id: Optional[int]
) -> MetabolicAssessment:
    """Persist a snapshot unless the latest one was computed from identical data."""
    fp = fingerprint(result)
    latest = (
        db.query(MetabolicAssessment)
        .filter(MetabolicAssessment.patient_id == patient_id)
        .order_by(MetabolicAssessment.assessed_at.desc(), MetabolicAssessment.id.desc())
        .first()
    )
    if latest is not None and latest.fingerprint == fp:
        return latest
    assessment = MetabolicAssessment(
        patient_id=patient_id,
        algorithm_version=result["algorithm_version"],
        config_version=result["config_version"],
        fingerprint=fp,
        score=result["score"]["value"],
        risk_level=result["score"]["level"],
        metabolic_syndrome_status=result["metabolic_syndrome"]["status"],
        result=result,
        source="auto",
        created_by_user_id=user_id,
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return assessment
