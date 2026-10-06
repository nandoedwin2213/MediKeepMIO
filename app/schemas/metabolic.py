from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class MetabolicConfigResponse(BaseModel):
    version: int
    algorithm_version: str
    config: Dict[str, Any]
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    created_by_user_id: Optional[int] = None


class MetabolicConfigUpdate(BaseModel):
    config: Dict[str, Any]
    notes: Optional[str] = Field(None, max_length=2000)


class MetabolicEvaluationResponse(BaseModel):
    assessment_id: Optional[int] = None
    assessed_at: Optional[datetime] = None
    saved: bool
    result: Dict[str, Any]


class MetabolicAssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    assessed_at: datetime
    algorithm_version: str
    config_version: int
    score: Optional[float] = None
    risk_level: Optional[str] = None
    metabolic_syndrome_status: Optional[str] = None
    source: str
    result: Dict[str, Any]


class MetabolicProfileBase(BaseModel):
    has_diabetes: Optional[bool] = None
    has_prediabetes: Optional[bool] = None
    has_hypertension: Optional[bool] = None
    has_dyslipidemia: Optional[bool] = None
    has_fatty_liver: Optional[bool] = None
    has_obesity: Optional[bool] = None
    has_cardiovascular_disease: Optional[bool] = None
    family_diabetes: Optional[bool] = None

    physical_activity_minutes_week: Optional[int] = Field(None, ge=0, le=3000)
    sitting_hours_day: Optional[float] = Field(None, ge=0, le=24)
    sleep_hours: Optional[float] = Field(None, ge=0, le=24)
    alcohol: Optional[Literal["none", "occasional", "weekly", "daily"]] = None
    smoking: Optional[Literal["never", "former", "current"]] = None
    sugary_drinks_per_week: Optional[int] = Field(None, ge=0, le=100)
    ultraprocessed_per_week: Optional[int] = Field(None, ge=0, le=100)
    fruit_veg_servings_day: Optional[int] = Field(None, ge=0, le=30)

    musculoskeletal_limitations: Optional[str] = Field(None, max_length=2000)
    pain_level: Optional[int] = Field(None, ge=0, le=10)
    goals: Optional[str] = Field(None, max_length=2000)
    diet_pattern: Optional[
        Literal["omnivore", "vegetarian", "vegan", "pescatarian", "other"]
    ] = None
    food_intolerances: Optional[str] = Field(None, max_length=1000)
    food_dislikes: Optional[str] = Field(None, max_length=1000)
    meals_per_day: Optional[int] = Field(None, ge=1, le=8)


class MetabolicProfileUpdate(MetabolicProfileBase):
    pass


class MetabolicProfileResponse(MetabolicProfileBase):
    model_config = ConfigDict(from_attributes=True)

    patient_id: int
    updated_at: Optional[datetime] = None
    updated_by_user_id: Optional[int] = None


MetabolicAssessmentList = List[MetabolicAssessmentResponse]
