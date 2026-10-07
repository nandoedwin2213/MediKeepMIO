"""Pseudonymised research export of metabolic assessments.

Only patients who opted in (``MetabolicProfile.research_consent``) are exported. Rows carry
a keyed pseudonym instead of any identifier, 5-year age bands instead of birth dates, and
days since the patient's first assessment instead of calendar dates. Free text (notes,
goals, limitations, food preferences) is never exported.
"""

import csv
import hashlib
import hmac
import io
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.metabolic import MetabolicAssessment, MetabolicProfile
from app.models.patient import Patient
from app.services.metabolic_engine import CANONICAL_UNITS, LOINC_CODES

EXPORT_VERSION = "research-0.1.0"
MIN_GROUP_SIZE = 5

VITAL_LOINC = {
    "weight": "29463-7",
    "height": "8302-2",
    "bmi": "39156-5",
    "waist": "8280-0",
    "hip": "62409-8",
    "systolic": "8480-6",
    "diastolic": "8462-4",
}
INDEX_UNITS = {
    "homa_ir": None,
    "quicki": None,
    "tyg": None,
    "tyg_bmi": None,
    "mets_ir": None,
    "tg_hdl": "ratio",
    "waist_height": "ratio",
    "waist_hip": "ratio",
}
LAB_COLUMNS = list(LOINC_CODES)
VITAL_COLUMNS = list(VITAL_LOINC)
INDEX_COLUMNS = list(INDEX_UNITS)
HABIT_COLUMNS = [
    "physical_activity",
    "sitting",
    "sleep",
    "sugary_drinks",
    "ultraprocessed",
    "fruit_veg",
    "smoking",
    "alcohol",
]
HISTORY_COLUMNS = [
    "has_diabetes",
    "has_prediabetes",
    "has_hypertension",
    "has_dyslipidemia",
    "has_fatty_liver",
    "has_obesity",
    "has_cardiovascular_disease",
    "family_diabetes",
]
BASE_COLUMNS = [
    "research_id",
    "sex",
    "age_band",
    "day",
    "algorithm_version",
    "config_version",
    "score",
    "risk_level",
    "metabolic_syndrome",
    "metabolic_syndrome_criteria_met",
]
COLUMNS = (
    BASE_COLUMNS
    + LAB_COLUMNS
    + VITAL_COLUMNS
    + INDEX_COLUMNS
    + HABIT_COLUMNS
    + HISTORY_COLUMNS
)

_BASE_DESCRIPTIONS = {
    "research_id": "Keyed pseudonym of the patient (stable across exports of this server)",
    "sex": "M / F as recorded",
    "age_band": "Age at the assessment in 5-year bands",
    "day": "Days since the patient's first exported assessment",
    "algorithm_version": "Metabolic engine version",
    "config_version": "Clinical configuration version (ranges, weights)",
    "score": "Score Metabólico FISAI (0-100, internal follow-up indicator)",
    "risk_level": "favorable / initial / moderate / high",
    "metabolic_syndrome": "compatible / not_compatible / indeterminate",
    "metabolic_syndrome_criteria_met": "Number of metabolic syndrome criteria met",
}
_HABIT_UNITS = {
    "physical_activity": "min/week",
    "sitting": "h/day",
    "sleep": "h/day",
    "sugary_drinks": "per week",
    "ultraprocessed": "per week",
    "fruit_veg": "servings/day",
}


def research_id(patient_id: int) -> str:
    digest = hmac.new(
        settings.SECRET_KEY.encode(),
        f"silho-research:{patient_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"R-{digest[:12].upper()}"


def age_band(birth: Optional[date], when: date) -> Optional[str]:
    if not birth:
        return None
    age = when.year - birth.year - ((when.month, when.day) < (birth.month, birth.day))
    if age < 18:
        return "<18"
    if age >= 90:
        return "90+"
    lo = age // 5 * 5
    return f"{lo}-{lo + 4}"


def data_dictionary() -> List[Dict[str, Any]]:
    out = []
    for col in COLUMNS:
        entry: Dict[str, Any] = {"column": col, "unit": None, "loinc": None}
        if col in _BASE_DESCRIPTIONS:
            entry["description"] = _BASE_DESCRIPTIONS[col]
        elif col in LOINC_CODES:
            entry.update(
                description=f"Lab: {col} (latest value used by the assessment)",
                unit=CANONICAL_UNITS[col],
                loinc=LOINC_CODES[col][0],
            )
        elif col in VITAL_LOINC:
            entry.update(
                description=f"Anthropometry / vital sign: {col}",
                unit=CANONICAL_UNITS.get(col),
                loinc=VITAL_LOINC[col],
            )
        elif col in INDEX_UNITS:
            entry.update(description=f"Derived index: {col}", unit=INDEX_UNITS[col])
        elif col in HABIT_COLUMNS:
            entry.update(
                description=f"Self-reported habit: {col}", unit=_HABIT_UNITS.get(col)
            )
        else:
            entry["description"] = f"Self-reported history: {col} (true/false)"
        out.append(entry)
    return out


def _consented(db: Session):
    return (
        db.query(Patient, MetabolicProfile)
        .join(MetabolicProfile, MetabolicProfile.patient_id == Patient.id)
        .filter(MetabolicProfile.research_consent.is_(True))
        .order_by(Patient.id)
        .all()
    )


def _value(result: Dict[str, Any], key: str) -> Any:
    for section in ("indicators", "inputs"):
        v = (result.get(section) or {}).get(key, {}).get("value")
        if v is not None:
            return round(v, 2) if isinstance(v, float) else v
    return None


def _when(assessment: MetabolicAssessment) -> date:
    at = assessment.assessed_at
    return at.date() if isinstance(at, datetime) else at


def build_rows(db: Session) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for patient, _profile in _consented(db):
        assessments = (
            db.query(MetabolicAssessment)
            .filter(MetabolicAssessment.patient_id == patient.id)
            .order_by(MetabolicAssessment.assessed_at, MetabolicAssessment.id)
            .all()
        )
        if not assessments:
            continue
        first = _when(assessments[0])
        rid = research_id(patient.id)
        for a in assessments:
            result = a.result or {}
            ms = result.get("metabolic_syndrome") or {}
            history = result.get("history") or {}
            row = {
                "research_id": rid,
                "sex": (result.get("patient") or {}).get("sex"),
                "age_band": age_band(patient.birth_date, _when(a)),
                "day": (_when(a) - first).days,
                "algorithm_version": a.algorithm_version,
                "config_version": a.config_version,
                "score": a.score,
                "risk_level": a.risk_level,
                "metabolic_syndrome": a.metabolic_syndrome_status,
                "metabolic_syndrome_criteria_met": ms.get("met"),
            }
            for col in LAB_COLUMNS + VITAL_COLUMNS + INDEX_COLUMNS + HABIT_COLUMNS:
                row[col] = _value(result, col)
            for col in HISTORY_COLUMNS:
                row[col] = history.get(col)
            rows.append(row)
    return rows


def summary(db: Session) -> Dict[str, Any]:
    consented = _consented(db)
    ids = [p.id for p, _ in consented]
    assessments = (
        db.query(MetabolicAssessment)
        .filter(MetabolicAssessment.patient_id.in_(ids))
        .count()
        if ids
        else 0
    )
    return {
        "version": EXPORT_VERSION,
        "patients_total": db.query(Patient).count(),
        "patients_consented": len(ids),
        "assessments": assessments,
        "columns": len(COLUMNS),
        "min_group_size": MIN_GROUP_SIZE,
        "small_sample": len(ids) < MIN_GROUP_SIZE,
    }


def to_csv(rows: List[Dict[str, Any]], columns: List[str]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {k: ("" if row.get(k) is None else row.get(k)) for k in columns}
        )
    return buffer.getvalue()


def build_json(db: Session) -> Dict[str, Any]:
    return {
        "dataset": "SILHO metabolic research export",
        "version": EXPORT_VERSION,
        "generated_on": date.today().isoformat(),
        "anonymization": {
            "consent": "only patients with research consent",
            "identifier": "keyed pseudonym (HMAC-SHA256)",
            "age": "5-year bands",
            "dates": "days since first assessment",
            "free_text": "excluded",
        },
        "data_dictionary": data_dictionary(),
        "rows": build_rows(db),
    }
