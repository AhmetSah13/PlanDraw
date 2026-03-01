# step_size_utils.py — Preview recommended_step_size bbox-adaptif clamp (test edilebilir)
from __future__ import annotations

from typing import List, Optional


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def preview_recommended_step_size(
    total_length: float,
    target_moves: Optional[int],
    bbox: Optional[List[float]],
) -> Optional[float]:
    """
    Bbox-adaptif recommended_step_size: raw = total_length/target_moves,
    clamp(adaptive_min, adaptive_max) ile plan ölçeğine göre sınırlanır.
    """
    if target_moves is None or target_moves <= 0 or total_length <= 0.0:
        return None
    raw = total_length / float(target_moves)
    scale = 0.0
    if bbox and isinstance(bbox, list) and len(bbox) >= 4:
        w = float(bbox[2]) - float(bbox[0])
        h = float(bbox[3]) - float(bbox[1])
        scale = max(w, h)
    adaptive_min = max(0.05, scale * 0.005) if scale > 0 else 0.05
    adaptive_max = min(0.50, scale * 0.05) if scale > 0 else 0.50
    if adaptive_min > adaptive_max:
        adaptive_min, adaptive_max = 0.05, 0.50
    return _clamp(raw, adaptive_min, adaptive_max)
