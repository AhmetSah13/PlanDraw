from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence


@dataclass(frozen=True)
class SourceRef:
    """Kaynak DXF entity izlenebilirliği (traceability) için minimal referans."""

    layer: str
    entity_type: str
    handle: str | None = None


RejectionReason = Literal[
    "unsupported_entity",
    "unsupported_polyline",
    "unsupported_insert",
    "ignored_layer",
    "invalid_geometry",
]


@dataclass(frozen=True)
class RejectedObject:
    reason: RejectionReason
    source: SourceRef
    message: str
    tag: Literal["geometry", "ignored_layer", "unsupported_entity"] = "unsupported_entity"


@dataclass(frozen=True)
class LineObject:
    x1: float
    y1: float
    x2: float
    y2: float
    source: SourceRef
    tag: Literal["geometry"] = "geometry"


@dataclass(frozen=True)
class PolylineObject:
    """Basit polyline: ardışık noktalar listesi (kapalı olabilir)."""

    points: tuple[tuple[float, float], ...]
    closed: bool
    source: SourceRef
    tag: Literal["geometry"] = "geometry"


@dataclass(frozen=True)
class PrintableLayout:
    """Çizilebilir niyetin (print intent) minimal ara temsili."""

    units: Literal["m"] = "m"
    objects: tuple[LineObject | PolylineObject, ...] = ()
    rejected: tuple[RejectedObject, ...] = ()


Decision = Literal["PASS", "WARN", "FAIL"]


@dataclass(frozen=True)
class PrintabilityReport:
    decision: Decision
    supported_object_count: int
    rejected_object_count: int
    drawn_length_m: float
    bounds_m: tuple[float, float, float, float] | None
    short_segment_count: int
    reasons: tuple[str, ...]
    recommendations: tuple[str, ...]


def iter_object_points(obj: LineObject | PolylineObject) -> Sequence[tuple[float, float]]:
    if isinstance(obj, LineObject):
        return ((obj.x1, obj.y1), (obj.x2, obj.y2))
    return obj.points

