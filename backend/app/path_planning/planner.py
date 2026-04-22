from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Sequence

from app.alignment.alignment_model import AlignedLayout
from app.layout_ir.ir_types import LineObject, PolylineObject, SourceRef
from app.path_planning.plan_model import (
    PathMetrics,
    PathPlanningReport,
    PlannedPath,
    PlannedStroke,
)


@dataclass(frozen=True)
class PathPlanningOptions:
    """İlk sürüm: greedy nearest-neighbor; gelişmiş TSP yok."""

    min_segment_length_m: float = 0.005
    start_x_m: float = 0.0
    start_y_m: float = 0.0
    strategy: Literal["greedy_nearest"] = "greedy_nearest"


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _tie_key(src: SourceRef) -> tuple[str, str, str]:
    h = src.handle or ""
    return (src.layer, h, src.entity_type)


@dataclass(frozen=True)
class _Candidate:
    """Gezici sıralama için ara temsil."""

    points_forward: tuple[tuple[float, float], ...]
    closed: bool
    kind: Literal["line", "polyline"]
    source: SourceRef
    stroke_length_m: float


def _line_length(p0: tuple[float, float], p1: tuple[float, float]) -> float:
    return _dist(p0, p1)


def _polyline_length(points: Sequence[tuple[float, float]], closed: bool) -> float:
    n = len(points)
    if n < 2:
        return 0.0
    s = 0.0
    for i in range(n - 1):
        s += _dist(points[i], points[i + 1])
    if closed:
        s += _dist(points[-1], points[0])
    return s


def _open_polyline_split_by_short_edges(
    points: tuple[tuple[float, float], ...],
    min_len: float,
) -> tuple[list[tuple[tuple[float, float], ...]], int]:
    """
    Açık polyline: ardışık noktalar arası kenar < min_len ise zinciri böler.
    Dönüş: zincir listesi + atlanan kısa kenar sayısı.
    """
    n = len(points)
    skipped = 0
    if n < 2:
        return [], 0
    chains: list[tuple[tuple[float, float], ...]] = []
    cur: list[tuple[float, float]] = [points[0]]
    for i in range(n - 1):
        if _dist(points[i], points[i + 1]) >= min_len:
            cur.append(points[i + 1])
        else:
            skipped += 1
            if len(cur) >= 2:
                chains.append(tuple(cur))
            cur = [points[i + 1]]
    if len(cur) >= 2:
        chains.append(tuple(cur))
    return chains, skipped


def _closed_polyline_to_candidate(
    points: tuple[tuple[float, float], ...],
    min_len: float,
    source: SourceRef,
) -> tuple[_Candidate | None, int]:
    """
    Kapalı polyline: kenarlar sırayla p0->p1->...->pn-1->p0.
    Kısa kenar varsa o kenarı çizmeden atla (zinciri aç) veya tüm şekli at.
    İlk sürüm: herhangi bir kenar < min ise tüm stroke'u at (deterministik, basit).
    """
    n = len(points)
    if n < 3:
        return None, 0
    skipped = 0
    for i in range(n - 1):
        if _dist(points[i], points[i + 1]) < min_len:
            skipped += 1
    if _dist(points[-1], points[0]) < min_len:
        skipped += 1
    if skipped > 0:
        return None, skipped
    length = _polyline_length(points, closed=True)
    return (
        _Candidate(
            points_forward=points,
            closed=True,
            kind="polyline",
            source=source,
            stroke_length_m=length,
        ),
        0,
    )


def _build_candidates(layout: AlignedLayout, min_len: float) -> tuple[list[_Candidate], int]:
    candidates: list[_Candidate] = []
    skipped = 0

    for obj in layout.objects:
        if isinstance(obj, LineObject):
            p0 = (obj.x1, obj.y1)
            p1 = (obj.x2, obj.y2)
            L = _line_length(p0, p1)
            if L < min_len:
                skipped += 1
                continue
            candidates.append(
                _Candidate(
                    points_forward=(p0, p1),
                    closed=False,
                    kind="line",
                    source=obj.source,
                    stroke_length_m=L,
                )
            )
        else:
            pts = obj.points
            if len(pts) < 2:
                continue
            if obj.closed:
                cand, sk = _closed_polyline_to_candidate(pts, min_len, obj.source)
                skipped += sk
                if cand is not None:
                    candidates.append(cand)
            else:
                chains, sk = _open_polyline_split_by_short_edges(pts, min_len)
                skipped += sk
                for ch in chains:
                    L = _polyline_length(ch, closed=False)
                    if L < min_len:
                        skipped += 1
                        continue
                    candidates.append(
                        _Candidate(
                            points_forward=ch,
                            closed=False,
                            kind="polyline",
                            source=obj.source,
                            stroke_length_m=L,
                        )
                    )

    return candidates, skipped


def _stroke_endpoints(
    cand: _Candidate, reversed: bool
) -> tuple[tuple[float, float], tuple[float, float]]:
    pts = cand.points_forward
    if len(pts) < 2:
        return pts[0], pts[0]
    if reversed:
        return pts[-1], pts[0]
    return pts[0], pts[-1]


def _oriented_points(cand: _Candidate, reversed: bool) -> tuple[tuple[float, float], ...]:
    if not reversed:
        return cand.points_forward
    return tuple(reversed(cand.points_forward))


def plan_path_from_aligned_layout(
    layout: AlignedLayout,
    *,
    options: PathPlanningOptions | None = None,
) -> tuple[PlannedPath, PathPlanningReport]:
    """
    Deterministik greedy nearest-neighbor stroke sıralaması.

    - Başlangıç: (start_x_m, start_y_m).
    - Her adımda kalan stroke'lar arasında, mevcut uçtan en yakın **giriş noktasına**
      sahip stroke seçilir; gerekirse stroke ters çevrilir (reversed=True).
    - Eşit mesafe: (layer, handle, entity_type) sözlük sırası.
    - Kapalı polyline: yön ters çevrilebilir; başlangıç noktası her zaman
      filtrelenmiş points_forward[0] veya ters çevirmede son nokta (yani yine
      geometrik uç); döngü sırası korunur, kapanış kenarı son çizilir.
    """
    opts = options or PathPlanningOptions()
    min_len = float(opts.min_segment_length_m)
    sx, sy = float(opts.start_x_m), float(opts.start_y_m)

    candidates, skipped_seg = _build_candidates(layout, min_len)
    if not candidates:
        metrics = PathMetrics(
            stroke_count=0,
            drawing_length_m=0.0,
            travel_length_m=0.0,
            pen_lifts=0,
            skipped_short_segment_count=skipped_seg,
            total_points=0,
            strategy=opts.strategy,
            notes=(
                "Hiç stroke kalmadı (min_segment_length_m filtresi veya boş layout).",
                "Kapalı polyline: tüm kenarlar >= eşik değilse stroke tamamen atlanır.",
                "Açık polyline: kısa kenarlarda zincir bölünür.",
            ),
        )
        return PlannedPath(strokes=()), PathPlanningReport(metrics=metrics)

    remaining: list[_Candidate] = list(candidates)
    pos = (sx, sy)
    ordered: list[PlannedStroke] = []
    total_travel = 0.0
    total_draw = 0.0
    total_pts = 0

    while remaining:
        best_i = -1
        best_rev = False
        best_tuple: tuple[float, tuple[str, str, str], int, bool] | None = None

        for i, cand in enumerate(remaining):
            for rev in (False, True):
                start_p, _end_p = _stroke_endpoints(cand, rev)
                d = _dist(pos, start_p)
                key = _tie_key(cand.source)
                t = (d, key, i, rev)
                if best_tuple is None or t < best_tuple:
                    best_tuple = t
                    best_i = i
                    best_rev = rev

        assert best_i >= 0
        cand = remaining.pop(best_i)
        travel = _dist(pos, _stroke_endpoints(cand, best_rev)[0])
        total_travel += travel

        oriented = _oriented_points(cand, best_rev)
        if cand.closed and len(oriented) >= 3:
            draw_pts = tuple(oriented) + (oriented[0],)
        else:
            draw_pts = tuple(oriented)

        total_pts += len(draw_pts)
        total_draw += cand.stroke_length_m

        ordered.append(
            PlannedStroke(
                kind=cand.kind,
                points=draw_pts,
                source=cand.source,
                stroke_length_m=cand.stroke_length_m,
                travel_from_previous_m=travel,
                reversed=best_rev,
                closed=cand.closed,
            )
        )
        pos = _stroke_endpoints(cand, best_rev)[1]

    stroke_count = len(ordered)
    pen_lifts = max(0, stroke_count - 1)

    notes = (
        f"Strateji: {opts.strategy} (deterministik NN + sözlük tie-break).",
        "Kapalı polyline: perimeter sırası korunur; reversed=True sadece nokta dizisini ters çevirir.",
        "Açık polyline: kısa kenarlar bölünür; aynı kaynaktan birden fazla PlannedStroke oluşabilir.",
    )

    metrics = PathMetrics(
        stroke_count=stroke_count,
        drawing_length_m=total_draw,
        travel_length_m=total_travel,
        pen_lifts=pen_lifts,
        skipped_short_segment_count=skipped_seg,
        total_points=total_pts,
        strategy=opts.strategy,
        notes=notes,
    )
    return PlannedPath(strokes=tuple(ordered)), PathPlanningReport(metrics=metrics)
