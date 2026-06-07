# path_optimizer.py — Komut sadeleştirme + stroke sıralama (NN, 2-opt, reverse, join)
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import List, Tuple

from app.execution.commands import (
    Command,
    MoveCommand,
    MoveRelCommand,
    PenCommand,
    SpeedCommand,
    WaitCommand,
    TurnCommand,
    ForwardCommand,
)


@dataclass(frozen=True)
class OptimizeConfig:
    enabled: bool = True
    collinear_angle_eps_deg: float = 1.0
    min_segment_length: float = 0.5
    rdp_epsilon: float = 0.0
    preserve_pen_lifts: bool = True
    # Stroke sıralama ve birleştirme
    join_epsilon_m: float = 0.001
    max_2opt_iterations: int = 50
    time_budget_ms: float = 5000.0
    preserve_order_for_layers: bool = False
    deterministic_seed: int | None = None
    # MVP güvenlik: travel artarsa optimize'ı geri al
    require_travel_improvement: bool = True
    min_travel_reduction_pct: float = 0.0


@dataclass
class Segment:
    """Tek bir polyline segmenti: pen durumu, noktalar, hız, nokta sonrası bekleme süreleri."""
    pen_down: bool = True
    points: List[Tuple[float, float]] = field(default_factory=list)
    speed: float | None = None
    wait_after_point: List[float] = field(default_factory=list)


def _dist(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _angle_between_deg(
    a: Tuple[float, float],
    b: Tuple[float, float],
    c: Tuple[float, float],
) -> float:
    """B açısı (derece): BA vektörü ile BC vektörü arasındaki açı."""
    v1x = a[0] - b[0]
    v1y = a[1] - b[1]
    v2x = c[0] - b[0]
    v2y = c[1] - b[1]
    n1 = math.hypot(v1x, v1y)
    n2 = math.hypot(v2x, v2y)
    if n1 < 1e-12 or n2 < 1e-12:
        return 0.0
    dot = (v1x * v2x + v1y * v2y) / (n1 * n2)
    dot = max(-1.0, min(1.0, dot))
    return math.degrees(math.acos(dot))


def commands_to_polyline_segments(
    commands: List[Command],
    start: Tuple[float, float],
) -> List[Segment]:
    """
    Komut listesini segmentlere çevirir.
    MOVE/MOVE_REL/TURN+FORWARD mutlak noktaya dönüştürülür.
    PEN değişiminde yeni segment başlar (preserve_pen_lifts sonraki aşamada kullanılır).
    """
    x, y = float(start[0]), float(start[1])
    heading_deg = 0.0
    current_speed: float | None = None
    segments: List[Segment] = []
    current = Segment(pen_down=False, points=[], speed=None, wait_after_point=[])

    def flush_if_pen_change(pen_down: bool) -> None:
        nonlocal current
        if current.points and current.pen_down != pen_down:
            segments.append(current)
            current = Segment(pen_down=pen_down, points=[], speed=current_speed, wait_after_point=[])

    for cmd in commands:
        if isinstance(cmd, SpeedCommand):
            current_speed = max(0.0, float(cmd.speed))
            if not current.points:
                current.speed = current_speed
            continue
        if isinstance(cmd, PenCommand):
            flush_if_pen_change(bool(cmd.is_down))
            current.pen_down = bool(cmd.is_down)
            continue
        if isinstance(cmd, WaitCommand):
            secs = max(0.0, float(cmd.seconds))
            if current.points:
                current.wait_after_point[-1] = current.wait_after_point[-1] + secs
            else:
                current.wait_after_point.append(secs)
                current.points.append((x, y))
            continue
        if isinstance(cmd, TurnCommand):
            heading_deg += float(cmd.deg)
            continue
        if isinstance(cmd, ForwardCommand):
            dist = float(cmd.dist)
            rad = math.radians(heading_deg)
            if not current.points:
                current.points.append((x, y))
                current.wait_after_point.append(0.0)
            x += math.cos(rad) * dist
            y += math.sin(rad) * dist
            current.points.append((x, y))
            current.wait_after_point.append(0.0)
            continue
        if isinstance(cmd, MoveCommand):
            nx, ny = float(cmd.x), float(cmd.y)
            if current.pen_down and not current.points:
                current.points.append((x, y))
                current.wait_after_point.append(0.0)
            x, y = nx, ny
            current.points.append((x, y))
            current.wait_after_point.append(0.0)
            continue
        if isinstance(cmd, MoveRelCommand):
            if not current.points:
                current.points.append((x, y))
                current.wait_after_point.append(0.0)
            x += float(cmd.dx)
            y += float(cmd.dy)
            current.points.append((x, y))
            current.wait_after_point.append(0.0)
            continue

    if current.points:
        segments.append(current)
    return segments


def _simplify_min_segment(
    points: List[Tuple[float, float]],
    wait_after: List[float],
    min_len: float,
) -> Tuple[List[Tuple[float, float]], List[float]]:
    """Ardışık noktalar arası < min_len ise ara noktayı atla; son noktayı koru. WAIT'lar ilk noktaya taşınır."""
    if len(points) <= 2 or min_len <= 0.0:
        return list(points), list(wait_after)
    out_pts: List[Tuple[float, float]] = [points[0]]
    out_wait: List[float] = [wait_after[0] if wait_after else 0.0]
    for i in range(1, len(points)):
        p = points[i]
        w = wait_after[i] if i < len(wait_after) else 0.0
        if _dist(out_pts[-1], p) < min_len:
            out_wait[-1] = out_wait[-1] + w
            continue
        out_pts.append(p)
        out_wait.append(w)
    if len(points) > 1 and out_pts[-1] != points[-1]:
        out_pts.append(points[-1])
        out_wait.append(wait_after[-1] if len(wait_after) >= len(points) else 0.0)
    return out_pts, out_wait


def _simplify_collinear(
    points: List[Tuple[float, float]],
    wait_after: List[float],
    angle_eps_deg: float,
) -> Tuple[List[Tuple[float, float]], List[float]]:
    """A-B-C kollinear ise (açı < eps) B'yi sil. Son nokta korunur."""
    if len(points) <= 2 or angle_eps_deg <= 0.0:
        return list(points), list(wait_after)
    out_pts: List[Tuple[float, float]] = [points[0]]
    out_wait: List[float] = [wait_after[0] if wait_after else 0.0]
    i = 1
    while i < len(points) - 1:
        a, b, c = out_pts[-1], points[i], points[i + 1]
        angle = _angle_between_deg(a, b, c)
        w_b = wait_after[i] if i < len(wait_after) else 0.0
        if angle < angle_eps_deg or angle > (180.0 - angle_eps_deg):
            out_wait[-1] = out_wait[-1] + w_b
            i += 1
            continue
        out_pts.append(b)
        out_wait.append(w_b)
        i += 1
    if len(points) > 1:
        out_pts.append(points[-1])
        out_wait.append(wait_after[-1] if len(wait_after) >= len(points) else 0.0)
    return out_pts, out_wait


def _rdp_indices(points: List[Tuple[float, float]], epsilon: float) -> List[int]:
    """Ramer-Douglas-Peucker; tutulan nokta indekslerini döndürür."""
    if len(points) <= 2 or epsilon <= 0.0:
        return list(range(len(points)))

    def perpendicular_dist(p: Tuple[float, float], line_start: Tuple[float, float], line_end: Tuple[float, float]) -> float:
        dx = line_end[0] - line_start[0]
        dy = line_end[1] - line_start[1]
        n = math.hypot(dx, dy)
        if n < 1e-12:
            return _dist(p, line_start)
        u = ((p[0] - line_start[0]) * dx + (p[1] - line_start[1]) * dy) / (n * n)
        u = max(0.0, min(1.0, u))
        proj = (line_start[0] + u * dx, line_start[1] + u * dy)
        return _dist(p, proj)

    def rdp_rec(idx_list: List[int]) -> List[int]:
        if len(idx_list) <= 2:
            return idx_list
        start, end = idx_list[0], idx_list[-1]
        line_start, line_end = points[start], points[end]
        max_d = 0.0
        max_i = start
        for i in idx_list[1:-1]:
            d = perpendicular_dist(points[i], line_start, line_end)
            if d > max_d:
                max_d = d
                max_i = i
        if max_d <= epsilon:
            return [start, end]
        left = rdp_rec([start] + [j for j in idx_list if start < j < max_i] + [max_i])
        right = rdp_rec([max_i] + [j for j in idx_list if max_i < j < end] + [end])
        return left[:-1] + right

    return rdp_rec(list(range(len(points))))


def _apply_rdp_to_segment(
    seg: Segment,
    epsilon: float,
) -> Segment:
    """Segment noktalarına RDP uygula. WAIT süreleri tutulan noktalar arasında toplanır."""
    if epsilon <= 0.0 or len(seg.points) <= 2:
        return seg
    indices = _rdp_indices(seg.points, epsilon)
    new_pts = [seg.points[i] for i in indices]
    waits = seg.wait_after_point if seg.wait_after_point else [0.0] * len(seg.points)
    new_wait: List[float] = []
    for k in range(len(indices)):
        i0 = indices[k]
        i1 = indices[k + 1] if k + 1 < len(indices) else len(seg.points)
        total = sum(waits[j] for j in range(i0, min(i1, len(waits))))
        new_wait.append(total)
    return Segment(pen_down=seg.pen_down, points=new_pts, speed=seg.speed, wait_after_point=new_wait)


def segments_to_commands(segments: List[Segment]) -> List[Command]:
    """Sadeleştirilmiş segmentlerden komut listesi üretir: SPEED (değişimde), PEN (değişimde), MOVE, WAIT."""
    out: List[Command] = []
    last_speed: float | None = None
    last_pen: bool | None = None
    for seg in segments:
        if seg.speed is not None and seg.speed != last_speed:
            out.append(SpeedCommand(speed=seg.speed))
            last_speed = seg.speed
        if last_pen is None or last_pen != seg.pen_down:
            out.append(PenCommand(is_down=seg.pen_down))
            last_pen = seg.pen_down
        waits = seg.wait_after_point if seg.wait_after_point else [0.0] * len(seg.points)
        for i, (px, py) in enumerate(seg.points):
            out.append(MoveCommand(x=px, y=py))
            w = waits[i] if i < len(waits) else 0.0
            if w > 0.0:
                out.append(WaitCommand(seconds=w))
    if last_pen is True:
        out.append(PenCommand(is_down=False))
    return out


def _squared_dist(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    return dx * dx + dy * dy


def _reorder_strokes_nn_2opt(
    strokes: List[Segment],
    start_pos: Tuple[float, float],
    cfg: OptimizeConfig,
) -> List[Tuple[List[Tuple[float, float]], bool]]:
    """
    Stroke'ları NN ile sırala, her stroke için başlangıç/bitiş seç (ters çevir), isteğe bağlı 2-opt.
    Döner: [(points, reversed), ...] sıralı ve yön seçilmiş stroke listesi.
    """
    if not strokes or cfg.preserve_order_for_layers:
        return [(list(s.points), False) for s in strokes]

    # Her stroke için (start_pt, end_pt, points)
    stroke_data: List[Tuple[Tuple[float, float], Tuple[float, float], List[Tuple[float, float]]]] = []
    for s in strokes:
        if len(s.points) < 2:
            continue
        stroke_data.append((s.points[0], s.points[-1], list(s.points)))

    if not stroke_data:
        return []

    t0 = time.perf_counter()
    budget_s = cfg.time_budget_ms / 1000.0
    n = len(stroke_data)

    # NN: mevcut konumdan en yakın stroke uç noktasını seç; stroke'u normal veya ters çevir
    remaining = set(range(n))
    current = (float(start_pos[0]), float(start_pos[1]))
    order: List[Tuple[int, bool]] = []  # (stroke_idx, reversed)

    while remaining and (time.perf_counter() - t0) < budget_s:
        best_idx: int | None = None
        best_rev = False
        best_key: Tuple[float, int, float, float] = (float("inf"), 0, 0.0, 0.0)
        for idx in remaining:
            start_pt, end_pt, pts = stroke_data[idx]
            d_start = _squared_dist(current, start_pt)
            d_end = _squared_dist(current, end_pt)
            if d_start <= d_end:
                key = (d_start, idx, start_pt[0], start_pt[1])
                if key < best_key:
                    best_key = key
                    best_idx = idx
                    best_rev = False
            else:
                key = (d_end, idx, end_pt[0], end_pt[1])
                if key < best_key:
                    best_key = key
                    best_idx = idx
                    best_rev = True
        if best_idx is None:
            break
        remaining.discard(best_idx)
        order.append((best_idx, best_rev))
        start_pt, end_pt, pts = stroke_data[best_idx]
        current = start_pt if best_rev else end_pt

    # 2-opt: stroke sırasında i,j yer değiştir; toplam travel azalıyorsa uygula
    def total_travel(ord_list: List[Tuple[int, bool]]) -> float:
        pos = start_pos
        total = 0.0
        for idx, rev in ord_list:
            start_pt, end_pt, pts = stroke_data[idx]
            entry = end_pt if rev else start_pt
            total += math.sqrt(_squared_dist(pos, entry))
            pos = start_pt if rev else end_pt
        return total

    max_iter = getattr(cfg, "max_2opt_iterations", 50) or 0
    for _ in range(max_iter):
        if (time.perf_counter() - t0) >= budget_s:
            break
        improved = False
        for i in range(len(order)):
            for j in range(i + 1, len(order)):
                new_order = order[:i] + order[i : j + 1][::-1] + order[j + 1 :]
                if total_travel(new_order) < total_travel(order):
                    order = new_order
                    improved = True
                    break
            if improved:
                break
        if not improved:
            break

    result: List[Tuple[List[Tuple[float, float]], bool]] = []
    for idx, rev in order:
        _, _, pts = stroke_data[idx]
        result.append((list(pts), rev))
    return result


def _join_strokes(
    ordered_strokes: List[Tuple[List[Tuple[float, float]], bool]],
    epsilon: float,
) -> List[List[Tuple[float, float]]]:
    """Uçları epsilon içinde olan ardışık stroke'ları birleştir."""
    if not ordered_strokes or epsilon <= 0.0:
        return [pts if not rev else list(reversed(pts)) for pts, rev in ordered_strokes]

    merged: List[List[Tuple[float, float]]] = []
    for pts, rev in ordered_strokes:
        seg = list(reversed(pts)) if rev else list(pts)
        if not seg:
            continue
        if merged and _dist(merged[-1][-1], seg[0]) <= epsilon:
            merged[-1].extend(seg)
        elif merged and _dist(merged[-1][-1], seg[-1]) <= epsilon:
            merged[-1].extend(reversed(seg))
        else:
            merged.append(seg)
    return merged


def optimize_commands(
    commands: List[Command],
    start: Tuple[float, float],
    cfg: OptimizeConfig,
) -> List[Command]:
    """
    Komut listesini optimize eder: stroke'ları NN+2-opt ile sıralar, yön seçer, birleştirir,
    ardından min_segment + collinear + (opsiyonel) RDP uygular.
    """
    if not getattr(cfg, "enabled", True) or not commands:
        return list(commands)

    # Travel ölçümü: komutları segmente çevirip pen_down=False segmentlerinin uzunluğu
    def _travel_length(cmds: List[Command]) -> float:
        segs = commands_to_polyline_segments(cmds, start)
        total = 0.0
        for s in segs:
            if s.pen_down:
                continue
            for i in range(len(s.points) - 1):
                total += _dist(s.points[i], s.points[i + 1])
        return total

    travel_before = _travel_length(commands)

    segments = commands_to_polyline_segments(commands, start)
    if not segments:
        return list(commands)

    strokes = [s for s in segments if s.pen_down and len(s.points) >= 2]
    if not strokes:
        new_segments = []
        for seg in segments:
            pts = list(seg.points)
            waits = list(seg.wait_after_point) if seg.wait_after_point else [0.0] * len(pts)
            if len(waits) < len(pts):
                waits.extend([0.0] * (len(pts) - len(waits)))
            if cfg.min_segment_length > 0.0:
                pts, waits = _simplify_min_segment(pts, waits, cfg.min_segment_length)
            if cfg.collinear_angle_eps_deg > 0.0:
                pts, waits = _simplify_collinear(pts, waits, cfg.collinear_angle_eps_deg)
            seg2 = Segment(pen_down=seg.pen_down, points=pts, speed=seg.speed, wait_after_point=waits[: len(pts)])
            if cfg.rdp_epsilon > 0.0:
                seg2 = _apply_rdp_to_segment(seg2, cfg.rdp_epsilon)
            new_segments.append(seg2)
        return segments_to_commands(new_segments)

    join_eps = getattr(cfg, "join_epsilon_m", 0.001)
    ordered = _reorder_strokes_nn_2opt(strokes, start, cfg)
    joined = _join_strokes(ordered, join_eps)

    # Birleştirilmiş stroke'lar + aralarında travel segmentleri
    new_segments_list: List[Segment] = []
    speed = strokes[0].speed if strokes else None
    prev_end: Tuple[float, float] | None = None
    for seg_pts in joined:
        if not seg_pts:
            continue
        travel_from = prev_end if prev_end is not None else start
        if _dist(travel_from, seg_pts[0]) > 1e-9:
            new_segments_list.append(
                Segment(
                    pen_down=False,
                    points=[travel_from, seg_pts[0]],
                    speed=speed,
                    wait_after_point=[0.0, 0.0],
                )
            )
        new_segments_list.append(
            Segment(pen_down=True, points=seg_pts, speed=speed, wait_after_point=[0.0] * len(seg_pts))
        )
        prev_end = seg_pts[-1]

    new_segments = []
    for seg in new_segments_list:
        pts = list(seg.points)
        waits = list(seg.wait_after_point) if seg.wait_after_point else [0.0] * len(pts)
        if len(waits) < len(pts):
            waits.extend([0.0] * (len(pts) - len(waits)))
        if cfg.min_segment_length > 0.0:
            pts, waits = _simplify_min_segment(pts, waits, cfg.min_segment_length)
        if cfg.collinear_angle_eps_deg > 0.0:
            pts, waits = _simplify_collinear(pts, waits, cfg.collinear_angle_eps_deg)
        seg2 = Segment(pen_down=seg.pen_down, points=pts, speed=seg.speed, wait_after_point=waits[: len(pts)])
        if cfg.rdp_epsilon > 0.0:
            seg2 = _apply_rdp_to_segment(seg2, cfg.rdp_epsilon)
        new_segments.append(seg2)

    out_cmds = segments_to_commands(new_segments)
    travel_after = _travel_length(out_cmds)
    if getattr(cfg, "require_travel_improvement", True) and travel_before > 0.0:
        min_pct = float(getattr(cfg, "min_travel_reduction_pct", 0.0) or 0.0)
        required_after = travel_before * (1.0 - min_pct / 100.0)
        if travel_after > required_after:
            return list(commands)
    return out_cmds
