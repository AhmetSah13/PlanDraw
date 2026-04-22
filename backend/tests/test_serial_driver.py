# SerialDriver: enjekte edilmiş sahte UART ile birim testleri (gerçek port yok)
from __future__ import annotations

import sys
from collections import deque
from pathlib import Path
from unittest import mock

import pytest

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app.drivers.serial_driver import SerialDriver
from app.drivers.serial_protocol import SerialWireProfile
from app.execution.commands import MoveCommand, SpeedCommand


class _FakeSerialPort:
    """pyserial benzeri: yazılan baytlar + kuyruklu readline."""

    def __init__(self, responses: list[bytes] | None = None) -> None:
        self._written = bytearray()
        self._queue: deque[bytes] = deque(responses or [])
        self.is_open = True

    def write(self, data: bytes) -> int:
        n = len(data)
        self._written.extend(data)
        return n

    def readline(self) -> bytes:
        if not self._queue:
            return b""
        return self._queue.popleft()

    def close(self) -> None:
        self.is_open = False

    @property
    def written_text(self) -> str:
        return self._written.decode("utf-8")


def test_send_commands_writes_framed_payload_and_done_succeeds() -> None:
    fake = _FakeSerialPort([b"DONE\n"])
    d = SerialDriver("COM1", serial_connection=fake)
    d.connect()
    d.send_commands([SpeedCommand(1.0), MoveCommand(10.0, 0.0)])
    assert "BEGIN" in fake.written_text
    assert "END" in fake.written_text
    assert "SPEED" in fake.written_text
    assert d.get_status()["last_send_succeeded"] is True
    d.disconnect()


def test_err_raises_runtime_error() -> None:
    fake = _FakeSerialPort([b"ERR parse\n"])
    d = SerialDriver("COM1", serial_connection=fake)
    d.connect()
    with pytest.raises(RuntimeError, match="MCU ERR"):
        d.send_commands([MoveCommand(1.0, 0.0)])
    assert d.get_status()["last_send_succeeded"] is False
    d.disconnect()


def test_timeout_on_empty_readline() -> None:
    fake = _FakeSerialPort([])
    d = SerialDriver("COM1", serial_connection=fake)
    d.connect()
    with pytest.raises(TimeoutError, match="yok"):
        d.send_commands([MoveCommand(1.0, 0.0)])
    d.disconnect()


def test_ok_then_done() -> None:
    fake = _FakeSerialPort([b"OK\n", b"DONE\n"])
    d = SerialDriver("COM1", serial_connection=fake)
    d.connect()
    d.send_commands([MoveCommand(0.0, 0.0)])
    assert d.get_status()["last_send_succeeded"] is True
    d.disconnect()


def test_connect_without_pyserial_raises() -> None:
    import app.drivers.serial_driver as sd

    with mock.patch.object(sd, "serial_mod", None):
        d = SerialDriver("/dev/ttyFAKE")
        with pytest.raises(ImportError, match="pyserial"):
            d.connect()


def test_send_without_connect_raises() -> None:
    fake = _FakeSerialPort([b"DONE\n"])
    d = SerialDriver("COM1", serial_connection=fake)
    with pytest.raises(RuntimeError, match="bağlı"):
        d.send_commands([MoveCommand(1.0, 0.0)])


def test_expect_done_false_skips_read() -> None:
    fake = _FakeSerialPort([])
    d = SerialDriver(
        "COM1",
        serial_connection=fake,
        expect_done_after_batch=False,
    )
    d.connect()
    d.send_commands([MoveCommand(1.0, 0.0)])
    assert d.get_status()["last_send_succeeded"] is True
    d.disconnect()


def test_profile_a_framing() -> None:
    fake = _FakeSerialPort([b"DONE\n"])
    d = SerialDriver("COM1", serial_connection=fake, wire_profile=SerialWireProfile.A)
    d.connect()
    d.send_commands([SpeedCommand(2.0)])
    assert "BEGIN" not in fake.written_text
    assert "SPEED" in fake.written_text
    d.disconnect()
