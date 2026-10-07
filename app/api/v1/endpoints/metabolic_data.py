"""Metabolic lab import (LOINC-coded) and pseudonymised research export."""

from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api import deps
from app.api.deps import ValidationException
from app.core.http.error_handling import handle_database_errors
from app.crud.activity_log import activity_log
from app.models.activity_log import EntityType
from app.models.models import User
from app.models.patient import Patient
from app.schemas.metabolic_labs import LabImportRequest
from app.services.metabolic_engine import evaluate_patient, save_if_changed
from app.services.metabolic_labs import (
    catalog,
    import_lab_rows,
    parse_lab_text,
    validate_rows,
)
from app.services.metabolic_research import (
    COLUMNS,
    build_json,
    build_rows,
    data_dictionary,
    summary,
    to_csv,
)

router = APIRouter()

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_TEXT_CHARS = 100_000


@router.get("/labs/catalog")
def lab_catalog(current_user: User = Depends(deps.get_current_user)) -> Any:
    """Metabolic lab variables with their LOINC codes and accepted units."""
    return catalog()


@router.post("/patients/{patient_id}/labs/parse")
async def parse_labs(
    *,
    patient_id: int,
    request: Request,
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Suggest lab rows from pasted text, CSV/TXT or PDF. Nothing is stored."""
    deps.verify_patient_access(patient_id, db, current_user, "edit")
    source = "text"
    if file is not None and file.filename:
        content = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(content) > MAX_UPLOAD_BYTES:
            raise ValidationException(message="File too large", request=request)
        name = file.filename.lower()
        if name.endswith(".pdf") or content[:4] == b"%PDF":
            from app.services.pdf_text_extraction_service import (
                PDFTextExtractionService,
            )

            extracted = PDFTextExtractionService().extract_text(content, name)
            if extracted.get("method") == "failed" or not extracted.get("text"):
                raise ValidationException(
                    message="Could not read text from the PDF", request=request
                )
            text, source = extracted["text"], f"pdf_{extracted['method']}"
        else:
            try:
                text = content.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = content.decode("latin-1")
            source = "file"
    if not text or not text.strip():
        raise ValidationException(message="No text to analyse", request=request)
    out = parse_lab_text(text[:MAX_TEXT_CHARS])
    out["source"] = source
    return out


@router.post("/patients/{patient_id}/labs/import")
def import_labs(
    *,
    patient_id: int,
    body: LabImportRequest,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Store reviewed rows as one LOINC-coded lab result and refresh the assessment."""
    deps.verify_patient_access(patient_id, db, current_user, "edit")
    if body.collected_on > date.today():
        raise ValidationException(
            message="Date cannot be in the future", request=request
        )
    rows = [r.model_dump() for r in body.rows]
    errors = validate_rows(rows)
    if errors:
        raise ValidationException(message="; ".join(errors), request=request)
    with handle_database_errors(request=request):
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        result = import_lab_rows(
            db, patient, rows, body.collected_on, body.name, body.facility
        )
        db.commit()
        db.refresh(result)
        activity_log.log_activity(
            db=db,
            action="metabolic_lab_import",
            entity_type=EntityType.LAB_RESULT,
            entity_id=result.id,
            description=f"Imported {len(rows)} metabolic lab values",
            user_id=current_user.id,
            patient_id=patient_id,
            metadata={"variables": [r["variable"] for r in rows]},
        )
        evaluation = evaluate_patient(db, patient)
        assessment = save_if_changed(db, patient_id, evaluation, current_user.id)
        return {
            "lab_result_id": result.id,
            "imported": len(rows),
            "assessment_id": assessment.id,
            "score": evaluation["score"],
        }


@router.get("/research/summary")
def research_summary(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_admin_user),
) -> Any:
    return summary(db)


@router.get("/research/export")
def research_export(
    *,
    request: Request,
    format: str = Query("csv", pattern="^(csv|json|dictionary)$"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_admin_user),
) -> Any:
    """Pseudonymised dataset of consenting patients (admin only, audited)."""
    stamp = date.today().strftime("%Y%m%d")
    if format == "dictionary":
        content = to_csv(data_dictionary(), ["column", "description", "unit", "loinc"])
        return _download(content, "text/csv", f"silho-research-dictionary-{stamp}.csv")
    with handle_database_errors(request=request):
        if format == "json":
            import json

            payload = build_json(db)
            count = len(payload["rows"])
            content = json.dumps(payload, ensure_ascii=False, default=str)
            media, filename = "application/json", f"silho-research-{stamp}.json"
        else:
            rows = build_rows(db)
            count = len(rows)
            content = to_csv(rows, COLUMNS)
            media, filename = "text/csv", f"silho-research-{stamp}.csv"
        activity_log.log_activity(
            db=db,
            action="metabolic_research_export",
            entity_type=EntityType.SYSTEM,
            description=f"Research export ({format}, {count} rows)",
            user_id=current_user.id,
            metadata={"format": format, "rows": count},
        )
    return _download(content, media, filename)


def _download(content: str, media: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type=f"{media}; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
