from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

try:
    import ezdxf
    from ezdxf.entities import DXFGraphic
    from ezdxf.path import make_path
except Exception:  # pragma: no cover
    ezdxf = None  # type: ignore
    DXFGraphic = object  # type: ignore
    make_path = None  # type: ignore

from app.normalization.normalized_plan import SegmentIn


@dataclass(frozen=True)
class DiscretizeConfig:
    tolerance_m: float = 0.005  # metre
    max_segments: int = 15000
    drop_zero_length_eps: float = 1e-12


def _dist(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _segments_from_polyline_points(
    points: List[Tuple[float, float]],
    *,
    cfg: DiscretizeConfig,
) -> List[SegmentIn]:
    out: List[SegmentIn] = []
    for i in range(len(points) - 1):
        a = points[i]
        b = points[i + 1]
        if _dist(a, b) <= cfg.drop_zero_length_eps:
            continue
        out.append(SegmentIn(x1=a[0], y1=a[1], x2=b[0], y2=b[1]))
    return out


def discretize_entity_to_segments(
    e: "DXFGraphic",
    *,
    cfg: DiscretizeConfig,
    scale_to_world_m: float,
    origin_m: Tuple[float, float],
) -> Tuple[List[SegmentIn], List[Dict[str, Any]], int]:
    """
    Bir entity'i segmente çevirir.
    Dönüş: (segments, warnings, discretized_count)
    discretized_count: ARC/CIRCLE/SPLINE/bulge gibi eğri kaynaklı ise 1, değilse 0.
    """
    warnings: List[Dict[str, Any]] = []
    layer = getattr(getattr(e, "dxf", None), "layer", "0") or "0"
    t = getattr(e, "dxftype", lambda: "")()

    # LINE -> direkt
    if t == "LINE":
        start = e.dxf.start  # type: ignore[attr-defined]
        end = e.dxf.end  # type: ignore[attr-defined]
        a = (float(start.x) * scale_to_world_m + origin_m[0], float(start.y) * scale_to_world_m + origin_m[1])
        b = (float(end.x) * scale_to_world_m + origin_m[0], float(end.y) * scale_to_world_m + origin_m[1])
        return _segments_from_polyline_points([a, b], cfg=cfg), warnings, 0

    # Diğer çoğu şey: ezdxf.path.make_path() + Path.flattening(distance)
    if make_path is None:
        warnings.append(
            {
                "code": "EZDXF_NOT_AVAILABLE",
                "type": t,
                "layer": layer,
                "message": "ezdxf yüklü değil; eğriler/bloklar işlenemiyor.",
                "user_action": "Sunucuda ezdxf kurun (requirements.txt).",
            }
        )
        return [], warnings, 0

    try:
        p = make_path(e)  # type: ignore[misc]
    except Exception as ex:
        warnings.append(
            {
                "code": "EZDXF_MAKE_PATH_FAIL",
                "type": t,
                "layer": layer,
                "message": f"make_path hatası: {ex!s}",
                "user_action": "Dosyayı CAD'de temizleyip tekrar deneyin.",
            }
        )
        return [], warnings, 0

    pts: List[Tuple[float, float]] = []
    try:
        for v in p.flattening(distance=float(cfg.tolerance_m)):  # type: ignore[attr-defined]
            pts.append(
                (
                    float(v.x) * scale_to_world_m + origin_m[0],
                    float(v.y) * scale_to_world_m + origin_m[1],
                )
            )
            if len(pts) > cfg.max_segments + 5:
                warnings.append(
                    {
                        "code": "DISCRETIZE_TOO_MANY_POINTS",
                        "type": t,
                        "layer": layer,
                        "message": f"Çok fazla nokta üretildi (>{cfg.max_segments}).",
                        "user_action": "Toleransı artırın veya segment bütçesi uygulayın.",
                    }
                )
                break
    except Exception as ex:
        warnings.append(
            {
                "code": "EZDXF_FLATTEN_FAIL",
                "type": t,
                "layer": layer,
                "message": f"flattening hatası: {ex!s}",
                "user_action": "Dosyayı CAD'de sadeleştirip tekrar deneyin.",
            }
        )
        return [], warnings, 0

    if len(pts) < 2:
        return [], warnings, 0

    segs = _segments_from_polyline_points(pts, cfg=cfg)
    discretized = 1 if t in ("ARC", "CIRCLE", "SPLINE", "LWPOLYLINE", "POLYLINE", "ELLIPSE", "HELIX") else 0
    return segs, warnings, discretized

