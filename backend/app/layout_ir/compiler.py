from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, overload

from app.layout_ir.ir_types import (
    LineObject,
    PolylineObject,
    PrintableLayout,
    RejectedObject,
    SourceRef,
)
from app.layout_ir.units import UnitsInfo, resolve_units_info

try:
    from ezdxf import recover  # type: ignore
except Exception:  # pragma: no cover
    recover = None  # type: ignore


@dataclass(frozen=True)
class CompileOptions:
    """
    Minimum kapsam: LINE + (bulge=0) LWPOLYLINE + düz POLYLINE.

    - explode/flatten yok
    - INSERT desteklenmez
    """

    layer_whitelist: list[str] | None = None
    layer_blacklist: list[str] | None = None
    # None ise DXF $INSUNITS ile otomatik ölçek çözülür (başarısızsa 1.0 fallback).
    # float verilirse explicit kabul edilir ve DXF units bunu override etmez.
    scale_to_world_m: float | None = None
    origin_m: tuple[float, float] = (0.0, 0.0)


def _layer_allowed(layer: str, opts: CompileOptions) -> bool:
    if opts.layer_whitelist is not None and layer not in opts.layer_whitelist:
        return False
    if opts.layer_blacklist is not None and layer in opts.layer_blacklist:
        return False
    return True


def _src_ref(e: Any) -> SourceRef:
    layer = getattr(getattr(e, "dxf", None), "layer", "0") or "0"
    etype = getattr(e, "dxftype", lambda: "UNKNOWN")()
    handle = getattr(getattr(e, "dxf", None), "handle", None)
    return SourceRef(layer=str(layer), entity_type=str(etype), handle=str(handle) if handle else None)


def _to_world(x: float, y: float, *, scale_to_world_m: float, origin_m: tuple[float, float]) -> tuple[float, float]:
    return (float(x) * scale_to_world_m + origin_m[0], float(y) * scale_to_world_m + origin_m[1])


def _compile_line(
    e: Any, *, scale_to_world_m: float, origin_m: tuple[float, float]
) -> LineObject | RejectedObject:
    src = _src_ref(e)
    try:
        start = e.dxf.start
        end = e.dxf.end
        x1, y1 = _to_world(float(start.x), float(start.y), scale_to_world_m=scale_to_world_m, origin_m=origin_m)
        x2, y2 = _to_world(float(end.x), float(end.y), scale_to_world_m=scale_to_world_m, origin_m=origin_m)
        return LineObject(x1=x1, y1=y1, x2=x2, y2=y2, source=src)
    except Exception as ex:
        return RejectedObject(
            reason="invalid_geometry",
            source=src,
            message=f"LINE okunamadı: {ex!s}",
            tag="unsupported_entity",
        )


def _compile_lwpolyline(
    e: Any, *, scale_to_world_m: float, origin_m: tuple[float, float]
) -> PolylineObject | RejectedObject:
    src = _src_ref(e)
    try:
        # ezdxf: LWPOLYLINE.get_points() -> (x, y, start_width, end_width, bulge) gibi tuple’lar dönebilir.
        pts = []
        for p in e.get_points():  # type: ignore[attr-defined]
            x = float(p[0])
            y = float(p[1])
            bulge = float(p[4]) if len(p) >= 5 else 0.0
            if abs(bulge) > 1e-12:
                return RejectedObject(
                    reason="unsupported_polyline",
                    source=src,
                    message="LWPOLYLINE bulge!=0 (eğri) desteklenmiyor (Phase B kapsamı dışı).",
                    tag="unsupported_entity",
                )
            pts.append(_to_world(x, y, scale_to_world_m=scale_to_world_m, origin_m=origin_m))

        if len(pts) < 2:
            return RejectedObject(
                reason="invalid_geometry",
                source=src,
                message="LWPOLYLINE için nokta sayısı < 2",
                tag="unsupported_entity",
            )
        closed = bool(getattr(getattr(e, "dxf", None), "closed", False))
        return PolylineObject(points=tuple(pts), closed=closed, source=src)
    except Exception as ex:
        return RejectedObject(
            reason="invalid_geometry",
            source=src,
            message=f"LWPOLYLINE okunamadı: {ex!s}",
            tag="unsupported_entity",
        )


def _compile_polyline(
    e: Any, *, scale_to_world_m: float, origin_m: tuple[float, float]
) -> PolylineObject | RejectedObject:
    src = _src_ref(e)
    try:
        pts = []
        for v in e.vertices():  # type: ignore[attr-defined]
            loc = getattr(v, "dxf", None)
            if loc is None:
                continue
            # POLYLINE+VERTEX: bulge bazen vertex üzerinde gelir.
            bulge = float(getattr(loc, "bulge", 0.0) or 0.0)
            if abs(bulge) > 1e-12:
                return RejectedObject(
                    reason="unsupported_polyline",
                    source=src,
                    message="POLYLINE bulge!=0 (eğri) desteklenmiyor (Phase B kapsamı dışı).",
                    tag="unsupported_entity",
                )
            x = float(getattr(loc, "x", 0.0))
            y = float(getattr(loc, "y", 0.0))
            pts.append(_to_world(x, y, scale_to_world_m=scale_to_world_m, origin_m=origin_m))

        if len(pts) < 2:
            return RejectedObject(
                reason="invalid_geometry",
                source=src,
                message="POLYLINE için nokta sayısı < 2",
                tag="unsupported_entity",
            )
        closed = bool(getattr(getattr(e, "dxf", None), "closed", False))
        return PolylineObject(points=tuple(pts), closed=closed, source=src)
    except Exception as ex:
        return RejectedObject(
            reason="invalid_geometry",
            source=src,
            message=f"POLYLINE okunamadı: {ex!s}",
            tag="unsupported_entity",
        )


@overload
def compile_dxf_to_printable_layout(
    dxf_path: str,
    *,
    options: CompileOptions | None = None,
    tag_supported: Literal["geometry"] = "geometry",
) -> PrintableLayout: ...


@overload
def compile_dxf_to_printable_layout(
    dxf_path: str,
    *,
    options: CompileOptions | None = None,
    tag_supported: Literal["geometry"] = "geometry",
    return_units_info: Literal[True],
) -> tuple[PrintableLayout, UnitsInfo]: ...


def compile_dxf_to_printable_layout(
    dxf_path: str,
    *,
    options: CompileOptions | None = None,
    tag_supported: Literal["geometry"] = "geometry",
    return_units_info: bool = False,
) -> PrintableLayout | tuple[PrintableLayout, UnitsInfo]:
    """
    Phase A+B giriş noktası: DXF -> PrintableLayout IR.

    - INSERT/BLOCK patlatma yok: INSERT gelirse reddedilir.
    - ARC/SPLINE/HATCH/TEXT/... reddedilir ve raporlanır.
    """
    if recover is None:
        raise RuntimeError("ezdxf yok: DXF -> PrintableLayoutIR için ezdxf gerekli")

    opts = options or CompileOptions()
    doc, _auditor = recover.readfile(dxf_path)  # type: ignore[call-arg]
    msp = doc.modelspace()

    units_info = resolve_units_info(doc=doc, explicit_scale_to_world_m=opts.scale_to_world_m)
    applied_scale = units_info.applied_scale_to_world_m
    origin_m = opts.origin_m

    supported: list[LineObject | PolylineObject] = []
    rejected: list[RejectedObject] = []

    for e in list(msp):
        src = _src_ref(e)
        layer = src.layer

        if not _layer_allowed(layer, opts):
            rejected.append(
                RejectedObject(
                    reason="ignored_layer",
                    source=src,
                    message="Katman filtrelendi (whitelist/blacklist).",
                    tag="ignored_layer",
                )
            )
            continue

        etype = src.entity_type.upper()

        if etype == "LINE":
            r = _compile_line(e, scale_to_world_m=applied_scale, origin_m=origin_m)
        elif etype == "LWPOLYLINE":
            r = _compile_lwpolyline(e, scale_to_world_m=applied_scale, origin_m=origin_m)
        elif etype == "POLYLINE":
            r = _compile_polyline(e, scale_to_world_m=applied_scale, origin_m=origin_m)
        elif etype == "INSERT":
            r = RejectedObject(
                reason="unsupported_insert",
                source=src,
                message="INSERT/BLOCK desteklenmiyor (Phase B kapsamı dışı; explode yok).",
                tag="unsupported_entity",
            )
        else:
            r = RejectedObject(
                reason="unsupported_entity",
                source=src,
                message=f"DXF entity desteklenmiyor: {etype}",
                tag="unsupported_entity",
            )

        if isinstance(r, RejectedObject):
            rejected.append(r)
        else:
            # tag şu an minimal; ileride semantik zenginleştirilecek
            if isinstance(r, LineObject):
                supported.append(LineObject(r.x1, r.y1, r.x2, r.y2, r.source, tag=tag_supported))
            else:
                supported.append(PolylineObject(r.points, r.closed, r.source, tag=tag_supported))

    layout = PrintableLayout(objects=tuple(supported), rejected=tuple(rejected))
    if return_units_info:
        return (layout, units_info)
    return layout

