"""Recipe library seeding and rule-based "recommended for you" ranking."""

import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.metabolic import Recipe
from app.services.metabolic_recipe_library import library_recipes

RANKER_VERSION = "recipes-0.1.0"

# Patient free text (allergies, intolerances, plan exclusions) → recipe allergen keys.
ALLERGEN_KEYWORDS = {
    "gluten": ["gluten", "trigo", "wheat", "celiac", "celiaq", "cebada", "centeno"],
    "lactose": ["lact", "leche", "milk", "dairy", "queso", "cheese", "yogur", "yogurt"],
    "egg": ["huevo", "egg"],
    "fish": ["pescado", "fish", "atun", "tuna", "salmon"],
    "shellfish": [
        "marisco",
        "shellfish",
        "camaron",
        "shrimp",
        "crustace",
        "langost",
        "concha",
    ],
    "nuts": [
        "nuez",
        "nueces",
        "nut",
        "almendra",
        "almond",
        "frutos secos",
        "anacardo",
        "avellana",
    ],
    "peanut": ["mani", "peanut", "cacahuate", "cacahuete"],
    "soy": ["soya", "soja", "soy", "tofu"],
    "sesame": ["sesamo", "ajonjoli", "sesame", "tahini"],
}

REASON_TAG_WEIGHTS = {
    "glycemic": {"low_gi": 3, "high_fiber": 2},
    "triglycerides": {"no_added_sugar": 2, "omega3": 2, "low_gi": 1},
    "lipids": {"omega3": 2, "high_fiber": 1, "low_fat": 1},
    "blood_pressure": {"low_sodium": 3},
    "weight_loss": {"high_protein": 1, "high_fiber": 1, "low_fat": 1},
    "uric_acid": {"no_added_sugar": 1},
    "liver": {"no_added_sugar": 2, "high_fiber": 1},
}


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def allergen_keys(texts: Iterable[str]) -> List[str]:
    found = set()
    for text in texts:
        t = _norm(text or "")
        for key, words in ALLERGEN_KEYWORDS.items():
            if any(re.search(rf"\b{re.escape(w)}", t) for w in words):
                found.add(key)
    return sorted(found)


def ensure_library(db: Session) -> None:
    """Insert library recipes that are missing; existing rows are never overwritten."""
    seeds = library_recipes()
    present = {
        s
        for (s,) in db.query(Recipe.slug)
        .filter(Recipe.slug.in_([r["slug"] for r in seeds]))
        .all()
    }
    missing = [r for r in seeds if r["slug"] not in present]
    if not missing:
        return
    try:
        db.add_all(Recipe(**r) for r in missing)
        db.commit()
    except IntegrityError:
        db.rollback()


def _dislike_hits(recipe: Recipe, dislikes: List[str]) -> List[str]:
    haystack = _norm(" ".join([recipe.name, *(recipe.ingredients or [])]))
    return [d for d in dislikes if len(d) > 2 and _norm(d) in haystack]


def recommend(
    recipes: List[Recipe],
    *,
    diet_pattern: Optional[str],
    avoid: List[str],
    dislikes: List[str],
    rationale: List[str],
    assigned_ids: List[int],
    kcal_target: Optional[int] = None,
    limit: int = 12,
) -> Dict[str, Any]:
    blocked = set(allergen_keys(avoid))
    weights: Dict[str, float] = {}
    for reason in rationale:
        for tag, w in REASON_TAG_WEIGHTS.get(reason, {}).items():
            weights[tag] = weights.get(tag, 0) + w
    excluded = {"diet": 0, "allergen": 0, "dislike": 0}
    items = []
    for recipe in recipes:
        assigned = recipe.id in assigned_ids
        conflicts = sorted(blocked & set(recipe.allergens or []))
        diet_ok = not diet_pattern or diet_pattern in (recipe.diets or [])
        disliked = _dislike_hits(recipe, dislikes)
        if not diet_ok:
            conflicts.append("diet")
        if disliked:
            conflicts.append("dislike")
        if conflicts and not assigned:
            key = (
                "allergen"
                if blocked & set(recipe.allergens or [])
                else ("diet" if not diet_ok else "dislike")
            )
            excluded[key] += 1
            continue
        tags = set(recipe.tags or [])
        reasons = sorted((t for t in tags if t in weights), key=lambda t: -weights[t])
        score = 1.0 + sum(weights[t] for t in reasons) + 0.25 * len(tags)
        if "weight_loss" in rationale and recipe.kcal and recipe.category != "drink":
            budget = (kcal_target or 1600) / 3
            if recipe.kcal > budget * 1.15:
                score -= 2
        if assigned:
            score += 100
        items.append(
            {
                "recipe": recipe,
                "score": round(score, 2),
                "reasons": reasons,
                "assigned": assigned,
                "conflicts": conflicts,
            }
        )
    items.sort(key=lambda i: (-i["score"], i["recipe"].name))
    return {"items": items[:limit], "excluded": excluded}
