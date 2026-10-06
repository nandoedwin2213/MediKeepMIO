"""METABOLIC NUTRITION endpoints: draft, edit and approve nutrition plans."""

from typing import Any, List

from fastapi import APIRouter, Depends, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api import deps
from app.api.v1.endpoints.metabolic_movement import (
    _patient,
    _require_professional_editor,
)
from app.core.http.error_handling import (
    ConflictException,
    NotFoundException,
    handle_database_errors,
)
from app.models.base import get_utc_now
from app.models.clinical import Allergy
from app.models.metabolic import MetabolicProfile, NutritionPlan
from app.models.models import User
from app.schemas.metabolic_nutrition import NutritionPlanResponse, NutritionPlanWrite
from app.services.metabolic_dashboard import is_professional
from app.services.metabolic_engine import evaluate_patient
from app.services.metabolic_nutrition import (
    GENERATOR_VERSION,
    generate_nutrition_plan,
)

router = APIRouter()


def _get_plan(db: Session, patient_id: int, plan_id: int, request: Request):
    plan = (
        db.query(NutritionPlan)
        .filter(NutritionPlan.id == plan_id, NutritionPlan.patient_id == patient_id)
        .first()
    )
    if plan is None:
        raise NotFoundException(message="Nutrition plan not found", request=request)
    return plan


def _active_allergens(db: Session, patient_id: int) -> List[str]:
    rows = (
        db.query(Allergy.allergen)
        .filter(
            Allergy.patient_id == patient_id,
            or_(Allergy.status.is_(None), Allergy.status == "active"),
        )
        .all()
    )
    return [r[0].strip() for r in rows if r[0] and r[0].strip()]


@router.get(
    "/patients/{patient_id}/nutrition-plans",
    response_model=List[NutritionPlanResponse],
)
def list_nutrition_plans(
    *,
    patient_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Professionals see every version; patients only see the approved plan."""
    deps.verify_patient_access(patient_id, db, current_user)
    query = db.query(NutritionPlan).filter(NutritionPlan.patient_id == patient_id)
    if not is_professional(current_user):
        query = query.filter(NutritionPlan.status == "approved")
    return query.order_by(
        NutritionPlan.created_at.desc(), NutritionPlan.id.desc()
    ).all()


@router.post(
    "/patients/{patient_id}/nutrition-plans/generate",
    response_model=NutritionPlanResponse,
)
def generate_plan(
    *,
    patient_id: int,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Draft from the metabolic evaluation, history, food preferences and allergies."""
    _require_professional_editor(patient_id, db, current_user, request)
    with handle_database_errors(request=request):
        patient = _patient(db, patient_id)
        result = evaluate_patient(db, patient)
        profile = (
            db.query(MetabolicProfile)
            .filter(MetabolicProfile.patient_id == patient_id)
            .first()
        )
        content, rationale = generate_nutrition_plan(
            result, profile, _active_allergens(db, patient_id)
        )
        plan = NutritionPlan(
            patient_id=patient_id,
            status="draft",
            plan=NutritionPlanWrite(plan=content).plan.model_dump(),
            rationale=rationale,
            generator_version=GENERATOR_VERSION,
            created_by_user_id=current_user.id,
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)
        return plan


@router.post(
    "/patients/{patient_id}/nutrition-plans", response_model=NutritionPlanResponse
)
def create_nutrition_plan(
    *,
    patient_id: int,
    body: NutritionPlanWrite,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Create a draft written (or copied and edited) by the professional."""
    _require_professional_editor(patient_id, db, current_user, request)
    with handle_database_errors(request=request):
        plan = NutritionPlan(
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
    "/patients/{patient_id}/nutrition-plans/{plan_id}",
    response_model=NutritionPlanResponse,
)
def update_nutrition_plan(
    *,
    patient_id: int,
    plan_id: int,
    body: NutritionPlanWrite,
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
    "/patients/{patient_id}/nutrition-plans/{plan_id}/approve",
    response_model=NutritionPlanResponse,
)
def approve_nutrition_plan(
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
        db.query(NutritionPlan).filter(
            NutritionPlan.patient_id == patient_id,
            NutritionPlan.status == "approved",
        ).update({"status": "archived"})
        plan.status = "approved"
        plan.approved_by_user_id = current_user.id
        plan.approved_at = get_utc_now()
        db.commit()
        db.refresh(plan)
        return plan


@router.delete("/patients/{patient_id}/nutrition-plans/{plan_id}")
def delete_nutrition_plan(
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
