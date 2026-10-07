from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

LabVariable = Literal[
    "glucose",
    "insulin",
    "hba1c",
    "triglycerides",
    "hdl",
    "ldl",
    "total_cholesterol",
    "alt",
    "ast",
    "ggt",
    "creatinine",
    "uric_acid",
]


class LabImportRow(BaseModel):
    variable: LabVariable
    value: float = Field(..., gt=0, lt=100000)
    unit: str = Field(..., max_length=20)
    ref_min: Optional[float] = None
    ref_max: Optional[float] = None
    ref_text: Optional[str] = Field(None, max_length=100)


class LabImportRequest(BaseModel):
    collected_on: date
    name: str = Field(..., min_length=1, max_length=120)
    facility: Optional[str] = Field(None, max_length=120)
    rows: List[LabImportRow] = Field(..., min_length=1, max_length=30)
