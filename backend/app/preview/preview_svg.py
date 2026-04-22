from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Union

from app.alignment.alignment_model import AlignedLayout
from app.layout_ir.ir_types import LineObject, PolylineObject, PrintableLayout


@dataclass(frozen=True)
class SvgPreviewOptions:
    stroke_width_px: float = 1.0
    padding_px: float = 10.0
    # Basit renklendirme: layer bazlı değil; tip bazlı.
    line_color: str = "#1f77b4"
    polyline_color: str = "#2ca02c"
    # None ise varsayılan başlık (supported/rejected sayıları)
    title_override: str | None = None


LayoutLike = Union[PrintableLayout, AlignedLayout]


def _bounds_of_layout(layout: LayoutLike) -> tuple[float, float, float, float] | None:
    minx = miny = maxx = maxy = 0.0
    have = False
    for obj in layout.objects:
        if isinstance(obj, LineObject):
            pts = [(obj.x1, obj.y1), (obj.x2, obj.y2)]
        else:
            pts = list(obj.points)
        for x, y in pts:
            if not have:
                minx = maxx = x
                miny = maxy = y
                have = True
            else:
                minx = min(minx, x)
                miny = min(miny, y)
                maxx = max(maxx, x)
                maxy = max(maxy, y)
    if not have:
        return None
    return (minx, miny, maxx, maxy)


def render_pre_alignment_svg(layout: LayoutLike, *, options: SvgPreviewOptions | None = None) -> str:
    """
    Pre-alignment preview: IR geometry'yi basit bir SVG olarak verir.
    Ölçek: 1:1 metre -> SVG koordinatı (doğrudan). Görsel amaçlıdır.
    """
    opts = options or SvgPreviewOptions()
    b = _bounds_of_layout(layout)
    if b is None:
        # Boş SVG
        return (
            "<svg xmlns='http://www.w3.org/2000/svg' width='200' height='100'>"
            "<text x='10' y='20' font-size='12'>Boş layout</text>"
            "</svg>"
        )
    minx, miny, maxx, maxy = b
    w = maxx - minx
    h = maxy - miny
    if w <= 1e-12:
        w = 1.0
    if h <= 1e-12:
        h = 1.0

    # SVG y ekseni aşağı; görsel için y'yi ters çevirelim.
    # Dünya: (minx,miny) -> SVG padding ile; y tersine çevrilir.
    pad = opts.padding_px
    view_w = w + 2 * pad
    view_h = h + 2 * pad

    def tx(x: float) -> float:
        return (x - minx) + pad

    def ty(y: float) -> float:
        return (maxy - y) + pad

    parts: list[str] = []
    parts.append(
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {view_w:.6f} {view_h:.6f}'>"
    )
    parts.append("<rect x='0' y='0' width='100%' height='100%' fill='white'/>")

    sw = opts.stroke_width_px

    for obj in layout.objects:
        if isinstance(obj, LineObject):
            x1, y1 = tx(obj.x1), ty(obj.y1)
            x2, y2 = tx(obj.x2), ty(obj.y2)
            parts.append(
                f"<line x1='{x1:.6f}' y1='{y1:.6f}' x2='{x2:.6f}' y2='{y2:.6f}' "
                f"stroke='{opts.line_color}' stroke-width='{sw}' />"
            )
        elif isinstance(obj, PolylineObject):
            pts = obj.points
            if len(pts) < 2:
                continue
            coords = " ".join(f"{tx(x):.6f},{ty(y):.6f}" for x, y in pts)
            if obj.closed:
                parts.append(
                    f"<polygon points='{coords}' fill='none' stroke='{opts.polyline_color}' stroke-width='{sw}' />"
                )
            else:
                parts.append(
                    f"<polyline points='{coords}' fill='none' stroke='{opts.polyline_color}' stroke-width='{sw}' />"
                )

    # Basit başlık
    if opts.title_override is not None:
        title = html.escape(opts.title_override)
    else:
        title = html.escape(f"pre_alignment supported={len(layout.objects)} rejected={len(layout.rejected)}")
    parts.append(f"<text x='{pad}' y='{pad}' font-size='10' fill='#444'>{title}</text>")
    parts.append("</svg>")
    return "".join(parts)


def render_post_alignment_svg(layout: AlignedLayout, *, options: SvgPreviewOptions | None = None) -> str:
    """
    Saha koordinatlarına hizalanmış layout için SVG (pre ile aynı çizim mantığı, ayrı artifact adı için).
    """
    base = options or SvgPreviewOptions()
    from dataclasses import replace

    title = f"post_alignment supported={len(layout.objects)} rejected={len(layout.rejected)}"
    opts2 = replace(base, title_override=title)
    return render_pre_alignment_svg(layout, options=opts2)

