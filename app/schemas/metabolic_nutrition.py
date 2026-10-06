from datetime import datetime
from typing import Annotated, Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.metabolic_movement import ShortList, _check_range

FreeText = Annotated[str, Field(max_length=120)]


class EnergyTarget(BaseModel):
    kcal_target: Optional[int] = Field(None, ge=800, le=5000)
    deficit_kcal: int = Field(0, ge=0, le=1500)
    bmr_kcal: Optional[int] = Field(None, ge=0, le=6000)
    tdee_kcal: Optional[int] = Field(None, ge=0, le=8000)
    notes: Optional[str] = Field(None, max_length=1000)


class MacroTargets(BaseModel):
    protein_g_kg_min: float = Field(1.0, ge=0.5, le=2.5)
    protein_g_kg_max: float = Field(1.2, ge=0.5, le=2.5)
    protein_g_min: Optional[int] = Field(None, ge=0, le=400)
    protein_g_max: Optional[int] = Field(None, ge=0, le=400)
    carbs_pct_min: int = Field(45, ge=10, le=70)
    carbs_pct_max: int = Field(55, ge=10, le=70)
    fat_pct_min: int = Field(25, ge=15, le=50)
    fat_pct_max: int = Field(35, ge=15, le=50)
    fiber_g_min: int = Field(25, ge=10, le=80)
    added_sugar_g_max: int = Field(25, ge=0, le=100)
    saturated_fat_pct_max: int = Field(10, ge=3, le=15)
    sodium_mg_max: int = Field(2000, ge=500, le=5000)
    notes: Optional[str] = Field(None, max_length=1000)

    @model_validator(mode="after")
    def _ranges(self):
        _check_range(self.protein_g_kg_min, self.protein_g_kg_max, "protein g/kg")
        _check_range(self.protein_g_min, self.protein_g_max, "protein grams")
        _check_range(self.carbs_pct_min, self.carbs_pct_max, "carbohydrates %")
        _check_range(self.fat_pct_min, self.fat_pct_max, "fat %")
        return self


class MealStructure(BaseModel):
    meals_per_day: int = Field(3, ge=1, le=8)
    snacks_per_day: int = Field(0, ge=0, le=4)
    plate_model: bool = True
    protein_each_meal: bool = True
    regular_schedule: bool = False
    notes: Optional[str] = Field(None, max_length=1000)


class NutritionPlanContent(BaseModel):
    energy: EnergyTarget = Field(default_factory=EnergyTarget)
    macros: MacroTargets = Field(default_factory=MacroTargets)
    meals: MealStructure = Field(default_factory=MealStructure)
    hydration_l: Optional[float] = Field(None, ge=0, le=6)
    prioritize: ShortList = Field(default_factory=list, max_length=20)
    limit: ShortList = Field(default_factory=list, max_length=20)
    avoid: List[FreeText] = Field(default_factory=list, max_length=30)
    dislikes: List[FreeText] = Field(default_factory=list, max_length=30)
    targets: ShortList = Field(default_factory=list, max_length=12)
    safety: ShortList = Field(default_factory=list, max_length=12)
    recipe_ids: List[int] = Field(default_factory=list, max_length=40)


class NutritionPlanWrite(BaseModel):
    plan: NutritionPlanContent
    notes: Optional[str] = Field(None, max_length=2000)


class NutritionPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    status: str
    plan: Dict[str, Any]
    rationale: Optional[List[str]] = None
    generator_version: Optional[str] = None
    notes: Optional[str] = None
    created_by_user_id: Optional[int] = None
    approved_by_user_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
