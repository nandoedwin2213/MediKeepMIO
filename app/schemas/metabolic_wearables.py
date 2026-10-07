from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

WearableSource = Literal["apple_health", "google_fit", "csv"]


class WearableDay(BaseModel):
    date: date
    steps: Optional[int] = Field(None, ge=0, le=100_000)
    exercise_minutes: Optional[int] = Field(None, ge=0, le=1_000)
    active_kcal: Optional[int] = Field(None, ge=0, le=10_000)
    sleep_hours: Optional[float] = Field(None, ge=0, le=16)
    resting_hr: Optional[float] = Field(None, ge=25, le=150)
    avg_hr: Optional[float] = Field(None, ge=25, le=220)
    weight_kg: Optional[float] = Field(None, ge=20, le=350)


class WearableImportRequest(BaseModel):
    source: WearableSource
    days: List[WearableDay] = Field(..., min_length=1, max_length=400)
