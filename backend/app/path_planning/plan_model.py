from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.layout_ir.ir_types import SourceRef

StrokeKind = Literal["line", "polyline"]


@dataclass(frozen=True)
class PlannedStroke:
    """Tek çizilebilir hat (kalem aşağıda takip edilen nokta dizisi)."""

    kind: StrokeKind
    points: tuple[tuple[float, float], ...]
    source: SourceRef
    stroke_length_m: float
    travel_from_previous_m: float
    reversed: bool
    closed: bool


@dataclass(frozen=True)
class PlannedPath:
    """Sıralı stroke listesi (robot komutu değil, plan artifact)."""

    strokes: tuple[PlannedStroke, ...]


@dataclass(frozen=True)
class PathMetrics:
    stroke_count: int
    drawing_length_m: float
    travel_length_m: float
    pen_lifts: int
    skipped_short_segment_count: int
    total_points: int
    strategy: str
    notes: tuple[str, ...]


@dataclass(frozen=True)
class PathPlanningReport:
    metrics: PathMetrics
