from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.layout_ir.ir_types import LineObject, PolylineObject, PrintabilityReport, PrintableLayout, RejectedObject
from app.layout_ir.units import UnitsInfo


def layout_to_json_summary(
    layout: PrintableLayout, report: PrintabilityReport, *, units_info: UnitsInfo | None = None
) -> dict[str, Any]:
    """
    UI/CLI için küçük, deterministik bir özet JSON.
    IR'nin tamamını taşımak yerine sayımlar + sınırlı örnekler.
    """
    by_layer_supported: dict[str, int] = {}
    for obj in layout.objects:
        layer = obj.source.layer
        by_layer_supported[layer] = by_layer_supported.get(layer, 0) + 1

    by_reason_rejected: dict[str, int] = {}
    for r in layout.rejected:
        by_reason_rejected[r.reason] = by_reason_rejected.get(r.reason, 0) + 1

    # İlk birkaç rejection örneği (debug için)
    rejected_examples: list[dict[str, Any]] = []
    for r in layout.rejected[:20]:
        rejected_examples.append(
            {
                "reason": r.reason,
                "message": r.message,
                "tag": r.tag,
                "source": {
                    "layer": r.source.layer,
                    "entity_type": r.source.entity_type,
                    "handle": r.source.handle,
                },
            }
        )

    out: dict[str, Any] = {
        "layout": {
            "units": layout.units,
            "supported_object_count": len(layout.objects),
            "rejected_object_count": len(layout.rejected),
            "supported_by_layer": dict(sorted(by_layer_supported.items(), key=lambda kv: (-kv[1], kv[0]))),
            "rejected_by_reason": dict(sorted(by_reason_rejected.items(), key=lambda kv: (-kv[1], kv[0]))),
            "rejected_examples": rejected_examples,
        },
        "report": {
            "decision": report.decision,
            "supported_object_count": report.supported_object_count,
            "rejected_object_count": report.rejected_object_count,
            "drawn_length_m": report.drawn_length_m,
            "bounds_m": list(report.bounds_m) if report.bounds_m is not None else None,
            "short_segment_count": report.short_segment_count,
            "reasons": list(report.reasons),
            "recommendations": list(report.recommendations),
        },
    }

    if units_info is not None:
        out["units"] = {
            "detected_units": units_info.detected_units,
            "original_units_code": units_info.insunits_code,
            "applied_scale_to_world_m": units_info.applied_scale_to_world_m,
            "units_source": units_info.units_source,
        }

    return out

