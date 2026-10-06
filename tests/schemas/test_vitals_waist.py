from datetime import datetime

import pytest
from pydantic import ValidationError

from app.schemas.vitals import VitalsCreate


def _vitals(**kwargs):
    return VitalsCreate(recorded_date=datetime(2026, 1, 1), patient_id=1, **kwargs)


def test_waist_circumference_accepts_valid_inches():
    assert _vitals(waist_circumference=36.2).waist_circumference == 36.2
    assert _vitals().waist_circumference is None


@pytest.mark.parametrize("value", [14.9, 80.1])
def test_waist_circumference_rejects_out_of_range(value):
    with pytest.raises(ValidationError):
        _vitals(waist_circumference=value)
