"""
TCP socket based driver for driver-free loopback validation.

This mirrors the SerialDriver batch contract without opening a COM port. It is
intended for localhost hardware-prep protocol checks only.
"""

from __future__ import annotations

import socket
from typing import Any, Optional

from app.drivers.serial_protocol import (
    SerialWireProfile,
    frame_dsl_payload,
    frame_stop_line,
    parse_response_line,
    wire_text_to_bytes,
)
from app.execution.commands import Command, serialize_commands

_MAX_RESPONSE_LINES = 10_000


class SocketDriver:
    """SerialDriver-like TCP client for localhost loopback responders."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 9000,
        *,
        timeout_s: float = 2.0,
        wire_profile: SerialWireProfile = SerialWireProfile.B,
        expect_done_after_batch: bool = True,
    ) -> None:
        self._host = host
        self._port = int(port)
        self._timeout_s = float(timeout_s)
        self._wire_profile = wire_profile
        self._expect_done = bool(expect_done_after_batch)
        self._sock: Optional[socket.socket] = None
        self._reader = None
        self._last_commands: list[Command] = []
        self._last_send_ok = False
        self._last_error: str | None = None
        self._stopped = False

    def connect(self) -> None:
        self._last_error = None
        if self._sock is not None:
            return
        self._sock = socket.create_connection((self._host, self._port), timeout=self._timeout_s)
        self._sock.settimeout(self._timeout_s)
        self._reader = self._sock.makefile("rb")

    def disconnect(self) -> None:
        if self._reader is not None:
            try:
                self._reader.close()
            except Exception:
                pass
            self._reader = None
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    def send_commands(self, commands: list[Command], **_: Any) -> None:
        self._ensure_connected()
        self._last_commands = list(commands)
        self._last_error = None
        self._last_send_ok = False

        dsl = serialize_commands(commands)
        wire = frame_dsl_payload(dsl, profile=self._wire_profile)
        if wire:
            self._write(wire_text_to_bytes(wire))

        if self._expect_done:
            self._read_until_done()
        self._last_send_ok = True

    def stop(self) -> None:
        self._ensure_connected()
        self._stopped = True
        self._last_error = None
        try:
            self._write(wire_text_to_bytes(frame_stop_line()))
            if self._expect_done:
                self._read_until_done()
        except Exception as exc:
            self._last_error = str(exc)
            raise

    def query_status(self) -> str:
        self._ensure_connected()
        self._write(b"STATUS\n")
        raw = self._readline()
        pr = parse_response_line(raw)
        if pr.kind != "status":
            raise RuntimeError(f"unexpected status response: {pr.kind} {pr.text or ''}".strip())
        return pr.text or ""

    def get_status(self) -> dict[str, Any]:
        return {
            "connected": self._sock is not None,
            "driver_name": "socket",
            "host": self._host,
            "port": self._port,
            "timeout_s": self._timeout_s,
            "wire_profile": self._wire_profile.value,
            "expect_done_after_batch": self._expect_done,
            "last_command_count": len(self._last_commands),
            "last_send_succeeded": self._last_send_ok,
            "last_error": self._last_error,
            "stopped": self._stopped,
        }

    def _ensure_connected(self) -> None:
        if self._sock is None or self._reader is None:
            raise RuntimeError("socket not connected; call connect() first")

    def _write(self, data: bytes) -> None:
        self._ensure_connected()
        assert self._sock is not None
        self._sock.sendall(data)

    def _readline(self) -> bytes:
        self._ensure_connected()
        assert self._reader is not None
        raw = self._reader.readline()
        if not raw:
            raise TimeoutError("socket responder returned no data")
        return raw

    def _read_until_done(self) -> None:
        for _ in range(_MAX_RESPONSE_LINES):
            raw = self._readline()
            pr = parse_response_line(raw)
            if pr.kind == "done":
                return
            if pr.kind == "err":
                msg = pr.text or "ERR"
                raise RuntimeError(f"responder ERR: {msg}")
            if pr.kind in ("ok", "status", "unknown"):
                continue
        raise RuntimeError("socket responder response too long or DONE not received")
