"""FISAI Metabolic AI endpoints: supervised explanations and the educational simulator."""

from typing import Any, List

from fastapi import APIRouter, Depends, Request
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
from app.models.metabolic import MetabolicAssessment, MetabolicInsight
from app.models.models import User
from app.schemas.metabolic_ai import InsightResponse, InsightWrite, SimulationRequest
from app.services.metabolic_ai import (
    INSIGHT_VERSION,
    apply_priorities,
    build_insight,
    simulate_patient,
)
from app.services.metabolic_dashboard import is_professional
from app.services.metabolic_engine import evaluate_patient, get_active_config
from app.services.metabolic_progress import build_progress

router = APIRouter()


def _get_insight(db: Session, patient_id: int, insight_id: int, request: Request):
    row = (
        db.query(MetabolicInsight)
        .filter(
            MetabolicInsight.id == insight_id,
            MetabolicInsight.patient_id == patient_id,
        )
        .first()
    )
    if row is None:
        raise NotFoundException(message="Insight not found", request=request)
    return row


def _require_draft(row: MetabolicInsight, request: Request, action: str) -> None:
    if row.status != "draft":
        raise ConflictException(message=f"Only drafts can be {action}", request=request)


@router.post("/patients/{patient_id}/simulate")
def simulate(
    *,
    patient_id: int,
    body: SimulationRequest,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Educational what-if: recompute the score with the given changes (nothing is saved)."""
    deps.verify_patient_access(patient_id, db, current_user)
    with handle_database_errors(request=request):
        return simulate_patient(
            db, _patient(db, patient_id), body.model_dump(exclude_none=True)
        )


@router.get("/patients/{patient_id}/insights", response_model=List[InsightResponse])
def list_insights(
    *,
    patient_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Professionals see every version; patients only the approved explanation."""
    deps.verify_patient_access(patient_id, db, current_user)
    query = db.query(MetabolicInsight).filter(MetabolicInsight.patient_id == patient_id)
    if not is_professional(current_user):
        query = query.filter(MetabolicInsight.status == "approved")
    return (
        query.order_by(MetabolicInsight.created_at.desc(), MetabolicInsight.id.desc())
        .limit(20)
        .all()
    )


@router.post("/patients/{patient_id}/insights/generate", response_model=InsightResponse)
def generate_insight(
    *,
    patient_id: int,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Draft an explanation from the current evaluation and the latest score change."""
    _require_professional_editor(patient_id, db, current_user, request)
    with handle_database_errors(request=request):
        result = evaluate_patient(db, _patient(db, patient_id))
        _, config, _ = get_active_config(db)
        assessments = (
            db.query(MetabolicAssessment)
            .filter(MetabolicAssessment.patient_id == patient_id)
            .order_by(MetabolicAssessment.assessed_at.desc())
            .limit(500)
            .all()
        )
        change = build_progress(assessments).get("change")
        row = MetabolicInsight(
            patient_id=patient_id,
            status="draft",
            content=build_insight(result, config, change),
            engine_version=INSIGHT_VERSION,
            created_by_user_id=current_user.id,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row


@router.put(
    "/patients/{patient_id}/insights/{insight_id}", response_model=InsightResponse
)
def update_insight(
    *,
    patient_id: int,
    insight_id: int,
    body: InsightWrite,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Professional note and choice/order of priorities on a draft."""
    _require_professional_editor(patient_id, db, current_user, request)
    row = _get_insight(db, patient_id, insight_id, request)
    _require_draft(row, request, "edited")
    with handle_database_errors(request=request):
        row.note = body.note
        if body.priorities is not None:
            row.content = apply_priorities(row.content, body.priorities)
        db.commit()
        db.refresh(row)
        return row


@router.post(
    "/patients/{patient_id}/insights/{insight_id}/approve",
    response_model=InsightResponse,
)
def approve_insight(
    *,
    patient_id: int,
    insight_id: int,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Publish a draft to the patient; the previously approved one is archived."""
    _require_professional_editor(patient_id, db, current_user, request)
    row = _get_insight(db, patient_id, insight_id, request)
    _require_draft(row, request, "approved")
    with handle_database_errors(request=request):
        db.query(MetabolicInsight).filter(
            MetabolicInsight.patient_id == patient_id,
            MetabolicInsight.status == "approved",
        ).update({"status": "archived"})
        row.status = "approved"
        row.approved_by_user_id = current_user.id
        row.approved_at = get_utc_now()
        db.commit()
        db.refresh(row)
        return row


@router.delete("/patients/{patient_id}/insights/{insight_id}")
def delete_insight(
    *,
    patient_id: int,
    insight_id: int,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    _require_professional_editor(patient_id, db, current_user, request)
    row = _get_insight(db, patient_id, insight_id, request)
    _require_draft(row, request, "deleted")
    with handle_database_errors(request=request):
        db.delete(row)
        db.commit()
    return {"deleted": True}
