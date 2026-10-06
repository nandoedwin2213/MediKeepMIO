"""METABOLIC MOVEMENT endpoints: functional assessments and exercise plans."""

from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api import deps
from app.core.http.error_handling import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    handle_database_errors,
)
from app.models.base import get_utc_now
from app.models.metabolic import ExercisePlan, FunctionalAssessment, MetabolicProfile
from app.models.models import User
from app.models.patient import Patient
from app.schemas.metabolic_movement import (
    ExercisePlanResponse,
    ExercisePlanWrite,
    FunctionalAssessmentCreate,
    FunctionalAssessmentResponse,
)
from app.services.metabolic_dashboard import is_professional
from app.services.metabolic_engine import (
    _age,
    collect_vitals,
    evaluate_patient,
    normalize_sex,
)
from app.services.metabolic_movement import (
    GENERATOR_VERSION,
    REFERENCES_VERSION,
    functional_indicators,
    generate_plan,
)

router = APIRouter()


def _patient(db: Session, patient_id: int) -> Patient:
    return db.query(Patient).filter(Patient.id == patient_id).first()


def _require_professional_editor(
    patient_id: int, db: Session, user: User, request: Request
) -> None:
    if not is_professional(user):
        raise ForbiddenException(message="Professional role required", request=request)
    deps.verify_patient_access(patient_id, db, user, "edit")


def _with_indicators(db: Session, patient: Patient, rows) -> List[Dict[str, Any]]:
    vitals = collect_vitals(db, patient)
    age = _age(patient.birth_date, date.today())
    sex = normalize_sex(patient.gender)
    height = vitals.get("height", {}).get("value")
    weight = vitals.get("weight", {}).get("value")
    out = []
    for row in rows:
        item = FunctionalAssessmentResponse.model_validate(row).model_dump()
        item["indicators"] = functional_indicators(row, age, sex, height, weight)
        out.append(item)
    return out


@router.get("/patients/{patient_id}/functional", response_model=Dict[str, Any])
def list_functional(
    *,
    patient_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    deps.verify_patient_access(patient_id, db, current_user)
    rows = (
        db.query(FunctionalAssessment)
        .filter(FunctionalAssessment.patient_id == patient_id)
        .order_by(
            FunctionalAssessment.assessed_at.desc(), FunctionalAssessment.id.desc()
        )
        .limit(200)
        .all()
    )
    return {
        "references_version": REFERENCES_VERSION,
        "items": _with_indicators(db, _patient(db, patient_id), rows),
    }


@router.post("/patients/{patient_id}/functional", response_model=Dict[str, Any])
def create_functional(
    *,
    patient_id: int,
    body: FunctionalAssessmentCreate,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    deps.verify_patient_access(patient_id, db, current_user, "edit")
    with handle_database_errors(request=request):
        row = FunctionalAssessment(
            patient_id=patient_id,
            created_by_user_id=current_user.id,
            **body.model_dump(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _with_indicators(db, _patient(db, patient_id), [row])[0]


@router.delete("/patients/{patient_id}/functional/{assessment_id}")
def delete_functional(
    *,
    patient_id: int,
    assessment_id: int,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    deps.verify_patient_access(patient_id, db, current_user, "edit")
    row = (
        db.query(FunctionalAssessment)
        .filter(
            FunctionalAssessment.id == assessment_id,
            FunctionalAssessment.patient_id == patient_id,
        )
        .first()
    )
    if row is None:
        raise NotFoundException(
            message="Functional assessment not found", request=request
        )
    with handle_database_errors(request=request):
        db.delete(row)
        db.commit()
    return {"deleted": True}


def _get_plan(db: Session, patient_id: int, plan_id: int, request: Request):
    plan = (
        db.query(ExercisePlan)
        .filter(ExercisePlan.id == plan_id, ExercisePlan.patient_id == patient_id)
        .first()
    )
    if plan is None:
        raise NotFoundException(message="Exercise plan not found", request=request)
    return plan


@router.get(
    "/patients/{patient_id}/exercise-plans",
    response_model=List[ExercisePlanResponse],
)
def list_exercise_plans(
    *,
    patient_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Professionals see every version; patients only see the approved plan."""
    deps.verify_patient_access(patient_id, db, current_user)
    query = db.query(ExercisePlan).filter(ExercisePlan.patient_id == patient_id)
    if not is_professional(current_user):
        query = query.filter(ExercisePlan.status == "approved")
    return query.order_by(ExercisePlan.created_at.desc(), ExercisePlan.id.desc()).all()


@router.post(
    "/patients/{patient_id}/exercise-plans/generate",
    response_model=ExercisePlanResponse,
)
def generate_exercise_plan(
    *,
    patient_id: int,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Create a draft from the metabolic evaluation, history and latest functional tests."""
    _require_professional_editor(patient_id, db, current_user, request)
    with handle_database_errors(request=request):
        patient = _patient(db, patient_id)
        result = evaluate_patient(db, patient)
        profile = (
            db.query(MetabolicProfile)
            .filter(MetabolicProfile.patient_id == patient_id)
            .first()
        )
        latest = (
            db.query(FunctionalAssessment)
            .filter(FunctionalAssessment.patient_id == patient_id)
            .order_by(
                FunctionalAssessment.assessed_at.desc(),
                FunctionalAssessment.id.desc(),
            )
            .first()
        )
        functional: Optional[Dict[str, Any]] = (
            _with_indicators(db, patient, [latest])[0]["indicators"] if latest else None
        )
        content, rationale = generate_plan(result, profile, functional)
        plan = ExercisePlan(
            patient_id=patient_id,
            status="draft",
            plan=ExercisePlanWrite(plan=content).plan.model_dump(),
            rationale=rationale,
            generator_version=GENERATOR_VERSION,
            created_by_user_id=current_user.id,
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)
        return plan


@router.post(
    "/patients/{patient_id}/exercise-plans", response_model=ExercisePlanResponse
)
def create_exercise_plan(
    *,
    patient_id: int,
    body: ExercisePlanWrite,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Create a draft written (or copied and edited) by the professional."""
    _require_professional_editor(patient_id, db, current_user, request)
    with handle_database_errors(request=request):
        plan = ExercisePlan(
            patient_id=patient_id,
            status="draft",
            plan=body.plan.model_dump(),
            notes=body.notes,
            generator_version="manual",
            created_by_user_id=current_user.id,
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)
        return plan


@router.put(
    "/patients/{patient_id}/exercise-plans/{plan_id}",
    response_model=ExercisePlanResponse,
)
def update_exercise_plan(
    *,
    patient_id: int,
    plan_id: int,
    body: ExercisePlanWrite,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    _require_professional_editor(patient_id, db, current_user, request)
    plan = _get_plan(db, patient_id, plan_id, request)
    if plan.status != "draft":
        raise ConflictException(
            message="Only drafts can be edited; create a new draft instead",
            request=request,
        )
    with handle_database_errors(request=request):
        plan.plan = body.plan.model_dump()
        plan.notes = body.notes
        db.commit()
        db.refresh(plan)
        return plan


@router.post(
    "/patients/{patient_id}/exercise-plans/{plan_id}/approve",
    response_model=ExercisePlanResponse,
)
def approve_exercise_plan(
    *,
    patient_id: int,
    plan_id: int,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Publish a draft to the patient; the previously approved plan is archived."""
    _require_professional_editor(patient_id, db, current_user, request)
    plan = _get_plan(db, patient_id, plan_id, request)
    if plan.status != "draft":
        raise ConflictException(message="Only drafts can be approved", request=request)
    with handle_database_errors(request=request):
        db.query(ExercisePlan).filter(
            ExercisePlan.patient_id == patient_id,
            ExercisePlan.status == "approved",
        ).update({"status": "archived"})
        plan.status = "approved"
        plan.approved_by_user_id = current_user.id
        plan.approved_at = get_utc_now()
        db.commit()
        db.refresh(plan)
        return plan


@router.delete("/patients/{patient_id}/exercise-plans/{plan_id}")
def delete_exercise_plan(
    *,
    patient_id: int,
    plan_id: int,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    _require_professional_editor(patient_id, db, current_user, request)
    plan = _get_plan(db, patient_id, plan_id, request)
    if plan.status != "draft":
        raise ConflictException(message="Only drafts can be deleted", request=request)
    with handle_database_errors(request=request):
        db.delete(plan)
        db.commit()
    return {"deleted": True}
