"""Weekly programme ("Mi semana metabólica") and adherence score built from approved plans."""

from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

WEEK_VERSION = "week-0.1.0"
WEEKLY_ITEMS = ("weight", "waist")
MEALS = ("breakfast", "lunch", "dinner", "snack")
DEFAULT_STEPS = 5000

AEROBIC_DAYS = {
    1: [2],
    2: [1, 4],
    3: [0, 2, 4],
    4: [0, 1, 3, 4],
    5: [0, 1, 2, 3, 4],
    6: [0, 1, 2, 3, 4, 5],
    7: [0, 1, 2, 3, 4, 5, 6],
}
STRENGTH_DAYS = {
    1: [1],
    2: [1, 3],
    3: [1, 3, 5],
    4: [0, 1, 3, 5],
    5: [0, 1, 2, 3, 5],
    6: [0, 1, 2, 3, 4, 5],
    7: [0, 1, 2, 3, 4, 5, 6],
}
SPREAD_DAYS = AEROBIC_DAYS


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _days(n: Any, table: Dict[int, List[int]]) -> Set[int]:
    try:
        count = int(n or 0)
    except (TypeError, ValueError):
        count = 0
    return set(table.get(max(0, min(7, count)), []))


def _brief(recipe: Any) -> Dict[str, Any]:
    return {
        "id": recipe.id,
        "name": recipe.name,
        "category": recipe.category,
        "kcal": recipe.kcal,
        "image_url": recipe.image_url,
    }


def _meals(
    by_category: Dict[str, List[Any]], day_index: int, offset: int, snacks: int
) -> Dict[str, Any]:
    meals: Dict[str, Any] = {}
    for meal in MEALS:
        if meal == "snack" and snacks <= 0:
            continue
        options = by_category.get(meal) or []
        if options:
            meals[meal] = _brief(options[(offset + day_index) % len(options)])
    return meals


def build_week(
    start: date,
    *,
    exercise: Optional[Dict[str, Any]],
    nutrition: Optional[Dict[str, Any]],
    recipes: Sequence[Any],
    logs: Iterable[Any],
    measured: Dict[str, Set[date]],
    today: date,
    exercise_since: Optional[date] = None,
    nutrition_since: Optional[date] = None,
) -> Dict[str, Any]:
    """Lay out the approved plans over Monday–Sunday and score the checklist."""
    start = week_start(start)
    end = start + timedelta(days=6)
    done = {(log.log_date, log.item): bool(log.done) for log in logs}
    by_category: Dict[str, List[Any]] = {}
    for recipe in recipes:
        by_category.setdefault(recipe.category, []).append(recipe)
    offset = start.isocalendar()[1]
    snacks = int(((nutrition or {}).get("meals") or {}).get("snacks_per_day") or 0)

    aerobic = (exercise or {}).get("aerobic") or {}
    strength = (exercise or {}).get("strength") or {}
    mobility = (exercise or {}).get("mobility") or {}
    balance = (exercise or {}).get("balance") or {}
    daily = (exercise or {}).get("daily") or {}
    aerobic_days = _days(aerobic.get("days_per_week"), AEROBIC_DAYS)
    strength_days = _days(strength.get("days_per_week"), STRENGTH_DAYS)
    mobility_days = _days(mobility.get("days_per_week"), SPREAD_DAYS)
    balance_days = _days(balance.get("days_per_week"), STRENGTH_DAYS)
    types = list(aerobic.get("types") or [])

    days = []
    for i in range(7):
        day_date = start + timedelta(days=i)
        day: Dict[str, Any] = {
            "date": day_date.isoformat(),
            "weekday": i,
            "is_today": day_date == today,
            "is_future": day_date > today,
            "meals": {},
            "aerobic": None,
            "strength": None,
            "mobility": None,
            "balance": None,
            "steps_target": None,
            "walk_after_meals": False,
            "items": [],
        }
        items: List[str] = []
        if exercise is not None:
            if i in aerobic_days:
                day["aerobic"] = {
                    "minutes": aerobic.get("minutes"),
                    "intensity": aerobic.get("intensity"),
                    "type": types[i % len(types)] if types else None,
                }
            if i in strength_days:
                day["strength"] = {
                    key: strength.get(key)
                    for key in (
                        "sets_min",
                        "sets_max",
                        "reps_min",
                        "reps_max",
                        "muscle_groups",
                        "exercises",
                    )
                }
            if i in mobility_days:
                day["mobility"] = {"minutes": mobility.get("minutes")}
            if i in balance_days:
                day["balance"] = {"minutes": balance.get("minutes")}
            day["steps_target"] = daily.get("steps_start") or DEFAULT_STEPS
            day["walk_after_meals"] = bool(daily.get("walk_after_meals"))
            if exercise_since is None or day_date >= exercise_since:
                if day["aerobic"] or day["strength"]:
                    items.append("exercise")
                items.append("walk")
        if nutrition is not None:
            day["meals"] = _meals(by_category, i, offset, snacks)
            if nutrition_since is None or day_date >= nutrition_since:
                items.append("nutrition")
        day["items"] = [
            {"item": key, "done": done.get((day_date, key), False)} for key in items
        ]
        days.append(day)

    active = (exercise is not None and (exercise_since or start) <= end) or (
        nutrition is not None and (nutrition_since or start) <= end
    )
    weekly = []
    if active:
        for key in WEEKLY_ITEMS:
            in_week = any(start <= d <= end for d in measured.get(key, ()))
            logged = any(done.get((start + timedelta(days=i), key)) for i in range(7))
            weekly.append(
                {
                    "item": key,
                    "done": in_week or logged,
                    "source": "vitals" if in_week else ("log" if logged else None),
                }
            )

    elapsed = [d for d in days if not d["is_future"]]
    done_count = sum(it["done"] for d in elapsed for it in d["items"])
    done_count += sum(1 for w in weekly if w["done"])
    expected = sum(len(d["items"]) for d in elapsed)
    expected += sum(1 for w in weekly if w["done"] or end < today)
    planned = sum(len(d["items"]) for d in days) + len(weekly)
    return {
        "version": WEEK_VERSION,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "is_current": start <= today <= end,
        "days": days,
        "weekly": weekly,
        "adherence": {
            "done": done_count,
            "expected": expected,
            "planned": planned,
            "percent": round(100 * done_count / expected) if expected else None,
        },
    }
