# normalized_plan.py — JSON tabanlı plan import (Milestone 1)
from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class SegmentIn(BaseModel):
    """Tek bir segment: başlangıç ve bitiş noktası; opsiyonel kalınlık."""

    x1: float
    y1: float
    x2: float
    y2: float
    thickness: float | None = None


class OriginIn(BaseModel):
    x: float = 0.0
    y: float = 0.0


class NormalizedPlan(BaseModel):
    """
    JSON import sonrası doğrulanmış plan.
    Sadece segment listesi + temel metadata (Milestone 1).
    """

    version: str = Field(default="v1", description="Şema sürümü")
    units: str = Field(default="mm", description="mm | cm | m")
    scale: float = Field(default=1.0, gt=0, description="Ölçek çarpanı")
    origin: OriginIn = Field(default_factory=OriginIn)
    segments: List[SegmentIn] = Field(..., min_length=1, description="En az bir segment gerekli")
    metadata: Dict[str, Any] | None = None

    model_config = {"extra": "forbid"}


def _validate_units(units: str) -> None:
    if units not in ("mm", "cm", "m"):
        raise ValueError(f"Geçersiz units: '{units}' (mm, cm, m olmalı)")


def import_plan_from_json(data: dict) -> NormalizedPlan:
    """
    JSON (dict) verisini doğrular ve NormalizedPlan döndürür.

    - Şema uyumsuzluğunda Pydantic ValidationError.
    - segments boş veya yoksa ValueError (fatal).
    - units mm/cm/m dışında ise ValueError.
    """
    if not data.get("segments"):
        raise ValueError("segments boş olamaz veya eksik")
    plan = NormalizedPlan.model_validate(data)
    _validate_units(plan.units)
    return plan
