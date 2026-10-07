"""Weekly programme ("Mi semana metabólica") and adherence checklist endpoints."""

from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional, Set

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api import deps
from app.core.http.error_handling import ValidationException, handle_database_errors
from app.models.clinical import Vitals
from app.models.metabolic import (
    AdherenceLog,
    ExercisePlan,
    MetabolicProfile,
    NutritionPlan,
    Recipe,
    WearableDaily,
)
from app.models.models import User
from app.schemas.metabolic_week import AdherenceWrite
from app.services.metabolic_dashboard import is_professional
from app.services.metabolic_recipes import ensure_library, recommend
from app.services.metabolic_wearables import merge_daily
from app.services.metabolic_week import build_week, week_start

router = APIRouter()
MAX_HISTORY_WEEKS = 26


def _approved(db: Session, model: Any, patient_id: int) -> Any:
    return (
        db.query(model)
        .filter(model.patient_id == patient_id, model.status == "approved")
        .order_by(model.approved_at.desc(), model.id.desc())
        .first()
    )


def _since(plan: Any) -> Optional[date]:
    return plan.approved_at.date() if plan is not None and plan.approved_at else None


def _week_recipes(db: Session, patient_id: int, nutrition: Any) -> list:
    if nutrition is None:
        return []
    ensure_library(db)
    content = nutrition.plan or {}
    profile = (
        db.query(MetabolicProfile)
        .filter(MetabolicProfile.patient_id == patient_id)
        .first()
    )
    ranked = recommend(
        db.query(Recipe).filter(Recipe.is_active.is_(True)).all(),
        diet_pattern=getattr(profile, "diet_pattern", None),
        avoid=list(content.get("avoid") or []),
        dislikes=list(content.get("dislikes") or []),
        rationale=list(nutrition.rationale or []),
        assigned_ids=list(content.get("recipe_ids") or []),
        kcal_target=(content.get("energy") or {}).get("kcal_target"),
        limit=50,
    )
    return [item["recipe"] for item in ranked["items"] if not item["conflicts"]]


def _measured(db: Session, patient_id: int, start: date, end: date) -> Dict[str, Set]:
    rows = (
        db.query(Vitals.recorded_date, Vitals.weight, Vitals.waist_circumference)
        .filter(
            Vitals.patient_id == patient_id,
            Vitals.recorded_date >= datetime.combine(start, datetime.min.time()),
            Vitals.recorded_date
            < datetime.combine(end + timedelta(days=1), datetime.min.time()),
        )
        .all()
    )
    out: Dict[str, Set] = {"weight": set(), "waist": set()}
    for recorded, weight, waist in rows:
        day = recorded.date() if isinstance(recorded, datetime) else recorded
        if weight is not None:
            out["weight"].add(day)
        if waist is not None:
            out["waist"].add(day)
    return out


def _activity(db: Session, patient_id: int, start: date, end: date) -> Dict:
    return merge_daily(
        db.query(WearableDaily).filter(
            WearableDaily.patient_id == patient_id,
            WearableDaily.day >= start,
            WearableDaily.day <= end,
        )
    )


def _logs(db: Session, patient_id: int, start: date, end: date) -> list:
    return (
        db.query(AdherenceLog)
        .filter(
            AdherenceLog.patient_id == patient_id,
            AdherenceLog.log_date >= start,
            AdherenceLog.log_date <= end,
        )
        .all()
    )


def _plan_ref(plan: Any) -> Optional[Dict[str, Any]]:
    if plan is None:
        return None
    return {
        "id": plan.id,
        "approved_at": plan.approved_at.isoformat() if plan.approved_at else None,
    }


@router.get("/patients/{patient_id}/week")
def get_week(
    *,
    patient_id: int,
    start: Optional[date] = None,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Monday–Sunday programme from the approved plans plus the adherence checklist."""
    deps.verify_patient_access(patient_id, db, current_user)
    today = date.today()
    monday = week_start(start or today)
    sunday = monday + timedelta(days=6)
    exercise = _approved(db, ExercisePlan, patient_id)
    nutrition = _approved(db, NutritionPlan, patient_id)
    week = build_week(
        monday,
        exercise=exercise.plan if exercise else None,
        nutrition=nutrition.plan if nutrition else None,
        recipes=_week_recipes(db, patient_id, nutrition),
        logs=_logs(db, patient_id, monday, sunday),
        measured=_measured(db, patient_id, monday, sunday),
        activity=_activity(db, patient_id, monday, sunday),
        today=today,
        exercise_since=_since(exercise),
        nutrition_since=_since(nutrition),
    )
    week["plans"] = {
        "exercise": _plan_ref(exercise),
        "nutrition": _plan_ref(nutrition),
    }
    return week


@router.put("/patients/{patient_id}/adherence")
def log_adherence(
    *,
    patient_id: int,
    body: AdherenceWrite,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Mark (or unmark) one checklist item for a day; future days are rejected."""
    deps.verify_patient_access(patient_id, db, current_user, "edit")
    if body.log_date > date.today():
        raise ValidationException(
            message="Cannot log adherence for a future date", request=request
        )
    source = "professional" if is_professional(current_user) else "patient"
    with handle_database_errors(request=request):
        entry = (
            db.query(AdherenceLog)
            .filter(
                AdherenceLog.patient_id == patient_id,
                AdherenceLog.log_date == body.log_date,
                AdherenceLog.item == body.item,
            )
            .first()
        )
        if entry is None:
            entry = AdherenceLog(
                patient_id=patient_id,
                log_date=body.log_date,
                item=body.item,
                created_by_user_id=current_user.id,
            )
            db.add(entry)
        entry.done = body.done
        entry.value = body.value
        entry.source = source
        db.commit()
        db.refresh(entry)
    return {
        "log_date": entry.log_date.isoformat(),
        "item": entry.item,
        "done": entry.done,
        "value": entry.value,
        "source": entry.source,
    }


@router.get("/patients/{patient_id}/adherence/history")
def adherence_history(
    *,
    patient_id: int,
    weeks: int = Query(8, ge=1, le=MAX_HISTORY_WEEKS),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Weekly adherence percentages (oldest first) against the current approved plans."""
    deps.verify_patient_access(patient_id, db, current_user)
    today = date.today()
    current = week_start(today)
    first = current - timedelta(weeks=weeks - 1)
    last = current + timedelta(days=6)
    exercise = _approved(db, ExercisePlan, patient_id)
    nutrition = _approved(db, NutritionPlan, patient_id)
    logs = _logs(db, patient_id, first, last)
    measured = _measured(db, patient_id, first, last)
    activity = _activity(db, patient_id, first, last + timedelta(days=6))
    out = []
    for k in range(weeks):
        monday = first + timedelta(weeks=k)
        week = build_week(
            monday,
            exercise=exercise.plan if exercise else None,
            nutrition=nutrition.plan if nutrition else None,
            recipes=[],
            logs=logs,
            measured=measured,
            activity=activity,
            today=today,
            exercise_since=_since(exercise),
            nutrition_since=_since(nutrition),
        )
        out.append({"start": week["start"], "end": week["end"], **week["adherence"]})
    return {"weeks": out}
