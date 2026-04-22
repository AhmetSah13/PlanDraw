from __future__ import annotations

from typing import List, Tuple

from app.execution.commands import Command, MoveCommand, PenCommand, SpeedCommand


def compile_path_to_commands_from_segments(
    segments: List[List[Tuple[float, float]]],
    speed: float = 120.0,
) -> List[Command]:
    """
    Segment bazlı nokta listelerinden komut üretir.
    Her segment = bir stroke (PEN DOWN, MOVE*, PEN UP); segmentler arası MOVE ile travel.
    Böylece pen-up travel ayrıştırılabilir ve optimize edilebilir.
    """
    commands: List[Command] = []
    if not segments:
        commands.append(SpeedCommand(speed=speed))
        commands.append(PenCommand(is_down=False))
        return commands

    commands.append(SpeedCommand(speed=speed))
    for seg_idx, seg in enumerate(segments):
        if not seg:
            continue
        commands.append(PenCommand(is_down=True))
        prev: Tuple[float, float] | None = None
        for x, y in seg:
            pt = (float(x), float(y))
            if prev is not None and pt == prev:
                continue
            commands.append(MoveCommand(x=pt[0], y=pt[1]))
            prev = pt
        commands.append(PenCommand(is_down=False))
        # Travel to next segment start (bir sonraki segment varsa)
        if seg_idx + 1 < len(segments) and segments[seg_idx + 1]:
            next_start = segments[seg_idx + 1][0]
            commands.append(MoveCommand(x=float(next_start[0]), y=float(next_start[1])))
    return commands


def compile_path_to_commands(
    path: List[Tuple[float, float]],
    speed: float = 120.0,
) -> List[Command]:
    """
    Nokta listesini, basit bir komut dizisine çevirir.

    Sözleşme:
        - Önce SPEED komutu
        - Ardından PEN DOWN
        - Sonra her nokta için (tekrar edenler atlanarak) MOVE
        - Son olarak PEN UP
    """
    commands: List[Command] = []

    if not path:
        # Yol yoksa yalnızca kalemi kaldırılmış ve hız ayarlı halde bırak.
        commands.append(SpeedCommand(speed=speed))
        commands.append(PenCommand(is_down=False))
        return commands

    commands.append(SpeedCommand(speed=speed))
    commands.append(PenCommand(is_down=True))

    onceki_nokta: Tuple[float, float] | None = None
    for x, y in path:
        nokta = (float(x), float(y))
        if onceki_nokta is not None and nokta == onceki_nokta:
            continue
        commands.append(MoveCommand(x=nokta[0], y=nokta[1]))
        onceki_nokta = nokta

    commands.append(PenCommand(is_down=False))

    return commands

