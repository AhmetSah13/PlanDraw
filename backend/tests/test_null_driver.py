# test_null_driver.py — NullDriver birim testleri (HTTP yok)
from __future__ import annotations

import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app.drivers.null_driver import NullDriver
from app.execution.commands import (
    MoveCommand,
    PenCommand,
    SpeedCommand,
    WaitCommand,
)


def test_null_driver_empty_commands() -> None:
    d = NullDriver()
    d.connect()
    d.send_commands([], start=(0.0, 0.0))
    st = d.get_status()
    assert st["connected"] is True
    assert st["driver_name"] == "null"
    assert st["last_command_count"] == 0
    assert d.last_commands == []
    assert d.last_serialized_dsl == ""


def test_null_driver_single_move() -> None:
    d = NullDriver()
    d.connect()
    cmds = [MoveCommand(x=1.0, y=2.0)]
    d.send_commands(cmds, start=(0.5, 0.5), metadata={"job": "t1"})
    st = d.get_status()
    assert st["last_command_count"] == 1
    assert len(d.last_commands) == 1
    assert d.last_commands[0].x == 1.0 and d.last_commands[0].y == 2.0
    assert d.last_metadata == {"job": "t1"}
    assert "MOVE 1" in (d.last_serialized_dsl or "")


def test_null_driver_mixed_small_list() -> None:
    d = NullDriver()
    d.connect()
    mixed = [
        SpeedCommand(speed=100.0),
        PenCommand(is_down=True),
        MoveCommand(x=0.0, y=0.0),
        WaitCommand(seconds=0.1),
        PenCommand(is_down=False),
    ]
    d.send_commands(mixed)
    assert d.get_status()["last_command_count"] == 5
    dsl = d.last_serialized_dsl or ""
    assert "SPEED 100" in dsl
    assert "PEN DOWN" in dsl
    assert "WAIT 0.1" in dsl


def test_null_driver_stop_and_disconnect() -> None:
    d = NullDriver()
    d.connect()
    d.send_commands([MoveCommand(x=1.0, y=1.0)])
    d.stop()
    assert d.get_status()["stopped"] is True
    d.disconnect()
    assert d.get_status()["connected"] is False
