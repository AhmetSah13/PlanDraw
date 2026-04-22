"""Gerçek donanım olmadan komutları kaydeden ve hata üretmeyen sürücü."""

from __future__ import annotations

from typing import Any

from app.execution.commands import Command, serialize_commands


class NullDriver:
    """Donanım yok; ``send_commands`` ile gelen listeyi ve türetilmiş DSL'i saklar."""

    def __init__(self) -> None:
        self._connected = False
        self._stopped = False
        self._last_commands: list[Command] = []
        self._last_start: tuple[float, float] = (0.0, 0.0)
        self._last_metadata: dict[str, Any] | None = None
        self._last_serialized_dsl: str | None = None

    def connect(self) -> None:
        self._connected = True
        self._stopped = False

    def disconnect(self) -> None:
        self._connected = False

    def stop(self) -> None:
        self._stopped = True

    def send_commands(
        self,
        commands: list[Command],
        *,
        start: tuple[float, float] = (0.0, 0.0),
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._last_commands = list(commands)
        self._last_start = (float(start[0]), float(start[1]))
        self._last_metadata = dict(metadata) if metadata is not None else None
        self._last_serialized_dsl = serialize_commands(commands) if commands else ""

    def get_status(self) -> dict[str, Any]:
        return {
            "connected": self._connected,
            "driver_name": "null",
            "last_command_count": len(self._last_commands),
            "stopped": self._stopped,
            "last_start": list(self._last_start),
        }

    @property
    def last_commands(self) -> list[Command]:
        return list(self._last_commands)

    @property
    def last_serialized_dsl(self) -> str | None:
        return self._last_serialized_dsl

    @property
    def last_metadata(self) -> dict[str, Any] | None:
        return self._last_metadata
