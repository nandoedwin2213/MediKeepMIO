from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

ShortList = List[str]


def _check_range(lo: Optional[int], hi: Optional[int], name: str) -> None:
    if lo is not None and hi is not None and lo > hi:
        raise ValueError(f"{name}: minimum is greater than maximum")


class FunctionalAssessmentCreate(BaseModel):
    assessed_at: datetime
    sit_to_stand_30s: Optional[int] = Field(None, ge=0, le=60)
    grip_strength_kg: Optional[float] = Field(None, ge=0, le=100)
    gait_speed_m_s: Optional[float] = Field(None, ge=0, le=3)
    walk_test_m: Optional[float] = Field(None, ge=0, le=1200)
    rpe: Optional[int] = Field(None, ge=0, le=10)
    notes: Optional[str] = Field(None, max_length=2000)

    @model_validator(mode="after")
    def _at_least_one(self):
        fields = (
            self.sit_to_stand_30s,
            self.grip_strength_kg,
            self.gait_speed_m_s,
            self.walk_test_m,
            self.rpe,
        )
        if all(v is None for v in fields):
            raise ValueError("Enter at least one functional test result")
        return self


class FunctionalAssessmentResponse(FunctionalAssessmentCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    created_by_user_id: Optional[int] = None
    indicators: Dict[str, Any] = {}


class AerobicPlan(BaseModel):
    days_per_week: int = Field(0, ge=0, le=7)
    minutes: int = Field(0, ge=0, le=180)
    intensity: Literal[
        "light", "light_moderate", "moderate", "moderate_vigorous", "vigorous"
    ] = "moderate"
    rpe_min: int = Field(3, ge=0, le=10)
    rpe_max: int = Field(4, ge=0, le=10)
    types: ShortList = Field(default_factory=list, max_length=12)
    notes: Optional[str] = Field(None, max_length=1000)

    @model_validator(mode="after")
    def _ranges(self):
        _check_range(self.rpe_min, self.rpe_max, "aerobic RPE")
        return self


class StrengthPlan(BaseModel):
    days_per_week: int = Field(0, ge=0, le=7)
    sets_min: int = Field(1, ge=0, le=10)
    sets_max: int = Field(2, ge=0, le=10)
    reps_min: int = Field(10, ge=0, le=50)
    reps_max: int = Field(15, ge=0, le=50)
    rpe_min: int = Field(5, ge=0, le=10)
    rpe_max: int = Field(6, ge=0, le=10)
    muscle_groups: ShortList = Field(default_factory=list, max_length=12)
    exercises: ShortList = Field(default_factory=list, max_length=20)
    notes: Optional[str] = Field(None, max_length=1000)

    @model_validator(mode="after")
    def _ranges(self):
        _check_range(self.sets_min, self.sets_max, "sets")
        _check_range(self.reps_min, self.reps_max, "repetitions")
        _check_range(self.rpe_min, self.rpe_max, "strength RPE")
        return self


class MobilityPlan(BaseModel):
    days_per_week: int = Field(0, ge=0, le=7)
    minutes: int = Field(0, ge=0, le=120)
    focus: ShortList = Field(default_factory=list, max_length=12)
    notes: Optional[str] = Field(None, max_length=1000)


class BalancePlan(BaseModel):
    days_per_week: int = Field(0, ge=0, le=7)
    minutes: int = Field(0, ge=0, le=120)
    exercises: ShortList = Field(default_factory=list, max_length=12)
    notes: Optional[str] = Field(None, max_length=1000)


class DailyActivityPlan(BaseModel):
    steps_start: Optional[int] = Field(None, ge=0, le=40000)
    steps_target: Optional[int] = Field(None, ge=0, le=40000)
    walk_after_meals: bool = False
    break_sitting: bool = False
    notes: Optional[str] = Field(None, max_length=1000)

    @model_validator(mode="after")
    def _ranges(self):
        _check_range(self.steps_start, self.steps_target, "steps")
        return self


class ExercisePlanContent(BaseModel):
    aerobic: AerobicPlan = Field(default_factory=AerobicPlan)
    strength: StrengthPlan = Field(default_factory=StrengthPlan)
    mobility: MobilityPlan = Field(default_factory=MobilityPlan)
    balance: BalancePlan = Field(default_factory=BalancePlan)
    daily: DailyActivityPlan = Field(default_factory=DailyActivityPlan)
    progression: ShortList = Field(default_factory=list, max_length=12)
    safety: ShortList = Field(default_factory=list, max_length=12)


class ExercisePlanWrite(BaseModel):
    plan: ExercisePlanContent
    notes: Optional[str] = Field(None, max_length=2000)


class ExercisePlanResponse(BaseModel):
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
