"""
Gerçek seri port olmadan ``List[Command]`` → DSL wire yükü (dry-run).

İleride ``pyserial`` ve ACK katmanı buraya eklenecek; bu sürümde yalnızca
``serialize_commands`` çıktısı UTF-8 baytları olarak saklanır.

Hareket planlama veya PID motor kontrolü yoktur; sınır ``List[Command]``'dır.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.execution.commands import Command, serialize_commands

WireFormat = Literal["dsl"]


@dataclass(frozen=True)
class SerialDriverStubConfig:
    """Gelecek gerçek seri sürücü için yer tutucu; stub davranışını da taşır."""

    port: str | None = None
    baudrate: int = 115200
    dry_run: bool = True
    wire_format: str = "dsl"
    payload_preview_max_chars: int = 512


class SerialDriverStub:
    """
    ``RobotDriver`` protokolüne uygun kuru çalıştırma: port yok, ACK yok.

    ``wire_format`` şu an yalnızca ``\"dsl\"`` (``serialize_commands``).
    """

    def __init__(
        self,
        *,
        port: str | None = None,
        baudrate: int = 115200,
        dry_run: bool = True,
        wire_format: str = "dsl",
        payload_preview_max_chars: int = 512,
    ) -> None:
        if wire_format != "dsl":
            raise ValueError("Bu sürümde wire_format yalnızca 'dsl' destekler")
        self._port = port
        self._baudrate = int(baudrate)
        self._dry_run = bool(dry_run)
        self._wire_format: WireFormat = "dsl"
        self._preview_max = max(0, int(payload_preview_max_chars))

        self._connected = False
        self._stopped = False
        self._stop_requested = False
        self._last_commands: list[Command] = []
        self._last_start: tuple[float, float] = (0.0, 0.0)
        self._last_metadata: dict[str, Any] | None = None
        self._last_payload_text: str = ""
        self._last_payload_bytes: bytes = b""
        self._last_write_succeeded = False

    def connect(self) -> None:
        self._connected = True
        self._stopped = False

    def disconnect(self) -> None:
        self._connected = False

    def stop(self) -> None:
        self._stopped = True
        self._stop_requested = True

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

        text = serialize_commands(commands)
        self._last_payload_text = text
        self._last_payload_bytes = text.encode("utf-8")
        # Dry-run: sanal yazım her zaman başarılı sayılır (gerçek port yok).
        self._last_write_succeeded = True

    def get_status(self) -> dict[str, Any]:
        preview = self._last_payload_text
        if self._preview_max > 0 and len(preview) > self._preview_max:
            preview = preview[: self._preview_max] + "…"
        return {
            "connected": self._connected,
            "driver_name": "serial_stub",
            "last_command_count": len(self._last_commands),
            "port": self._port,
            "baudrate": self._baudrate,
            "wire_format": self._wire_format,
            "dry_run": self._dry_run,
            "last_write_succeeded": self._last_write_succeeded,
            "last_payload_preview": preview if preview else None,
            "stopped": self._stopped,
            "stop_requested": self._stop_requested,
            "last_start": list(self._last_start),
        }

    @property
    def last_payload_text(self) -> str:
        """Son üretilen wire metni (DSL)."""
        return self._last_payload_text

    @property
    def last_payload_bytes(self) -> bytes:
        """Son üretilen UTF-8 baytları."""
        return self._last_payload_bytes
