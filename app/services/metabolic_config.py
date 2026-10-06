"""Default clinical configuration for the metabolic risk engine.

Every threshold here is orientative and can be overridden from the medical
administration panel; overrides are stored as new versions in
``metabolic_engine_configs``.
"""

import copy
from typing import Any, Dict, List, Optional

ALGORITHM_VERSION = "1.0.0"

LEVELS = ("low", "normal", "borderline", "high", "veryHigh")
RISK_LEVELS = ("favorable", "initial", "moderate", "high")
SEXES = ("M", "F")


def _bands(*rows) -> List[Dict[str, Optional[float]]]:
    return [{"level": level, "min": lo, "max": hi} for level, lo, hi in rows]


DEFAULT_CONFIG: Dict[str, Any] = {
    "indicators": {
        "homa_ir": {
            "bands": _bands(
                ("normal", None, 2.5),
                ("borderline", 2.5, 3.5),
                ("high", 3.5, 5),
                ("veryHigh", 5, None),
            )
        },
        "quicki": {
            "bands": _bands(
                ("veryHigh", None, 0.30),
                ("high", 0.30, 0.32),
                ("borderline", 0.32, 0.34),
                ("normal", 0.34, None),
            )
        },
        "tyg": {
            "bands": _bands(
                ("normal", None, 8.5),
                ("borderline", 8.5, 8.8),
                ("high", 8.8, 9.3),
                ("veryHigh", 9.3, None),
            )
        },
        "tyg_bmi": {
            "bands": _bands(
                ("normal", None, 200),
                ("borderline", 200, 230),
                ("high", 230, 260),
                ("veryHigh", 260, None),
            )
        },
        "mets_ir": {
            "bands": _bands(
                ("normal", None, 40),
                ("borderline", 40, 50.4),
                ("high", 50.4, 60),
                ("veryHigh", 60, None),
            )
        },
        "tg_hdl": {
            "bands": _bands(
                ("normal", None, 2),
                ("borderline", 2, 3),
                ("high", 3, 5),
                ("veryHigh", 5, None),
            )
        },
        "glucose": {
            "bands": _bands(
                ("normal", None, 100),
                ("borderline", 100, 126),
                ("high", 126, 200),
                ("veryHigh", 200, None),
            )
        },
        "insulin": {
            "bands": _bands(
                ("normal", None, 15),
                ("borderline", 15, 25),
                ("high", 25, 50),
                ("veryHigh", 50, None),
            )
        },
        "hba1c": {
            "bands": _bands(
                ("normal", None, 5.7),
                ("borderline", 5.7, 6.5),
                ("high", 6.5, 8),
                ("veryHigh", 8, None),
            )
        },
        "triglycerides": {
            "bands": _bands(
                ("normal", None, 150),
                ("borderline", 150, 200),
                ("high", 200, 500),
                ("veryHigh", 500, None),
            )
        },
        "hdl": {
            "by_sex": {
                "M": _bands(
                    ("veryHigh", None, 35), ("high", 35, 40), ("normal", 40, None)
                ),
                "F": _bands(
                    ("veryHigh", None, 40), ("high", 40, 50), ("normal", 50, None)
                ),
            }
        },
        "ldl": {
            "bands": _bands(
                ("normal", None, 100),
                ("borderline", 100, 130),
                ("high", 130, 160),
                ("veryHigh", 160, None),
            )
        },
        "total_cholesterol": {
            "bands": _bands(
                ("normal", None, 200), ("borderline", 200, 240), ("high", 240, None)
            )
        },
        "alt": {
            "bands": _bands(
                ("normal", None, 35), ("high", 35, 70), ("veryHigh", 70, None)
            )
        },
        "ast": {
            "bands": _bands(
                ("normal", None, 35), ("high", 35, 70), ("veryHigh", 70, None)
            )
        },
        "ggt": {
            "bands": _bands(
                ("normal", None, 50), ("high", 50, 100), ("veryHigh", 100, None)
            )
        },
        "creatinine": {
            "by_sex": {
                "M": _bands(
                    ("normal", None, 1.3), ("high", 1.3, 2), ("veryHigh", 2, None)
                ),
                "F": _bands(
                    ("normal", None, 1.1), ("high", 1.1, 2), ("veryHigh", 2, None)
                ),
            }
        },
        "uric_acid": {
            "by_sex": {
                "M": _bands(("normal", None, 7), ("high", 7, 9), ("veryHigh", 9, None)),
                "F": _bands(("normal", None, 6), ("high", 6, 8), ("veryHigh", 8, None)),
            }
        },
        "bmi": {
            "bands": _bands(
                ("low", None, 18.5),
                ("normal", 18.5, 25),
                ("borderline", 25, 30),
                ("high", 30, 35),
                ("veryHigh", 35, None),
            )
        },
        "waist": {
            "by_sex": {
                "M": _bands(
                    ("normal", None, 90), ("high", 90, 102), ("veryHigh", 102, None)
                ),
                "F": _bands(
                    ("normal", None, 80), ("high", 80, 88), ("veryHigh", 88, None)
                ),
            }
        },
        "waist_height": {
            "bands": _bands(
                ("normal", None, 0.5),
                ("borderline", 0.5, 0.55),
                ("high", 0.55, 0.6),
                ("veryHigh", 0.6, None),
            )
        },
        "waist_hip": {
            "by_sex": {
                "M": _bands(
                    ("normal", None, 0.9), ("high", 0.9, 1.0), ("veryHigh", 1.0, None)
                ),
                "F": _bands(
                    ("normal", None, 0.85), ("high", 0.85, 0.9), ("veryHigh", 0.9, None)
                ),
            }
        },
        "systolic": {
            "bands": _bands(
                ("normal", None, 120),
                ("borderline", 120, 130),
                ("high", 130, 140),
                ("veryHigh", 140, None),
            )
        },
        "diastolic": {
            "bands": _bands(
                ("normal", None, 80), ("high", 80, 90), ("veryHigh", 90, None)
            )
        },
        "physical_activity": {
            "bands": _bands(
                ("veryHigh", None, 1),
                ("high", 1, 75),
                ("borderline", 75, 150),
                ("normal", 150, None),
            )
        },
        "sitting": {
            "bands": _bands(
                ("normal", None, 6), ("borderline", 6, 8), ("high", 8, None)
            )
        },
        "sleep": {
            "bands": _bands(
                ("high", None, 6),
                ("borderline", 6, 7),
                ("normal", 7, 9.5),
                ("borderline", 9.5, None),
            )
        },
        "sugary_drinks": {
            "bands": _bands(
                ("normal", None, 2), ("borderline", 2, 7), ("high", 7, None)
            )
        },
        "ultraprocessed": {
            "bands": _bands(
                ("normal", None, 3), ("borderline", 3, 7), ("high", 7, None)
            )
        },
        "fruit_veg": {
            "bands": _bands(
                ("high", None, 2), ("borderline", 2, 5), ("normal", 5, None)
            )
        },
        "smoking": {
            "map": {"never": "normal", "former": "borderline", "current": "high"}
        },
        "alcohol": {
            "map": {
                "none": "normal",
                "occasional": "normal",
                "weekly": "borderline",
                "daily": "high",
            }
        },
    },
    "level_points": {
        "low": 65,
        "normal": 100,
        "borderline": 65,
        "high": 35,
        "veryHigh": 10,
    },
    "score_weights": {
        "waist": 20,
        "homa_ir": 15,
        "blood_pressure": 15,
        "tyg": 10,
        "glucose": 10,
        "hba1c": 10,
        "tg_hdl": 10,
        "bmi": 10,
        "physical_activity": 10,
        "smoking": 5,
    },
    "score_min_coverage": 0.4,
    "risk_bands": [
        {"level": "favorable", "min": 80},
        {"level": "initial", "min": 60},
        {"level": "moderate", "min": 40},
        {"level": "high", "min": 0},
    ],
    # Harmonized criteria (IDF/AHA 2009) with IDF waist cut-offs for Latin America.
    "metabolic_syndrome": {
        "required": 3,
        "criteria": [
            {"id": "waist", "metric": "waist", "op": ">=", "value": {"M": 90, "F": 80}},
            {
                "id": "triglycerides",
                "metric": "triglycerides",
                "op": ">=",
                "value": 150,
                "history": "has_dyslipidemia",
            },
            {"id": "hdl", "metric": "hdl", "op": "<", "value": {"M": 40, "F": 50}},
            {
                "id": "blood_pressure",
                "any": [
                    {"metric": "systolic", "op": ">=", "value": 130},
                    {"metric": "diastolic", "op": ">=", "value": 85},
                ],
                "history": "has_hypertension",
            },
            {
                "id": "glucose",
                "metric": "glucose",
                "op": ">=",
                "value": 100,
                "history": "has_diabetes",
            },
        ],
    },
    "alerts": [
        {"id": "glucose_critical", "metric": "glucose", "op": ">=", "value": 250},
        {"id": "hba1c_critical", "metric": "hba1c", "op": ">=", "value": 9},
        {"id": "systolic_critical", "metric": "systolic", "op": ">=", "value": 180},
        {"id": "diastolic_critical", "metric": "diastolic", "op": ">=", "value": 120},
        {
            "id": "triglycerides_critical",
            "metric": "triglycerides",
            "op": ">=",
            "value": 500,
        },
        {"id": "alt_critical", "metric": "alt", "op": ">=", "value": 120},
        {"id": "creatinine_critical", "metric": "creatinine", "op": ">=", "value": 2},
    ],
}

OPERATORS = (">=", ">", "<=", "<")


def default_config() -> Dict[str, Any]:
    return copy.deepcopy(DEFAULT_CONFIG)


def _check_bands(name: str, bands: Any) -> None:
    if not isinstance(bands, list) or not bands:
        raise ValueError(f"{name}: bands must be a non-empty list")
    for band in bands:
        if not isinstance(band, dict) or band.get("level") not in LEVELS:
            raise ValueError(f"{name}: invalid band level")
        lo, hi = band.get("min"), band.get("max")
        for bound in (lo, hi):
            if bound is not None and not isinstance(bound, (int, float)):
                raise ValueError(f"{name}: band limits must be numbers")
        if lo is not None and hi is not None and lo >= hi:
            raise ValueError(f"{name}: band min must be lower than max")


def validate_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a submitted config and fill any missing section with defaults."""
    if not isinstance(config, dict):
        raise ValueError("config must be an object")
    merged = default_config()
    for key, value in config.items():
        if key == "indicators":
            if not isinstance(value, dict):
                raise ValueError("indicators must be an object")
            merged["indicators"].update(value)
        elif key in merged:
            merged[key] = value
        else:
            raise ValueError(f"unknown config section: {key}")

    for name, indicator in merged["indicators"].items():
        if not isinstance(indicator, dict):
            raise ValueError(f"{name}: invalid indicator")
        if "bands" in indicator:
            _check_bands(name, indicator["bands"])
        elif "by_sex" in indicator:
            for sex in SEXES:
                _check_bands(f"{name}.{sex}", indicator["by_sex"].get(sex))
        elif "map" in indicator:
            if any(level not in LEVELS for level in indicator["map"].values()):
                raise ValueError(f"{name}: invalid level in map")
        else:
            raise ValueError(f"{name}: indicator needs bands, by_sex or map")

    points = merged["level_points"]
    if not isinstance(points, dict) or any(
        not isinstance(points.get(level), (int, float)) or not 0 <= points[level] <= 100
        for level in LEVELS
    ):
        raise ValueError("level_points must give 0-100 points for every level")

    weights = merged["score_weights"]
    if not isinstance(weights, dict) or any(
        not isinstance(w, (int, float)) or w < 0 for w in weights.values()
    ):
        raise ValueError("score_weights must be non-negative numbers")
    if sum(weights.values()) <= 0:
        raise ValueError("score_weights must add up to more than 0")

    coverage = merged["score_min_coverage"]
    if not isinstance(coverage, (int, float)) or not 0 <= coverage <= 1:
        raise ValueError("score_min_coverage must be between 0 and 1")

    bands = merged["risk_bands"]
    if not isinstance(bands, list) or {b.get("level") for b in bands} != set(
        RISK_LEVELS
    ):
        raise ValueError("risk_bands must define favorable, initial, moderate and high")
    if any(not isinstance(b.get("min"), (int, float)) for b in bands):
        raise ValueError("risk_bands min must be numbers")

    syndrome = merged["metabolic_syndrome"]
    if not isinstance(syndrome.get("required"), int) or syndrome["required"] < 1:
        raise ValueError("metabolic_syndrome.required must be a positive integer")
    for criterion in syndrome.get("criteria", []):
        for rule in criterion.get("any", [criterion]):
            if rule.get("op") not in OPERATORS:
                raise ValueError(
                    f"metabolic_syndrome {criterion.get('id')}: invalid operator"
                )

    for alert in merged["alerts"]:
        if (
            not alert.get("id")
            or alert.get("op") not in OPERATORS
            or not isinstance(alert.get("value"), (int, float))
        ):
            raise ValueError("alerts need id, a valid op and a numeric value")
    return merged
