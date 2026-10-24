"""Harmonisation of heterogeneous clinical and lab records.

Two concerns live here: converting measurements to canonical units, and mapping
site-local codes onto shared vocabularies (LOINC for observations). The tables
are intentionally small and explicit; production mappings are loaded from the
curated zone and versioned with the dataset that uses them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sciagent.core.errors import ValidationFailed

# canonical unit per quantity, and factors/offsets to reach it: canonical = v * a + b
CANONICAL_UNITS: dict[str, str] = {
    "temperature": "Cel",
    "glucose": "mmol/L",
    "creatinine": "umol/L",
    "weight": "kg",
    "height": "cm",
    "heart_rate": "/min",
    "hemoglobin": "g/dL",
}
CONVERSIONS: dict[tuple[str, str], tuple[float, float]] = {
    ("temperature", "[degF]"): (5 / 9, -32 * 5 / 9),
    ("temperature", "K"): (1.0, -273.15),
    ("glucose", "mg/dL"): (1 / 18.016, 0.0),
    ("creatinine", "mg/dL"): (88.42, 0.0),
    ("weight", "[lb_av]"): (0.45359237, 0.0),
    ("weight", "g"): (0.001, 0.0),
    ("height", "[in_i]"): (2.54, 0.0),
    ("height", "m"): (100.0, 0.0),
    ("hemoglobin", "g/L"): (0.1, 0.0),
    ("hemoglobin", "mmol/L"): (1.611, 0.0),
}
UNIT_ALIASES: dict[str, str] = {
    "c": "Cel",
    "°c": "Cel",
    "celsius": "Cel",
    "f": "[degF]",
    "°f": "[degF]",
    "fahrenheit": "[degF]",
    "kelvin": "K",
    "lb": "[lb_av]",
    "lbs": "[lb_av]",
    "in": "[in_i]",
    "inch": "[in_i]",
    "bpm": "/min",
    "beats/min": "/min",
    "mg/dl": "mg/dL",
    "mmol/l": "mmol/L",
    "umol/l": "umol/L",
    "µmol/l": "umol/L",
    "g/dl": "g/dL",
    "g/l": "g/L",
}
LOCAL_TO_LOINC: dict[str, tuple[str, str, str]] = {
    # local code -> (LOINC, display, quantity)
    "TEMP": ("8310-5", "Body temperature", "temperature"),
    "BT": ("8310-5", "Body temperature", "temperature"),
    "GLU": ("2345-7", "Glucose [Mass or Moles/volume] in Serum or Plasma", "glucose"),
    "GLUC": ("2345-7", "Glucose [Mass or Moles/volume] in Serum or Plasma", "glucose"),
    "CREA": ("2160-0", "Creatinine [Mass or Moles/volume] in Serum or Plasma", "creatinine"),
    "WT": ("29463-7", "Body weight", "weight"),
    "HT": ("8302-2", "Body height", "height"),
    "HR": ("8867-4", "Heart rate", "heart_rate"),
    "HGB": ("718-7", "Hemoglobin [Mass/volume] in Blood", "hemoglobin"),
}


def normalise_unit(unit: str) -> str:
    return UNIT_ALIASES.get(unit.strip().lower(), unit.strip())


def to_canonical(quantity: str, value: float, unit: str) -> tuple[float, str]:
    if quantity not in CANONICAL_UNITS:
        raise ValidationFailed("unknown quantity", quantity=quantity)
    target = CANONICAL_UNITS[quantity]
    unit = normalise_unit(unit)
    if unit == target:
        return float(value), target
    factor = CONVERSIONS.get((quantity, unit))
    if factor is None:
        raise ValidationFailed("no conversion", quantity=quantity, unit=unit)
    a, b = factor
    return round(float(value) * a + b, 4), target


@dataclass(frozen=True)
class HarmonisedRecord:
    source_code: str
    loinc: str | None
    display: str | None
    value: float | None
    unit: str | None
    status: str
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def harmonise_record(code: str, value: float, unit: str) -> HarmonisedRecord:
    mapping = LOCAL_TO_LOINC.get(code.strip().upper())
    if mapping is None:
        return HarmonisedRecord(code, None, None, None, None, "unmapped", "no LOINC mapping")
    loinc, display, quantity = mapping
    try:
        v, u = to_canonical(quantity, value, unit)
    except ValidationFailed as exc:
        return HarmonisedRecord(code, loinc, display, None, None, "rejected", exc.message)
    return HarmonisedRecord(code, loinc, display, v, u, "ok")
