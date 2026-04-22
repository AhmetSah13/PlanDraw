from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Sequence, Tuple


Point = Tuple[float, float]
PathType = List[Point]


def _normalize_angle_deg(angle: float) -> float:
    """Açıyı [-180, 180] aralığına normalize et."""
    a = float(angle)
    while a > 180.0:
        a -= 360.0
    while a <= -180.0:
        a += 360.0
    return a


def _angle_diff_abs(a_deg: float, b_deg: float) -> float:
    """İki heading arasındaki mutlak farkı [0, 180] aralığında döndür."""
    da = _normalize_angle_deg(a_deg - b_deg)
    return abs(da)


def _heading_from_vec(dx: float, dy: float) -> float:
    """Bir vektörden heading (derece) üret (0°=+X, CCW pozitif)."""
    if dx == 0.0 and dy == 0.0:
        return 0.0
    ang_rad = math.atan2(dy, dx)
    ang_deg = math.degrees(ang_rad)
    return _normalize_angle_deg(ang_deg)


def _path_start(path: Sequence[Point]) -> Point:
    return path[0]


def _path_end(path: Sequence[Point]) -> Point:
    return path[-1]


def _path_reverse(path: PathType) -> PathType:
    return list(reversed(path))


def _first_segment_vec(path: Sequence[Point], *, forward: bool) -> Tuple[float, float] | None:
    """İlk çizim segmenti vektörü (stroke yönünü temsil eder)."""
    if len(path) < 2:
        return None
    if forward:
        x0, y0 = path[0]
        x1, y1 = path[1]
    else:
        x0, y0 = path[-1]
        x1, y1 = path[-2]
    return x1 - x0, y1 - y0


def _last_segment_vec(path: Sequence[Point], *, forward: bool) -> Tuple[float, float] | None:
    """Son çizim segmenti vektörü (stroke bitiş heading'i için)."""
    if len(path) < 2:
        return None
    if forward:
        x0, y0 = path[-2]
        x1, y1 = path[-1]
    else:
        x0, y0 = path[1]
        x1, y1 = path[0]
    return x1 - x0, y1 - y0


def _step_cost(
    current_pos: Point,
    current_heading_deg: float,
    path: Sequence[Point],
    *,
    forward: bool,
    travel_weight: float,
    turn_weight: float,
) -> Tuple[float, float, float, Point, float]:
    """
    Tek bir path seçimi için maliyeti hesapla.

    Döner:
      - cost
      - travel_distance
      - heading_change_deg
      - new_pos
      - new_heading_deg
    """
    if not path:
        return 0.0, 0.0, 0.0, current_pos, current_heading_deg

    start_pt = _path_start(path) if forward else _path_end(path)
    end_pt = _path_end(path) if forward else _path_start(path)

    # Travel vektörü: mevcut pozdan stroke başlangıcına
    tx = start_pt[0] - current_pos[0]
    ty = start_pt[1] - current_pos[1]
    travel_dist = math.hypot(tx, ty)

    # Heading hedefi: önce travel yönü, travel yoksa ilk draw vektörü
    if travel_dist > 0.0:
        target_vec = (tx, ty)
    else:
        seg = _first_segment_vec(path, forward=forward)
        target_vec = seg if seg is not None else (0.0, 0.0)

    target_heading = _heading_from_vec(target_vec[0], target_vec[1])
    heading_change = _angle_diff_abs(target_heading, current_heading_deg)

    # Stroke sonunda heading'i yaklaşık olarak son segment yönüyle hizala
    last_seg = _last_segment_vec(path, forward=forward)
    if last_seg is not None:
        new_heading = _heading_from_vec(last_seg[0], last_seg[1])
    else:
        new_heading = current_heading_deg

    new_pos = end_pt
    cost = travel_weight * travel_dist + turn_weight * heading_change
    return cost, travel_dist, heading_change, new_pos, new_heading


def _evaluate_sequence(
    paths: Sequence[PathType],
    *,
    start_xy: Point,
    start_heading_deg: float,
) -> Dict[str, float]:
    """Verilen sırayla, yön değiştirmeden (forward) temel metrikleri hesapla."""
    cx, cy = start_xy
    heading = float(start_heading_deg)
    total_travel = 0.0
    total_turn = 0.0

    for path in paths:
        if not path:
            continue
        _, travel_dist, heading_change, new_pos, new_heading = _step_cost(
            (cx, cy),
            heading,
            path,
            forward=True,
            travel_weight=1.0,
            turn_weight=1.0,
        )
        total_travel += travel_dist
        total_turn += heading_change
        cx, cy = new_pos
        heading = new_heading

    return {
        "total_travel_m": total_travel,
        "estimated_turn_deg": total_turn,
    }


def plan_mobile_mission(
    paths: Iterable[PathType],
    start_xy: Point = (0.0, 0.0),
    start_heading_deg: float = 0.0,
    *,
    optimize_order: bool = True,
    optimize_direction: bool = True,
    travel_weight: float = 1.0,
    turn_weight: float = 1.0,
    planner_mode: str = "travel_first",
    travel_tie_band_ratio: float = 0.05,
    degradation_limit: float = 1.05,
) -> Dict[str, Any]:
    """
    Basit greedy mobil görev planlayıcı (V2 mission layer).

    Girdi:
      - paths: PathGenerator'dan gelen stroke listesi (polylines).
      - start_xy, start_heading_deg: robotun göreve başlarkenki durumu.
      - optimize_order, optimize_direction: sıra ve yön optimizasyonu.
      - travel_weight, turn_weight: weighted modda maliyet ağırlıkları.
      - planner_mode: "travel_first" (default) veya "weighted".
      - travel_tie_band_ratio: travel_first modda tie-break bandı (örn. 0.05 = %5).
      - degradation_limit: optimized > naive * limit ise naive plana fallback.

    Çıktı sözlüğü:
      - planned_paths, fallback_used, planner_mode, degradation_limit
      - naive_total_travel_m, total_travel_m (optimized), naive_estimated_turn_deg, estimated_turn_deg
      - travel_improvement_ratio
    """
    orig_paths: List[PathType] = [list(p) for p in paths]
    original_count = len(orig_paths)

    naive = _evaluate_sequence(
        orig_paths, start_xy=start_xy, start_heading_deg=start_heading_deg
    )
    naive_travel = float(naive["total_travel_m"])
    naive_turn = float(naive["estimated_turn_deg"])

    naive_planned_paths = [list(p) for p in orig_paths]

    if original_count == 0:
        return {
            "planned_paths": [],
            "original_path_count": 0,
            "planned_path_count": 0,
            "total_travel_m": 0.0,
            "estimated_turn_deg": 0.0,
            "planning_cost": 0.0,
            "naive_total_travel_m": 0.0,
            "naive_estimated_turn_deg": 0.0,
            "travel_improvement_ratio": 0.0,
            "fallback_used": False,
            "planner_mode": planner_mode,
            "degradation_limit": degradation_limit,
            "start_xy": [float(start_xy[0]), float(start_xy[1])],
            "start_heading_deg": float(start_heading_deg),
            "debug": {},
        }

    # Hiç optimize edilmemiş mod: sıralama ve yön aynen korunur.
    if not optimize_order and not optimize_direction:
        planned_paths = [list(p) for p in orig_paths]
        total_travel = naive_travel
        total_turn = naive_turn
        planning_cost = travel_weight * total_travel + turn_weight * total_turn
        travel_improvement_ratio = 1.0
        return {
            "planned_paths": planned_paths,
            "original_path_count": original_count,
            "planned_path_count": len(planned_paths),
            "total_travel_m": total_travel,
            "estimated_turn_deg": total_turn,
            "planning_cost": planning_cost,
            "naive_total_travel_m": naive_travel,
            "naive_estimated_turn_deg": naive_turn,
            "travel_improvement_ratio": travel_improvement_ratio,
            "fallback_used": False,
            "planner_mode": planner_mode,
            "degradation_limit": degradation_limit,
            "start_xy": [float(start_xy[0]), float(start_xy[1])],
            "start_heading_deg": float(start_heading_deg),
            "debug": {"mode": "no_optimization"},
        }

    # Greedy planlama
    planned_paths: List[PathType] = []
    remaining_indices = list(range(original_count))
    cx, cy = float(start_xy[0]), float(start_xy[1])
    heading = float(start_heading_deg)
    total_travel = 0.0
    total_turn = 0.0
    planning_cost = 0.0
    use_travel_first = planner_mode == "travel_first"

    # optimize_order=False ise orijinal sırayı koru; sadece yön seçiminde greedy kullan.
    if not optimize_order:
        for idx in remaining_indices:
            path = orig_paths[idx]
            if not path:
                planned_paths.append(list(path))
                continue

            if optimize_direction:
                choices = []
                for forward in (True, False):
                    _, travel_dist, heading_change, new_pos, new_heading = _step_cost(
                        (cx, cy),
                        heading,
                        path,
                        forward=forward,
                        travel_weight=1.0,
                        turn_weight=1.0,
                    )
                    choices.append(
                        (travel_dist, heading_change, new_pos, new_heading, forward)
                    )
                if use_travel_first:
                    best = min(choices, key=lambda c: (c[0], c[1]))
                else:
                    best = min(
                        choices,
                        key=lambda c: travel_weight * c[0] + turn_weight * c[1],
                    )
                travel_dist, heading_change, new_pos, new_heading, forward = best
            else:
                _, travel_dist, heading_change, new_pos, new_heading = _step_cost(
                    (cx, cy),
                    heading,
                    path,
                    forward=True,
                    travel_weight=1.0,
                    turn_weight=1.0,
                )
                forward = True

            planned_paths.append(list(path) if forward else _path_reverse(path))
            total_travel += travel_dist
            total_turn += heading_change
            planning_cost += travel_weight * travel_dist + turn_weight * heading_change
            cx, cy = new_pos
            heading = new_heading
    else:
        # Hem sıra hem yön greedy optimize edilir.
        while remaining_indices:
            candidates: List[Tuple[float, float, Point, float, int, bool]] = []

            for idx in remaining_indices:
                path = orig_paths[idx]
                if not path:
                    _, travel_dist, heading_change, new_pos, new_heading = _step_cost(
                        (cx, cy),
                        heading,
                        path,
                        forward=True,
                        travel_weight=1.0,
                        turn_weight=1.0,
                    )
                    candidates.append(
                        (travel_dist, heading_change, new_pos, new_heading, idx, True)
                    )
                    continue

                directions = [True]
                if optimize_direction:
                    directions.append(False)
                for forward in directions:
                    _, travel_dist, heading_change, new_pos, new_heading = _step_cost(
                        (cx, cy),
                        heading,
                        path,
                        forward=forward,
                        travel_weight=1.0,
                        turn_weight=1.0,
                    )
                    candidates.append(
                        (travel_dist, heading_change, new_pos, new_heading, idx, forward)
                    )

            if use_travel_first:
                min_travel = min(c[0] for c in candidates)
                tie_threshold = min_travel * (1.0 + travel_tie_band_ratio)
                tie_pool = [c for c in candidates if c[0] <= tie_threshold]
                # Tie-break: min heading_change, sonra min idx, sonra forward=True
                best = min(
                    tie_pool,
                    key=lambda c: (c[1], c[4], 0 if c[5] else 1),
                )
            else:
                # weighted: cost = travel_weight * travel + turn_weight * heading_change
                def _cost(c: Tuple[float, float, Point, float, int, bool]) -> float:
                    return travel_weight * c[0] + turn_weight * c[1]

                best = min(candidates, key=lambda c: (_cost(c), c[4], 0 if c[5] else 1))

            travel_dist, heading_change, new_pos, new_heading, chosen_idx, forward = best
            chosen_path = orig_paths[chosen_idx]
            planned_paths.append(
                list(chosen_path) if forward else _path_reverse(chosen_path)
            )
            total_travel += travel_dist
            total_turn += heading_change
            planning_cost += travel_weight * travel_dist + turn_weight * heading_change
            cx, cy = new_pos
            heading = new_heading
            remaining_indices.remove(chosen_idx)

    travel_improvement_ratio: float
    if naive_travel > 0.0:
        travel_improvement_ratio = total_travel / naive_travel
    else:
        travel_improvement_ratio = 1.0

    fallback_used = False
    if (
        degradation_limit > 0.0
        and naive_travel > 0.0
        and total_travel > naive_travel * degradation_limit
    ):
        fallback_used = True
        planned_paths = naive_planned_paths
        total_travel = naive_travel
        total_turn = naive_turn
        planning_cost = travel_weight * total_travel + turn_weight * total_turn
        travel_improvement_ratio = 1.0

    return {
        "planned_paths": planned_paths,
        "original_path_count": original_count,
        "planned_path_count": len(planned_paths),
        "total_travel_m": total_travel,
        "estimated_turn_deg": total_turn,
        "planning_cost": planning_cost,
        "naive_total_travel_m": naive_travel,
        "naive_estimated_turn_deg": naive_turn,
        "travel_improvement_ratio": travel_improvement_ratio,
        "fallback_used": fallback_used,
        "planner_mode": planner_mode,
        "degradation_limit": degradation_limit,
        "start_xy": [float(start_xy[0]), float(start_xy[1])],
        "start_heading_deg": float(start_heading_deg),
        "debug": {
            "optimize_order": optimize_order,
            "optimize_direction": optimize_direction,
            "travel_weight": travel_weight,
            "turn_weight": turn_weight,
        },
    }

