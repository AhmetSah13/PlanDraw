from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

from app.execution.commands import (
    Command,
    MoveCommand,
    PenCommand,
    SpeedCommand,
)


@dataclass(frozen=True)
class PenSafeViolation:
    index: int
    message: str


class PenSafeValidationError(ValueError):
    """Compile çıktısı pen-safe sözleşmesini ihlal ettiğinde fırlatılır."""

    def __init__(self, violations: Sequence[PenSafeViolation]) -> None:
        self.violations = tuple(violations)
        detail = "; ".join(f"[{v.index}] {v.message}" for v in self.violations)
        super().__init__(f"Pen-safe doğrulama başarısız: {detail}")


def validate_pen_safe_commands(
    commands: List[Command],
    *,
    start_pos: Tuple[float, float] = (0.0, 0.0),
) -> None:
    """
    Komut listesinin pen-safe gramerini doğrular.

    Beklenen yapı (SPEED sonrası):
        PEN UP
        (MOVE* PEN DOWN MOVE+ PEN UP)*

    Yani kalem aşağıdayken yalnızca çizim MOVE'ları olabilir; stroke dışı travel
    her zaman PEN UP sonrası MOVE* bloğunda yer alır.
    """
    del start_pos  # gramer doğrulaması konumdan bağımsız; API uyumluluğu için parametre korunur.

    violations: list[PenSafeViolation] = []
    i = 0
    n = len(commands)

    if n == 0:
        violations.append(PenSafeViolation(0, "Komut listesi boş"))
        raise PenSafeValidationError(violations)

    if isinstance(commands[0], SpeedCommand):
        i = 1

    if i >= n:
        violations.append(PenSafeViolation(n - 1, "SPEED sonrası komut yok"))
        raise PenSafeValidationError(violations)

    if not isinstance(commands[i], PenCommand) or commands[i].is_down:
        violations.append(
            PenSafeViolation(
                i,
                "İlk kalem komutu PEN UP olmalı (çizim öncesi kalem yukarıda)",
            ),
        )
        raise PenSafeValidationError(violations)
    i += 1

    stroke_index = 0
    while i < n:
        while i < n and isinstance(commands[i], MoveCommand):
            i += 1
        if i >= n:
            break

        if not isinstance(commands[i], PenCommand) or not commands[i].is_down:
            violations.append(
                PenSafeViolation(
                    i,
                    f"Stroke {stroke_index}: çizim öncesi PEN DOWN bekleniyor",
                ),
            )
            break
        i += 1

        draw_moves = 0
        while i < n and isinstance(commands[i], MoveCommand):
            draw_moves += 1
            i += 1

        if draw_moves == 0:
            violations.append(
                PenSafeViolation(
                    i,
                    f"Stroke {stroke_index}: PEN DOWN sonrası en az bir çizim MOVE gerekli",
                ),
            )
            break

        if i >= n:
            violations.append(
                PenSafeViolation(
                    n - 1,
                    f"Stroke {stroke_index}: stroke sonu PEN UP eksik",
                ),
            )
            break

        if not isinstance(commands[i], PenCommand) or commands[i].is_down:
            violations.append(
                PenSafeViolation(
                    i,
                    f"Stroke {stroke_index}: çizim sonrası PEN UP bekleniyor",
                ),
            )
            break
        i += 1
        stroke_index += 1

    if i < n:
        violations.append(
            PenSafeViolation(i, "Beklenmeyen komut: stroke döngüsü dışında kalan girdi"),
        )

    if violations:
        raise PenSafeValidationError(violations)

    if n > 0 and isinstance(commands[-1], PenCommand) and commands[-1].is_down:
        raise PenSafeValidationError(
            (PenSafeViolation(n - 1, "Komut listesi PEN DOWN ile bitmemeli"),),
        )
