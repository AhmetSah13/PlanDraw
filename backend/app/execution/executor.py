from __future__ import annotations

import math
from typing import List, Optional, Tuple

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


class CommandExecutor:
    """
    Komut akışını adım adım ilerleten, saf mantık katmanı.

    Hız, kalem durumu ve hedef nokta gibi bilgileri takip eder.
    """

    def __init__(self, commands: List[Command]) -> None:
        self._commands: List[Command] = list(commands)
        self._index: int = 0
        self.current_speed: float = 0.0
        self.pen_down: bool = False
        self._current_target: Optional[Tuple[float, float]] = None
        self.finished: bool = False
        self._wait_remaining: float = 0.0
        self.heading_deg: float = 0.0

    def _advance_to_next_move(self, x: float, y: float) -> None:
        """
        Bir MOVE komutu bulunana kadar komutları işler.

        SPEED ve PEN komutları anında uygulanır.
        MOVE komutu bulunursa hedef nokta ayarlanır ve durulur.
        Komutlar bittiğinde finished True olur.
        """
        while self._current_target is None and not self.finished:
            if self._index >= len(self._commands):
                self.finished = True
                return

            cmd = self._commands[self._index]
            self._index += 1

            if isinstance(cmd, SpeedCommand):
                self.current_speed = max(0.0, float(cmd.speed))
            elif isinstance(cmd, PenCommand):
                self.pen_down = bool(cmd.is_down)
            elif isinstance(cmd, WaitCommand):
                self._wait_remaining = max(0.0, float(cmd.seconds))
                return
            elif isinstance(cmd, TurnCommand):
                self.heading_deg += float(cmd.deg)
            elif isinstance(cmd, ForwardCommand):
                dist = float(cmd.dist)
                rad = math.radians(self.heading_deg)
                dx = math.cos(rad) * dist
                dy = math.sin(rad) * dist
                self._current_target = (x + dx, y + dy)
                return
            elif isinstance(cmd, MoveRelCommand):
                self._current_target = (float(x) + float(cmd.dx), float(y) + float(cmd.dy))
                return
            elif isinstance(cmd, MoveCommand):
                self._current_target = (float(cmd.x), float(cmd.y))
                return

    def update(
        self,
        dt: float,
        robot_position: Tuple[float, float],
        speed_override: Optional[float] = None,
    ) -> Tuple[Tuple[float, float], bool]:
        """
        Komutları dt kadar ilerletir.
        speed_override verilirse hareket hesabında current_speed yerine kullanılır.
        """
        if self.finished:
            return robot_position, False

        effective_speed = speed_override if speed_override is not None else self.current_speed
        x, y = robot_position

        # Eğer bekleme komutundayız, zamanı tüket
        if self._wait_remaining > 0.0:
            if dt <= 0.0:
                return (x, y), False

            consumed = min(self._wait_remaining, dt)
            self._wait_remaining -= consumed
            dt -= consumed  # Kalan zamanı MOVE adımlarına aktarmak için koru

            # Bekleme devam ediyorsa hareket yok
            if self._wait_remaining > 0.0:
                return (x, y), False

            # Bekleme bitti -> sıradaki komutlara geçebilmek için hedefi advance et
            self._advance_to_next_move(x, y)

        # Önce MOVE olmayan komutları (SPEED, PEN, WAIT) işle
        if self._current_target is None and self._wait_remaining <= 0.0:
            self._advance_to_next_move(x, y)

        # Hedefe zaten varılmış MOVE komutlarını, kalan mesafeden bağımsız olarak tüket
        while not self.finished and self._current_target is not None:
            hedef_x, hedef_y = self._current_target
            dx = hedef_x - x
            dy = hedef_y - y
            mesafe = math.hypot(dx, dy)
            if mesafe >= 1e-6:
                break
            # Zaten hedefteyiz, bu MOVE'u tüket ve bir sonrakine geç
            x, y = hedef_x, hedef_y
            self._current_target = None
            self._advance_to_next_move(x, y)

        # Hareket edecek hedef yoksa veya dt/hız/bekleme uygun değilse sadece konumu döndür
        if (
            dt <= 0.0
            or self.finished
            or self._current_target is None
            or effective_speed <= 0.0
            or self._wait_remaining > 0.0
        ):
            return (x, y), False

        kalan_mesafe = max(0.0, effective_speed * dt)
        cizdi_mi = False

        while kalan_mesafe > 0.0 and not self.finished:
            if self._current_target is None:
                self._advance_to_next_move(x, y)
                if self._current_target is None:
                    # Artık MOVE komutu kalmadı
                    break

            hedef_x, hedef_y = self._current_target
            dx = hedef_x - x
            dy = hedef_y - y
            mesafe = math.hypot(dx, dy)

            if mesafe < 1e-6:
                # Hedefe varıldı, bir sonraki MOVE komutuna geç
                x, y = hedef_x, hedef_y
                self._current_target = None
                continue

            if kalan_mesafe < mesafe:
                oran = kalan_mesafe / mesafe
                x += dx * oran
                y += dy * oran
                kalan_mesafe = 0.0
            else:
                # Hedefe kadar git, kalan mesafe ile devam et
                x, y = hedef_x, hedef_y
                kalan_mesafe -= mesafe
                self._current_target = None

            if self.pen_down:
                cizdi_mi = True

        return (x, y), cizdi_mi

    def get_current_target(self) -> Optional[Tuple[float, float]]:
        """Şu an gidilen MOVE hedefi (yoksa None)."""
        return self._current_target

    def get_wait_remaining(self) -> float:
        """Aktif WAIT komutundan kalan süre (saniye)."""
        return float(self._wait_remaining)

    def debug_state(self) -> dict:
        """Executor iç durumunun debug-friendly özetini döndürür."""
        return {
            "index": self._index,
            "speed": self.current_speed,
            "pen": self.pen_down,
            "wait": self._wait_remaining,
            "target": self._current_target,
            "finished": self.finished,
            "heading_deg": self.heading_deg,
        }



