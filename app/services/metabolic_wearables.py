"""Wearable exports (Apple Health, Google Fit, generic CSV) as daily activity summaries.

Files are parsed into reviewable daily rows; nothing is stored until import.
"""

import csv
import io
import re
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta
from statistics import mean
from typing import IO, Any, Dict, Iterable, List, Optional, Tuple
from xml.parsers import expat

from sqlalchemy.orm import Session

from app.models.base import get_utc_now
from app.models.clinical import Vitals
from app.models.metabolic import MetabolicProfile, WearableDaily
from app.models.patient import Patient
from app.services.metabolic_engine import LB_TO_KG, classify, normalize_sex

WEARABLES_VERSION = "wearables-0.1.0"
METRICS = (
    "steps",
    "exercise_minutes",
    "active_kcal",
    "sleep_hours",
    "resting_hr",
    "avg_hr",
    "weight_kg",
)
SOURCES = ("apple_health", "google_fit", "csv")
MAX_DAYS = 400
WINDOW_DAYS = 28
WEIGHT_WEEKS = 12
MAX_XML_BYTES = 4 * 1024**3

PLAUSIBLE = {
    "steps": (0, 100_000),
    "exercise_minutes": (0, 1_000),
    "active_kcal": (0, 10_000),
    "sleep_hours": (0, 16),
    "resting_hr": (25, 150),
    "avg_hr": (25, 220),
    "weight_kg": (20, 350),
}

# Steps/day (Tudor-Locke) and resting heart rate: proposal pending clinical review.
STEPS_BANDS = [
    {"level": "high", "min": None, "max": 5000},
    {"level": "borderline", "min": 5000, "max": 7500},
    {"level": "normal", "min": 7500, "max": None},
]
RESTING_HR_BANDS = [
    {"level": "low", "min": None, "max": 50},
    {"level": "normal", "min": 50, "max": 80},
    {"level": "borderline", "min": 80, "max": 90},
    {"level": "high", "min": 90, "max": None},
]

APPLE_SUM = {
    "HKQuantityTypeIdentifierStepCount": "steps",
    "HKQuantityTypeIdentifierAppleExerciseTime": "exercise_minutes",
    "HKQuantityTypeIdentifierActiveEnergyBurned": "active_kcal",
}
APPLE_MEAN = {
    "HKQuantityTypeIdentifierRestingHeartRate": "resting_hr",
    "HKQuantityTypeIdentifierHeartRate": "avg_hr",
}
APPLE_WEIGHT = "HKQuantityTypeIdentifierBodyMass"
APPLE_SLEEP = "HKCategoryTypeIdentifierSleepAnalysis"
ASLEEP_PREFIX = "HKCategoryValueSleepAnalysisAsleep"

CSV_ALIASES = {
    "date": ("date", "fecha", "día", "dia", "day", "start time", "start_date"),
    "steps": ("steps", "step count", "pasos", "número de pasos", "numero de pasos"),
    "exercise_minutes": (
        "exercise minutes",
        "exercise_minutes",
        "active minutes",
        "move minutes count",
        "move minutes",
        "minutos activos",
        "minutos de ejercicio",
        "minutos de movimiento",
        "heart minutes",
    ),
    "active_kcal": (
        "active calories",
        "active_kcal",
        "calories (kcal)",
        "calorías activas",
        "calorias activas",
        "kcal",
    ),
    "sleep_hours": (
        "sleep hours",
        "sleep_hours",
        "sleep",
        "sueño",
        "sueno",
        "horas de sueño",
        "horas de sueno",
    ),
    "resting_hr": (
        "resting heart rate",
        "resting_hr",
        "resting heart rate (bpm)",
        "fc reposo",
        "frecuencia cardiaca en reposo",
        "frecuencia cardíaca en reposo",
    ),
    "avg_hr": (
        "average heart rate (bpm)",
        "average heart rate",
        "avg_hr",
        "fc media",
        "frecuencia cardiaca media",
        "frecuencia cardíaca media",
    ),
    "weight_kg": (
        "average weight (kg)",
        "weight (kg)",
        "weight_kg",
        "weight",
        "peso",
        "peso (kg)",
    ),
}
DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y")


class WearableParseError(ValueError):
    pass


# --- Apple Health ------------------------------------------------------------


def _apple_day(stamp: Optional[str]) -> Optional[date]:
    try:
        return date.fromisoformat((stamp or "")[:10])
    except ValueError:
        return None


def _apple_dt(stamp: Optional[str]) -> Optional[datetime]:
    try:
        return datetime.strptime((stamp or "")[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


class _AppleCollector:
    def __init__(self) -> None:
        # (metric, day, source) -> total; max across sources avoids iPhone+Watch double counting
        self.sums: Dict[Tuple[str, date, str], float] = defaultdict(float)
        self.means: Dict[Tuple[str, date], List[float]] = defaultdict(list)
        self.weights: Dict[date, Tuple[str, float]] = {}
        self.records = 0

    def start(self, name: str, attrs: Dict[str, str]) -> None:
        if name != "Record":
            return
        kind = attrs.get("type")
        if kind in APPLE_SUM or kind in APPLE_MEAN or kind == APPLE_WEIGHT:
            day = _apple_day(attrs.get("startDate"))
            try:
                value = float(attrs.get("value", ""))
            except ValueError:
                return
            if day is None:
                return
            self.records += 1
            unit = (attrs.get("unit") or "").lower()
            source = attrs.get("sourceName") or ""
            if kind in APPLE_SUM:
                if kind.endswith("ActiveEnergyBurned") and unit == "kj":
                    value /= 4.184
                self.sums[(APPLE_SUM[kind], day, source)] += value
            elif kind in APPLE_MEAN:
                self.means[(APPLE_MEAN[kind], day)].append(value)
            else:
                if unit == "lb":
                    value *= LB_TO_KG
                stamp = attrs.get("startDate") or ""
                if day not in self.weights or stamp >= self.weights[day][0]:
                    self.weights[day] = (stamp, value)
        elif kind == APPLE_SLEEP and (attrs.get("value") or "").startswith(
            ASLEEP_PREFIX
        ):
            begin, end = _apple_dt(attrs.get("startDate")), _apple_dt(
                attrs.get("endDate")
            )
            if begin is None or end is None or end <= begin:
                return
            self.records += 1
            hours = (end - begin).total_seconds() / 3600
            self.sums[
                ("sleep_hours", end.date(), attrs.get("sourceName") or "")
            ] += hours

    def days(self) -> Dict[date, Dict[str, Any]]:
        out: Dict[date, Dict[str, Any]] = defaultdict(dict)
        for (metric, day, _source), total in self.sums.items():
            out[day][metric] = max(out[day].get(metric, 0), total)
        for (metric, day), values in self.means.items():
            out[day][metric] = mean(values)
        for day, (_stamp, value) in self.weights.items():
            out[day]["weight_kg"] = value
        return out


def _reject_entities(*_args: Any) -> None:
    raise WearableParseError("XML entity declarations are not allowed")


class _Limited(io.RawIOBase):
    def __init__(self, stream: IO[bytes], limit: int) -> None:
        self.stream, self.left = stream, limit

    def read(self, size: int = -1) -> bytes:
        chunk = self.stream.read(size if size and size > 0 else 1 << 20)
        self.left -= len(chunk)
        if self.left < 0:
            raise WearableParseError("Export file is too large")
        return chunk


def parse_apple_xml(stream: IO[bytes]) -> Dict[date, Dict[str, Any]]:
    collector = _AppleCollector()
    parser = expat.ParserCreate()
    parser.StartElementHandler = collector.start
    parser.EntityDeclHandler = _reject_entities
    parser.UnparsedEntityDeclHandler = _reject_entities
    parser.ExternalEntityRefHandler = lambda *a: 0
    try:
        parser.ParseFile(_Limited(stream, MAX_XML_BYTES))
    except expat.ExpatError as exc:
        raise WearableParseError(f"Invalid Apple Health XML: {exc}") from exc
    if not collector.records:
        raise WearableParseError("No activity, sleep or weight records found")
    return collector.days()


def parse_apple_zip(fileobj: IO[bytes]) -> Dict[date, Dict[str, Any]]:
    try:
        archive = zipfile.ZipFile(fileobj)
    except zipfile.BadZipFile as exc:
        raise WearableParseError("Invalid ZIP file") from exc
    names = [
        n
        for n in archive.namelist()
        if n.lower().endswith("export.xml") and "cda" not in n.lower()
    ]
    if names:
        with archive.open(names[0]) as member:
            return parse_apple_xml(member)
    csvs = [n for n in archive.namelist() if n.lower().endswith(".csv")]
    daily = [n for n in csvs if "daily" in n.lower() and "metrics" in n.lower()]
    if daily:
        return parse_daily_csv(archive.read(daily[0]).decode("utf-8-sig"))
    raise WearableParseError("The ZIP has no Apple Health export.xml or daily CSV")


# --- CSV (Google Fit Takeout "Daily activity metrics.csv" or template) --------


def _norm(header: str) -> str:
    return re.sub(r"\s+", " ", (header or "").strip().lower())


def _parse_date(raw: str) -> Optional[date]:
    raw = (raw or "").strip()[:10]
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _number(raw: Any, decimal_comma: bool) -> Optional[float]:
    text = str(raw or "").strip()
    if not text:
        return None
    if decimal_comma:
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def parse_daily_csv(text: str) -> Dict[date, Dict[str, Any]]:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise WearableParseError("The CSV file is empty")
    delimiter = ";" if lines[0].count(";") > lines[0].count(",") else ","
    reader = csv.reader(lines, delimiter=delimiter)
    header = [_norm(h) for h in next(reader)]
    columns: Dict[str, int] = {}
    for metric, aliases in CSV_ALIASES.items():
        for alias in aliases:
            if alias in header:
                columns[metric] = header.index(alias)
                break
    if "date" not in columns or len(columns) < 2:
        raise WearableParseError("CSV needs a date column and at least one metric")
    out: Dict[date, Dict[str, Any]] = {}
    for row in reader:
        idx = columns["date"]
        day = _parse_date(row[idx]) if idx < len(row) else None
        if day is None:
            continue
        values = out.setdefault(day, {})
        for metric, col in columns.items():
            if metric == "date" or col >= len(row):
                continue
            value = _number(row[col], delimiter == ";")
            if value is None:
                continue
            if metric == "sleep_hours" and value > 24:
                value /= 60  # minutes
            if metric in ("steps", "exercise_minutes", "active_kcal"):
                values[metric] = values.get(metric, 0) + value
            else:
                values[metric] = value
    if not any(out.values()):
        raise WearableParseError("No daily values found in the CSV")
    return out


# --- shared ----------------------------------------------------------------


def detect_and_parse(fileobj: IO[bytes], filename: str) -> Tuple[str, Dict]:
    name = (filename or "").lower()
    head = fileobj.read(8)
    fileobj.seek(0)
    if head[:2] == b"PK" or name.endswith(".zip"):
        days = parse_apple_zip(fileobj)
        fileobj.seek(0)
        archive = zipfile.ZipFile(fileobj)
        apple = any(n.lower().endswith("export.xml") for n in archive.namelist())
        return ("apple_health" if apple else "google_fit"), days
    if name.endswith(".xml") or head.lstrip().startswith(b"<?xml"):
        return "apple_health", parse_apple_xml(fileobj)
    raw = fileobj.read(20 * 1024 * 1024)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    first = _norm(text.splitlines()[0] if text else "")
    source = (
        "google_fit" if "move minutes" in first or "heart points" in first else "csv"
    )
    return source, parse_daily_csv(text)


def clean_days(raw: Dict[date, Dict[str, Any]], today: date) -> Dict[str, Any]:
    """Drop future/implausible values, keep the last year and round for review."""
    warnings: Dict[str, int] = defaultdict(int)
    days = []
    dated = sorted(d for d in raw if d <= today)
    if len(dated) < len(raw):
        warnings["future"] += len(raw) - len(dated)
    if dated:
        first = dated[-1] - timedelta(days=MAX_DAYS - 1)
        if dated[0] < first:
            warnings["older_than_window"] += sum(1 for d in dated if d < first)
        dated = [d for d in dated if d >= first]
    for day in dated:
        row: Dict[str, Any] = {"date": day.isoformat()}
        for metric in METRICS:
            value = raw[day].get(metric)
            if value is None:
                row[metric] = None
                continue
            lo, hi = PLAUSIBLE[metric]
            if not lo <= value <= hi:
                warnings[f"implausible_{metric}"] += 1
                row[metric] = None
                continue
            row[metric] = (
                round(value)
                if metric in ("steps", "exercise_minutes", "active_kcal")
                else round(value, 1)
            )
        if any(row[m] is not None for m in METRICS):
            days.append(row)
    return {"days": days, "warnings": dict(warnings)}


def merge_daily(rows: Iterable[Any]) -> Dict[date, Dict[str, Any]]:
    """One value per day and metric across sources (max for totals, latest import otherwise)."""
    out: Dict[date, Dict[str, Any]] = {}
    for row in sorted(rows, key=lambda r: (r.day, r.updated_at or r.created_at)):
        day = out.setdefault(row.day, {"sources": []})
        day["sources"].append(row.source)
        for metric in METRICS:
            value = getattr(row, metric)
            if value is None:
                continue
            if metric in ("steps", "exercise_minutes", "active_kcal", "sleep_hours"):
                day[metric] = max(day.get(metric) or 0, value)
            else:
                day[metric] = value
    return out


def _avg(values: List[float], digits: int = 1) -> Optional[float]:
    return round(mean(values), digits) if values else None


def summarize(
    daily: Dict[date, Dict[str, Any]],
    config: Dict[str, Any],
    sex: Optional[str],
) -> Dict[str, Any]:
    """Averages over the last 28 days with data, each with its reference bands."""
    if not daily:
        return {"window_days": WINDOW_DAYS, "days_with_data": 0, "metrics": {}}
    end = max(daily)
    start = end - timedelta(days=WINDOW_DAYS - 1)
    window = [v for d, v in daily.items() if start <= d <= end]

    def values(metric: str) -> List[float]:
        return [v[metric] for v in window if v.get(metric) is not None]

    steps = _avg(values("steps"), 0)
    exercise_days = values("exercise_minutes")
    exercise_week = (
        round(sum(exercise_days) * 7 / len(window)) if exercise_days else None
    )
    sleep = _avg(values("sleep_hours"))
    resting = _avg(values("resting_hr"), 0)
    weights = [(d, v["weight_kg"]) for d, v in daily.items() if v.get("weight_kg")]
    latest_weight = max(weights)[1] if weights else None

    def entry(value: Any, unit: str, bands: Any = None, level: Any = None) -> Dict:
        return {"value": value, "unit": unit, "bands": bands, "level": level}

    activity_level, activity_bands = classify(
        config, "physical_activity", exercise_week, sex
    )
    sleep_level, sleep_bands = classify(config, "sleep", sleep, sex)
    return {
        "window_days": WINDOW_DAYS,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "days_with_data": len(window),
        "metrics": {
            "steps": entry(steps, "pasos/día", STEPS_BANDS, _band(STEPS_BANDS, steps)),
            "physical_activity": entry(
                exercise_week, "min/sem", activity_bands, activity_level
            ),
            "sleep": entry(sleep, "h", sleep_bands, sleep_level),
            "resting_hr": entry(
                resting, "lpm", RESTING_HR_BANDS, _band(RESTING_HR_BANDS, resting)
            ),
            "weight": entry(round(latest_weight, 1) if latest_weight else None, "kg"),
        },
    }


def _band(bands: List[Dict[str, Any]], value: Optional[float]) -> Optional[str]:
    if value is None:
        return None
    for band in bands:
        lo, hi = band["min"], band["max"]
        if (lo is None or value >= lo) and (hi is None or value < hi):
            return band["level"]
    return None


def validate_days(rows: List[Dict[str, Any]], today: date) -> List[str]:
    errors = []
    seen = set()
    if len(rows) > MAX_DAYS:
        errors.append(f"At most {MAX_DAYS} days per import")
    for row in rows:
        day = row["date"]
        if day > today:
            errors.append(f"{day}: date in the future")
        if day in seen:
            errors.append(f"{day}: duplicated day")
        seen.add(day)
        for metric in METRICS:
            value = row.get(metric)
            if value is None:
                continue
            lo, hi = PLAUSIBLE[metric]
            if not lo <= value <= hi:
                errors.append(f"{day}: {metric} out of range")
    return errors


def import_days(
    db: Session,
    patient: Patient,
    rows: List[Dict[str, Any]],
    source: str,
    user_id: Optional[int],
) -> Dict[str, int]:
    """Upsert one WearableDaily per day/source; weekly last weight also goes to Vitals."""
    existing = {
        r.day: r
        for r in db.query(WearableDaily).filter(
            WearableDaily.patient_id == patient.id, WearableDaily.source == source
        )
    }
    created = updated = 0
    for row in rows:
        entry = existing.get(row["date"])
        if entry is None:
            entry = WearableDaily(patient_id=patient.id, day=row["date"], source=source)
            db.add(entry)
            created += 1
        else:
            updated += 1
        for metric in METRICS:
            setattr(entry, metric, row.get(metric))
        entry.created_by_user_id = user_id
        entry.updated_at = get_utc_now()

    weights = sorted((r["date"], r["weight_kg"]) for r in rows if r.get("weight_kg"))
    weekly: Dict[Tuple[int, int], Tuple[date, float]] = {}
    for day, kg in weights:
        weekly[day.isocalendar()[:2]] = (day, kg)
    if weights:
        cutoff = weights[-1][0] - timedelta(weeks=WEIGHT_WEEKS)
        tag = f"wearable_{source}"
        vitals = {
            v.recorded_date.date(): v
            for v in db.query(Vitals).filter(
                Vitals.patient_id == patient.id, Vitals.import_source == tag
            )
        }
        for day, kg in weekly.values():
            if day < cutoff:
                continue
            vital = vitals.get(day)
            if vital is None:
                vital = Vitals(
                    patient_id=patient.id,
                    recorded_date=datetime.combine(day, datetime.min.time()).replace(
                        hour=8
                    ),
                    import_source=tag,
                    device_used=source,
                )
                db.add(vital)
            vital.weight = round(kg / LB_TO_KG, 2)
    return {"created": created, "updated": updated}


def apply_to_profile(
    db: Session, patient_id: int, summary: Dict[str, Any], user_id: Optional[int]
) -> MetabolicProfile:
    metrics = summary.get("metrics") or {}
    activity = (metrics.get("physical_activity") or {}).get("value")
    sleep = (metrics.get("sleep") or {}).get("value")
    profile = (
        db.query(MetabolicProfile)
        .filter(MetabolicProfile.patient_id == patient_id)
        .first()
    )
    if profile is None:
        profile = MetabolicProfile(patient_id=patient_id)
        db.add(profile)
    if activity is not None:
        profile.physical_activity_minutes_week = int(activity)
    if sleep is not None:
        profile.sleep_hours = float(sleep)
    profile.updated_by_user_id = user_id
    return profile


def patient_sex(patient: Patient) -> Optional[str]:
    return normalize_sex(getattr(patient, "gender", None))
