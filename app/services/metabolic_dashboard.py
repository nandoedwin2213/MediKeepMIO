"""Professional dashboard: risk distribution and follow-up alerts across accessible patients."""

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.metabolic import AdherenceLog, ExercisePlan, MetabolicAssessment
from app.models.models import User
from app.services.metabolic_engine import evaluate_patient, save_if_changed
from app.services.metabolic_progress import MEASURED_SOURCES, _to_date, build_progress
from app.services.patient_access import PatientAccessService

PROFESSIONAL_ROLES = {
    "admin",
    "administrator",
    "doctor",
    "nurse",
    "staff",
    "physio",
    "nutritionist",
}
LEVELS = ("favorable", "initial", "moderate", "high", "unknown")
ALERT_KEYS = (
    "high_risk",
    "risk_increased",
    "critical",
    "hba1c",
    "stale",
    "no_data",
    "no_activity",
)
LEVEL_SEVERITY = {"high": 3, "moderate": 2, "initial": 1, "favorable": 0}
STALE_DAYS = 90
INACTIVE_DAYS = 7
ACTIVITY_ITEMS = ("exercise", "walk")
MAX_PATIENTS = 500


def is_professional(user: User) -> bool:
    return (user.role or "").lower() in PROFESSIONAL_ROLES


def last_measured_date(result: Dict[str, Any]) -> Optional[date]:
    dates = [
        d
        for d in (
            _to_date(v.get("date"))
            for v in result.get("inputs", {}).values()
            if v.get("source") in MEASURED_SOURCES
        )
        if d
    ]
    return max(dates) if dates else None


def summarize(
    result: Dict[str, Any],
    change: Optional[Dict[str, Any]],
    today: date,
    inactive: bool = False,
) -> Dict[str, Any]:
    score = result.get("score") or {}
    last = last_measured_date(result)
    days = (today - last).days if last else None
    delta = change.get("score_delta") if change else None
    hba1c = (result.get("indicators") or {}).get("hba1c") or {}
    alerts: List[str] = []
    if score.get("level") == "high":
        alerts.append("high_risk")
    if delta is not None and delta < 0:
        alerts.append("risk_increased")
    if result.get("alerts"):
        alerts.append("critical")
    if hba1c.get("level") in ("high", "veryHigh"):
        alerts.append("hba1c")
    if last is None:
        alerts.append("no_data")
    elif days > STALE_DAYS:
        alerts.append("stale")
    if inactive:
        alerts.append("no_activity")
    return {
        "score": score.get("value"),
        "level": score.get("level") or "unknown",
        "metabolic_syndrome": (result.get("metabolic_syndrome") or {}).get("status"),
        "score_delta": delta,
        "last_data_date": last.isoformat() if last else None,
        "days_since_data": days,
        "alerts": alerts,
        "critical_alerts": result.get("alerts") or [],
        "top_factors": [
            f
            for f in (result.get("factors") or [])
            if f.get("level") in ("high", "veryHigh")
        ][:3],
    }


def is_inactive(db: Session, patient_id: int, today: date) -> bool:
    """Approved exercise plan older than INACTIVE_DAYS with no activity logged since."""
    cutoff = today - timedelta(days=INACTIVE_DAYS)
    plan = (
        db.query(ExercisePlan.approved_at)
        .filter(
            ExercisePlan.patient_id == patient_id, ExercisePlan.status == "approved"
        )
        .order_by(ExercisePlan.approved_at.desc())
        .first()
    )
    if plan is None or plan.approved_at is None or plan.approved_at.date() > cutoff:
        return False
    logged = (
        db.query(AdherenceLog.id)
        .filter(
            AdherenceLog.patient_id == patient_id,
            AdherenceLog.item.in_(ACTIVITY_ITEMS),
            AdherenceLog.done.is_(True),
            AdherenceLog.log_date > cutoff,
        )
        .first()
    )
    return logged is None


def build_dashboard(db: Session, user: User) -> Dict[str, Any]:
    access = PatientAccessService(db)
    patients = sorted(access.get_accessible_patients(user), key=lambda p: p.id)[
        :MAX_PATIENTS
    ]
    today = date.today()
    rows = []
    for patient in patients:
        result = evaluate_patient(db, patient)
        if access.can_access_patient(user, patient, "edit"):
            save_if_changed(db, patient.id, result, user.id)
        assessments = (
            db.query(MetabolicAssessment)
            .filter(MetabolicAssessment.patient_id == patient.id)
            .order_by(
                MetabolicAssessment.assessed_at.desc(), MetabolicAssessment.id.desc()
            )
            .limit(100)
            .all()
        )
        change = build_progress(assessments)["change"]
        rows.append(
            {
                "patient_id": patient.id,
                "name": f"{patient.first_name} {patient.last_name}".strip(),
                **summarize(result, change, today, is_inactive(db, patient.id, today)),
            }
        )
    rows.sort(
        key=lambda r: (
            -len(r["alerts"]),
            -LEVEL_SEVERITY.get(r["level"], -1),
            r["score"] if r["score"] is not None else 101,
        )
    )
    by_level = {level: 0 for level in LEVELS}
    alert_counts = {key: 0 for key in ALERT_KEYS}
    for row in rows:
        by_level[row["level"] if row["level"] in by_level else "unknown"] += 1
        for key in row["alerts"]:
            alert_counts[key] += 1
    return {
        "total": len(rows),
        "by_level": by_level,
        "alerts": alert_counts,
        "needs_follow_up": sum(1 for r in rows if r["alerts"]),
        "stale_days": STALE_DAYS,
        "inactive_days": INACTIVE_DAYS,
        "patients": rows,
    }
