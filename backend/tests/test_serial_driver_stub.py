# SerialDriverStub: dry-run wire yükü ve durum testleri
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app.drivers.serial_driver_stub import SerialDriverStub, SerialDriverStubConfig
from app.execution.commands import MoveCommand, PenCommand, SpeedCommand
from app.execution.commands import serialize_commands


def test_send_produces_dsl_payload_matching_serialize() -> None:
    cmds = [SpeedCommand(1.0), PenCommand(is_down=True), MoveCommand(1.0, 2.0)]
    d = SerialDriverStub()
    d.connect()
    d.send_commands(cmds)
    expected = serialize_commands(cmds)
    assert d.last_payload_text == expected
    assert d.last_payload_bytes == expected.encode("utf-8")
    assert len(d.last_payload_text) > 0


def test_status_after_send() -> None:
    cmds = [MoveCommand(0.5, 0.0)]
    d = SerialDriverStub(port="COM99", baudrate=57600)
    d.connect()
    d.send_commands(cmds, start=(0.0, 0.0))
    st = d.get_status()
    assert st["driver_name"] == "serial_stub"
    assert st["connected"] is True
    assert st["last_command_count"] == 1
    assert st["port"] == "COM99"
    assert st["baudrate"] == 57600
    assert st["wire_format"] == "dsl"
    assert st["dry_run"] is True
    assert st["last_write_succeeded"] is True
    assert "MOVE" in (st.get("last_payload_preview") or "")


def test_connect_disconnect() -> None:
    d = SerialDriverStub()
    assert d.get_status()["connected"] is False
    d.connect()
    assert d.get_status()["connected"] is True
    d.disconnect()
    assert d.get_status()["connected"] is False


def test_stop_records_request() -> None:
    d = SerialDriverStub()
    d.connect()
    d.stop()
    st = d.get_status()
    assert st["stopped"] is True
    assert st["stop_requested"] is True


def test_wire_format_invalid_raises() -> None:
    with pytest.raises(ValueError, match="dsl"):
        SerialDriverStub(wire_format="json")


def test_config_dataclass_frozen() -> None:
    cfg = SerialDriverStubConfig(port="/dev/ttyUSB0", baudrate=115200)
    assert cfg.dry_run is True
    assert cfg.wire_format == "dsl"
