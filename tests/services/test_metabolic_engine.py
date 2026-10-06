"""Unit tests for the metabolic risk engine (pure evaluation step)."""

import pytest

from app.services.metabolic_config import default_config, validate_config
from app.services.metabolic_engine import convert_lab_value, evaluate_data


def lab(value, unit, date="2026-09-01", result_id=1):
    return {
        "value": value,
        "unit": unit,
        "date": date,
        "source": "lab",
        "lab_result_id": result_id,
        "_sort": (date, result_id, 0),
    }


def build(labs_by_result, vitals=None, habits=None, sex="M", history=None, config=None):
    """labs_by_result: {result_id: {var: (canonical_value, date)}}"""
    by_var, by_result = {}, {}
    for rid, values in labs_by_result.items():
        for var, (val, date) in values.items():
            point = lab(val, "x", date, rid)
            by_var.setdefault(var, []).append(point)
            by_result.setdefault(rid, {})[var] = point
    for points in by_var.values():
        points.sort(key=lambda p: p["_sort"], reverse=True)
    return evaluate_data(
        config or default_config(),
        0,
        sex,
        45,
        by_var,
        by_result,
        vitals or {},
        habits or {},
        history or {},
    )


def v(value, unit="cm", date="2026-09-01T08:00:00"):
    return {"value": value, "unit": unit, "date": date, "source": "vitals"}


class TestUnits:
    def test_conversions(self):
        assert convert_lab_value("glucose", 5, "mmol/L") == pytest.approx(90.08)
        assert convert_lab_value("insulin", 60, "pmol/L") == pytest.approx(10)
        assert convert_lab_value("insulin", 12, "μIU/mL") == 12
        assert convert_lab_value("triglycerides", 1.7, "mmol/L") == pytest.approx(
            150.57, 0.01
        )
        assert convert_lab_value("hba1c", 48, "mmol/mol") == pytest.approx(6.54, 0.01)
        assert convert_lab_value("glucose", 100, "g/L") is None


class TestIndices:
    def test_homa_quicki_tyg_same_sample(self):
        r = build(
            {
                1: {
                    "glucose": (100, "2026-09-01"),
                    "insulin": (20, "2026-09-01"),
                    "triglycerides": (150, "2026-09-01"),
                    "hdl": (50, "2026-09-01"),
                }
            },
            vitals={"weight": v(80, "kg"), "height": v(170)},
        )
        ind = r["indicators"]
        assert ind["homa_ir"]["value"] == 4.94 and ind["homa_ir"]["level"] == "high"
        assert ind["quicki"]["value"] == 0.303 and ind["quicki"]["level"] == "high"
        assert ind["tyg"]["value"] == 8.92 and ind["tyg"]["level"] == "high"
        assert ind["tg_hdl"]["value"] == 3.0
        assert ind["bmi"]["value"] == 27.7
        assert ind["tyg_bmi"]["value"] == pytest.approx(247.0, abs=0.5)
        assert ind["mets_ir"]["value"] == pytest.approx(42.0, abs=0.5)

    def test_no_homa_from_different_samples(self):
        r = build(
            {1: {"glucose": (200, "2026-09-01")}, 2: {"insulin": (100, "2026-09-01")}}
        )
        assert "homa_ir" not in r["indicators"]
        assert r["indicators"]["glucose"]["level"] == "veryHigh"

    def test_anthropometric_ratios_and_sex_specific_waist(self):
        r = build({}, vitals={"waist": v(95), "hip": v(100), "height": v(170)}, sex="F")
        ind = r["indicators"]
        assert ind["waist"]["level"] == "veryHigh"
        assert (
            ind["waist_hip"]["value"] == 0.95
            and ind["waist_hip"]["level"] == "veryHigh"
        )
        assert (
            ind["waist_height"]["value"] == 0.56
            and ind["waist_height"]["level"] == "high"
        )
        unknown = build({}, vitals={"waist": v(95)}, sex=None)
        assert unknown["indicators"]["waist"]["level"] is None

    def test_blood_pressure_uses_worst_value(self):
        r = build({}, vitals={"systolic": v(118, "mmHg"), "diastolic": v(85, "mmHg")})
        assert r["indicators"]["blood_pressure"]["value"] == "118/85"
        assert r["indicators"]["blood_pressure"]["level"] == "high"


class TestSyndromeScoreAlerts:
    def test_metabolic_syndrome_compatible(self):
        r = build(
            {
                1: {
                    "glucose": (105, "2026-09-01"),
                    "triglycerides": (160, "2026-09-01"),
                    "hdl": (35, "2026-09-01"),
                }
            },
            vitals={
                "waist": v(95),
                "systolic": v(125, "mmHg"),
                "diastolic": v(80, "mmHg"),
            },
        )
        ms = r["metabolic_syndrome"]
        assert ms["status"] == "compatible" and ms["met"] == 4

    def test_metabolic_syndrome_indeterminate_and_not_compatible(self):
        assert (
            build({}, vitals={"waist": v(95)})["metabolic_syndrome"]["status"]
            == "indeterminate"
        )
        r = build(
            {
                1: {
                    "glucose": (90, "2026-09-01"),
                    "triglycerides": (100, "2026-09-01"),
                    "hdl": (55, "2026-09-01"),
                }
            }
        )
        assert r["metabolic_syndrome"]["status"] == "not_compatible"

    def test_history_counts_as_criterion(self):
        r = build({}, history={"has_hypertension": True})
        bp = next(
            c
            for c in r["metabolic_syndrome"]["criteria"]
            if c["id"] == "blood_pressure"
        )
        assert bp["met"] is True

    def test_score_favorable_and_insufficient(self):
        r = build(
            {
                1: {
                    "glucose": (90, "2026-09-01"),
                    "insulin": (8, "2026-09-01"),
                    "triglycerides": (90, "2026-09-01"),
                    "hdl": (60, "2026-09-01"),
                    "hba1c": (5.2, "2026-09-01"),
                }
            },
            vitals={
                "waist": v(80),
                "weight": v(70, "kg"),
                "height": v(175),
                "systolic": v(110, "mmHg"),
                "diastolic": v(70, "mmHg"),
            },
            habits={"physical_activity": {"value": 200}, "smoking": {"value": "never"}},
        )
        assert r["score"]["value"] == 100 and r["score"]["level"] == "favorable"
        assert r["score"]["coverage"] == 1.0
        sparse = build({}, vitals={"waist": v(80)})
        assert sparse["score"]["value"] is None

    def test_factors_sorted_by_severity_and_alerts(self):
        r = build(
            {1: {"glucose": (260, "2026-09-01"), "triglycerides": (160, "2026-09-01")}},
            vitals={"waist": v(85)},
            habits={"physical_activity": {"value": 100}},
        )
        levels = [f["level"] for f in r["factors"]]
        assert levels[0] == "veryHigh"
        assert levels == sorted(
            levels,
            key=lambda lv: -{
                "veryHigh": 4,
                "high": 3,
                "borderline": 2,
                "low": 2,
                "normal": 0,
            }[lv],
        )
        assert [a["id"] for a in r["alerts"]] == ["glucose_critical"]

    def test_custom_config_changes_classification(self):
        cfg = default_config()
        cfg["indicators"]["homa_ir"]["bands"] = [
            {"level": "normal", "min": None, "max": 1.8},
            {"level": "high", "min": 1.8, "max": None},
        ]
        r = build(
            {1: {"glucose": (90, "2026-09-01"), "insulin": (9, "2026-09-01")}},
            config=cfg,
        )
        assert r["indicators"]["homa_ir"]["value"] == 2.0
        assert r["indicators"]["homa_ir"]["level"] == "high"


class TestValidateConfig:
    def test_partial_override_is_merged(self):
        merged = validate_config({"score_min_coverage": 0.5})
        assert merged["score_min_coverage"] == 0.5
        assert "homa_ir" in merged["indicators"]

    @pytest.mark.parametrize(
        "bad",
        [
            {"unknown": 1},
            {
                "indicators": {
                    "homa_ir": {"bands": [{"level": "normal", "min": 3, "max": 2}]}
                }
            },
            {
                "indicators": {
                    "homa_ir": {
                        "bands": [{"level": "terrible", "min": None, "max": None}]
                    }
                }
            },
            {"score_weights": {"waist": -1}},
            {"risk_bands": [{"level": "favorable", "min": 80}]},
            {"alerts": [{"id": "x", "metric": "glucose", "op": "!=", "value": 1}]},
        ],
    )
    def test_invalid_configs_rejected(self, bad):
        with pytest.raises(ValueError):
            validate_config(bad)
