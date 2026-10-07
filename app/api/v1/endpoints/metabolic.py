"""Metabolic Risk Engine endpoints: clinical config, evaluations and metabolic history."""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api import deps
from app.api.deps import ValidationException
from app.core.http.error_handling import ForbiddenException, handle_database_errors
from app.models.base import get_utc_now
from app.models.metabolic import (
    MetabolicAssessment,
    MetabolicEngineConfig,
    MetabolicProfile,
)
from app.models.models import User
from app.models.patient import Patient
from app.schemas.metabolic import (
    MetabolicAssessmentResponse,
    MetabolicConfigResponse,
    MetabolicConfigUpdate,
    MetabolicEvaluationResponse,
    MetabolicProfileResponse,
    MetabolicProfileUpdate,
)
from app.services.metabolic_config import (
    ALGORITHM_VERSION,
    default_config,
    validate_config,
)
from app.services.metabolic_dashboard import build_dashboard, is_professional
from app.services.metabolic_engine import (
    evaluate_patient,
    get_active_config,
    save_if_changed,
)
from app.services.metabolic_progress import build_progress

router = APIRouter()


def _can_edit(patient_id: int, db: Session, user: User) -> bool:
    try:
        deps.verify_patient_access(patient_id, db, user, "edit")
        return True
    except ForbiddenException:
        return False


@router.get("/config", response_model=MetabolicConfigResponse)
def read_config(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    version, config, row = get_active_config(db)
    return MetabolicConfigResponse(
        version=version,
        algorithm_version=ALGORITHM_VERSION,
        config=config,
        notes=row.notes if row else None,
        created_at=row.created_at if row else None,
        created_by_user_id=row.created_by_user_id if row else None,
    )


@router.get("/config/default", response_model=MetabolicConfigResponse)
def read_default_config(
    current_user: User = Depends(deps.get_current_admin_user),
) -> Any:
    return MetabolicConfigResponse(
        version=0, algorithm_version=ALGORITHM_VERSION, config=default_config()
    )


@router.put("/config", response_model=MetabolicConfigResponse)
def update_config(
    *,
    body: MetabolicConfigUpdate,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_admin_user),
) -> Any:
    """Save the clinical configuration as a new version (previous versions are kept)."""
    try:
        config = validate_config(body.config)
    except ValueError as exc:
        raise ValidationException(message=str(exc), request=request)
    with handle_database_errors(request=request):
        current_version, _, _ = get_active_config(db)
        row = MetabolicEngineConfig(
            version=current_version + 1,
            config=config,
            notes=body.notes,
            created_by_user_id=current_user.id,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return MetabolicConfigResponse(
        version=row.version,
        algorithm_version=ALGORITHM_VERSION,
        config=row.config,
        notes=row.notes,
        created_at=row.created_at,
        created_by_user_id=row.created_by_user_id,
    )


@router.post(
    "/patients/{patient_id}/evaluate", response_model=MetabolicEvaluationResponse
)
def evaluate(
    *,
    patient_id: int,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Run the engine on the latest data; users with edit access also store a snapshot."""
    deps.verify_patient_access(patient_id, db, current_user)
    with handle_database_errors(request=request):
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        result = evaluate_patient(db, patient)
        if not _can_edit(patient_id, db, current_user):
            return MetabolicEvaluationResponse(saved=False, result=result)
        assessment = save_if_changed(db, patient_id, result, current_user.id)
        return MetabolicEvaluationResponse(
            assessment_id=assessment.id,
            assessed_at=assessment.assessed_at,
            saved=True,
            result=result,
        )


@router.get("/professional/dashboard", response_model=Dict[str, Any])
def professional_dashboard(
    *,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Risk distribution and follow-up alerts for the patients this professional can access."""
    if not is_professional(current_user):
        raise ForbiddenException(message="Professional role required", request=request)
    with handle_database_errors(request=request):
        return build_dashboard(db, current_user)


@router.get("/patients/{patient_id}/progress", response_model=Dict[str, Any])
def read_progress(
    *,
    patient_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Baseline/30/60/90-day/6/12-month comparison, progress and why the score changed."""
    deps.verify_patient_access(patient_id, db, current_user)
    assessments = (
        db.query(MetabolicAssessment)
        .filter(MetabolicAssessment.patient_id == patient_id)
        .order_by(MetabolicAssessment.assessed_at.desc(), MetabolicAssessment.id.desc())
        .limit(500)
        .all()
    )
    return build_progress(assessments)


@router.get(
    "/patients/{patient_id}/assessments",
    response_model=List[MetabolicAssessmentResponse],
)
def list_assessments(
    *,
    patient_id: int,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    deps.verify_patient_access(patient_id, db, current_user)
    return (
        db.query(MetabolicAssessment)
        .filter(MetabolicAssessment.patient_id == patient_id)
        .order_by(MetabolicAssessment.assessed_at.desc(), MetabolicAssessment.id.desc())
        .limit(limit)
        .all()
    )


@router.get("/patients/{patient_id}/profile", response_model=MetabolicProfileResponse)
def read_profile(
    *,
    patient_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    deps.verify_patient_access(patient_id, db, current_user)
    profile = (
        db.query(MetabolicProfile)
        .filter(MetabolicProfile.patient_id == patient_id)
        .first()
    )
    if profile is None:
        return MetabolicProfileResponse(patient_id=patient_id)
    return profile


@router.put("/patients/{patient_id}/profile", response_model=MetabolicProfileResponse)
def update_profile(
    *,
    patient_id: int,
    body: MetabolicProfileUpdate,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    deps.verify_patient_access(patient_id, db, current_user, "edit")
    with handle_database_errors(request=request):
        profile = (
            db.query(MetabolicProfile)
            .filter(MetabolicProfile.patient_id == patient_id)
            .first()
        )
        if profile is None:
            profile = MetabolicProfile(patient_id=patient_id)
            db.add(profile)
        was_consenting = bool(profile.research_consent)
        for field, value in body.model_dump().items():
            setattr(profile, field, value)
        if profile.research_consent and not was_consenting:
            profile.research_consent_at = get_utc_now()
        elif not profile.research_consent:
            profile.research_consent_at = None
        profile.updated_by_user_id = current_user.id
        db.commit()
        db.refresh(profile)
        return profile
