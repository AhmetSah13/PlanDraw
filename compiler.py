from __future__ import annotations

from typing import List, Tuple

from commands import Command, MoveCommand, PenCommand, SpeedCommand


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

