"""
Komut listesini isteğe bağlı olarak bir ``RobotDriver`` üzerinden iletir.

Resmi entegrasyon noktası: ``parse_commands`` / ``compile_path_to_commands`` ve
isteğe bağlı ``optimize_commands`` sonrası elde edilen ``List[Command]``.
Bu modül **HTTP ile bağlı değildir**; FastAPI endpoint'leri değiştirilmeden
çağrılabilir veya ileride ince bir kablo ile bağlanabilir.

Metin DSL ve export formatları bu katmanın dışında kalır; sınır ``List[Command]``'dır.
"""

from __future__ import annotations

from typing import Any

from app.drivers.base import RobotDriver
from app.execution.commands import Command


def dispatch_commands(
    commands: list[Command],
    *,
    start: tuple[float, float] = (0.0, 0.0),
    metadata: dict[str, Any] | None = None,
    driver: RobotDriver | None = None,
) -> None:
    """
    ``driver`` yoksa hiçbir şey yapmaz.

    Aksi halde ``connect()`` çağrılır, ardından ``send_commands``; ``connect()``
    başarılı olduktan sonra ``disconnect()`` her durumda ``finally`` içinde
    denenir (``send_commands`` hata verse bile).
    """
    if driver is None:
        return

    connected = False
    try:
        driver.connect()
        connected = True
        driver.send_commands(commands, start=start, metadata=metadata)
    finally:
        if connected:
            driver.disconnect()
