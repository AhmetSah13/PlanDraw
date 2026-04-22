from __future__ import annotations

import math
from dataclasses import dataclass

from app.execution.commands import Command, MoveCommand, PenCommand, SpeedCommand
from app.path_planning.plan_model import PlannedPath


@dataclass(frozen=True)
class PlannedPathCompileOptions:
    """Planner ile aynı başlangıç kullanılırsa travel ile tutarlılık artar."""

    speed: float = 120.0
    start_x_m: float = 0.0
    start_y_m: float = 0.0
    # Ardışık aynı hedefe MOVE üretmemek için (deterministik)
    position_epsilon_m: float = 1e-9


@dataclass(frozen=True)
class PathCompilationReport:
    command_count: int
    stroke_count: int
    travel_command_count: int
    draw_command_count: int
    pen_toggle_count: int
    total_travel_m: float
    total_draw_m: float
    notes: tuple[str, ...]


def _dedupe_consecutive_points(
    points: tuple[tuple[float, float], ...],
    *,
    eps: float,
) -> tuple[tuple[float, float], ...]:
    if not points:
        return ()
    out: list[tuple[float, float]] = [points[0]]
    for i in range(1, len(points)):
        px, py = points[i]
        lx, ly = out[-1]
        if math.hypot(px - lx, py - ly) <= eps:
            continue
        out.append((px, py))
    return tuple(out)


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def compile_planned_path_to_commands(
    path: PlannedPath,
    *,
    options: PlannedPathCompileOptions | None = None,
) -> tuple[list[Command], PathCompilationReport]:
    """
    PlannedPath -> mevcut execution Command modeli (SPEED, PEN UP/DOWN, MOVE).

    Sözleşme (stroke sırası planner’dan geldiği gibi korunur):
    - Başta: SPEED, PEN UP (kalem yukarı varsayımı).
    - Her stroke: gerekiyorsa stroke başına travel MOVE; PEN DOWN; çizim MOVE’ları;
      stroke sonu PEN UP.
    - İlk nokta travel ile ulaşılır; çizim MOVE’ları pts[1..] içindir.

    BEGIN/END wire çerçevesi burada yok; sadece komut listesi üretilir.
    """
    opts = options or PlannedPathCompileOptions()
    eps = float(opts.position_epsilon_m)
    speed = float(opts.speed)
    sx, sy = float(opts.start_x_m), float(opts.start_y_m)

    cmds: list[Command] = []
    travel_moves = 0
    draw_moves = 0
    pen_count = 0

    total_travel = sum(s.travel_from_previous_m for s in path.strokes)
    total_draw = sum(s.stroke_length_m for s in path.strokes)

    notes_list = [
        "Komutlar: SPEED, PEN UP, (stroke) travel MOVE?, PEN DOWN, çizim MOVE*, PEN UP.",
        "Başlangıç (start_x_m, start_y_m) path planner ile aynı olmalıdır.",
    ]

    cmds.append(SpeedCommand(speed=speed))

    if not path.strokes:
        cmds.append(PenCommand(is_down=False))
        pen_count += 1
        rep = PathCompilationReport(
            command_count=len(cmds),
            stroke_count=0,
            travel_command_count=0,
            draw_command_count=0,
            pen_toggle_count=pen_count,
            total_travel_m=0.0,
            total_draw_m=0.0,
            notes=tuple(notes_list + ["Boş PlannedPath: yalnızca SPEED ve PEN UP."]),
        )
        return cmds, rep

    cmds.append(PenCommand(is_down=False))
    pen_count += 1

    pos: tuple[float, float] = (sx, sy)

    for si, stroke in enumerate(path.strokes):
        pts = _dedupe_consecutive_points(stroke.points, eps=eps)
        if len(pts) < 2:
            raise ValueError(
                f"Stroke {si} geçersiz: iki ayrı nokta yok (dedupe sonrası). "
                "Planner tek noktalı stroke üretmemeli."
            )

        start = pts[0]
        tr = _dist(pos, start)
        if tr > eps:
            cmds.append(MoveCommand(x=start[0], y=start[1]))
            travel_moves += 1
            pos = start

        cmds.append(PenCommand(is_down=True))
        pen_count += 1

        for j in range(1, len(pts)):
            nx, ny = pts[j]
            if _dist(pos, (nx, ny)) <= eps:
                continue
            cmds.append(MoveCommand(x=nx, y=ny))
            draw_moves += 1
            pos = (nx, ny)

        cmds.append(PenCommand(is_down=False))
        pen_count += 1

    rep = PathCompilationReport(
        command_count=len(cmds),
        stroke_count=len(path.strokes),
        travel_command_count=travel_moves,
        draw_command_count=draw_moves,
        pen_toggle_count=pen_count,
        total_travel_m=total_travel,
        total_draw_m=total_draw,
        notes=tuple(notes_list),
    )
    return cmds, rep
