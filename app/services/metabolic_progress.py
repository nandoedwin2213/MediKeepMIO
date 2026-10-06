"""Longitudinal view of metabolic assessments: comparison windows, progress and change drivers."""

from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

PROGRESS_KEYS = (
    "waist",
    "weight",
    "bmi",
    "homa_ir",
    "tyg",
    "glucose",
    "hba1c",
    "triglycerides",
    "hdl",
    "systolic",
    "diastolic",
    "physical_activity",
)
HIGHER_IS_BETTER = {"hdl", "quicki", "physical_activity", "fruit_veg"}
LEVEL_RANK = {"normal": 0, "low": 1, "borderline": 1, "high": 2, "veryHigh": 3}
MEASURED_SOURCES = {"lab", "vitals"}
WINDOWS = (("d30", 30), ("d60", 60), ("d90", 90), ("m6", 182), ("m12", 365))


def _to_date(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and len(value) >= 10:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def snapshot(assessment: Any) -> Dict[str, Any]:
    """Reduce a stored assessment to the values needed to compare it over time."""
    result = assessment.result or {}
    indicators = result.get("indicators") or {}
    inputs = result.get("inputs") or {}
    dates = [
        d
        for d in (
            _to_date(v.get("date"))
            for v in inputs.values()
            if v.get("source") in MEASURED_SOURCES
        )
        if d
    ]
    data_date = max(dates) if dates else _to_date(assessment.assessed_at)
    values: Dict[str, Dict[str, Any]] = {}
    for key in PROGRESS_KEYS:
        source = indicators.get(key) or inputs.get(key)
        if not source:
            continue
        value = _number(source.get("value"))
        if value is None:
            continue
        values[key] = {
            "value": round(value, 2),
            "unit": source.get("unit"),
            "level": source.get("level"),
        }
    components = {
        c["key"]: c for c in (result.get("score") or {}).get("components") or []
    }
    return {
        "assessment_id": assessment.id,
        "assessed_at": assessment.assessed_at,
        "data_date": data_date,
        "score": assessment.score,
        "risk_level": assessment.risk_level,
        "values": values,
        "components": components,
        "levels": {k: v.get("level") for k, v in indicators.items() if v.get("level")},
    }


def _direction(key: str, before: Dict[str, Any], after: Dict[str, Any]) -> str:
    rank_before = LEVEL_RANK.get(before.get("level"))
    rank_after = LEVEL_RANK.get(after.get("level"))
    if rank_before is not None and rank_after is not None and rank_before != rank_after:
        return "improved" if rank_after < rank_before else "worsened"
    vb, va = before.get("value"), after.get("value")
    if vb is None or va is None or vb == va:
        return "same"
    better = va > vb if key in HIGHER_IS_BETTER else va < vb
    return "improved" if better else "worsened"


def compare(before: Dict[str, Any], after: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Per-indicator change between two snapshots, for keys present in both."""
    rows = []
    for key in PROGRESS_KEYS:
        b, a = before["values"].get(key), after["values"].get(key)
        if not b or not a:
            continue
        rows.append(
            {
                "key": key,
                "from": b["value"],
                "to": a["value"],
                "delta": round(a["value"] - b["value"], 2),
                "unit": a.get("unit") or b.get("unit"),
                "from_level": b.get("level"),
                "to_level": a.get("level"),
                "direction": _direction(key, b, a),
            }
        )
    return rows


def change_drivers(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    """Explain a score change by the score components whose level moved."""
    drivers = []
    keys = set(before["components"]) | set(after["components"])
    for key in keys:
        cb, ca = before["components"].get(key), after["components"].get(key)
        if not cb or not ca or cb["level"] == ca["level"]:
            continue
        impact = (ca["points"] - cb["points"]) * ca["weight"]
        value_b = before["values"].get(key, {}).get("value")
        value_a = after["values"].get(key, {}).get("value")
        drivers.append(
            {
                "key": key,
                "from_level": cb["level"],
                "to_level": ca["level"],
                "from": value_b,
                "to": value_a,
                "delta": (
                    round(value_a - value_b, 2)
                    if value_a is not None and value_b is not None
                    else None
                ),
                "unit": after["values"].get(key, {}).get("unit"),
                "direction": "improved" if impact > 0 else "worsened",
                "impact": impact,
            }
        )
    drivers.sort(key=lambda d: abs(d["impact"]), reverse=True)
    score_b, score_a = before["score"], after["score"]
    delta = (
        round(score_a - score_b)
        if score_a is not None and score_b is not None
        else None
    )
    other = [
        row
        for row in compare(before, after)
        if row["direction"] != "same" and row["key"] not in keys
    ]
    return {
        "from_date": before["data_date"],
        "to_date": after["data_date"],
        "from_score": score_b,
        "to_score": score_a,
        "score_delta": delta,
        "drivers": drivers,
        "other_changes": other,
    }


def _public(snap: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if snap is None:
        return None
    return {k: v for k, v in snap.items() if k not in ("components", "levels")}


def build_progress(assessments: Iterable[Any]) -> Dict[str, Any]:
    snaps = sorted(
        (snapshot(a) for a in assessments),
        key=lambda s: (
            s["data_date"] or date.min,
            s["assessed_at"],
            s["assessment_id"],
        ),
    )
    latest_per_day: Dict[Any, Dict[str, Any]] = {}
    for snap in snaps:
        latest_per_day[snap["data_date"]] = snap
    snaps = list(latest_per_day.values())
    if not snaps:
        return {"timeline": [], "windows": [], "progress": [], "change": None}
    baseline, latest = snaps[0], snaps[-1]
    windows = [
        {"key": "baseline", "days": 0, "snapshot": _public(baseline), "comparison": []}
    ]
    base_date = baseline["data_date"]
    for key, days in WINDOWS:
        chosen = None
        if base_date:
            target = base_date + timedelta(days=days)
            tolerance = max(15, days // 4)
            near = [
                s
                for s in snaps[1:]
                if s["data_date"] and abs((s["data_date"] - target).days) <= tolerance
            ]
            if near:
                chosen = min(near, key=lambda s: abs((s["data_date"] - target).days))
        windows.append(
            {
                "key": key,
                "days": days,
                "snapshot": _public(chosen),
                "comparison": compare(baseline, chosen) if chosen else [],
            }
        )
    windows.append(
        {
            "key": "latest",
            "days": None,
            "snapshot": _public(latest),
            "comparison": compare(baseline, latest) if len(snaps) > 1 else [],
        }
    )
    return {
        "timeline": [_public(s) for s in snaps],
        "windows": windows,
        "progress": compare(baseline, latest) if len(snaps) > 1 else [],
        "change": change_drivers(snaps[-2], latest) if len(snaps) > 1 else None,
    }
