from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

from app.layout_ir.ir_types import LineObject, PolylineObject, RejectedObject


@dataclass(frozen=True)
class ControlPoint:
    """CAD (layout) koordinatı ile saha (site) koordinatı eşlemesi."""

    cad_x: float
    cad_y: float
    site_x: float
    site_y: float
    label: str | None = None
    weight: float | None = None


@dataclass(frozen=True)
class RigidTransform2D:
    """
    2D rijit dönüşüm: site = R * cad + t
    R = [[cos(theta), -sin(theta)], [sin(theta), cos(theta)]]
    """

    theta_rad: float
    tx_m: float
    ty_m: float

    def apply_xy(self, x: float, y: float) -> tuple[float, float]:
        c = math.cos(self.theta_rad)
        s = math.sin(self.theta_rad)
        return (c * x - s * y + self.tx_m, s * x + c * y + self.ty_m)


TransformType = Literal["rigid_2d"]


@dataclass(frozen=True)
class AlignmentReport:
    """Hizalama kalitesi ve güvenlik kapısı (execution öncesi engelleme için)."""

    transform_type: TransformType
    point_count: int
    residual_mean_m: float
    residual_max_m: float
    tolerance_m: float
    blocked: bool
    transform: RigidTransform2D
    reasons: tuple[str, ...]
    notes: tuple[str, ...]


@dataclass(frozen=True)
class AlignedLayout:
    """Saha koordinatlarında (metre) çizilebilir layout (PrintableLayout ile aynı geometri şeması)."""

    units: Literal["m"] = "m"
    objects: tuple[LineObject | PolylineObject, ...] = ()
    rejected: tuple[RejectedObject, ...] = ()


def alignment_report_to_jsonable(report: AlignmentReport) -> dict[str, Any]:
    """CLI/JSON artifact için deterministik sözlük."""
    return {
        "transform_type": report.transform_type,
        "point_count": report.point_count,
        "residual_mean_m": report.residual_mean_m,
        "residual_max_m": report.residual_max_m,
        "tolerance_m": report.tolerance_m,
        "blocked": report.blocked,
        "transform": {
            "theta_rad": report.transform.theta_rad,
            "theta_deg": math.degrees(report.transform.theta_rad),
            "tx_m": report.transform.tx_m,
            "ty_m": report.transform.ty_m,
        },
        "reasons": list(report.reasons),
        "notes": list(report.notes),
    }
