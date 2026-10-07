"""FISAI Metabolic AI: rule-based explanations and an educational what-if simulator.

Everything here is deterministic and runs locally: no clinical data leaves the server.
Outputs are codes and numbers that the frontend turns into translated, plain-language
text. Explanations are drafts until a professional approves them, and the simulator is
an educational recalculation of the score, never a clinical prediction.
"""

import copy
import json
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.metabolic import MetabolicProfile
from app.models.patient import Patient
from app.services.metabolic_engine import (
    FACTOR_KEYS,
    SEVERITY,
    _age,
    collect_lab_points,
    collect_profile,
    collect_vitals,
    evaluate_data,
    get_active_config,
    history_flags,
    normalize_sex,
)
from app.services.metabolic_progress import HIGHER_IS_BETTER, LEVEL_RANK

INSIGHT_VERSION = "insight-0.1.0"
SIMULATOR_VERSION = "sim-0.1.0"
NON_NORMAL = {"borderline", "low", "high", "veryHigh"}
SKIP_KEYS = {"systolic", "diastolic"}

# Priority code -> indicators that trigger it (in display order).
PRIORITY_RULES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("reduce_waist", ("waist", "waist_height", "waist_hip", "bmi")),
    ("increase_activity", ("physical_activity", "sitting")),
    (
        "carb_quality",
        (
            "glucose",
            "hba1c",
            "homa_ir",
            "tyg",
            "triglycerides",
            "tg_hdl",
            "sugary_drinks",
            "ultraprocessed",
        ),
    ),
    (
        "strength",
        ("homa_ir", "tyg", "tyg_bmi", "mets_ir", "waist", "physical_activity"),
    ),
    ("blood_pressure", ("blood_pressure",)),
    ("healthy_fats", ("ldl", "hdl", "total_cholesterol")),
    ("liver", ("alt", "ast", "ggt")),
    ("sleep", ("sleep",)),
    ("stop_smoking", ("smoking",)),
)
MAX_PRIORITIES = 5

LAB_DELTAS = {"triglycerides": 1.0, "glucose": 40.0, "hba1c": 3.5}
VITAL_DELTAS = {"weight": 20.0, "waist": 40.0}


def _weight(config: Dict[str, Any], key: str) -> float:
    return config.get("score_weights", {}).get(key, 0)


def _row(key: str, ind: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "key": key,
        "level": ind.get("level"),
        "value": ind.get("value"),
        "unit": ind.get("unit"),
    }


def build_insight(
    result: Dict[str, Any],
    config: Dict[str, Any],
    change: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Turn an engine result (and optional score change) into explanation codes."""
    indicators = result.get("indicators", {})
    concerns = sorted(
        (
            _row(k, v)
            for k, v in indicators.items()
            if k not in SKIP_KEYS and v.get("level") in NON_NORMAL
        ),
        key=lambda r: (-SEVERITY.get(r["level"], 0), -_weight(config, r["key"])),
    )
    strengths = sorted(
        (
            _row(k, indicators[k])
            for k in set(FACTOR_KEYS) | set(config.get("score_weights", {}))
            if k in indicators and indicators[k].get("level") == "normal"
        ),
        key=lambda r: -_weight(config, r["key"]),
    )
    score = result.get("score") or {}
    alerts = result.get("alerts") or []
    very_high = any(c["level"] == "veryHigh" for c in concerns)
    if not concerns and score.get("value") is None:
        pattern = "insufficient"
    elif not concerns:
        pattern = "favorable"
    elif very_high or alerts:
        pattern = "needs_review"
    elif len(concerns) >= 2:
        pattern = "combination"
    else:
        pattern = "single"

    concern_keys = [c["key"] for c in concerns]
    priorities: List[Dict[str, Any]] = []
    for code, keys in PRIORITY_RULES:
        because = [k for k in concern_keys if k in keys]
        if because:
            priorities.append({"code": code, "because": because})
    priorities = priorities[:MAX_PRIORITIES]
    priorities.append({"code": "repeat_labs", "because": []})

    change_out = None
    if change and change.get("score_delta") is not None:
        change_out = {
            "score_delta": change["score_delta"],
            "from_score": change.get("from_score"),
            "to_score": change.get("to_score"),
            "from_date": change.get("from_date"),
            "to_date": change.get("to_date"),
            "drivers": [
                {
                    k: d.get(k)
                    for k in ("key", "direction", "from", "to", "delta", "unit")
                }
                for d in (change.get("drivers") or [])[:4]
            ],
        }

    content = {
        "version": INSIGHT_VERSION,
        "algorithm_version": result.get("algorithm_version"),
        "config_version": result.get("config_version"),
        "pattern": pattern,
        "needs_review": bool(very_high or alerts),
        "score": {"value": score.get("value"), "level": score.get("level")},
        "concerns": concerns[:6],
        "strengths": strengths[:4],
        "priorities": priorities,
        "change": change_out,
    }
    # Stored in a JSON column: dates from the progress module become ISO strings.
    return json.loads(json.dumps(content, default=str))


def apply_priorities(content: Dict[str, Any], codes: List[str]) -> Dict[str, Any]:
    """Professional edit: keep the chosen priority codes in the chosen order."""
    known = {p["code"]: p for p in content.get("priorities", [])}
    seen, out = set(), []
    for code in codes:
        if code in seen:
            continue
        seen.add(code)
        out.append(known.get(code, {"code": code, "because": []}))
    updated = dict(content)
    updated["priorities"] = out
    updated["edited"] = True
    return updated


# --- simulator --------------------------------------------------------------


def apply_changes(
    lab_by_var: Dict[str, list],
    lab_by_result: Dict[int, Dict[str, dict]],
    vitals: Dict[str, dict],
    habits: Dict[str, dict],
    changes: Dict[str, Optional[float]],
):
    """Copy the inputs with the what-if deltas applied; returns copies + what applied."""
    lab_by_var, lab_by_result = copy.deepcopy((lab_by_var, lab_by_result))
    vitals, habits = copy.deepcopy(vitals), copy.deepcopy(habits)
    applied: Dict[str, Dict[str, Any]] = {}

    def floor(key: str) -> float:
        return 3.0 if key == "hba1c" else 1.0

    for key, delta in changes.items():
        if not delta:
            continue
        hit = None
        if key in LAB_DELTAS:
            for point in lab_by_var.get(key, []):
                hit = hit if hit is not None else point["value"]
                point["value"] = max(point["value"] + delta, floor(key))
            if key in vitals:
                hit = hit if hit is not None else vitals[key]["value"]
                vitals[key]["value"] = max(vitals[key]["value"] + delta, floor(key))
        elif key in VITAL_DELTAS:
            if key in vitals:
                hit = vitals[key]["value"]
                vitals[key]["value"] = max(hit + delta, floor(key))
        elif key == "physical_activity":
            current = habits.get(key, {}).get("value")
            base = float(current) if isinstance(current, (int, float)) else 0.0
            hit = base
            habits[key] = {
                **habits.get(key, {}),
                "value": base + delta,
                "source": "simulation",
            }
        applied[key] = {
            "delta": delta,
            "from": round(hit, 2) if hit is not None else None,
            "missing": hit is None,
        }
    return lab_by_var, lab_by_result, vitals, habits, applied


def _direction(key: str, before: Dict[str, Any], after: Dict[str, Any]) -> str:
    rb, ra = LEVEL_RANK.get(before.get("level")), LEVEL_RANK.get(after.get("level"))
    if rb is not None and ra is not None and rb != ra:
        return "improved" if ra < rb else "worsened"
    vb, va = before.get("value"), after.get("value")
    if vb == va or not isinstance(vb, (int, float)) or not isinstance(va, (int, float)):
        return "same"
    better = va > vb if key in HIGHER_IS_BETTER else va < vb
    return "improved" if better else "worsened"


def compare_results(
    base: Dict[str, Any], sim: Dict[str, Any], applied: Dict[str, Any]
) -> Dict[str, Any]:
    rows = []
    for key, after in sim["indicators"].items():
        before = base["indicators"].get(key)
        if (
            key in SKIP_KEYS
            or before is None
            or before.get("value") == after.get("value")
        ):
            continue
        rows.append(
            {
                "key": key,
                "from": before.get("value"),
                "to": after.get("value"),
                "unit": after.get("unit"),
                "from_level": before.get("level"),
                "to_level": after.get("level"),
                "direction": _direction(key, before, after),
                "level_changed": before.get("level") != after.get("level"),
            }
        )
    rows.sort(key=lambda r: (not r["level_changed"], r["key"]))
    sb, sa = base["score"], sim["score"]
    delta = (
        sa["value"] - sb["value"]
        if sa.get("value") is not None and sb.get("value") is not None
        else None
    )
    return {
        "version": SIMULATOR_VERSION,
        "educational": True,
        "applied": applied,
        "before": {"value": sb.get("value"), "level": sb.get("level")},
        "after": {"value": sa.get("value"), "level": sa.get("level")},
        "score_delta": delta,
        "changes": rows,
    }


def simulate_patient(
    db: Session, patient: Patient, changes: Dict[str, Optional[float]]
) -> Dict[str, Any]:
    config_version, config, _ = get_active_config(db)
    lab_by_var, lab_by_result, warnings = collect_lab_points(db, patient.id)
    profile = (
        db.query(MetabolicProfile)
        .filter(MetabolicProfile.patient_id == patient.id)
        .first()
    )
    vitals, habits, history = (
        collect_vitals(db, patient),
        collect_profile(profile),
        history_flags(profile),
    )
    sex, age = normalize_sex(patient.gender), _age(patient.birth_date, date.today())
    base = evaluate_data(
        config,
        config_version,
        sex,
        age,
        lab_by_var,
        lab_by_result,
        vitals,
        habits,
        history,
        warnings,
    )
    lv, lr, vt, hb, applied = apply_changes(
        lab_by_var, lab_by_result, vitals, habits, changes
    )
    sim = evaluate_data(
        config, config_version, sex, age, lv, lr, vt, hb, history, warnings
    )
    return compare_results(base, sim, applied)
