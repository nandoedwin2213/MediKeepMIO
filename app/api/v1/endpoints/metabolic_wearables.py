"""Wearable exports (Apple Health / Google Fit / CSV): parse, review, import and apply."""

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.api import deps
from app.api.deps import ValidationException
from app.core.http.error_handling import handle_database_errors
from app.crud.activity_log import activity_log
from app.models.activity_log import EntityType
from app.models.metabolic import WearableDaily
from app.models.models import User
from app.models.patient import Patient
from app.schemas.metabolic_wearables import WearableImportRequest
from app.services.metabolic_engine import (
    evaluate_patient,
    get_active_config,
    save_if_changed,
)
from app.services.metabolic_wearables import (
    MAX_DAYS,
    METRICS,
    WEARABLES_VERSION,
    WearableParseError,
    apply_to_profile,
    clean_days,
    detect_and_parse,
    import_days,
    merge_daily,
    patient_sex,
    summarize,
    validate_days,
)

router = APIRouter()

MAX_UPLOAD_BYTES = 1024 * 1024 * 1024


def _patient(db: Session, patient_id: int) -> Patient:
    return db.query(Patient).filter(Patient.id == patient_id).first()


def _daily(db: Session, patient_id: int, since: date) -> dict:
    rows = db.query(WearableDaily).filter(
        WearableDaily.patient_id == patient_id, WearableDaily.day >= since
    )
    return merge_daily(rows)


@router.post("/patients/{patient_id}/wearables/parse")
async def parse_wearables(
    *,
    patient_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Daily summaries suggested from an export file. Nothing is stored."""
    deps.verify_patient_access(patient_id, db, current_user, "edit")
    if file.size is not None and file.size > MAX_UPLOAD_BYTES:
        raise ValidationException(
            message="File is too large (max 1 GB)", request=request
        )
    try:
        source, raw = await run_in_threadpool(
            detect_and_parse, file.file, file.filename or ""
        )
    except WearableParseError as exc:
        raise ValidationException(message=str(exc), request=request)
    cleaned = clean_days(raw, date.today())
    if not cleaned["days"]:
        raise ValidationException(
            message="No usable daily values found", request=request
        )
    patient = _patient(db, patient_id)
    _version, config, _row = get_active_config(db)
    preview = {date.fromisoformat(d["date"]): d for d in cleaned["days"]}
    return {
        "version": WEARABLES_VERSION,
        "source": source,
        "days": cleaned["days"],
        "warnings": cleaned["warnings"],
        "summary": summarize(preview, config, patient_sex(patient)),
    }


@router.post("/patients/{patient_id}/wearables/import")
def import_wearables(
    *,
    patient_id: int,
    body: WearableImportRequest,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Store reviewed daily rows (upsert per day and source) and refresh the assessment."""
    deps.verify_patient_access(patient_id, db, current_user, "edit")
    rows = [d.model_dump() for d in body.days]
    errors = validate_days(rows, date.today())
    if errors:
        raise ValidationException(message="; ".join(errors[:10]), request=request)
    with handle_database_errors(request=request):
        patient = _patient(db, patient_id)
        counts = import_days(db, patient, rows, body.source, current_user.id)
        db.commit()
        activity_log.log_activity(
            db=db,
            action="metabolic_wearable_import",
            entity_type=EntityType.VITALS,
            description=f"Imported {len(rows)} wearable days ({body.source})",
            user_id=current_user.id,
            patient_id=patient_id,
            metadata={"source": body.source, **counts},
        )
        evaluation = evaluate_patient(db, patient)
        save_if_changed(db, patient_id, evaluation, current_user.id)
    return {**counts, "days": len(rows), "score": evaluation["score"]}


@router.get("/patients/{patient_id}/wearables")
def read_wearables(
    *,
    patient_id: int,
    days: int = Query(90, ge=7, le=MAX_DAYS),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Merged daily series plus 28-day averages with their reference bands."""
    deps.verify_patient_access(patient_id, db, current_user)
    daily = _daily(db, patient_id, date.today() - timedelta(days=days - 1))
    patient = _patient(db, patient_id)
    _version, config, _row = get_active_config(db)
    last = (
        db.query(WearableDaily.updated_at)
        .filter(WearableDaily.patient_id == patient_id)
        .order_by(WearableDaily.updated_at.desc())
        .first()
    )
    return {
        "version": WEARABLES_VERSION,
        "days": [
            {
                "date": d.isoformat(),
                **{m: v.get(m) for m in METRICS},
                "sources": v["sources"],
            }
            for d, v in sorted(daily.items())
        ],
        "summary": summarize(daily, config, patient_sex(patient)),
        "last_import": last[0].isoformat() if last else None,
    }


@router.post("/patients/{patient_id}/wearables/apply-profile")
def apply_wearables_to_profile(
    *,
    patient_id: int,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Copy the 28-day activity and sleep averages into the metabolic history."""
    deps.verify_patient_access(patient_id, db, current_user, "edit")
    patient = _patient(db, patient_id)
    _version, config, _row = get_active_config(db)
    summary = summarize(
        _daily(db, patient_id, date.today() - timedelta(days=MAX_DAYS)),
        config,
        patient_sex(patient),
    )
    if not summary["days_with_data"]:
        raise ValidationException(message="No wearable data to apply", request=request)
    with handle_database_errors(request=request):
        profile = apply_to_profile(db, patient_id, summary, current_user.id)
        db.commit()
        db.refresh(profile)
        evaluation = evaluate_patient(db, patient)
        save_if_changed(db, patient_id, evaluation, current_user.id)
    return {
        "physical_activity_minutes_week": profile.physical_activity_minutes_week,
        "sleep_hours": profile.sleep_hours,
        "score": evaluation["score"],
    }
