"""
Gerçek UART üzerinden ``List[Command]`` gönderen sürücü (pyserial).

SERIAL_PROTOCOL_V1 ile uyumlu çerçeveleme ``serial_protocol`` modülündedir.
Hareket planlama yok; HTTP yok.

``pyserial`` yüklü değilse ``connect()`` açık bir ``ImportError`` verir.
Testlerde ``serial_connection`` ile sahte bağlantı enjekte edilebilir.
"""

from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable

from app.execution.commands import Command, serialize_commands
from app.drivers.serial_protocol import (
    SerialWireProfile,
    frame_dsl_payload,
    frame_stop_line,
    parse_response_line,
    wire_text_to_bytes,
)

try:
    import serial as serial_mod
except ImportError:
    serial_mod = None


_MAX_RESPONSE_LINES = 10_000


@runtime_checkable
class _SerialConnection(Protocol):
    """``pyserial.Serial`` ve test çiftleri için minimal arayüz."""

    def write(self, data: bytes) -> int | None: ...

    def readline(self) -> bytes: ...

    def close(self) -> None: ...

    @property
    def is_open(self) -> bool: ...


class SerialDriver:
    """Profil B (BEGIN/END) batch + ``DONE`` sonunda başarı beklenir (varsayılan)."""

    def __init__(
        self,
        port: str,
        *,
        baudrate: int = 115200,
        timeout_s: float = 2.0,
        wire_profile: SerialWireProfile = SerialWireProfile.B,
        expect_done_after_batch: bool = True,
        serial_connection: Optional[_SerialConnection] = None,
    ) -> None:
        self._port = port
        self._baudrate = int(baudrate)
        self._timeout_s = float(timeout_s)
        self._wire_profile = wire_profile
        self._expect_done = bool(expect_done_after_batch)
        self._injected: Optional[_SerialConnection] = serial_connection

        self._conn: Optional[_SerialConnection] = None
        self._stopped = False
        self._last_commands: list[Command] = []
        self._last_start: tuple[float, float] = (0.0, 0.0)
        self._last_metadata: dict[str, Any] | None = None
        self._last_send_ok: bool = False
        self._last_stop_ok: bool = False
        self._last_error: str | None = None

    def connect(self) -> None:
        self._last_error = None
        if serial_mod is None and self._injected is None:
            raise ImportError(
                "pyserial yok: pip install pyserial veya serial_connection enjekte edin"
            )
        if self._conn is not None and self._conn.is_open:
            return
        if self._injected is not None:
            self._conn = self._injected
            return
        assert serial_mod is not None
        self._conn = serial_mod.Serial(
            port=self._port,
            baudrate=self._baudrate,
            timeout=self._timeout_s,
        )

    def disconnect(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def send_stop(self, *, require_connected: bool = True) -> None:
        """Tek satirlik STOP komutunu gonderir ve gerekiyorsa DONE bekler."""
        self._stopped = True
        self._last_error = None
        self._last_stop_ok = False
        if self._conn is None or not self._conn.is_open:
            if require_connected:
                raise RuntimeError("serial bagli degil; STOP gonderilemedi")
            return
        try:
            self._conn.write(wire_text_to_bytes(frame_stop_line()))
            if self._expect_done:
                self._read_until_done()
            self._last_stop_ok = True
        except Exception as exc:
            self._last_error = str(exc)
            raise

    def stop(self) -> None:
        self.send_stop(require_connected=False)

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
        self._last_error = None
        self._last_send_ok = False

        if self._conn is None or not self._conn.is_open:
            raise RuntimeError("serial bağlı değil; önce connect()")

        dsl = serialize_commands(commands)
        wire = frame_dsl_payload(dsl, profile=self._wire_profile)
        payload = wire_text_to_bytes(wire)
        if payload:
            self._conn.write(payload)

        if self._expect_done:
            self._read_until_done()
        self._last_send_ok = True

    def _read_until_done(self) -> None:
        assert self._conn is not None
        for _ in range(_MAX_RESPONSE_LINES):
            raw = self._conn.readline()
            if not raw:
                raise TimeoutError("MCU yanıtı yok (zaman aşımı veya boş okuma)")
            pr = parse_response_line(raw)
            if pr.kind == "done":
                return
            if pr.kind == "err":
                msg = pr.text or "ERR"
                raise RuntimeError(f"MCU ERR: {msg}")
            if pr.kind in ("ok", "status", "unknown"):
                continue
        raise RuntimeError("MCU yanıtı çok uzun veya DONE beklenemedi")

    def get_status(self) -> dict[str, Any]:
        return {
            "connected": self._conn is not None and self._conn.is_open,
            "driver_name": "serial",
            "port": self._port,
            "baudrate": self._baudrate,
            "timeout_s": self._timeout_s,
            "wire_profile": self._wire_profile.value,
            "expect_done_after_batch": self._expect_done,
            "pyserial_available": serial_mod is not None,
            "last_command_count": len(self._last_commands),
            "last_send_succeeded": self._last_send_ok,
            "last_stop_succeeded": self._last_stop_ok,
            "last_error": self._last_error,
            "stopped": self._stopped,
            "last_start": list(self._last_start),
        }
