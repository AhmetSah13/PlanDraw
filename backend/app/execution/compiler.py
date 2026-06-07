from __future__ import annotations

import math
from typing import List, Tuple

from app.execution.commands import Command, MoveCommand, PenCommand, SpeedCommand
from app.execution.pen_safe_validator import validate_pen_safe_commands


def _dedupe_consecutive_points(
    points: List[Tuple[float, float]],
    *,
    eps: float,
) -> List[Tuple[float, float]]:
    if not points:
        return []
    out: List[Tuple[float, float]] = [points[0]]
    for i in range(1, len(points)):
        px, py = points[i]
        lx, ly = out[-1]
        if math.hypot(px - lx, py - ly) <= eps:
            continue
        out.append((px, py))
    return out


def _dist(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def compile_path_to_commands_from_segments(
    segments: List[List[Tuple[float, float]]],
    speed: float = 120.0,
    *,
    start_x: float = 0.0,
    start_y: float = 0.0,
    position_epsilon_m: float = 1e-9,
) -> List[Command]:
    """
    Segment bazlı nokta listelerinden pen-safe komut üretir.

    Her segment = bir stroke:
        travel (PEN UP) -> PEN DOWN -> çizim MOVE* -> PEN UP
    Kopuk stroke'lar arasında kalem yukarıda kalır; pen-down travel oluşmaz.
    """
    commands: List[Command] = []
    eps = float(position_epsilon_m)
    commands.append(SpeedCommand(speed=speed))

    processed: List[List[Tuple[float, float]]] = []
    for seg in segments:
        if not seg:
            continue
        pts = _dedupe_consecutive_points(seg, eps=eps)
        if len(pts) < 2:
            continue
        processed.append(pts)

    if not processed:
        commands.append(PenCommand(is_down=False))
        return commands

    commands.append(PenCommand(is_down=False))
    pos: Tuple[float, float] = (float(start_x), float(start_y))

    for pts in processed:
        start = pts[0]
        if _dist(pos, start) > eps:
            commands.append(MoveCommand(x=start[0], y=start[1]))
            pos = start

        commands.append(PenCommand(is_down=True))
        for j in range(1, len(pts)):
            nx, ny = pts[j]
            if _dist(pos, (nx, ny)) <= eps:
                continue
            commands.append(MoveCommand(x=nx, y=ny))
            pos = (nx, ny)

        commands.append(PenCommand(is_down=False))

    return commands


def compile_path_to_commands(
    path: List[Tuple[float, float]],
    speed: float = 120.0,
    *,
    start_x: float = 0.0,
    start_y: float = 0.0,
) -> List[Command]:
    """
    Tek sürekli stroke (düz nokta listesi) için pen-safe komut üretir.

    Çoklu kopuk stroke içeren planlar için ``compile_path_to_commands_from_segments``
    veya ``compile_segments_pen_safe`` kullanın; düz liste stroke sınırlarını kaybeder.
    """
    if not path:
        commands: List[Command] = []
        commands.append(SpeedCommand(speed=speed))
        commands.append(PenCommand(is_down=False))
        return commands

    return compile_path_to_commands_from_segments(
        [path],
        speed=speed,
        start_x=start_x,
        start_y=start_y,
    )


def compile_segments_pen_safe(
    segments: List[List[Tuple[float, float]]],
    speed: float = 120.0,
    *,
    start_x: float = 0.0,
    start_y: float = 0.0,
    validate: bool = True,
) -> List[Command]:
    """Segment listesinden komut üretir ve isteğe bağlı pen-safe doğrulaması yapar."""
    commands = compile_path_to_commands_from_segments(
        segments,
        speed=speed,
        start_x=start_x,
        start_y=start_y,
    )
    if validate:
        validate_pen_safe_commands(commands, start_pos=(start_x, start_y))
    return commands
