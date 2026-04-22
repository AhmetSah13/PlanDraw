from __future__ import annotations

import math
from dataclasses import dataclass

from app.layout_ir.ir_types import LineObject, PolylineObject, PrintabilityReport, PrintableLayout


@dataclass(frozen=True)
class ValidationOptions:
    min_segment_length_m: float = 0.005
    warn_short_segment_count: int = 200
    fail_if_no_supported: bool = True


def _segment_length(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _accum_bounds(bounds: tuple[float, float, float, float] | None, p: tuple[float, float]) -> tuple[float, float, float, float]:
    if bounds is None:
        return (p[0], p[1], p[0], p[1])
    minx, miny, maxx, maxy = bounds
    return (min(minx, p[0]), min(miny, p[1]), max(maxx, p[0]), max(maxy, p[1]))


def validate_printable_layout(layout: PrintableLayout, *, options: ValidationOptions | None = None) -> PrintabilityReport:
    opts = options or ValidationOptions()

    supported = list(layout.objects)
    rejected = list(layout.rejected)

    bounds: tuple[float, float, float, float] | None = None
    drawn_length_m = 0.0
    short_segment_count = 0

    for obj in supported:
        if isinstance(obj, LineObject):
            a = (obj.x1, obj.y1)
            b = (obj.x2, obj.y2)
            bounds = _accum_bounds(bounds, a)
            bounds = _accum_bounds(bounds, b)
            L = _segment_length(a, b)
            drawn_length_m += L
            if L < opts.min_segment_length_m:
                short_segment_count += 1
        elif isinstance(obj, PolylineObject):
            pts = list(obj.points)
            if not pts:
                continue
            for p in pts:
                bounds = _accum_bounds(bounds, p)
            for i in range(len(pts) - 1):
                L = _segment_length(pts[i], pts[i + 1])
                drawn_length_m += L
                if L < opts.min_segment_length_m:
                    short_segment_count += 1
            if obj.closed and len(pts) >= 3:
                L = _segment_length(pts[-1], pts[0])
                drawn_length_m += L
                if L < opts.min_segment_length_m:
                    short_segment_count += 1

    reasons: list[str] = []
    recommendations: list[str] = []

    if opts.fail_if_no_supported and len(supported) == 0:
        decision = "FAIL"
        reasons.append("Çizilebilir obje yok (supported_object_count=0).")
        if rejected:
            recommendations.append("Katman filtrelerini ve desteklenen entity kapsamını kontrol edin.")
        else:
            recommendations.append("Girdi boş olabilir veya tüm entity'ler elenmiş olabilir.")
        return PrintabilityReport(
            decision=decision,
            supported_object_count=0,
            rejected_object_count=len(rejected),
            drawn_length_m=0.0,
            bounds_m=bounds,
            short_segment_count=short_segment_count,
            reasons=tuple(reasons),
            recommendations=tuple(recommendations),
        )

    decision = "PASS"

    if short_segment_count > 0:
        reasons.append(f"Kısa segment sayısı: {short_segment_count} (min={opts.min_segment_length_m} m)")
        if short_segment_count >= opts.warn_short_segment_count:
            decision = "WARN"
            recommendations.append("Kısa segmentleri azaltmak için tolerans/filtreleme uygulayın.")

    if len(rejected) > 0:
        # İlk sürümde reddedilen entity'ler beklenen bir durum; ancak oran yüksekse WARN.
        rejected_ratio = len(rejected) / max(1, (len(rejected) + len(supported)))
        if rejected_ratio >= 0.7:
            decision = "WARN" if decision != "FAIL" else decision
            reasons.append(f"Reddedilen entity oranı yüksek: {rejected_ratio:.0%}")
            recommendations.append("Katman seçimi veya kapsam (entity türleri) gözden geçirilmeli.")

    return PrintabilityReport(
        decision=decision,
        supported_object_count=len(supported),
        rejected_object_count=len(rejected),
        drawn_length_m=float(drawn_length_m),
        bounds_m=bounds,
        short_segment_count=int(short_segment_count),
        reasons=tuple(reasons),
        recommendations=tuple(recommendations),
    )

