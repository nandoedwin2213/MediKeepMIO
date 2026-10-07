"""Metabolic lab import (LOINC) and pseudonymised research export."""

from datetime import date, datetime

from app.models.activity_log import ActivityLog
from app.models.labs import LabTestComponent
from app.models.metabolic import MetabolicAssessment, MetabolicProfile
from app.services.metabolic_labs import parse_lab_text
from app.services.metabolic_research import age_band, research_id

BASE = "/api/v1/metabolic/patients/{}"

REPORT = """LABORATORIO CLINICO
Fecha de toma: 12/09/2026
Glucosa en ayunas      104 mg/dL     70 - 100
Glucosa 2 horas post   150 mg/dL
Insulina basal 18,5 uUI/mL (2.6 - 24.9)
Hemoglobina glicosilada (HbA1c)  6.1 %  4.0 - 5.6
Colesterol total 212 mg/dL < 200
Colesterol HDL 38 mg/dL > 40
HDL colesterol 39 mg/dl
VLDL 40 mg/dL
Relación Colesterol/HDL 5.5
Triglicéridos 230 mg/dL hasta 150
TGP (ALT) 45 U/L
Glucosa;5.8;mmol/L;3.9-5.5
"""


def test_parse_spanish_report():
    out = parse_lab_text(REPORT)
    rows = {(r["variable"], r["selected"]): r for r in out["rows"]}
    assert out["suggested_date"] == "2026-09-12"
    glucose = rows[("glucose", True)]
    assert (glucose["value"], glucose["unit"], glucose["loinc"]) == (
        104,
        "mg/dL",
        "2345-7",
    )
    assert (glucose["ref_min"], glucose["ref_max"]) == (70, 100)
    assert rows[("insulin", True)]["value"] == 18.5
    assert rows[("hba1c", True)]["unit"] == "%"
    assert rows[("total_cholesterol", True)]["ref_max"] == 200
    assert rows[("hdl", True)]["value"] == 38 and rows[("hdl", True)]["ref_min"] == 40
    assert "duplicate" in rows[("hdl", False)]["warnings"]
    assert rows[("triglycerides", True)]["ref_max"] == 150
    mmol = rows[("glucose", False)]
    assert mmol["unit"] == "mmol/L" and abs(mmol["canonical_value"] - 104.49) < 0.1
    variables = [r["variable"] for r in out["rows"]]
    assert "ldl" not in variables and variables.count("glucose") == 2


def test_parse_flags_missing_and_absurd_units():
    out = parse_lab_text("Glucosa 5.6\nTriglicéridos 12000 mg/dL")
    glucose, tg = out["rows"]
    assert glucose["unit"] is None and "unit_assumed" in glucose["warnings"]
    assert "implausible" in glucose["warnings"]
    assert "implausible" in tg["warnings"]


def test_parse_and_import_endpoint(authenticated_client, db_session, test_patient):
    url = BASE.format(test_patient.id)
    r = authenticated_client.post(url + "/labs/parse", data={"text": REPORT})
    assert r.status_code == 200, r.text
    assert r.json()["source"] == "text"
    r = authenticated_client.post(
        url + "/labs/parse",
        files={
            "file": ("labs.csv", "Prueba;Valor;Unidad\nGlucosa;95;mg/dL\n", "text/csv")
        },
    )
    assert r.status_code == 200 and r.json()["rows"][0]["value"] == 95

    body = {
        "collected_on": "2026-09-12",
        "name": "Laboratorio metabólico",
        "facility": "Lab XYZ",
        "rows": [
            {
                "variable": "glucose",
                "value": 104,
                "unit": "mg/dL",
                "ref_min": 70,
                "ref_max": 100,
            },
            {"variable": "insulin", "value": 18.5, "unit": "µUI/mL"},
            {"variable": "triglycerides", "value": 2.6, "unit": "mmol/L"},
            {"variable": "hdl", "value": 38, "unit": "mg/dL"},
        ],
    }
    r = authenticated_client.post(url + "/labs/import", json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["imported"] == 4 and out["assessment_id"]
    comps = (
        db_session.query(LabTestComponent)
        .filter(LabTestComponent.lab_result_id == out["lab_result_id"])
        .all()
    )
    by_code = {c.test_code: c for c in comps}
    assert set(by_code) == {"2345-7", "20448-7", "2571-8", "2085-9"}
    assert by_code["2345-7"].status == "high"

    ev = authenticated_client.post(url + "/evaluate").json()["result"]
    assert round(ev["inputs"]["triglycerides"]["value"]) == 230
    assert "homa_ir" in ev["indicators"]

    bad = {**body, "rows": [{"variable": "glucose", "value": 5.6, "unit": "mg/dL"}]}
    assert authenticated_client.post(url + "/labs/import", json=bad).status_code == 422
    wrong_unit = {**body, "rows": [{"variable": "alt", "value": 30, "unit": "mg/dL"}]}
    assert (
        authenticated_client.post(url + "/labs/import", json=wrong_unit).status_code
        == 422
    )
    future = {**body, "collected_on": "2999-01-01"}
    assert (
        authenticated_client.post(url + "/labs/import", json=future).status_code == 422
    )
    assert authenticated_client.get("/api/v1/metabolic/labs/catalog").status_code == 200


def test_research_consent_and_export(
    client, user_token_headers, admin_token_headers, db_session, test_patient
):
    user, admin = user_token_headers, admin_token_headers
    url = BASE.format(test_patient.id) + "/profile"
    r = client.put(url, json={"research_consent": True}, headers=user)
    assert r.status_code == 200 and r.json()["research_consent_at"]

    assert (
        client.get("/api/v1/metabolic/research/summary", headers=user).status_code
        == 403
    )
    for when, score, sampled in (
        (datetime(2026, 6, 1), 52, "2026-05-30"),
        (datetime(2026, 6, 2), 52, "2026-05-30"),
        (datetime(2026, 9, 1), 60, "2026-08-30T08:00:00"),
    ):
        db_session.add(
            MetabolicAssessment(
                patient_id=test_patient.id,
                assessed_at=when,
                algorithm_version="1",
                config_version=0,
                fingerprint=f"{score}-{when.day}",
                score=score,
                risk_level="moderate",
                metabolic_syndrome_status="indeterminate",
                result={
                    "patient": {"sex": "M"},
                    "inputs": {
                        "glucose": {"value": 104.0, "date": sampled},
                        "weight": {"value": 80.0},
                    },
                    "indicators": {"homa_ir": {"value": 4.567}},
                    "metabolic_syndrome": {"met": 2},
                    "history": {"has_diabetes": False},
                },
            )
        )
    db_session.commit()

    summary = client.get("/api/v1/metabolic/research/summary", headers=admin).json()
    assert summary["patients_consented"] == 1 and summary["assessments"] == 2
    assert summary["small_sample"] is True

    r = client.get("/api/v1/metabolic/research/export?format=csv", headers=admin)
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    lines = r.text.strip().splitlines()
    header = lines[0].split(",")
    assert len(lines) == 3 and header[0] == "research_id"
    first = dict(zip(header, lines[1].split(",")))
    second = dict(zip(header, lines[2].split(",")))
    assert first["research_id"] == research_id(test_patient.id)
    assert (first["day"], second["day"]) == ("0", "92")
    assert first["glucose"] == "104.0" and first["homa_ir"] == "4.57"
    text = r.text
    for secret in (test_patient.first_name, test_patient.last_name, "2026-06-01"):
        assert secret not in text

    data = client.get(
        "/api/v1/metabolic/research/export?format=json", headers=admin
    ).json()
    assert len(data["rows"]) == 2
    loinc = {d["column"]: d["loinc"] for d in data["data_dictionary"]}
    assert loinc["glucose"] == "2345-7" and loinc["waist"] == "8280-0"
    d = client.get("/api/v1/metabolic/research/export?format=dictionary", headers=admin)
    assert d.status_code == 200 and d.text.startswith("column,description,unit,loinc")
    audited = [
        log.description
        for log in db_session.query(ActivityLog)
        .filter(ActivityLog.action == "metabolic_research_export")
        .all()
    ]
    assert len(audited) == 3 and any("dictionary" in a for a in audited)

    client.put(url, json={"research_consent": False}, headers=user)
    profile = (
        db_session.query(MetabolicProfile)
        .filter(MetabolicProfile.patient_id == test_patient.id)
        .first()
    )
    db_session.refresh(profile)
    assert profile.research_consent_at is None
    r = client.get("/api/v1/metabolic/research/export?format=csv", headers=admin)
    assert len(r.text.strip().splitlines()) == 1


def test_age_band():
    assert age_band(date(1980, 5, 10), date(2026, 5, 9)) == "45-49"
    assert age_band(date(2010, 1, 1), date(2026, 1, 1)) == "<18"
    assert age_band(None, date(2026, 1, 1)) is None


def _assessment(patient_id, when, score):
    return MetabolicAssessment(
        patient_id=patient_id,
        assessed_at=when,
        algorithm_version="1",
        config_version=0,
        fingerprint=f"{patient_id}-{score}-{when.day}",
        score=score,
        risk_level="moderate",
        metabolic_syndrome_status="indeterminate",
        result={
            "patient": {"sex": "F"},
            "inputs": {"glucose": {"value": 99.0, "date": when.date().isoformat()}},
            "indicators": {},
        },
    )


def test_parse_txt_latin1_and_scanned_pdf(
    authenticated_client, test_patient, monkeypatch
):
    url = BASE.format(test_patient.id) + "/labs/parse"
    r = authenticated_client.post(
        url, files={"file": ("informe.txt", REPORT.encode("latin-1"), "text/plain")}
    )
    assert r.status_code == 200 and r.json()["source"] == "file"
    tg = [x for x in r.json()["rows"] if x["variable"] == "triglycerides"]
    assert tg and tg[0]["value"] == 230

    from app.services.pdf_text_extraction_service import PDFTextExtractionService

    monkeypatch.setattr(
        PDFTextExtractionService,
        "extract_text",
        lambda self, content, name: {"text": REPORT, "method": "ocr"},
    )
    r = authenticated_client.post(
        url, files={"file": ("scan.pdf", b"%PDF-1.4 scanned", "application/pdf")}
    )
    assert r.status_code == 200 and r.json()["source"] == "pdf_ocr"
    assert r.json()["suggested_date"] == "2026-09-12"


def test_research_export_mixed_cohort(
    client, user_token_headers, admin_token_headers, db_session, test_patient
):
    from app.crud.patient import patient as patient_crud
    from app.crud.user import user as user_crud
    from app.schemas.patient import PatientCreate
    from app.schemas.user import UserCreate

    other_user = user_crud.create(
        db_session,
        obj_in=UserCreate(
            username="otheruser",
            email="other@example.com",
            password="otherpassword123",
            full_name="Other User",
            role="user",
        ),
    )
    other = patient_crud.create_for_user(
        db_session,
        user_id=other_user.id,
        patient_data=PatientCreate(
            first_name="Nadia",
            last_name="Noconsent",
            birth_date=date(1980, 5, 5),
            gender="F",
            address="1 Other St",
        ),
    )
    db_session.add(MetabolicProfile(patient_id=other.id, research_consent=False))
    for pid in (test_patient.id, other.id):
        db_session.add(_assessment(pid, datetime(2026, 7, 1), 50))
    db_session.commit()
    url = BASE.format(test_patient.id) + "/profile"
    assert (
        client.put(
            url, json={"research_consent": True}, headers=user_token_headers
        ).status_code
        == 200
    )

    admin = admin_token_headers
    summary = client.get("/api/v1/metabolic/research/summary", headers=admin).json()
    assert summary["patients_consented"] == 1
    r = client.get("/api/v1/metabolic/research/export?format=csv", headers=admin)
    body = r.text
    assert research_id(test_patient.id) in body
    assert research_id(other.id) not in body and "Noconsent" not in body

    client.put(url, json={"research_consent": False}, headers=user_token_headers)
    r = client.get("/api/v1/metabolic/research/export?format=csv", headers=admin)
    assert len(r.text.strip().splitlines()) == 1


def test_parse_skips_reference_range_when_ocr_misses_value():
    """An OCR-garbled result must not fall back to the lower reference limit."""
    garbled = parse_lab_text(
        "Acido urico Pal mg/dL 3.5 =~ 7.2\nAcido urico 5.1 mg/dL 3.5 - 7.2"
    )
    assert [(r["value"], r["ref_min"], r["ref_max"]) for r in garbled["rows"]] == [
        (5.1, 3.5, 7.2)
    ]
    assert garbled["unrecognized"] == 1
