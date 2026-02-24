# scenario_analysis.py — Safety Gate + dry-run istatistikleri
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Tuple, Optional, TYPE_CHECKING, Literal

from commands import (
    Command,
    Diagnostic,
    MoveCommand,
    MoveRelCommand,
    SpeedCommand,
    WaitCommand,
    PenCommand,
    TurnCommand,
    ForwardCommand,
    serialize_commands,
)

if TYPE_CHECKING:
    from path_optimizer import OptimizeConfig


@dataclass(frozen=True)
class ScenarioLimits:
    max_total_time: float = 600.0  # saniye
    max_path_length: float = 20000.0  # world unit
    max_moves: int = 50000
    max_bounds_size: float = 50000.0  # tek kenar
    max_abs_coord: float = 1e6  # koordinat uç değer


def _merge_limits(base: ScenarioLimits, override: Optional[ScenarioLimits]) -> ScenarioLimits:
    return override if override is not None else base


# --- Kalite eşikleri (uyarıda WARN) ---
MIN_SEGMENT_LENGTH: float = 1e-3
MAX_WAIT_COUNT: int = 1000


MAX_PATH_POINTS = 20_000
MAX_COLLISIONS = 200


@dataclass
class Collision:
    kind: Literal["touch", "proper", "overlap"]
    x: Optional[float]
    y: Optional[float]
    wall_index: int
    seg_index: int
    message: str


@dataclass
class ScenarioStats:
    bounds: Tuple[float, float, float, float]  # minx, miny, maxx, maxy
    move_count: int
    wait_total: float
    path_length: float
    estimated_time: Optional[float]  # hız komutlarına göre hesaplanabiliyorsa
    path_points: Optional[List[Tuple[float, float]]] = None  # ideal path, max MAX_PATH_POINTS
    original_move_count: Optional[int] = None  # optimize açıksa kullanılan
    optimized_move_count: Optional[int] = None
    reduction_ratio: Optional[float] = None  # yüzde (0–100)
    collision_count: int = 0
    collisions_sample: Optional[List[Tuple[Optional[float], Optional[float], str]]] = None


def _count_moves(commands: List[Command]) -> int:
    """Hareket komutu sayısı (MOVE, MOVE_REL, FORWARD)."""
    return sum(
        1
        for c in commands
        if isinstance(c, (MoveCommand, MoveRelCommand, ForwardCommand))
    )


def analyze_commands(
    commands: List[Command],
    start: Tuple[float, float],
    *,
    limits: Optional[ScenarioLimits] = None,
    optimize_cfg: Optional["OptimizeConfig"] = None,
    walls: Optional[List[List[float]]] = None,
    collision_mode: str = "warn",
) -> Tuple[ScenarioStats, List[Diagnostic]]:
    """
    Komutları çalıştırmadan dry-run ile analiz eder.
    limits verilirse metadata/default override kullanılır.
    optimize_cfg verilip enabled=True ise önce optimize edilir, sonra analiz yapılır;
    stats içinde original_move_count, optimized_move_count, reduction_ratio dolar.
    Döner: (ScenarioStats, analysis_diagnostics).
    """
    lim = _merge_limits(ScenarioLimits(), limits)

    original_move_count: Optional[int] = None
    optimized_move_count: Optional[int] = None
    reduction_ratio: Optional[float] = None

    if optimize_cfg is not None and getattr(optimize_cfg, "enabled", False):
        from path_optimizer import optimize_commands
        original_move_count = _count_moves(commands)
        commands = optimize_commands(commands, start, optimize_cfg)
        optimized_move_count = _count_moves(commands)
        if original_move_count and optimized_move_count is not None:
            reduction_ratio = (1.0 - optimized_move_count / original_move_count) * 100.0

    x, y = float(start[0]), float(start[1])
    minx = maxx = x
    miny = maxy = y
    heading_deg = 0.0

    current_speed: float = 0.0
    move_count = 0
    wait_count = 0
    wait_total = 0.0
    path_length = 0.0
    estimated_time = 0.0
    time_known = True
    diagnostics: List[Diagnostic] = []
    short_segment_count = 0
    has_move_with_speed_zero = False
    path_points: List[Tuple[float, float]] = []  # noqa: RUF013
    path_points.append((float(start[0]), float(start[1])))

    def add(severity: str, msg: str, text: str = "") -> None:
        diagnostics.append(
            Diagnostic(severity=severity, line=0, message=msg, text=text or "Analysis")
        )

    def expand_bounds(px: float, py: float) -> None:
        nonlocal minx, miny, maxx, maxy
        minx = min(minx, px)
        miny = min(miny, py)
        maxx = max(maxx, px)
        maxy = max(maxy, py)

    for cmd in commands:
        if isinstance(cmd, SpeedCommand):
            current_speed = max(0.0, float(cmd.speed))
            continue

        if isinstance(cmd, WaitCommand):
            w = max(0.0, float(cmd.seconds))
            wait_total += w
            wait_count += 1
            if time_known:
                estimated_time += w
            continue

        if isinstance(cmd, PenCommand):
            continue

        if isinstance(cmd, TurnCommand):
            heading_deg += float(cmd.deg)
            continue

        if isinstance(cmd, ForwardCommand):
            dist = float(cmd.dist)
            rad = math.radians(heading_deg)
            dx = math.cos(rad) * dist
            dy = math.sin(rad) * dist
            nx, ny = x + dx, y + dy
        elif isinstance(cmd, MoveCommand):
            nx, ny = float(cmd.x), float(cmd.y)
        elif isinstance(cmd, MoveRelCommand):
            nx, ny = x + float(cmd.dx), y + float(cmd.dy)
        else:
            continue

        seg = math.hypot(nx - x, ny - y)
        path_length += seg
        move_count += 1

        if seg > 0.0:
            if seg < MIN_SEGMENT_LENGTH:
                short_segment_count += 1
            if current_speed <= 0.0:
                has_move_with_speed_zero = True
            if current_speed > 0.0 and time_known:
                estimated_time += seg / current_speed
            else:
                time_known = False

        expand_bounds(nx, ny)
        x, y = nx, ny
        path_points.append((x, y))

    if len(path_points) > MAX_PATH_POINTS:
        step = len(path_points) / MAX_PATH_POINTS
        path_points = [path_points[int(i * step)] for i in range(MAX_PATH_POINTS)]

    stats = ScenarioStats(
        bounds=(minx, miny, maxx, maxy),
        move_count=move_count,
        wait_total=wait_total,
        path_length=path_length,
        estimated_time=estimated_time if time_known else None,
        path_points=path_points if path_points else None,
        original_move_count=original_move_count,
        optimized_move_count=optimized_move_count,
        reduction_ratio=reduction_ratio,
    )

    # --- Safety Gate kontrolleri (ERROR) ---
    if stats.estimated_time is not None and stats.estimated_time > lim.max_total_time:
        diagnostics.append(
            Diagnostic(
                severity="ERROR",
                line=0,
                message=f"MAX_TOTAL_TIME aşıldı: {stats.estimated_time:.2f}s > {lim.max_total_time:.2f}s",
                text="",
            )
        )
    if stats.path_length > lim.max_path_length:
        diagnostics.append(
            Diagnostic(
                severity="ERROR",
                line=0,
                message=f"MAX_PATH_LENGTH aşıldı: {stats.path_length:.2f} > {lim.max_path_length:.2f}",
                text="",
            )
        )
    if stats.move_count > lim.max_moves:
        diagnostics.append(
            Diagnostic(
                severity="ERROR",
                line=0,
                message=f"MAX_MOVES aşıldı: {stats.move_count} > {lim.max_moves}",
                text="",
            )
        )
    sx_min, sy_min, sx_max, sy_max = stats.bounds
    bw = sx_max - sx_min
    bh = sy_max - sy_min
    if bw > lim.max_bounds_size or bh > lim.max_bounds_size:
        diagnostics.append(
            Diagnostic(
                severity="ERROR",
                line=0,
                message=(
                    f"MAX_BOUNDS_SIZE aşıldı: w={bw:.2f}, h={bh:.2f} > {lim.max_bounds_size:.2f}"
                ),
                text="",
            )
        )
    for v in (sx_min, sy_min, sx_max, sy_max, start[0], start[1]):
        if abs(v) > lim.max_abs_coord:
            diagnostics.append(
                Diagnostic(
                    severity="ERROR",
                    line=0,
                    message=f"MAX_ABS_COORD aşıldı: |coord|={abs(v):.2f} > {lim.max_abs_coord:.2f}",
                    text="",
                )
            )
            break

    # --- Kalite uyarıları (WARN) ---
    if short_segment_count > 0:
        add(
            "WARN",
            f"Çok kısa segment sayısı: {short_segment_count} (eşik: < {MIN_SEGMENT_LENGTH})",
        )
    if wait_count > MAX_WAIT_COUNT:
        add(
            "WARN",
            f"WAIT komutu sayısı ({wait_count}) yüksek (eşik: {MAX_WAIT_COUNT})",
        )
    if has_move_with_speed_zero:
        add(
            "WARN",
            "SPEED=0 iken hareket komutları var (executor çalışır ama ilerleme yavaş/teşhis zor)",
        )

    # --- W7: Duvar – çizim çakışma analizi ---
    collisions: List[Collision] = []
    if walls:
        from webapp.backend.app.geometry_utils import segment_intersection, polyline_segments

        # Sadece PEN DOWN sırasında oluşan çizim polylinelerini çıkar
        draw_polylines = extract_draw_polylines(commands, start)
        wall_segments: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
        for w in walls:
            if len(w) >= 4:
                wall_segments.append(((float(w[0]), float(w[1])), (float(w[2]), float(w[3]))))

        seg_index = 0
        total_collisions = 0
        for wall_idx, (wa, wb) in enumerate(wall_segments):
            # Her duvar ile tüm çizim segmentlerini test et
            for poly in draw_polylines:
                for sa, sb in polyline_segments(poly):
                    ok, pt, kind = segment_intersection(sa, sb, wa, wb)
                    if not ok:
                        seg_index += 1
                        continue
                    total_collisions += 1
                    if len(collisions) < MAX_COLLISIONS:
                        msg = f"Çizim yolu duvar ile kesişiyor (wall={wall_idx}, seg={seg_index}, kind={kind})"
                        cx, cy = (pt if pt is not None else (None, None))
                        collisions.append(
                            Collision(
                                kind=kind, x=cx, y=cy,
                                wall_index=wall_idx,
                                seg_index=seg_index,
                                message=msg,
                            )
                        )
                    seg_index += 1

        if total_collisions > 0:
            sev = "ERROR" if collision_mode == "error" else "WARN"
            add(sev, f"Duvarlarla kesişim tespit edildi: {total_collisions}")
            if total_collisions > MAX_COLLISIONS:
                add(
                    "WARN",
                    f"Kesişim sayısı yüksek: {total_collisions} (ilk {MAX_COLLISIONS} örnek tutuldu)",
                )
            stats.collision_count = total_collisions
            stats.collisions_sample = [
                (c.x, c.y, c.kind) for c in collisions[:20]
            ]

    return stats, diagnostics


def extract_draw_polylines(
    commands: List[Command],
    start: Tuple[float, float],
) -> List[List[Tuple[float, float]]]:
    """
    PEN DOWN iken çizilen polylineleri çıkarır.
    TURN/FORWARD/MOVE/MOVE_REL desteklenir; WAIT sadece süre olarak hesaba katılır.
    """
    x, y = float(start[0]), float(start[1])
    heading_deg = 0.0
    pen_down = False
    current: List[Tuple[float, float]] = []
    polylines: List[List[Tuple[float, float]]] = []

    def flush_current() -> None:
        nonlocal current
        if len(current) >= 2:
            polylines.append(current)
        current = []

    for cmd in commands:
        if isinstance(cmd, SpeedCommand):
            continue
        if isinstance(cmd, WaitCommand):
            continue
        if isinstance(cmd, PenCommand):
            if cmd.is_down and not pen_down:
                # Yeni çizim başlıyor
                pen_down = True
                current = [(x, y)]
            elif (not cmd.is_down) and pen_down:
                # Çizim bitiyor
                pen_down = False
                flush_current()
            continue
        if isinstance(cmd, TurnCommand):
            heading_deg += float(cmd.deg)
            continue

        if isinstance(cmd, ForwardCommand):
            dist = float(cmd.dist)
            rad = math.radians(heading_deg)
            nx, ny = x + math.cos(rad) * dist, y + math.sin(rad) * dist
        elif isinstance(cmd, MoveCommand):
            nx, ny = float(cmd.x), float(cmd.y)
        elif isinstance(cmd, MoveRelCommand):
            nx, ny = x + float(cmd.dx), y + float(cmd.dy)
        else:
            continue

        if pen_down:
            if not current:
                current.append((x, y))
            current.append((nx, ny))

        x, y = nx, ny

    if pen_down:
        flush_current()

    return polylines


def _commands_to_absolute_only(
    commands: List[Command],
    start: Tuple[float, float],
) -> List[Command]:
    """
    Göreli komutları (TURN, FORWARD, MOVE_REL) mutlak MOVE x y ile değiştirir.
    Sadece SPEED, PEN, WAIT, MOVE (absolute) çıkar.
    """
    x, y = float(start[0]), float(start[1])
    heading_deg = 0.0
    out: List[Command] = []
    for cmd in commands:
        if isinstance(cmd, SpeedCommand):
            out.append(cmd)
            continue
        if isinstance(cmd, PenCommand):
            out.append(cmd)
            continue
        if isinstance(cmd, WaitCommand):
            out.append(cmd)
            continue
        if isinstance(cmd, TurnCommand):
            heading_deg += float(cmd.deg)
            continue
        if isinstance(cmd, MoveCommand):
            x, y = float(cmd.x), float(cmd.y)
            out.append(MoveCommand(x=x, y=y))
            continue
        if isinstance(cmd, MoveRelCommand):
            x += float(cmd.dx)
            y += float(cmd.dy)
            out.append(MoveCommand(x=x, y=y))
            continue
        if isinstance(cmd, ForwardCommand):
            dist = float(cmd.dist)
            rad = math.radians(heading_deg)
            x += math.cos(rad) * dist
            y += math.sin(rad) * dist
            out.append(MoveCommand(x=x, y=y))
            continue
    return out


def _serialize_robot_v1(
    commands_absolute: List[Command],
    start: Tuple[float, float],
) -> List[str]:
    """Mutlak komut listesinden ROBOT_V1 satırları (MOVE x y t, SPEED, PEN 1|0, WAIT t)."""
    lines: List[str] = []
    x, y = float(start[0]), float(start[1])
    current_speed = 0.0
    for cmd in commands_absolute:
        if isinstance(cmd, SpeedCommand):
            current_speed = max(0.0, float(cmd.speed))
            lines.append(f"SPEED {current_speed}")
            continue
        if isinstance(cmd, PenCommand):
            lines.append(f"PEN {1 if cmd.is_down else 0}")
            continue
        if isinstance(cmd, WaitCommand):
            lines.append(f"WAIT {cmd.seconds}")
            continue
        if isinstance(cmd, MoveCommand):
            nx, ny = float(cmd.x), float(cmd.y)
            dist = math.hypot(nx - x, ny - y)
            duration = dist / current_speed if current_speed > 0 else 0.0
            lines.append(f"MOVE {nx} {ny} {duration}")
            x, y = nx, ny
            continue
    return lines


def _serialize_gcode_lite(
    commands_absolute: List[Command],
    start: Tuple[float, float],
) -> List[str]:
    """Mutlak komut listesinden GCODE_LITE satırları (G1, G4, M3, M5). F = v*60 unit/min."""
    lines: List[str] = []
    current_speed = 0.0
    for cmd in commands_absolute:
        if isinstance(cmd, SpeedCommand):
            current_speed = max(0.0, float(cmd.speed))
            continue
        if isinstance(cmd, PenCommand):
            lines.append("M3" if cmd.is_down else "M5")
            continue
        if isinstance(cmd, WaitCommand):
            ms = round(cmd.seconds * 1000)
            lines.append(f"G4 P{ms}")
            continue
        if isinstance(cmd, MoveCommand):
            nx, ny = float(cmd.x), float(cmd.y)
            f_val = round(current_speed * 60) if current_speed > 0 else 0
            lines.append(f"G1 X{nx} Y{ny} F{f_val}")
            continue
    return lines


def export_commands_to_string(
    commands: List[Command],
    start: Tuple[float, float],
    *,
    limits: Optional[ScenarioLimits] = None,
    format: str = "flat",  # noqa: A002
    optimize_cfg: Optional["OptimizeConfig"] = None,
) -> Tuple[str, bool, ScenarioStats, List[Diagnostic]]:
    """
    Export içeriğini string olarak döndürür.
    format: "flat" | "absolute_only" | "robot_v1" | "gcode_lite"
    Döner: (content, blocked, stats, analysis_diagnostics).
    """
    to_serialize = commands
    if format in ("absolute_only", "robot_v1", "gcode_lite"):
        to_serialize = _commands_to_absolute_only(commands, start)
    if optimize_cfg is not None and getattr(optimize_cfg, "enabled", False):
        from path_optimizer import optimize_commands
        to_serialize = optimize_commands(commands, start, optimize_cfg)
        to_serialize = _commands_to_absolute_only(to_serialize, start)

    stats, diags = analyze_commands(commands, start, limits=limits, optimize_cfg=optimize_cfg)
    error_count = sum(1 for d in diags if d.severity == "ERROR")
    blocked = error_count > 0

    header_lines: List[str] = []
    header_lines.append(f"; generated: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
    header_lines.append(f"; bounds: {stats.bounds}")
    header_lines.append(f"; path_length: {stats.path_length}")
    header_lines.append(f"; estimated_time: {stats.estimated_time}")
    if blocked:
        header_lines.append("; BLOCKED: true")
    header_lines.append("")

    if format == "robot_v1":
        body = _serialize_robot_v1(to_serialize, start)
    elif format == "gcode_lite":
        body = _serialize_gcode_lite(to_serialize, start)
    elif format == "absolute_only":
        body = serialize_commands(to_serialize).splitlines()
    else:
        body = serialize_commands(to_serialize).splitlines()

    content = "\n".join(header_lines + body)
    return content, blocked, stats, diags


def export_commands(
    commands: List[Command],
    filename: str,
    start: Tuple[float, float],
    *,
    limits: Optional[ScenarioLimits] = None,
    format: str = "flat",  # noqa: A002
) -> bool:
    """
    Parse/unroll edilmiş komut listesini robot tarafına gidecek dosyaya yazar.
    format: "flat" | "absolute_only" | "robot_v1" | "gcode_lite"
    Blocked ise dosya başına ; BLOCKED: true yazar ve False döner.
    """
    content, blocked, _stats, _diags = export_commands_to_string(
        commands, start, limits=limits, format=format
    )
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)
        return not blocked
    except OSError:
        return False
