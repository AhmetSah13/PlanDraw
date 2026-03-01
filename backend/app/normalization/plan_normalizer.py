# plan_normalizer.py — NormalizedPlan segment normalizasyonu (Milestone 2)
from __future__ import annotations

import math
from typing import List, Tuple, Optional, Literal

from pydantic import BaseModel, Field

from app.normalization.normalized_plan import NormalizedPlan, SegmentIn

EPS = 1e-12


def _dist(p: Tuple[float, float], q: Tuple[float, float]) -> float:
    return math.hypot(q[0] - p[0], q[1] - p[1])


def _seg_len(seg: SegmentIn) -> float:
    return _dist((seg.x1, seg.y1), (seg.x2, seg.y2))


def _unit_dir(seg: SegmentIn) -> Tuple[float, float]:
    """Yön vektörü (birim); uzunluk ~0 ise (0,0)."""
    L = _seg_len(seg)
    if L < EPS:
        return (0.0, 0.0)
    return ((seg.x2 - seg.x1) / L, (seg.y2 - seg.y1) / L)


def _angle_deg(u: Tuple[float, float], v: Tuple[float, float]) -> float:
    """İki yön vektörü arasındaki açı (derece). 0 = aynı yön, 180 = zıt."""
    dot = u[0] * v[0] + u[1] * v[1]
    dot = max(-1.0, min(1.0, dot))
    return math.degrees(math.acos(dot))


def _points_close(
    p: Tuple[float, float],
    q: Tuple[float, float],
    tol: float,
) -> bool:
    return _dist(p, q) <= tol


class NormalizeOptions(BaseModel):
    merge_endpoints_tol: float = Field(default=1e-6, ge=0)
    merge_collinear: bool = True
    collinear_angle_eps_deg: float = Field(default=1.0, ge=0, le=180)
    drop_zero_length: bool = True
    min_segment_len: float = 0.0
    segment_budget: Optional[int] = None
    budget_strategy: Literal["keep_longest", "error"] = "keep_longest"
    recenter: bool = False
    recenter_mode: Literal["center", "min_corner"] = "center"


def _thickness_eq(a: float | None, b: float | None) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(a - b) < EPS


def normalize_plan(
    plan: NormalizedPlan,
    options: NormalizeOptions | None = None,
) -> Tuple[NormalizedPlan, List[str]]:
    """
    Segment listesini güvenli ve deterministik şekilde sadeleştirir.
    Döner: (normalized_plan, warnings).
    """
    opts = options or NormalizeOptions()
    warnings: List[str] = []
    segments: List[SegmentIn] = []

    # A) Zero-length drop
    for i, seg in enumerate(plan.segments):
        L = _seg_len(seg)
        if L <= opts.merge_endpoints_tol and opts.drop_zero_length:
            warnings.append(f"Dropped zero-length segment {i}")
            continue
        segments.append(seg)

    if not segments:
        raise ValueError("Normalizasyon sonrası segment kalmadı (hepsi sıfır uzunluktu)")

    # B) Collinear merge: ardışık ve uç paylaşan segmentleri birleştir
    max_merges = 1000
    total_merges = 0

    while total_merges < max_merges and opts.merge_collinear:
        merged_any = False
        new_segments: List[SegmentIn] = []
        i = 0
        while i < len(segments):
            if i + 1 >= len(segments):
                new_segments.append(segments[i])
                i += 1
                continue
            s1, s2 = segments[i], segments[i + 1]
            p1a, p1b = (s1.x1, s1.y1), (s1.x2, s1.y2)
            p2a, p2b = (s2.x1, s2.y1), (s2.x2, s2.y2)
            tol = opts.merge_endpoints_tol

            # Ortak uç var mı?
            shared = None
            other1: Tuple[float, float]
            other2: Tuple[float, float]
            if _points_close(p1b, p2a, tol):
                shared = p1b
                other1, other2 = p1a, p2b
            elif _points_close(p1b, p2b, tol):
                shared = p1b
                other1, other2 = p1a, p2a
            elif _points_close(p1a, p2a, tol):
                shared = p1a
                other1, other2 = p1b, p2b
            elif _points_close(p1a, p2b, tol):
                shared = p1a
                other1, other2 = p1b, p2a
            else:
                new_segments.append(s1)
                i += 1
                continue

            # Collinear mı?
            u = _unit_dir(s1)
            v = _unit_dir(s2)
            if _seg_len(s1) < EPS or _seg_len(s2) < EPS:
                new_segments.append(s1)
                i += 1
                continue
            angle = _angle_deg(u, v)
            if angle > opts.collinear_angle_eps_deg and (180.0 - angle) > opts.collinear_angle_eps_deg:
                new_segments.append(s1)
                i += 1
                continue

            # Birleştir: en uzak iki uç = other1, other2
            thick = None
            if _thickness_eq(s1.thickness, s2.thickness):
                thick = s1.thickness
            else:
                warnings.append("Merged segments had different thickness; thickness set to None")
            merged = SegmentIn(
                x1=other1[0], y1=other1[1],
                x2=other2[0], y2=other2[1],
                thickness=thick,
            )
            new_segments.append(merged)
            i += 2
            merged_any = True
            total_merges += 1

        segments = new_segments
        if not merged_any:
            break

    # Normalize sonrası invariant: kalan segmentlerin çok küçük olmaması beklenir (tol üzeri).
    for seg in segments:
        if _seg_len(seg) < opts.merge_endpoints_tol:
            warnings.append(
                "Çok küçük segment kaldı; sonuçlar hassasiyet nedeniyle farklı olabilir."
            )
            break

    # C) min_segment_len: çok kısa segmentleri düşür
    if opts.min_segment_len and opts.min_segment_len > 0.0:
        kept: List[SegmentIn] = []
        dropped_count = 0
        for seg in segments:
            if _seg_len(seg) < opts.min_segment_len:
                dropped_count += 1
            else:
                kept.append(seg)
        if dropped_count > 0:
            warnings.append(
                f"Dropped {dropped_count} segments shorter than {opts.min_segment_len}."
            )
        segments = kept
        if not segments:
            raise ValueError("Normalizasyon sonrası segment kalmadı.")

    # D) segment_budget: çok fazla segment varsa sınırla
    if opts.segment_budget is not None and opts.segment_budget > 0:
        budget = int(opts.segment_budget)
        if len(segments) > budget:
            if opts.budget_strategy == "error":
                raise ValueError(
                    f"Plan çok detaylı: {len(segments)} segments > budget {budget}."
                )
            # keep_longest: en uzun N segmenti tut, orijinal sıralamayı koruyarak
            lengths = [(_seg_len(seg), idx) for idx, seg in enumerate(segments)]
            lengths_sorted = sorted(
                lengths, key=lambda item: (-item[0], item[1])
            )
            keep_indices = {idx for _, idx in lengths_sorted[:budget]}
            segments = [seg for idx, seg in enumerate(segments) if idx in keep_indices]
            warnings.append(
                f"Segment budget applied: kept {len(segments)} longest of {len(lengths)}."
            )

    # E) recenter: bbox merkezini veya min köşesini (0,0)'a taşı
    if opts.recenter:
        if segments:
            minx = min(min(seg.x1, seg.x2) for seg in segments)
            miny = min(min(seg.y1, seg.y2) for seg in segments)
            maxx = max(max(seg.x1, seg.x2) for seg in segments)
            maxy = max(max(seg.y1, seg.y2) for seg in segments)
            if opts.recenter_mode == "min_corner":
                dx = -minx
                dy = -miny
            else:
                cx = (minx + maxx) / 2.0
                cy = (miny + maxy) / 2.0
                dx = -cx
                dy = -cy
            if dx != 0.0 or dy != 0.0:
                shifted: List[SegmentIn] = []
                for seg in segments:
                    shifted.append(
                        SegmentIn(
                            x1=seg.x1 + dx,
                            y1=seg.y1 + dy,
                            x2=seg.x2 + dx,
                            y2=seg.y2 + dy,
                            thickness=seg.thickness,
                        )
                    )
                segments = shifted
                dx_r = round(dx, 6)
                dy_r = round(dy, 6)
                warnings.append(
                    f"Recentering applied (mode={opts.recenter_mode}, dx={dx_r}, dy={dy_r})."
                )

    out_plan = NormalizedPlan(
        version=plan.version,
        units=plan.units,
        scale=plan.scale,
        origin=plan.origin,
        segments=segments,
        metadata=plan.metadata,
    )
    return out_plan, warnings
