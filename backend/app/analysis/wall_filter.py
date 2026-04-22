from __future__ import annotations

"""
Wall-like segment filtresi (short segment + küçük komponent temizliği).

Bu modül, verify_dxf_drawability.py içindeki _apply_wall_filter fonksiyonunu
yeniden kullanılabilir hale getirmek için ayrılmıştır.
"""

from typing import Any, Dict, Tuple

from app.normalization.normalized_plan import NormalizedPlan
from app.normalization.normalized_plan import SegmentIn


WALL_FILTER_SNAP_TOL_M: float = 1e-4


def _seg_len(seg: SegmentIn) -> float:
    """Segment uzunluğu (metre)."""
    import math

    return math.hypot(seg.x2 - seg.x1, seg.y2 - seg.y1)


def apply_wall_filter(
    normalized_plan: NormalizedPlan,
    *,
    snap_tol: float = WALL_FILTER_SNAP_TOL_M,
) -> Tuple[NormalizedPlan, Dict[str, Any]]:
    """
    NormalizedPlan.segments üzerinde wall-like filtre uygular:
      - Kısa segmentler (<0.05m) atılır.
      - Çok küçük connected component'ler (toplam uzunluk <0.5m) atılır.
      - Single-edge component'ler sadece segment_length <0.2m ise atılır.

    Döner: (filtered_plan, metrics)
      metrics:
        - drops: {"short_segment": n, "small_component": m, "angle_noise": k}
        - snap_tol_m
        - component_min_length_m
        - single_edge_min_length_m
    """
    import math

    segments = list(normalized_plan.segments or [])
    drops = {"short_segment": 0, "small_component": 0, "angle_noise": 0}
    min_seg_len = 0.05
    min_comp_len = 0.5
    single_edge_min_len = 0.2

    if not segments:
        return normalized_plan, {
            "drops": drops,
            "snap_tol_m": float(snap_tol),
            "component_min_length_m": min_comp_len,
            "single_edge_min_length_m": single_edge_min_len,
        }

    # A) Short segment drop
    kept_indices: list[int] = []
    for idx, s in enumerate(segments):
        L = _seg_len(s)
        if L < min_seg_len:
            drops["short_segment"] += 1
        else:
            kept_indices.append(idx)

    if not kept_indices:
        # Tamamı çok kısa; fallback olarak orijinal planı koru
        return normalized_plan, {
            "drops": drops,
            "snap_tol_m": float(snap_tol),
            "component_min_length_m": min_comp_len,
            "single_edge_min_length_m": single_edge_min_len,
        }

    # B) Connected component analizi (segmentler arası bağlantı)
    def _snap_key(x: float, y: float) -> tuple[int, int]:
        return (int(round(x / snap_tol)), int(round(y / snap_tol)))

    # Endpoint -> segment listesi
    endpoint_map: dict[tuple[int, int], list[int]] = {}
    for idx in kept_indices:
        s = segments[idx]
        k1 = _snap_key(s.x1, s.y1)
        k2 = _snap_key(s.x2, s.y2)
        endpoint_map.setdefault(k1, []).append(idx)
        endpoint_map.setdefault(k2, []).append(idx)

    # Segment adjacency (komşuluk)
    adj: dict[int, set[int]] = {idx: set() for idx in kept_indices}
    for seg_list in endpoint_map.values():
        if len(seg_list) < 2:
            continue
        base = seg_list
        for i in range(len(base)):
            for j in range(i + 1, len(base)):
                a = base[i]
                b = base[j]
                adj[a].add(b)
                adj[b].add(a)

    # BFS ile segment komponentleri
    visited: set[int] = set()
    comp_segments: list[list[int]] = []
    for idx in kept_indices:
        if idx in visited:
            continue
        stack = [idx]
        visited.add(idx)
        comp: list[int] = []
        while stack:
            u = stack.pop()
            comp.append(u)
            for v in adj.get(u, ()):
                if v not in visited:
                    visited.add(v)
                    stack.append(v)
        comp_segments.append(comp)

    # C) Küçük component drop (single-edge için daha akıllı eşik)
    to_drop_small: set[int] = set()
    for comp in comp_segments:
        comp_len = sum(_seg_len(segments[i]) for i in comp)
        if comp_len < min_comp_len:
            # Çok küçük toplam uzunluk → tüm komponenti at
            for i in comp:
                to_drop_small.add(i)
            drops["small_component"] += len(comp)
        elif len(comp) == 1:
            # Tek segmentli komponent: sadece segment çok kısaysa at
            i = comp[0]
            seg_len = _seg_len(segments[i])
            if seg_len < single_edge_min_len:
                to_drop_small.add(i)
                drops["small_component"] += 1

    final_segments: list[SegmentIn] = []
    for idx in kept_indices:
        if idx in to_drop_small:
            continue
        final_segments.append(segments[idx])

    filtered = NormalizedPlan(
        version=normalized_plan.version,
        units=normalized_plan.units,
        scale=normalized_plan.scale,
        origin=normalized_plan.origin,
        segments=final_segments,
        metadata=normalized_plan.metadata,
    )
    return filtered, {
        "drops": drops,
        "snap_tol_m": float(snap_tol),
        "component_min_length_m": min_comp_len,
        "single_edge_min_length_m": single_edge_min_len,
    }

