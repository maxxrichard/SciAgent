import pytest

from sciagent.core.errors import ValidationFailed
from sciagent.data.harmonise import harmonise_record, normalise_unit, to_canonical


@pytest.mark.parametrize(
    "quantity,value,unit,expected",
    [
        ("temperature", 98.6, "°F", 37.0),
        ("temperature", 310.15, "K", 37.0),
        ("glucose", 90.08, "mg/dl", 5.0),
        ("creatinine", 1.0, "mg/dL", 88.42),
        ("weight", 1000, "g", 1.0),
        ("height", 1.8, "m", 180.0),
        ("hemoglobin", 140, "g/L", 14.0),
        ("heart_rate", 60, "bpm", 60.0),
    ],
)
def test_conversions(quantity, value, unit, expected):
    v, _ = to_canonical(quantity, value, unit)
    assert v == pytest.approx(expected, abs=1e-3)


def test_unit_aliases():
    assert normalise_unit(" Celsius ") == "Cel" and normalise_unit("mmHg") == "mmHg"


def test_unknown_quantity_or_unit():
    with pytest.raises(ValidationFailed):
        to_canonical("viscosity", 1, "cP")
    with pytest.raises(ValidationFailed):
        to_canonical("weight", 1, "stone")


def test_record_statuses():
    assert harmonise_record("glu", 100, "mg/dL").loinc == "2345-7"
    assert harmonise_record("XYZ", 1, "u").status == "unmapped"
    rejected = harmonise_record("WT", 1, "stone")
    assert rejected.status == "rejected" and rejected.value is None
