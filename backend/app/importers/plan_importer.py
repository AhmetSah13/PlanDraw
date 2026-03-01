# plan_importer.py — NormalizedPlan -> Plan / plan_text / walls (Milestone 3)
from __future__ import annotations

from typing import List

from app.core.plan_module import Plan, Wall

from app.normalization.normalized_plan import NormalizedPlan


def normalized_to_plan(normalized: NormalizedPlan) -> Plan:
    """NormalizedPlan segment listesini plan_module.Plan (Wall listesi) olarak döndürür."""
    walls: List[Wall] = []
    for seg in normalized.segments:
        walls.append(Wall(x1=seg.x1, y1=seg.y1, x2=seg.x2, y2=seg.y2))
    return Plan(walls=walls)


def normalized_to_plan_text(normalized: NormalizedPlan) -> str:
    """Her segment için 'LINE x1 y1 x2 y2' satırı; load_plan_from_string ile parse edilebilir."""
    lines = []
    for seg in normalized.segments:
        lines.append(f"LINE {seg.x1} {seg.y1} {seg.x2} {seg.y2}")
    return "\n".join(lines)


def normalized_to_walls_array(normalized: NormalizedPlan) -> List[List[float]]:
    """[[x1, y1, x2, y2], ...] formatında duvar listesi (/api/compile_plan ile aynı format)."""
    return [
        [seg.x1, seg.y1, seg.x2, seg.y2]
        for seg in normalized.segments
    ]
