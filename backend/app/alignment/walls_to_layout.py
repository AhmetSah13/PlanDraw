"""Prepare/Plan anlığındaki duvar segmentlerinden PrintableLayout üretir (hizalama önizlemesi için)."""

from __future__ import annotations

from app.layout_ir.ir_types import LineObject, PrintableLayout, SourceRef


def walls_list_to_printable_layout(walls: list[list[float]] | None) -> PrintableLayout:
    """
    walls: her satır [x1, y1, x2, y2] (metre, dünya koordinatı).
    """
    objs: list[LineObject] = []
    for i, w in enumerate(walls or []):
        if len(w) < 4:
            continue
        src = SourceRef(layer="walls", entity_type="segment", handle=str(i))
        objs.append(
            LineObject(
                x1=float(w[0]),
                y1=float(w[1]),
                x2=float(w[2]),
                y2=float(w[3]),
                source=src,
            )
        )
    return PrintableLayout(units="m", objects=tuple(objs), rejected=())
