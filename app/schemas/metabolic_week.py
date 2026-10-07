"""Schemas for the weekly programme and adherence checklist."""

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field

AdherenceItem = Literal["exercise", "nutrition", "walk", "weight", "waist"]


class AdherenceWrite(BaseModel):
    log_date: date
    item: AdherenceItem
    done: bool = True
    value: Optional[float] = Field(None, ge=0, le=100000)
