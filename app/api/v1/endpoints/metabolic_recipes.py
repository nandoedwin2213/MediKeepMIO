"""Recipe library and "recommended for you" endpoints."""

import re
import secrets
import unicodedata
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api import deps
from app.api.v1.endpoints.metabolic_movement import _patient
from app.api.v1.endpoints.metabolic_nutrition import _active_allergens
from app.core.http.error_handling import (
    ForbiddenException,
    NotFoundException,
    handle_database_errors,
)
from app.models.metabolic import MetabolicProfile, NutritionPlan, Recipe
from app.models.models import User
from app.schemas.metabolic_recipes import (
    Category,
    RecipeResponse,
    RecipeWrite,
    RecommendationResponse,
)
from app.services.metabolic_dashboard import is_professional
from app.services.metabolic_engine import evaluate_patient
from app.services.metabolic_nutrition import generate_nutrition_plan
from app.services.metabolic_recipes import ensure_library, recommend

router = APIRouter()


def _require_professional(user: User, request: Request) -> None:
    if not is_professional(user):
        raise ForbiddenException(message="Professional role required", request=request)


def _get_recipe(db: Session, recipe_id: int, request: Request) -> Recipe:
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if recipe is None:
        raise NotFoundException(message="Recipe not found", request=request)
    return recipe


def _slug(name: str) -> str:
    base = unicodedata.normalize("NFKD", name.lower())
    base = "".join(c for c in base if not unicodedata.combining(c))
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")[:60] or "receta"
    return f"{base}-{secrets.token_hex(3)}"


@router.get("/recipes", response_model=List[RecipeResponse])
def list_recipes(
    *,
    category: Optional[Category] = None,
    include_inactive: bool = False,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    ensure_library(db)
    query = db.query(Recipe)
    if category:
        query = query.filter(Recipe.category == category)
    if not (include_inactive and is_professional(current_user)):
        query = query.filter(Recipe.is_active.is_(True))
    return query.order_by(Recipe.category, Recipe.name).all()


@router.get("/recipes/{recipe_id}", response_model=RecipeResponse)
def get_recipe(
    *,
    recipe_id: int,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    recipe = _get_recipe(db, recipe_id, request)
    if not recipe.is_active and not is_professional(current_user):
        raise NotFoundException(message="Recipe not found", request=request)
    return recipe


@router.post("/recipes", response_model=RecipeResponse)
def create_recipe(
    *,
    body: RecipeWrite,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    _require_professional(current_user, request)
    with handle_database_errors(request=request):
        recipe = Recipe(
            **body.model_dump(),
            slug=_slug(body.name),
            is_library=False,
            created_by_user_id=current_user.id,
        )
        db.add(recipe)
        db.commit()
        db.refresh(recipe)
        return recipe


@router.put("/recipes/{recipe_id}", response_model=RecipeResponse)
def update_recipe(
    *,
    recipe_id: int,
    body: RecipeWrite,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    _require_professional(current_user, request)
    recipe = _get_recipe(db, recipe_id, request)
    with handle_database_errors(request=request):
        for key, value in body.model_dump().items():
            setattr(recipe, key, value)
        db.commit()
        db.refresh(recipe)
        return recipe


@router.delete("/recipes/{recipe_id}")
def delete_recipe(
    *,
    recipe_id: int,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Library recipes are hidden (so they are not re-seeded); custom ones are deleted."""
    _require_professional(current_user, request)
    recipe = _get_recipe(db, recipe_id, request)
    with handle_database_errors(request=request):
        if recipe.is_library:
            recipe.is_active = False
        else:
            db.delete(recipe)
        db.commit()
    return {"deleted": not recipe.is_library, "hidden": recipe.is_library}


@router.get(
    "/patients/{patient_id}/recipes/recommended",
    response_model=RecommendationResponse,
)
def recommended_recipes(
    *,
    patient_id: int,
    category: Optional[Category] = None,
    limit: int = Query(12, ge=1, le=50),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Rank recipes with the approved plan (drafts only for professionals)."""
    deps.verify_patient_access(patient_id, db, current_user)
    ensure_library(db)
    plans = db.query(NutritionPlan).filter(NutritionPlan.patient_id == patient_id)
    plan = (
        plans.filter(NutritionPlan.status == "approved")
        .order_by(NutritionPlan.approved_at.desc(), NutritionPlan.id.desc())
        .first()
    )
    basis = "approved_plan"
    if plan is None and is_professional(current_user):
        plan = (
            plans.filter(NutritionPlan.status == "draft")
            .order_by(NutritionPlan.id.desc())
            .first()
        )
        basis = "draft_plan"
    profile = (
        db.query(MetabolicProfile)
        .filter(MetabolicProfile.patient_id == patient_id)
        .first()
    )
    if plan is not None:
        content, rationale = plan.plan or {}, plan.rationale or []
    else:
        basis = "profile"
        result = evaluate_patient(db, _patient(db, patient_id))
        content, rationale = generate_nutrition_plan(
            result, profile, _active_allergens(db, patient_id)
        )
    query = db.query(Recipe).filter(Recipe.is_active.is_(True))
    if category:
        query = query.filter(Recipe.category == category)
    diet = getattr(profile, "diet_pattern", None)
    ranked = recommend(
        query.all(),
        diet_pattern=diet,
        avoid=list(content.get("avoid") or []),
        dislikes=list(content.get("dislikes") or []),
        rationale=list(rationale),
        assigned_ids=list(content.get("recipe_ids") or []),
        kcal_target=(content.get("energy") or {}).get("kcal_target"),
        limit=limit,
    )
    return {"basis": basis, "diet_pattern": diet, **ranked}
