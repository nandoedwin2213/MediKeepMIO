from datetime import datetime
from typing import Annotated, Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Category = Literal["breakfast", "lunch", "dinner", "snack", "drink"]
Diet = Literal["omnivore", "pescatarian", "vegetarian", "vegan", "other"]
Allergen = Literal[
    "gluten", "lactose", "egg", "fish", "shellfish", "nuts", "peanut", "soy", "sesame"
]
Tag = Literal[
    "high_fiber",
    "high_protein",
    "low_gi",
    "omega3",
    "low_sodium",
    "no_added_sugar",
    "low_fat",
    "quick",
]
Line = Annotated[str, Field(min_length=1, max_length=300)]


class RecipeWrite(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    category: Category
    description: Optional[str] = Field(None, max_length=1000)
    servings: int = Field(1, ge=1, le=20)
    prep_minutes: Optional[int] = Field(None, ge=0, le=600)
    kcal: Optional[float] = Field(None, ge=0, le=3000)
    protein_g: Optional[float] = Field(None, ge=0, le=300)
    carbs_g: Optional[float] = Field(None, ge=0, le=500)
    fat_g: Optional[float] = Field(None, ge=0, le=300)
    fiber_g: Optional[float] = Field(None, ge=0, le=100)
    diets: List[Diet] = Field(default_factory=lambda: ["omnivore", "other"])
    allergens: List[Allergen] = Field(default_factory=list)
    tags: List[Tag] = Field(default_factory=list)
    ingredients: List[Line] = Field(..., min_length=1, max_length=40)
    steps: List[Line] = Field(..., min_length=1, max_length=30)
    image_url: Optional[str] = Field(None, max_length=500, pattern=r"^(https://|/)\S+$")
    image_credit: Optional[str] = Field(None, max_length=300)
    image_source_url: Optional[str] = Field(
        None, max_length=500, pattern=r"^https?://\S+$"
    )
    is_active: bool = True


class RecipeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    category: str
    description: Optional[str] = None
    servings: int
    prep_minutes: Optional[int] = None
    kcal: Optional[float] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None
    fiber_g: Optional[float] = None
    diets: List[str]
    allergens: List[str]
    tags: List[str]
    ingredients: List[str]
    steps: List[str]
    image_url: Optional[str] = None
    image_credit: Optional[str] = None
    image_source_url: Optional[str] = None
    language: str
    is_library: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class RecommendedRecipe(BaseModel):
    recipe: RecipeResponse
    score: float
    reasons: List[str]
    assigned: bool = False
    conflicts: List[str] = Field(default_factory=list)


class RecommendationResponse(BaseModel):
    basis: Literal["approved_plan", "draft_plan", "profile"]
    diet_pattern: Optional[str] = None
    excluded: Dict[str, Any] = Field(default_factory=dict)
    items: List[RecommendedRecipe]
