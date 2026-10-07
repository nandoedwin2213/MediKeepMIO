from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

PriorityCode = Literal[
    "reduce_waist",
    "increase_activity",
    "carb_quality",
    "strength",
    "blood_pressure",
    "healthy_fats",
    "sleep",
    "stop_smoking",
    "liver",
    "repeat_labs",
]


class SimulationRequest(BaseModel):
    """Educational what-if deltas; reductions are negative, extra activity in min/week."""

    weight: Optional[float] = Field(None, ge=-30, le=0)
    waist: Optional[float] = Field(None, ge=-25, le=0)
    triglycerides: Optional[float] = Field(None, ge=-200, le=0)
    hba1c: Optional[float] = Field(None, ge=-3, le=0)
    glucose: Optional[float] = Field(None, ge=-80, le=0)
    physical_activity: Optional[float] = Field(None, ge=0, le=300)


class InsightWrite(BaseModel):
    note: Optional[str] = Field(None, max_length=4000)
    priorities: Optional[List[PriorityCode]] = Field(None, max_length=10)


class InsightResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    status: str
    content: Dict[str, Any]
    note: Optional[str] = None
    engine_version: Optional[str] = None
    created_by_user_id: Optional[int] = None
    approved_by_user_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
