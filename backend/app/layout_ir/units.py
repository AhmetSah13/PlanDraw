from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


UnitsSource = Literal["manual", "dxf_header", "fallback_default"]


@dataclass(frozen=True)
class UnitsInfo:
    detected_units: str | None
    insunits_code: int | None
    applied_scale_to_world_m: float
    units_source: UnitsSource


_INSUNITS_CODE_TO_UNIT: dict[int, str] = {
    0: "unitless",
    1: "inches",
    2: "feet",
    4: "millimeters",
    5: "centimeters",
    6: "meters",
}

_UNIT_TO_METERS: dict[str, float] = {
    "unitless": 1.0,
    "inches": 0.0254,
    "feet": 0.3048,
    "millimeters": 0.001,
    "centimeters": 0.01,
    "meters": 1.0,
}


def detect_units_info_from_dxf_doc(doc: Any) -> tuple[str | None, int | None, float | None]:
    """
    DXF dokümanından birim tespiti yapar.

    Dönüş:
    - detected_units: örn. "millimeters" (yoksa None)
    - insunits_code: DXF $INSUNITS kodu (yoksa None)
    - meters_per_unit: 1 birimin kaç metre olduğu (harita dışıysa None)
    """
    try:
        header = getattr(doc, "header", None)
        if header is None:
            return (None, None, None)
        raw = header.get("$INSUNITS", None)
    except Exception:
        return (None, None, None)

    if raw is None:
        return (None, None, None)

    try:
        code = int(raw)
    except Exception:
        return (None, None, None)

    unit = _INSUNITS_CODE_TO_UNIT.get(code)
    if unit is None:
        return (None, code, None)

    meters_per_unit = _UNIT_TO_METERS.get(unit)
    if meters_per_unit is None:
        return (unit, code, None)
    return (unit, code, float(meters_per_unit))


def resolve_units_info(*, doc: Any, explicit_scale_to_world_m: float | None) -> UnitsInfo:
    """
    Karar mantığı:
    - explicit_scale_to_world_m verilmişse onu kullan, DXF'den override etme
    - explicit yoksa DXF $INSUNITS ile auto-detect dene
    - auto-detect başarısızsa 1.0 fallback uygula
    """
    if explicit_scale_to_world_m is not None:
        detected_units, insunits_code, _meters_per_unit = detect_units_info_from_dxf_doc(doc)
        return UnitsInfo(
            detected_units=detected_units,
            insunits_code=insunits_code,
            applied_scale_to_world_m=float(explicit_scale_to_world_m),
            units_source="manual",
        )

    detected_units, insunits_code, meters_per_unit = detect_units_info_from_dxf_doc(doc)
    if meters_per_unit is None:
        return UnitsInfo(
            detected_units=detected_units,
            insunits_code=insunits_code,
            applied_scale_to_world_m=1.0,
            units_source="fallback_default",
        )

    return UnitsInfo(
        detected_units=detected_units,
        insunits_code=insunits_code,
        applied_scale_to_world_m=float(meters_per_unit),
        units_source="dxf_header",
    )

