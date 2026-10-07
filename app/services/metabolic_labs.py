"""Metabolic lab import: LOINC catalogue, a tolerant Spanish/English result parser and import.

The parser reads pasted report text, CSV rows or text extracted from a PDF, one result per
line ("Glucosa en ayunas 95 mg/dL 70 - 100"). Every row is only a suggestion: the user
reviews value, unit and reference range before anything is stored.
"""

import re
from datetime import date
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.base import get_utc_now
from app.models.labs import LabResult, LabTestComponent
from app.models.patient import Patient
from app.services.metabolic_engine import (
    CANONICAL_UNITS,
    LAB_ALIASES,
    LOINC_CODES,
    LOINC_INDEX,
    convert_lab_value,
    normalize_unit,
)

# variable -> primary LOINC, other accepted LOINC codes, library test name, abbreviation,
# component category and the units offered in the review table.
LAB_CATALOG: Dict[str, Dict[str, Any]] = {
    "glucose": {
        "name": "Glucose",
        "abbr": "GLU",
        "category": "endocrinology",
        "units": ["mg/dL", "mmol/L"],
        "plausible": (20, 800),
    },
    "insulin": {
        "name": "Insulin",
        "abbr": "INS",
        "category": "endocrinology",
        "units": ["µU/mL", "µUI/mL", "pmol/L"],
        "plausible": (0.5, 300),
    },
    "hba1c": {
        "name": "Hemoglobin A1c",
        "abbr": "HbA1c",
        "category": "endocrinology",
        "units": ["%", "mmol/mol"],
        "plausible": (3, 20),
    },
    "triglycerides": {
        "name": "Triglycerides",
        "abbr": "TRIG",
        "category": "lipids",
        "units": ["mg/dL", "mmol/L"],
        "plausible": (10, 5000),
    },
    "hdl": {
        "name": "HDL Cholesterol",
        "abbr": "HDL",
        "category": "lipids",
        "units": ["mg/dL", "mmol/L"],
        "plausible": (5, 200),
    },
    "ldl": {
        "name": "LDL Cholesterol",
        "abbr": "LDL",
        "category": "lipids",
        "units": ["mg/dL", "mmol/L"],
        "plausible": (5, 600),
    },
    "total_cholesterol": {
        "name": "Total Cholesterol",
        "abbr": "CHOL",
        "category": "lipids",
        "units": ["mg/dL", "mmol/L"],
        "plausible": (50, 800),
    },
    "alt": {
        "name": "Alanine Aminotransferase",
        "abbr": "ALT",
        "category": "hepatology",
        "units": ["U/L"],
        "plausible": (1, 5000),
    },
    "ast": {
        "name": "Aspartate Aminotransferase",
        "abbr": "AST",
        "category": "hepatology",
        "units": ["U/L"],
        "plausible": (1, 5000),
    },
    "ggt": {
        "name": "Gamma-glutamyl Transferase",
        "abbr": "GGT",
        "category": "hepatology",
        "units": ["U/L"],
        "plausible": (1, 5000),
    },
    "creatinine": {
        "name": "Creatinine",
        "abbr": "CREA",
        "category": "chemistry",
        "units": ["mg/dL", "µmol/L"],
        "plausible": (0.1, 25),
    },
    "uric_acid": {
        "name": "Uric Acid",
        "abbr": "UA",
        "category": "chemistry",
        "units": ["mg/dL", "µmol/L"],
        "plausible": (0.5, 25),
    },
}

for _var, _spec in LAB_CATALOG.items():
    _spec["loinc"], *_spec["alt_loinc"] = LOINC_CODES[_var]
assert set(LOINC_INDEX.values()) == set(LAB_CATALOG)

_EXTRA_ALIASES = {
    "glucose": [
        "glucemia",
        "glicemia",
        "glucosa basal",
        "glucosa en ayuno",
        "glucosa en ayunas",
        "glucosa sérica",
        "glucosa serica",
    ],
    "insulin": ["insulina sérica", "insulina serica"],
    "hba1c": ["hemoglobina a1c", "hb a1c", "hb glicosilada", "glicohemoglobina"],
    "hdl": [
        "hdl colesterol",
        "c-hdl",
        "colesterol de alta densidad",
        "colesterol hdl directo",
    ],
    "ldl": [
        "ldl colesterol",
        "c-ldl",
        "colesterol de baja densidad",
        "colesterol ldl directo",
        "colesterol ldl calculado",
    ],
    "triglycerides": ["triglicéridos séricos", "trigliceridos sericos"],
    "ggt": ["ggtp", "gamma glutamil transpeptidasa", "gama gt"],
    "creatinine": ["creatinina sérica", "creatinina serica"],
}

_WORD = "a-z0-9áéíóúüñ"
_ALIASES = sorted(
    {
        (alias, var)
        for var, aliases in LAB_ALIASES.items()
        for alias in [*aliases, *_EXTRA_ALIASES.get(var, [])]
    },
    key=lambda pair: -len(pair[0]),
)
_ALIAS_RES = [
    (re.compile(rf"(?<![{_WORD}]){re.escape(alias)}(?![{_WORD}])"), alias, var)
    for alias, var in _ALIASES
]

_UNITS = [
    "mmol/mol",
    "mmol/l",
    "µmol/l",
    "umol/l",
    "pmol/l",
    "mg/dl",
    "µui/ml",
    "uui/ml",
    "µiu/ml",
    "uiu/ml",
    "µu/ml",
    "uu/ml",
    "miu/l",
    "mui/l",
    "mu/l",
    "ui/l",
    "iu/l",
    "u/l",
    "%",
]
_UNIT_RE = re.compile(
    "(" + "|".join(re.escape(u).replace("/", r"\s*/\s*") for u in _UNITS) + ")"
)
_NUM = r"\d+(?:[.,]\d+)?"
_VALUE_RE = re.compile(rf"(?<![a-z\d.,])([<>≤≥]?)\s*({_NUM})(?![\d])")
_HOURS_RE = re.compile(r"^\s*(h|hr|hrs|hora|horas|min)\b")
_EXCLUDE_RE = re.compile(
    r"(vldl|no[\s-]?hdl|non[\s-]?hdl|ratio|relaci[oó]n|[ií]ndice|cociente|orina|urine"
    r"|urinari|promedio|average|\beag\b|post|\bpp\b|tolerancia|curva|estimad)"
)
_RANGE_RE = re.compile(rf"({_NUM})\s*(?:-|–|—|a|to|hasta)\s*({_NUM})")
_MAX_RE = re.compile(rf"(?:<|≤|menor\s+(?:a|de)|hasta|up\s+to)\s*=?\s*({_NUM})")
_MIN_RE = re.compile(rf"(?:>|≥|mayor\s+(?:a|de))\s*=?\s*({_NUM})")
_DATE_RES = (
    re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})"),
    re.compile(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})"),
)


def _num(text: str) -> float:
    return float(text.replace(",", "."))


def _display_unit(variable: str, raw: Optional[str]) -> Optional[str]:
    """Map a parsed unit to one of the catalogue units with the same conversion."""
    if raw is None:
        return None
    norm = normalize_unit(raw)
    for unit in LAB_CATALOG[variable]["units"]:
        if normalize_unit(unit) == norm:
            return unit
    if norm == "mmol/mol":
        return None
    target = convert_lab_value(variable, 1.0, raw)
    if target is None:
        return None
    for unit in LAB_CATALOG[variable]["units"]:
        if convert_lab_value(variable, 1.0, unit) == target:
            return unit
    return None


def _ref_range(text: str) -> Dict[str, Any]:
    m = _RANGE_RE.search(text)
    if m:
        lo, hi = _num(m.group(1)), _num(m.group(2))
        if lo < hi:
            return {"ref_min": lo, "ref_max": hi, "ref_text": m.group(0).strip()}
    m = _MAX_RE.search(text)
    if m:
        return {"ref_min": None, "ref_max": _num(m.group(1)), "ref_text": m.group(0)}
    m = _MIN_RE.search(text)
    if m:
        return {"ref_min": _num(m.group(1)), "ref_max": None, "ref_text": m.group(0)}
    return {"ref_min": None, "ref_max": None, "ref_text": None}


def _match_alias(line: str):
    """Longest alias wins (``colesterol hdl`` over ``colesterol``); ties go to the earliest."""
    found = None
    for regex, alias, var in _ALIAS_RES:
        m = regex.search(line)
        if m is None:
            continue
        if found is None or len(alias) > len(found[1]):
            found = (m, alias, var)
        elif len(alias) == len(found[1]) and m.start() < found[0].start():
            found = (m, alias, var)
    return found


def suggest_date(text: str) -> Optional[str]:
    lowered = text.lower()
    anchor = lowered.find("fecha")
    candidates = []
    for regex in _DATE_RES:
        for m in regex.finditer(lowered):
            parts = [int(p) for p in m.groups()]
            y, mo, d = (
                parts if regex is _DATE_RES[0] else (parts[2], parts[1], parts[0])
            )
            try:
                when = date(y, mo, d)
            except ValueError:
                continue
            if date(1950, 1, 1) <= when <= date.today():
                distance = abs(m.start() - anchor) if anchor >= 0 else m.start()
                candidates.append((distance, when))
    return min(candidates)[1].isoformat() if candidates else None


def assess_row(variable: str, value: float, unit: Optional[str]) -> Dict[str, Any]:
    """Canonical value and warnings for a reviewed or parsed value."""
    spec = LAB_CATALOG[variable]
    warnings: List[str] = []
    effective = unit or spec["units"][0]
    if unit is None:
        warnings.append("unit_assumed")
    canonical = convert_lab_value(variable, value, effective)
    if canonical is None:
        warnings.append("unknown_unit")
    else:
        lo, hi = spec["plausible"]
        if not lo <= canonical <= hi:
            warnings.append("implausible")
    return {
        "canonical_value": None if canonical is None else round(canonical, 2),
        "canonical_unit": CANONICAL_UNITS[variable],
        "warnings": warnings,
    }


def parse_lab_text(text: str) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    unrecognized = 0
    seen = set()
    for line_no, raw_line in enumerate((text or "").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        lowered = line.lower().replace("μ", "µ")
        found = _match_alias(lowered)
        if found is None:
            if re.search(r"\d", lowered):
                unrecognized += 1
            continue
        m, _, variable = found
        rest = lowered[m.end() :]
        vm = _VALUE_RE.search(rest)
        if vm is None:
            unrecognized += 1
            continue
        after = rest[vm.end() :]
        if _HOURS_RE.match(after):
            continue
        name_part = _UNIT_RE.sub("", lowered[: m.end() + vm.start()])
        if _EXCLUDE_RE.search(name_part) or re.search(r"[a-z]\s*/\s*[a-z]", name_part):
            continue
        if variable == "total_cholesterol" and re.search(
            r"\b[hlv]?[hl]dl\b", name_part
        ):
            continue
        um = _UNIT_RE.match(after.lstrip(" \t;,|:")) or _UNIT_RE.search(after)
        raw_unit = re.sub(r"\s+", "", um.group(1)) if um else None
        unit_text = after[um.end() :] if um else after
        unit = _display_unit(variable, raw_unit) if raw_unit else None
        value = _num(vm.group(2))
        spec = LAB_CATALOG[variable]
        row = {
            "line_no": line_no,
            "line": line[:200],
            "variable": variable,
            "test_name": spec["name"],
            "loinc": spec["loinc"],
            "value": value,
            "unit": unit,
            "raw_unit": raw_unit,
            "qualifier": vm.group(1) or None,
            **_ref_range(unit_text if um else after),
            **assess_row(variable, value, unit),
            "selected": variable not in seen,
        }
        if raw_unit and unit is None:
            row["warnings"].append("unknown_unit")
        if row["qualifier"]:
            row["warnings"].append("qualifier")
        if variable in seen:
            row["warnings"].append("duplicate")
        seen.add(variable)
        rows.append(row)
    return {
        "rows": rows,
        "unrecognized": unrecognized,
        "suggested_date": suggest_date(text or ""),
    }


def catalog() -> List[Dict[str, Any]]:
    return [
        {
            "variable": var,
            "loinc": spec["loinc"],
            "alt_loinc": spec["alt_loinc"],
            "name": spec["name"],
            "abbreviation": spec["abbr"],
            "units": spec["units"],
            "canonical_unit": CANONICAL_UNITS[var],
        }
        for var, spec in LAB_CATALOG.items()
    ]


def _status(value: float, lo: Optional[float], hi: Optional[float]) -> Optional[str]:
    if lo is None and hi is None:
        return None
    if hi is not None and value > hi:
        return "high"
    if lo is not None and value < lo:
        return "low"
    return "normal"


def validate_rows(rows: List[Dict[str, Any]]) -> List[str]:
    """Return error codes for rows that cannot be stored (unit unknown or absurd value)."""
    errors = []
    seen = set()
    for i, row in enumerate(rows):
        variable, unit = row["variable"], row["unit"]
        if unit not in LAB_CATALOG[variable]["units"]:
            errors.append(f"row {i}: unit {unit!r} not allowed for {variable}")
            continue
        if "implausible" in assess_row(variable, row["value"], unit)["warnings"]:
            errors.append(f"row {i}: implausible {variable} value")
        if variable in seen:
            errors.append(f"row {i}: duplicate {variable}")
        seen.add(variable)
    return errors


def import_lab_rows(
    db: Session,
    patient: Patient,
    rows: List[Dict[str, Any]],
    collected_on: date,
    name: str,
    facility: Optional[str],
) -> LabResult:
    now = get_utc_now()
    result = LabResult(
        patient_id=patient.id,
        test_name=name,
        test_category="blood work",
        status="completed",
        completed_date=collected_on,
        facility=facility or None,
        is_panel=True,
        tags=["metabolic-import"],
        created_at=now,
        updated_at=now,
    )
    db.add(result)
    db.flush()
    abnormal = False
    for order, row in enumerate(rows, start=1):
        spec = LAB_CATALOG[row["variable"]]
        status = _status(row["value"], row.get("ref_min"), row.get("ref_max"))
        abnormal = abnormal or status in ("high", "low")
        db.add(
            LabTestComponent(
                lab_result_id=result.id,
                test_name=spec["name"],
                abbreviation=spec["abbr"],
                test_code=spec["loinc"],
                canonical_test_name=spec["name"],
                result_type="quantitative",
                value=row["value"],
                unit=row["unit"],
                ref_range_min=row.get("ref_min"),
                ref_range_max=row.get("ref_max"),
                ref_range_text=(row.get("ref_text") or None),
                status=status,
                category=spec["category"],
                display_order=order,
            )
        )
    result.labs_result = "abnormal" if abnormal else None
    return result
